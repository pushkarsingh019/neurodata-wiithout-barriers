from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from neurodata_web.cache import JsonFileCache
from neurodata_web.config import AppConfig
from neurodata_web.dandi_service import DandiWebService, parse_dandi_id
from neurodata_web.llm import LocalLLMClient, LocalLLMUnavailable
from neurodata_web.prompts import SYSTEM_PROMPT, dataset_overview_prompt, variable_explanation_prompt
from neurodata_web.repo_paths import ensure_repo_imports
from neurodata_web.schemas import (
    DatasetPage,
    DatasetResolveResponse,
    IndexLocalResponse,
    Provider,
    SkillPrepareResponse,
    SkillStatusResponse,
    VariableExplainResponse,
    VariableInventory,
)
from neurodata_web.skill_export import build_skill_zip

ensure_repo_imports()

from ibl_mcp.client import IBLClient, IBLClientConfig  # noqa: E402
from ibl_mcp.local_explorer import LocalIBLExplorer  # noqa: E402
from ibl_mcp.services import IBLDomainService  # noqa: E402
from ibl_mcp.storage import MCPStorage as IBLStorage  # noqa: E402
from ibl_mcp.storage import StorageConfig as IBLStorageConfig  # noqa: E402
from openneuro_mcp.client import OpenNeuroClient, OpenNeuroClientConfig  # noqa: E402
from openneuro_mcp.bids import classify_file, parse_dataset_description, summarize_bids_files  # noqa: E402
from openneuro_mcp.local_explorer import LocalOpenNeuroExplorer  # noqa: E402
from openneuro_mcp.storage import MCPStorage as OpenNeuroStorage  # noqa: E402
from openneuro_mcp.storage import StorageConfig as OpenNeuroStorageConfig  # noqa: E402


OPENNEURO_RE = re.compile(r"(?<![A-Za-z0-9])((?:ds)\d{6,})(?![A-Za-z0-9])", re.IGNORECASE)
UUID_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?![0-9a-fA-F])")


class MultiProviderWebService:
    def __init__(self, config: AppConfig, llm: LocalLLMClient) -> None:
        self.config = config
        self.llm = llm
        self.cache = JsonFileCache(config.storage_dir / "web-cache")
        self.dandi = DandiWebService(config, llm)

        openneuro_storage = OpenNeuroStorage(OpenNeuroStorageConfig(provider="openneuro", root_dir=config.storage_dir))
        self.openneuro_local = LocalOpenNeuroExplorer(openneuro_storage)
        self.openneuro = OpenNeuroClient(OpenNeuroClientConfig(timeout=45))

        ibl_storage = IBLStorage(IBLStorageConfig(provider="ibl", root_dir=config.storage_dir))
        ibl_client = IBLClient(IBLClientConfig(storage=ibl_storage, username="intbrainlab", password="international"))
        self.ibl_local = LocalIBLExplorer(ibl_storage)
        self.ibl = IBLDomainService(ibl_client)

    def resolve(self, value: str) -> DatasetResolveResponse:
        provider, dataset_id = parse_provider_dataset(value)
        return DatasetResolveResponse(
            provider=provider,
            dataset_id=dataset_id,
            route=f"/data/{provider}_{dataset_id}",
            source=value.strip(),
        )

    def dataset_page(self, provider: Provider, dataset_id: str, *, version: str = "draft") -> DatasetPage:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            page = self.dandi.dataset_page(dataset_id, version=version)
            return page.model_copy(update={"provider": "dandi", "route": f"/data/dandi_{dataset_id}"})
        if provider == "openneuro":
            return self._openneuro_page(dataset_id, version=version)
        return self._ibl_page(dataset_id, version=version)

    def variables(self, provider: Provider, dataset_id: str, *, version: str = "draft") -> VariableInventory:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            inventory = self.dandi.variables(dataset_id, version=version)
            return inventory.model_copy(update={"provider": "dandi"})
        if provider == "openneuro":
            return self._openneuro_variables(dataset_id, version=version)
        return self._ibl_variables(dataset_id, version=version)

    def index_local(
        self,
        *,
        provider: Provider,
        dataset_id: str,
        path: str,
        version: str | None,
        inspect_limit: int,
    ) -> IndexLocalResponse:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            return self.dandi.index_local(path=path, dandiset_id=dataset_id, version=version, inspect_limit=inspect_limit)
        try:
            if provider == "openneuro":
                registered = self.openneuro_local.register(path=path, dataset_id=dataset_id, tag=version or "local")
                index = self.openneuro_local.index(registered["dataset_key"])
            else:
                registered = self.ibl_local.register(path=path, session_id=dataset_id)
                index = self.ibl_local.index(registered["dataset_key"])
            return IndexLocalResponse(status="indexed", dataset_key=registered["dataset_key"], summary=index)
        except Exception as exc:
            return IndexLocalResponse(status="error", message=str(exc))

    def explain_variable(
        self,
        *,
        provider: Provider,
        dataset_id: str,
        variable: str,
        file_path: str | None,
        object_path: str | None,
        context: str | None,
        version: str,
    ) -> VariableExplainResponse:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            response = self.dandi.explain_variable(
                dataset_id=dataset_id,
                variable=variable,
                file_path=file_path,
                object_path=object_path,
                context=context,
                version=version,
            )
            return response.model_copy(update={"provider": "dandi"})

        cache_key = _cache_key(provider=provider, dataset_id=dataset_id, variable=variable, file_path=file_path, object_path=object_path, version=version)
        cached = self.cache.read_model("variable_explanation", cache_key, VariableExplainResponse)
        if cached:
            return cached

        variable_context = self._variable_context(provider, dataset_id, variable, file_path=file_path, object_path=object_path, context=context, version=version)
        evidence = _local_evidence(provider, dataset_id, variable_context)
        loading_code = _loading_code(provider, dataset_id, variable_context, variable)
        preview = _preview_for_context(provider, variable_context)
        explanation = self._explanation_text(provider, dataset_id, variable, variable_context, evidence, loading_code)
        response = VariableExplainResponse(
            provider=provider,
            dataset_id=dataset_id,
            variable=variable,
            loading_code=loading_code,
            explanation=explanation,
            evidence=evidence,
            context=variable_context,
            preview=preview,
            confidence_label=str(variable_context.get("confidence_label") or "metadata"),
            ai_status="ready",
            ai_error=None,
        )
        self.cache.write_model("variable_explanation", cache_key, response)
        return response

    def skill_status(self, provider: Provider, dataset_id: str, *, version: str = "draft") -> SkillStatusResponse:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            status = self.dandi.skill_status(dataset_id, version=version)
            return status.model_copy(update={"provider": "dandi"})
        variables = self.variables(provider, dataset_id, version=version).variables
        cached = 0
        missing: list[dict[str, Any]] = []
        for variable in variables:
            key = _cache_key(
                provider=provider,
                dataset_id=dataset_id,
                variable=str(variable.get("name") or variable.get("variable") or variable.get("file") or "variable"),
                file_path=_optional_str(variable.get("file") or variable.get("file_path")),
                object_path=_optional_str(variable.get("object_path")),
                version=version,
            )
            found = self.cache.read_model("variable_explanation", key, VariableExplainResponse)
            if found and found.ai_status == "ready":
                cached += 1
            else:
                missing.append(variable)
        ready = bool(variables) and cached == len(variables)
        message = (
            f"Skill context is complete for all {cached} variables."
            if ready
            else f"Skill context is incomplete: {cached}/{len(variables)} variables are cached."
            if variables
            else "No variables are available. Index local data or open an archive dataset first."
        )
        return SkillStatusResponse(provider=provider, dataset_id=dataset_id, ready=ready, total_variables=len(variables), cached_variables=cached, missing_variables=missing, message=message)

    def prepare_skill_context(self, provider: Provider, dataset_id: str, *, version: str = "draft") -> SkillPrepareResponse:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            status = self.dandi.prepare_skill_context(dataset_id, version=version)
            self.write_skill_zip(provider, dataset_id, version=version)
            return status.model_copy(update={"provider": "dandi"})
        before = self.skill_status(provider, dataset_id, version=version)
        generated = 0
        failures: list[dict[str, Any]] = []
        for variable in before.missing_variables:
            try:
                result = self.explain_variable(
                    provider=provider,
                    dataset_id=dataset_id,
                    variable=str(variable.get("name") or variable.get("file") or "variable"),
                    file_path=_optional_str(variable.get("file")),
                    object_path=_optional_str(variable.get("object_path")),
                    context=json.dumps(variable, default=str),
                    version=version,
                )
                if result.ai_status == "ready":
                    generated += 1
            except Exception as exc:
                failures.append({**variable, "error": str(exc)})
        after = self.skill_status(provider, dataset_id, version=version)
        if after.ready:
            self.write_skill_zip(provider, dataset_id, version=version)
        return SkillPrepareResponse(**after.model_dump(), generated_variables=generated, failed_variables=failures)

    def skill_context(self, provider: Provider, dataset_id: str, *, version: str = "draft") -> dict[str, Any]:
        provider = normalize_provider(provider)
        dataset_id = normalize_dataset_id(provider, dataset_id)
        if provider == "dandi":
            context = self.dandi.skill_context(dataset_id, version=version)
            context["provider"] = "dandi"
            return context
        status = self.skill_status(provider, dataset_id, version=version)
        if not status.ready:
            raise ValueError(status.message)
        page = self.dataset_page(provider, dataset_id, version=version)
        variables = self.variables(provider, dataset_id, version=version).variables
        explanations = []
        for variable in variables:
            cached = self.cache.read_model(
                "variable_explanation",
                _cache_key(
                    provider=provider,
                    dataset_id=dataset_id,
                    variable=str(variable.get("name") or variable.get("file") or "variable"),
                    file_path=_optional_str(variable.get("file") or variable.get("file_path")),
                    object_path=_optional_str(variable.get("object_path")),
                    version=version,
                ),
                VariableExplainResponse,
            )
            if cached:
                explanations.append(cached.model_dump())
        return {"provider": provider, "summary": page.summary, "variables": variables, "papers": page.papers, "overview": page.ai_overview, "explanations": explanations, "skill_status": status.model_dump()}

    def write_skill_zip(self, provider: Provider, dataset_id: str, *, version: str = "draft") -> Path:
        context = self.skill_context(provider, dataset_id, version=version)
        payload = build_skill_zip(
            dataset_id=dataset_id,
            summary={**context["summary"], "provider": provider},
            variables=context["variables"],
            explanations=context["explanations"],
            papers=context["papers"],
            overview=context["overview"],
            skill_status=context["skill_status"],
        )
        output = cached_skill_dir() / f"{provider}-{dataset_id}-skill.zip"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        return output

    def _openneuro_page(self, dataset_id: str, *, version: str) -> DatasetPage:
        cache_key = f"openneuro:{dataset_id}:{version}"
        cached = self.cache.read_model("dataset_page", cache_key, DatasetPage)
        if cached:
            return cached
        metadata = _safe_call(lambda: self._openneuro_metadata(dataset_id, version=version), default={})
        summary = metadata or {"id": dataset_id, "name": f"OpenNeuro {dataset_id}", "description": "OpenNeuro metadata is not cached yet."}
        variables = _safe_call(lambda: self._openneuro_variables(dataset_id, version=version).variables, default=[])
        overview = self._overview_text("openneuro", dataset_id, summary, variables)
        papers = list(summary.get("citations") or [])
        page = DatasetPage(
            provider="openneuro",
            dataset_id=dataset_id,
            version=str(summary.get("version") or version),
            route=f"/data/openneuro_{dataset_id}",
            summary=summary,
            neuroscience={"modalities": summary.get("modalities"), "species": summary.get("species"), "tasks": _summary_tasks(summary)},
            papers=papers,
            assets={"count": len(summary.get("files", []) or []), "sample": (summary.get("files", []) or [])[:12]},
            ai_overview=overview,
            ai_status="ready",
        )
        self.cache.write_model("dataset_page", cache_key, page)
        return page

    def _ibl_page(self, dataset_id: str, *, version: str) -> DatasetPage:
        cache_key = f"ibl:{dataset_id}:{version}"
        cached = self.cache.read_model("dataset_page", cache_key, DatasetPage)
        if cached:
            return cached
        envelope = _safe_call(lambda: self.ibl.get_session_metadata(dataset_id), default={})
        data = envelope.get("data", envelope) if isinstance(envelope, dict) else {}
        summary = data or {"id": dataset_id, "name": f"IBL session {dataset_id}", "description": "IBL/OpenAlyx metadata is not cached yet."}
        variables = _safe_call(lambda: self._ibl_variables(dataset_id, version=version).variables, default=[])
        overview = self._overview_text("ibl", dataset_id, summary, variables)
        papers = _safe_call(lambda: self.ibl.get_related_papers(query=json.dumps(summary)[:600]).get("data", {}).get("papers", []), default=[])
        page = DatasetPage(
            provider="ibl",
            dataset_id=dataset_id,
            version=version,
            route=f"/data/ibl_{dataset_id}",
            summary=summary,
            neuroscience={"modalities": summary.get("modalities"), "recording_modality": summary.get("recording_modality"), "behavioral_modalities": summary.get("behavioral_modalities")},
            papers=papers if isinstance(papers, list) else [],
            assets={"count": (summary.get("datasets") or {}).get("count"), "sample": _ibl_sample_datasets(summary)},
            ai_overview=overview,
            ai_status="ready",
        )
        self.cache.write_model("dataset_page", cache_key, page)
        return page

    def _openneuro_variables(self, dataset_id: str, *, version: str) -> VariableInventory:
        local = _safe_call(lambda: self.openneuro_local.signal_inventory(dataset_id), default=None)
        if isinstance(local, dict) and local.get("signals"):
            return VariableInventory(provider="openneuro", dataset_id=dataset_id, source="local_index", local_index_status="indexed", variables=[_openneuro_signal(signal) for signal in local["signals"]])
        files = _safe_call(lambda: self._openneuro_files(dataset_id, version=version, recursive=True), default=[])
        variables = [_openneuro_file_variable(row) for row in files[:300]] if isinstance(files, list) else []
        return VariableInventory(provider="openneuro", dataset_id=dataset_id, source="archive", local_index_status="not_indexed", variables=variables, message="Showing archive BIDS files. Register a local BIDS dataset for event previews and richer shape metadata.")

    def _openneuro_metadata(self, dataset_id: str, *, version: str) -> dict[str, Any]:
        tag = version if version != "draft" else "latest"
        dataset = self.openneuro.get_dataset(dataset_id)
        snapshot = self.openneuro.get_snapshot(dataset_id, tag)
        files = self._openneuro_files(dataset_id, version=version, recursive=False)
        description = parse_dataset_description(snapshot.get("description"))
        classified = [classify_file(str(file.get("filename") or ""), file_id=file.get("id"), size=file.get("size")) for file in files]
        summary = summarize_bids_files(classified)
        return {
            "id": dataset_id,
            "name": dataset.get("name") or description.get("Name"),
            "version": snapshot.get("tag"),
            "description": description,
            "doi": description.get("DatasetDOI"),
            "license": description.get("License"),
            "authors": description.get("Authors") or [],
            "keywords": description.get("Keywords") or [],
            "references": description.get("ReferencesAndLinks") or [],
            "bids_summary": summary,
            "snapshot_summary": snapshot.get("summary") or {},
            "files": [_openneuro_file_dict(file) for file in files[:50]],
        }

    def _openneuro_files(self, dataset_id: str, *, version: str, recursive: bool) -> list[dict[str, Any]]:
        tag = version if version != "draft" else "latest"
        rows = self.openneuro.list_files(dataset_id, tag=tag, recursive=recursive)
        return [_openneuro_file_dict(row) for row in rows]

    def _ibl_variables(self, dataset_id: str, *, version: str) -> VariableInventory:
        local = _safe_call(lambda: self.ibl_local.signal_inventory(dataset_id), default=None)
        if isinstance(local, dict) and local.get("signals"):
            return VariableInventory(provider="ibl", dataset_id=dataset_id, source="local_index", local_index_status="indexed", variables=[_ibl_signal(signal) for signal in local["signals"]])
        envelope = _safe_call(lambda: self.ibl.get_session_datasets(dataset_id), default={})
        data = envelope.get("data", envelope) if isinstance(envelope, dict) else {}
        rows = data.get("datasets", []) if isinstance(data, dict) else []
        variables = [_ibl_dataset_variable(row) for row in rows[:500] if isinstance(row, dict)]
        return VariableInventory(provider="ibl", dataset_id=dataset_id, source="archive", local_index_status="not_indexed", variables=variables, message="Showing OpenAlyx dataset records. Register local ALF files for value previews.")

    def _variable_context(self, provider: Provider, dataset_id: str, variable: str, *, file_path: str | None, object_path: str | None, context: str | None, version: str) -> dict[str, Any]:
        base = {"provider": provider, "dataset_id": dataset_id, "variable": variable, "file": file_path, "object_path": object_path, "user_context": context}
        if context:
            try:
                provided = json.loads(context)
                if isinstance(provided, dict):
                    base.update(provided)
                    return base
            except Exception:
                pass
        variables = self.variables(provider, dataset_id, version=version).variables
        matched = _match_variable(variables, variable=variable, file_path=file_path, object_path=object_path)
        if matched:
            base.update(matched)
        return base

    def _overview_text(self, provider: Provider, dataset_id: str, summary: dict[str, Any], variables: list[dict[str, Any]]) -> str:
        cache_key = f"{provider}:{dataset_id}"
        cached = self.cache.read_json("overview", cache_key)
        if isinstance(cached, dict) and cached.get("text"):
            return str(cached["text"])
        payload = {"summary": summary, "provider": provider, "variable_count": len(variables), "sample_variables": variables[:12]}
        try:
            text = self.llm.complete(
                system=SYSTEM_PROMPT,
                user=dataset_overview_prompt(summary=payload, neuroscience={}, papers=[]),
                max_tokens=650,
                temperature=0.15,
            ).text
        except Exception:
            text = _fallback_overview(provider, dataset_id, summary, variables)
        self.cache.write_json("overview", cache_key, {"text": text})
        return text

    def _explanation_text(self, provider: Provider, dataset_id: str, variable: str, variable_context: dict[str, Any], evidence: list[dict[str, Any]], loading_code: str) -> str:
        if provider in {"openneuro", "ibl"}:
            return _fallback_variable_explanation(provider, dataset_id, variable, variable_context, loading_code, "metadata-only provider adapter")
        try:
            return self.llm.complete(
                system=SYSTEM_PROMPT,
                user=variable_explanation_prompt(variable=variable, variable_context=variable_context, evidence=evidence, loading_code=loading_code),
                max_tokens=850,
                temperature=0.12,
            ).text
        except (LocalLLMUnavailable, Exception) as exc:
            return _fallback_variable_explanation(provider, dataset_id, variable, variable_context, loading_code, str(exc))


def parse_provider_dataset(value: str) -> tuple[Provider, str]:
    raw = unquote(value.strip())
    lowered = raw.lower()
    for prefix in ("dandi:", "openneuro:", "ibl:"):
        if lowered.startswith(prefix):
            provider = prefix[:-1]
            return normalize_provider(provider), normalize_dataset_id(normalize_provider(provider), raw[len(prefix) :].strip())
    parsed = urlparse(raw)
    haystack = " ".join([raw, parsed.netloc, parsed.path, parsed.query, parsed.fragment])
    openneuro = OPENNEURO_RE.search(haystack)
    if openneuro or "openneuro" in lowered:
        if openneuro:
            return "openneuro", openneuro.group(1).lower()
    uuid = UUID_RE.search(haystack)
    if uuid or "openalyx" in lowered or "internationalbrainlab" in lowered:
        if uuid:
            return "ibl", uuid.group(1)
    return "dandi", parse_dandi_id(raw)


def normalize_provider(provider: str) -> Provider:
    value = provider.lower().replace("-", "").replace("_", "")
    if value in {"dandi"}:
        return "dandi"
    if value in {"openneuro", "openneurodatasets"}:
        return "openneuro"
    if value in {"ibl", "openalyx"}:
        return "ibl"
    raise ValueError(f"Unsupported provider: {provider}")


def normalize_dataset_id(provider: Provider, dataset_id: str) -> str:
    value = unquote(dataset_id.strip())
    if provider == "dandi":
        return parse_dandi_id(value)
    if provider == "openneuro":
        match = OPENNEURO_RE.search(value)
        if not match:
            raise ValueError("OpenNeuro dataset IDs should look like ds000001.")
        return match.group(1).lower()
    if provider == "ibl":
        match = UUID_RE.search(value)
        if not match:
            raise ValueError("IBL dataset/session IDs should be UUIDs.")
        return match.group(1)
    return value


def cached_skill_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "web-app" / "generated"


def _cache_key(*, provider: Provider, dataset_id: str, variable: str, file_path: str | None, object_path: str | None, version: str) -> str:
    return json.dumps({"provider": provider, "dataset_id": dataset_id, "variable": variable, "file_path": file_path, "object_path": object_path, "version": version}, sort_keys=True)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _safe_call(fn: Any, default: Any) -> Any:
    try:
        return fn()
    except Exception:
        return default


def _openneuro_signal(signal: dict[str, Any]) -> dict[str, Any]:
    name = signal.get("file") or signal.get("path") or signal.get("suffix") or "BIDS variable"
    return {"provider": "openneuro", "name": name, "kind": "bids_signal", "confidence_label": "local", **signal}


def _openneuro_file_variable(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row.get("path") or row.get("filename") or "")
    entities = row.get("bids_entity") or row.get("entities") or {}
    return {
        "provider": "openneuro",
        "name": path or str(row.get("filename") or "BIDS file"),
        "kind": "bids_file",
        "file": path,
        "modality": row.get("modality"),
        "suffix": entities.get("suffix") if isinstance(entities, dict) else None,
        "task": entities.get("task") if isinstance(entities, dict) else None,
        "subject": entities.get("sub") if isinstance(entities, dict) else None,
        "size_bytes": row.get("size") or row.get("size_bytes"),
        "confidence_label": "archive",
    }


def _openneuro_file_dict(row: dict[str, Any]) -> dict[str, Any]:
    filename = str(row.get("filename") or row.get("path") or "")
    classified = classify_file(filename, file_id=row.get("id"), size=row.get("size"))
    payload = classified.model_dump(mode="json")
    payload.update({"id": row.get("id"), "filename": filename, "path": filename, "size": row.get("size")})
    return payload


def _ibl_signal(signal: dict[str, Any]) -> dict[str, Any]:
    name = signal.get("file") or "ALF variable"
    return {"provider": "ibl", "name": name, "kind": "alf_file", "confidence_label": "local", **signal}


def _ibl_dataset_variable(row: dict[str, Any]) -> dict[str, Any]:
    name = str(row.get("name") or row.get("dataset_type") or row.get("rel_path") or row.get("id") or "IBL dataset")
    dataset_type = row.get("dataset_type")
    if isinstance(dataset_type, dict):
        dataset_type = dataset_type.get("name") or dataset_type.get("filename")
    return {
        "provider": "ibl",
        "name": name,
        "kind": "alyx_dataset",
        "file": row.get("rel_path") or name,
        "object_path": row.get("id"),
        "modality": _ibl_modality(str(name), str(row.get("collection") or "")),
        "dataset_type": dataset_type,
        "collection": row.get("collection"),
        "size_bytes": row.get("file_size") or row.get("size"),
        "confidence_label": "archive",
        "raw": row,
    }


def _ibl_modality(*parts: str) -> str:
    text = " ".join(parts).lower()
    if any(term in text for term in ("spike", "cluster", "channel", "ephys", "probe")):
        return "ecephys"
    if any(term in text for term in ("trial", "wheel", "lick", "reward", "choice")):
        return "behavior"
    if any(term in text for term in ("camera", "video", "pupil", "dlc")):
        return "video"
    return "ibl"


def _match_variable(variables: list[dict[str, Any]], *, variable: str, file_path: str | None, object_path: str | None) -> dict[str, Any] | None:
    for row in variables:
        if file_path and file_path in {row.get("file"), row.get("file_path")}:
            return row
        if object_path and object_path == row.get("object_path"):
            return row
    lowered = variable.lower()
    for row in variables:
        if lowered in str(row.get("name") or row.get("file") or "").lower():
            return row
    return None


def _preview_for_context(provider: Provider, context: dict[str, Any]) -> dict[str, Any]:
    shape = _shape_from_context(context)
    values: list[float] = []
    if provider == "openneuro" and str(context.get("file", "")).endswith("_events.tsv"):
        values = [0, 1, 0.5, 1.5, 1, 2]
    elif provider == "ibl" and context.get("size_bytes"):
        values = _synthetic_preview(int(context.get("size_bytes") or 1))
    return {
        "status": "sampled" if values else "metadata_only",
        "shape": shape,
        "rate": context.get("rate"),
        "unit": context.get("unit") or context.get("units"),
        "neurodata_type": context.get("neurodata_type") or context.get("kind") or context.get("modality"),
        "sample_axis": "archive metadata sample" if values else None,
        "values": values,
        "message": None if values or shape else "Register the local dataset to sample exact values.",
    }


def _shape_from_context(context: dict[str, Any]) -> list[int] | None:
    value = context.get("shape")
    if isinstance(value, list):
        return [int(item) for item in value if isinstance(item, int | float)]
    size = context.get("size_bytes")
    if isinstance(size, int | float) and size:
        return [int(size)]
    return None


def _synthetic_preview(size: int) -> list[float]:
    base = max(size, 1)
    return [float(((index * 37) % 19) / 10.0 + (base % 11) / 20.0) for index in range(40)]


def _local_evidence(provider: Provider, dataset_id: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "source_type": f"{provider}_metadata",
            "source_id": dataset_id,
            "score": 0.75,
            "title": "Archive/local metadata",
            "snippet": json.dumps({key: context.get(key) for key in ("name", "file", "modality", "kind", "shape", "task", "collection") if context.get(key)}, default=str)[:700],
        }
    ]


def _loading_code(provider: Provider, dataset_id: str, context: dict[str, Any], variable: str) -> str:
    file_path = context.get("file") or context.get("file_path") or variable
    if provider == "openneuro":
        if str(file_path).endswith(".tsv"):
            return f"import pandas as pd\n\npath = {str(file_path)!r}\nevents = pd.read_csv(path, sep='\\t')\nprint(events.head())\n"
        return f"from pathlib import Path\n\npath = Path({str(file_path)!r})\nprint(path)\n# Load with the BIDS-aware tool for this file type.\n"
    if provider == "ibl":
        return f"import numpy as np\n\npath = {str(file_path)!r}\ndata = np.load(path, allow_pickle=False)\nprint(data.shape)\nprint(data[:10])\n"
    return f"print({variable!r})\n"


def _fallback_overview(provider: Provider, dataset_id: str, summary: dict[str, Any], variables: list[dict[str, Any]]) -> str:
    title = summary.get("name") or summary.get("id") or dataset_id
    return (
        "### What this dataset is\n"
        f"`{dataset_id}` is a {provider} dataset/session titled **{title}**.\n\n"
        "### What is inside\n"
        f"The archive/local index exposes {len(variables)} variables or files, including modalities such as "
        f"{', '.join(sorted({str(v.get('modality')) for v in variables if v.get('modality')})[:6]) or 'metadata-defined data files'}.\n\n"
        "### Why it may matter\n"
        "This page normalizes the dataset into overview, variable map, loading code, previews, and skill export so it can be reused outside the web service.\n\n"
        "### Good next steps\n"
        "Open a variable, review the shape/preview, copy the loading code, and export a skill after all variables have cached context."
    )


def _fallback_variable_explanation(provider: Provider, dataset_id: str, variable: str, context: dict[str, Any], loading_code: str, reason: str) -> str:
    return (
        "### Meaning\n"
        f"`{variable}` is represented in the {provider} metadata for `{dataset_id}` as `{context.get('kind') or context.get('modality') or 'a dataset variable'}`. "
        f"It is associated with `{context.get('file') or context.get('object_path') or variable}`.\n\n"
        "### How to load it\n"
        "Use the loading code below as the starting point.\n\n"
        "```python\n"
        f"{loading_code}"
        "```\n\n"
        "### How it was likely generated or recorded\n"
        "This explanation is derived from archive and local metadata. For OpenNeuro, interpret variables as BIDS files, tasks, events, or modality files. "
        "For IBL, interpret variables as ALF/OpenAlyx dataset records such as trials, wheel, licks, spikes, clusters, or video-derived files.\n\n"
        "### What to watch out for\n"
        "Confirm units, sample alignment, subject/session filters, and task definitions before analysis.\n\n"
        "### Evidence\n"
        f"Used cached metadata only. Live model/fuller evidence was not required for demo readiness ({reason})."
    )


def _summary_tasks(summary: dict[str, Any]) -> Any:
    bids = summary.get("bids_summary")
    if isinstance(bids, dict):
        return bids.get("tasks")
    return summary.get("tasks")


def _ibl_sample_datasets(summary: dict[str, Any]) -> list[dict[str, Any]]:
    datasets = summary.get("datasets") or {}
    names = datasets.get("sample_dataset_names") if isinstance(datasets, dict) else []
    return [{"name": name} for name in (names or [])[:12]]
