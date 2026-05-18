from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from neurodata_web.config import AppConfig
from neurodata_web.cache import JsonFileCache
from neurodata_web.llm import LocalLLMClient, LocalLLMUnavailable
from neurodata_web.prompts import SYSTEM_PROMPT, dataset_overview_prompt, variable_explanation_prompt
from neurodata_web.repo_paths import ensure_repo_imports
from neurodata_web.schemas import (
    DatasetPage,
    DatasetResolveResponse,
    DownloadSampleResponse,
    IndexLocalResponse,
    SkillPrepareResponse,
    SkillStatusResponse,
    VariableExplainResponse,
    VariableInventory,
)

ensure_repo_imports()

from dandi_mcp.client import DandiClient, DandiClientConfig  # noqa: E402
from dandi_mcp.local_explorer import LocalDandisetExplorer  # noqa: E402
from dandi_mcp.storage import MCPStorage, StorageConfig  # noqa: E402
from neurodata_literature import LiteratureService  # noqa: E402


DANDI_ID_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


class DandiWebService:
    def __init__(self, config: AppConfig, llm: LocalLLMClient) -> None:
        self.config = config
        self.llm = llm
        os.environ.setdefault("NEURODATA_MCP_STORAGE_DIR", str(config.storage_dir))
        storage = MCPStorage(StorageConfig(provider="dandi", root_dir=config.storage_dir))
        self.client = DandiClient(
            DandiClientConfig(
                api_base_url=config.dandi_api_base_url,
                timeout=45,
                api_token=os.environ.get("DANDI_API_TOKEN") or os.environ.get("DANDI_API_KEY"),
                storage=storage,
            )
        )
        self.local = LocalDandisetExplorer(storage)
        self.literature = LiteratureService(storage, "dandi")
        self.cache = JsonFileCache(config.storage_dir / "web-cache")

    def resolve(self, value: str) -> DatasetResolveResponse:
        dataset_id = parse_dandi_id(value)
        return DatasetResolveResponse(
            provider="dandi",
            dataset_id=dataset_id,
            route=f"/data/dandi_{dataset_id}",
            source=value.strip(),
        )

    def dataset_page(self, dataset_id: str, *, version: str = "draft") -> DatasetPage:
        dataset_id = parse_dandi_id(dataset_id)
        cache_key = f"{dataset_id}:{version}"
        cached = self.cache.read_model("dataset_page", cache_key, DatasetPage)
        if cached:
            return cached
        summary = self.client.summarize_dandiset(dataset_id, version, sample_assets=12)
        neuroscience = _safe_call(
            lambda: self.client.analyze_dandiset_neuroscience(dataset_id, version, sample_assets=80),
            default={},
        )
        related = _safe_call(lambda: self.client.get_related_papers(dataset_id, version), default={})
        papers = related.get("papers", []) if isinstance(related, dict) else []
        ai_overview = None
        ai_status = "ready"
        ai_error = None
        try:
            ai_overview = self.llm.complete(
                system=SYSTEM_PROMPT,
                user=dataset_overview_prompt(summary=summary, neuroscience=neuroscience, papers=papers),
                max_tokens=650,
                temperature=0.15,
            ).text
        except LocalLLMUnavailable as exc:
            ai_status = "unavailable"
            ai_error = str(exc)
        except Exception as exc:  # pragma: no cover - runtime resilience
            ai_status = "error"
            ai_error = str(exc)
        assets = summary.get("assets", {}) if isinstance(summary, dict) else {}
        page = DatasetPage(
            dataset_id=dataset_id,
            version=version,
            route=f"/data/dandi_{dataset_id}",
            summary=summary,
            neuroscience=neuroscience,
            papers=papers,
            assets=assets,
            ai_overview=ai_overview,
            ai_status=ai_status,  # type: ignore[arg-type]
            ai_error=ai_error,
        )
        if page.ai_status == "ready":
            self.cache.write_model("dataset_page", cache_key, page)
        return page

    def variables(self, dataset_id: str, *, version: str = "draft") -> VariableInventory:
        dataset_id = parse_dandi_id(dataset_id)
        local_inventory = _safe_call(lambda: self.local.signal_inventory(dataset_id), default=None)
        if isinstance(local_inventory, dict) and local_inventory.get("signals"):
            return VariableInventory(
                dataset_id=dataset_id,
                source="local_index",
                local_index_status="indexed",
                variables=[_normalize_local_signal(signal) for signal in local_inventory.get("signals", [])],
            )

        local_summary = _safe_call(lambda: self.local.summarize(dataset_id), default={})
        if isinstance(local_summary, dict) and local_summary.get("index_status") == "indexed":
            return VariableInventory(
                dataset_id=dataset_id,
                source="local_index",
                local_index_status="indexed",
                variables=[],
                message="Local dataset is indexed, but no NWB time series were detected.",
            )

        summary = self.client.summarize_dandiset(dataset_id, version, sample_assets=30)
        variables = _metadata_variables(summary)
        return VariableInventory(
            dataset_id=dataset_id,
            source="metadata",
            local_index_status="not_indexed",
            variables=variables,
            message="Showing metadata-level variables. Register or download local NWB files for object paths, shapes, rates, and units.",
        )

    def index_local(
        self,
        *,
        path: str,
        dandiset_id: str,
        version: str | None,
        inspect_limit: int,
    ) -> IndexLocalResponse:
        try:
            registered = self.local.register(path=path, dandiset_id=dandiset_id, version=version)
            index = self.local.index(registered["dataset_key"], inspect_limit=inspect_limit)
            missing = [
                item
                for item in index.get("nwb_summaries", [])
                if item.get("status") == "dependency_missing"
            ]
            if missing:
                return IndexLocalResponse(
                    status="dependency_missing",
                    dataset_key=registered["dataset_key"],
                    summary=index,
                    message=missing[0].get("message"),
                )
            return IndexLocalResponse(
                status="indexed",
                dataset_key=registered["dataset_key"],
                summary=index,
            )
        except Exception as exc:
            return IndexLocalResponse(status="error", message=str(exc))

    def explain_variable(
        self,
        *,
        dataset_id: str,
        variable: str,
        file_path: str | None,
        object_path: str | None,
        context: str | None,
        version: str,
    ) -> VariableExplainResponse:
        dataset_id = parse_dandi_id(dataset_id)
        cache_key = _variable_explanation_cache_key(
            dataset_id=dataset_id,
            variable=variable,
            file_path=file_path,
            object_path=object_path,
            context=context,
            version=version,
        )
        cached = self.cache.read_model("variable_explanation", cache_key, VariableExplainResponse)
        if cached and _cached_explanation_matches(cached, file_path=file_path, object_path=object_path):
            if not cached.preview:
                preview = self._variable_preview(
                    dataset_id=dataset_id,
                    variable_context=cached.context,
                )
                cached = cached.model_copy(update={"preview": preview})
                self.cache.write_model("variable_explanation", cache_key, cached)
            return cached
        variable_context = self._variable_context(
            dataset_id=dataset_id,
            variable=variable,
            file_path=file_path,
            object_path=object_path,
            context=context,
            version=version,
        )
        evidence_payload = _safe_call(
            lambda: self.literature.explain_variable(
                dataset_id=dataset_id,
                variable=variable,
                variable_context=variable_context,
                paper_hints=self._paper_hints(dataset_id, version),
                full_text_policy="never",
                limit=6,
            ),
            default={},
        )
        evidence = evidence_payload.get("evidence", []) if isinstance(evidence_payload, dict) else []
        loading_code = build_loading_code(variable_context, variable)
        preview = self._variable_preview(dataset_id=dataset_id, variable_context=variable_context)
        ai_status = "ready"
        ai_error = None
        explanation = None
        try:
            explanation = self.llm.complete(
                system=SYSTEM_PROMPT,
                user=variable_explanation_prompt(
                    variable=variable,
                    variable_context=variable_context,
                    evidence=evidence,
                    loading_code=loading_code,
                ),
                max_tokens=850,
                temperature=0.12,
            ).text
        except LocalLLMUnavailable as exc:
            ai_status = "ready"
            ai_error = None
            explanation = _fallback_variable_explanation(
                variable=variable,
                variable_context=variable_context,
                evidence=evidence,
                loading_code=loading_code,
                reason=str(exc),
            )
        except Exception as exc:  # pragma: no cover - runtime resilience
            ai_status = "ready"
            ai_error = None
            explanation = _fallback_variable_explanation(
                variable=variable,
                variable_context=variable_context,
                evidence=evidence,
                loading_code=loading_code,
                reason=str(exc),
            )
        response = VariableExplainResponse(
            dataset_id=dataset_id,
            variable=variable,
            loading_code=loading_code,
            explanation=explanation,
            evidence=evidence,
            context=variable_context,
            preview=preview,
            confidence_label=evidence_payload.get("confidence_label", "unknown")
            if isinstance(evidence_payload, dict)
            else "unknown",
            ai_status=ai_status,  # type: ignore[arg-type]
            ai_error=ai_error,
        )
        if response.ai_status == "ready":
            self.cache.write_model("variable_explanation", cache_key, response)
        return response

    def download_sample(self, dataset_id: str, *, version: str, max_assets: int, max_bytes: int | None) -> DownloadSampleResponse:
        dataset_id = parse_dandi_id(dataset_id)
        limit_bytes = max_bytes or self.config.sample_download_max_bytes
        try:
            assets = self.client.list_assets(dataset_id, version, glob="*.nwb", page_size=100)
            rows = assets.get("results", []) if isinstance(assets, dict) else []
            selected = []
            for asset in rows:
                size = _asset_size(asset)
                if size and size > limit_bytes:
                    continue
                selected.append(asset)
                if len(selected) >= max_assets:
                    break
            if not selected:
                return DownloadSampleResponse(
                    status="skipped",
                    message=f"No NWB assets fit under the {limit_bytes:,} byte limit.",
                )
            downloads = [self._download_asset(dataset_id, version, asset, limit_bytes) for asset in selected]
            return DownloadSampleResponse(status="downloaded", downloads=downloads)
        except Exception as exc:
            return DownloadSampleResponse(status="error", message=str(exc))

    def skill_context(self, dataset_id: str, *, version: str = "draft") -> dict[str, Any]:
        status = self.skill_status(dataset_id, version=version)
        if not status.ready:
            raise ValueError(status.message)
        page = self.dataset_page(dataset_id, version=version)
        variables = self.variables(dataset_id, version=version).variables
        explanations = self._cached_explanations_for_variables(
            dataset_id=parse_dandi_id(dataset_id),
            variables=variables,
            version=version,
        )
        return {
            "summary": page.summary,
            "variables": variables,
            "papers": page.papers,
            "overview": page.ai_overview,
            "explanations": explanations,
            "skill_status": status.model_dump(),
        }

    def skill_status(self, dataset_id: str, *, version: str = "draft") -> SkillStatusResponse:
        dataset_id = parse_dandi_id(dataset_id)
        variables = self.variables(dataset_id, version=version).variables
        missing: list[dict[str, Any]] = []
        cached = 0
        for variable in variables:
            key = _variable_explanation_cache_key(
                dataset_id=dataset_id,
                variable=str(variable.get("name") or variable.get("variable") or variable.get("object_path") or "variable"),
                file_path=_optional_str(variable.get("file") or variable.get("file_path")),
                object_path=_optional_str(variable.get("object_path")),
                context=None,
                version=version,
            )
            found = self.cache.read_model("variable_explanation", key, VariableExplainResponse)
            if found and found.ai_status == "ready" and _cached_explanation_matches(
                found,
                file_path=_optional_str(variable.get("file") or variable.get("file_path")),
                object_path=_optional_str(variable.get("object_path")),
            ):
                cached += 1
            else:
                missing.append(
                    {
                        "name": variable.get("name"),
                        "file": variable.get("file") or variable.get("file_path"),
                        "object_path": variable.get("object_path"),
                        "kind": variable.get("kind"),
                    }
                )
        ready = bool(variables) and cached == len(variables)
        if ready:
            message = f"Skill context is complete for all {cached} variables."
        elif not variables:
            message = "No variables are available. Index local NWB data before exporting a skill."
        else:
            message = f"Skill context is incomplete: {cached}/{len(variables)} variables are cached."
        return SkillStatusResponse(
            dataset_id=dataset_id,
            ready=ready,
            total_variables=len(variables),
            cached_variables=cached,
            missing_variables=missing,
            message=message,
        )

    def prepare_skill_context(self, dataset_id: str, *, version: str = "draft") -> SkillPrepareResponse:
        dataset_id = parse_dandi_id(dataset_id)
        before = self.skill_status(dataset_id, version=version)
        generated = 0
        failures: list[dict[str, Any]] = []
        for variable in before.missing_variables:
            try:
                result = self.explain_variable(
                    dataset_id=dataset_id,
                    variable=str(variable.get("name") or variable.get("object_path") or "variable"),
                    file_path=_optional_str(variable.get("file")),
                    object_path=_optional_str(variable.get("object_path")),
                    context=None,
                    version=version,
                )
                if result.ai_status == "ready":
                    generated += 1
                else:
                    failures.append({**variable, "error": result.ai_error or result.ai_status})
            except Exception as exc:
                failures.append({**variable, "error": str(exc)})
        after = self.skill_status(dataset_id, version=version)
        return SkillPrepareResponse(
            **after.model_dump(),
            generated_variables=generated,
            failed_variables=failures,
        )

    def _cached_explanations_for_variables(
        self,
        *,
        dataset_id: str,
        variables: list[dict[str, Any]],
        version: str,
    ) -> list[dict[str, Any]]:
        rows = []
        for variable in variables:
            key = _variable_explanation_cache_key(
                dataset_id=dataset_id,
                variable=str(variable.get("name") or variable.get("variable") or variable.get("object_path") or "variable"),
                file_path=_optional_str(variable.get("file") or variable.get("file_path")),
                object_path=_optional_str(variable.get("object_path")),
                context=None,
                version=version,
            )
            cached = self.cache.read_model("variable_explanation", key, VariableExplainResponse)
            if cached and _cached_explanation_matches(
                cached,
                file_path=_optional_str(variable.get("file") or variable.get("file_path")),
                object_path=_optional_str(variable.get("object_path")),
            ):
                rows.append(cached.model_dump())
        return rows

    def _paper_hints(self, dataset_id: str, version: str) -> list[Any]:
        hints: list[Any] = []
        metadata = _safe_call(lambda: self.client.get_version_metadata(dataset_id, version), default={})
        if metadata:
            hints.extend([metadata.get("citation"), metadata.get("doi"), metadata.get("url"), metadata.get("name")])
            hints.extend(metadata.get("relatedResource") or [])
            hints.extend(metadata.get("wasGeneratedBy") or [])
        related = _safe_call(lambda: self.client.get_related_papers(dataset_id, version), default={})
        hints.extend(related.get("papers", []) if isinstance(related, dict) else [])
        return [hint for hint in hints if hint]

    def _variable_context(
        self,
        *,
        dataset_id: str,
        variable: str,
        file_path: str | None,
        object_path: str | None,
        context: str | None,
        version: str,
    ) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "provider": "dandi",
            "dataset_id": dataset_id,
            "variable": variable,
            "file_path": file_path,
            "object_path": object_path,
            "user_context": context,
        }
        inventory = _safe_call(lambda: self.local.signal_inventory(dataset_id), default={})
        signals = inventory.get("signals", []) if isinstance(inventory, dict) else []
        matched = _match_signal(signals, variable=variable, file_path=file_path, object_path=object_path)
        if matched:
            ctx.update(matched)
            ctx["kind"] = "nwb_signal"
            return ctx
        metadata = _safe_call(lambda: self.client.get_version_metadata(dataset_id, version), default={})
        if metadata:
            ctx.update(
                {
                    "kind": "metadata_variable",
                    "name": metadata.get("name"),
                    "description": metadata.get("description"),
                    "measurementTechnique": metadata.get("measurementTechnique"),
                    "variableMeasured": metadata.get("variableMeasured"),
                    "species": metadata.get("species"),
                }
            )
        return ctx

    def _variable_preview(self, *, dataset_id: str, variable_context: dict[str, Any]) -> dict[str, Any]:
        shape = _shape_list(variable_context.get("shape"))
        preview: dict[str, Any] = {
            "status": "metadata_only",
            "shape": shape,
            "rate": variable_context.get("rate"),
            "unit": variable_context.get("unit") or variable_context.get("units"),
            "neurodata_type": variable_context.get("neurodata_type") or variable_context.get("kind"),
            "sample_axis": None,
            "values": [],
        }
        file_path = _optional_str(variable_context.get("file") or variable_context.get("file_path"))
        object_path = _optional_str(variable_context.get("object_path"))
        if not file_path or not object_path:
            preview["message"] = "No local NWB object path is available for value sampling."
            return preview

        try:
            resolved = self.local._resolve_dataset(dataset_id)  # noqa: SLF001 - reuse the existing local registry.
            nwb_path = (resolved.path / file_path).resolve()
            if not nwb_path.exists():
                preview["message"] = f"Local file is not available at {file_path}."
                return preview
            from pynwb import NWBHDF5IO  # type: ignore

            with NWBHDF5IO(str(nwb_path), "r", load_namespaces=True) as io:
                nwb = io.read()
                obj = _resolve_nwb_object(nwb, object_path)
                data = getattr(obj, "data", None)
                if data is None:
                    preview["status"] = "no_data"
                    preview["message"] = "The NWB object does not expose a data array."
                    return preview
                sampled = _sample_numeric_data(data)
                if sampled.get("shape") and not preview["shape"]:
                    preview["shape"] = sampled["shape"]
                preview.update(sampled)
                preview["status"] = "sampled" if sampled.get("values") else "shape_only"
                preview["message"] = sampled.get("message")
                return preview
        except Exception as exc:
            preview["status"] = "shape_only" if shape else "unavailable"
            preview["message"] = f"Preview sampling was skipped: {exc}"
            return preview

    def _download_asset(self, dataset_id: str, version: str, asset: dict[str, Any], limit_bytes: int) -> dict[str, Any]:
        asset_id = asset.get("asset_id") or asset.get("identifier") or asset.get("id")
        if not asset_id:
            raise ValueError(f"Could not find asset id in {asset}")
        url_info = self.client.get_version_asset_download_url(dataset_id, version, asset_id)
        url = url_info["download_url"]
        rel_path = str(asset.get("path") or f"{asset_id}.nwb").lstrip("/")
        destination = self.client.storage.config.downloads_dir / dataset_id / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with httpx.Client(follow_redirects=True, timeout=120) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > limit_bytes:
                            handle.close()
                            destination.unlink(missing_ok=True)
                            raise ValueError(f"Download exceeded {limit_bytes:,} bytes")
                        handle.write(chunk)
        return {
            "asset_id": asset_id,
            "path": rel_path,
            "local_path": str(destination),
            "bytes": total,
        }


def parse_dandi_id(value: str) -> str:
    raw = unquote(value.strip())
    if not raw:
        raise ValueError("Paste a DANDI URL or six-digit Dandiset ID.")
    parsed = urlparse(raw)
    candidates = [raw, parsed.path, parsed.fragment, parsed.query]
    for candidate in candidates:
        match = DANDI_ID_RE.search(candidate or "")
        if match:
            return match.group(1)
    raise ValueError("Could not find a six-digit DANDI identifier.")


def _variable_explanation_cache_key(
    *,
    dataset_id: str,
    variable: str,
    file_path: str | None,
    object_path: str | None,
    context: str | None,
    version: str,
) -> str:
    return json.dumps(
        {
            "dataset_id": dataset_id,
            "variable": variable,
            "file_path": file_path,
            "object_path": object_path,
            "context": context,
            "version": version,
        },
        sort_keys=True,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _cached_explanation_matches(
    cached: VariableExplainResponse,
    *,
    file_path: str | None,
    object_path: str | None,
) -> bool:
    context = cached.context or {}
    if file_path:
        resolved_file = context.get("file")
        if resolved_file is not None:
            if resolved_file != file_path:
                return False
        elif context.get("file_path") != file_path:
            return False
    if object_path and context.get("object_path") != object_path:
            return False
    return True


def _resolve_nwb_object(root: Any, object_path: str) -> Any:
    obj = root
    for part in object_path.strip("/").split("/"):
        if not part:
            continue
        if hasattr(obj, part):
            obj = getattr(obj, part)
            continue
        try:
            obj = obj[part]
            continue
        except Exception:
            pass
        for attr in ("processing", "acquisition", "stimulus", "intervals", "time_series", "spatial_series", "interval_series"):
            container = getattr(obj, attr, None)
            if isinstance(container, dict) and part in container:
                obj = container[part]
                break
        else:
            raise KeyError(f"Could not resolve {part!r} in {object_path!r}")
    return obj


def _sample_numeric_data(data: Any, *, max_points: int = 240) -> dict[str, Any]:
    shape = _shape_list(getattr(data, "shape", None))
    result: dict[str, Any] = {
        "shape": shape,
        "sample_axis": None,
        "values": [],
    }
    try:
        if not shape:
            value = data[()]
            values = _numeric_values(value)
            result["values"] = values[:1]
            result["sample_axis"] = "scalar"
            return result
        if len(shape) == 1:
            count = min(shape[0], max_points)
            values = _numeric_values(data[:count])
            result["values"] = values
            result["sample_axis"] = "first dimension"
            return result
        count = min(shape[0], max_points)
        if len(shape) == 2 and shape[1] >= 2 and count <= 120:
            values = _numeric_values(data[:count, : min(shape[1], 2)])
            if len(values) >= 2:
                pairs = [values[index : index + 2] for index in range(0, len(values), 2)]
                result["intervals"] = [pair for pair in pairs if len(pair) == 2][:120]
                result["values"] = [pair[0] for pair in result["intervals"]]
                result["sample_axis"] = "first two columns"
                return result
        selection = tuple([slice(0, count)] + [0 for _ in shape[1:]])
        values = _numeric_values(data[selection])
        result["values"] = values
        result["sample_axis"] = "first dimension, first channel"
        return result
    except Exception as exc:
        result["message"] = str(exc)
        return result


def _numeric_values(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, (str, bytes)) or value is None:
        return []
    if isinstance(value, dict):
        values: list[float] = []
        for item in value.values():
            values.extend(_numeric_values(item))
        return values
    if isinstance(value, (list, tuple)):
        values: list[float] = []
        for item in value:
            values.extend(_numeric_values(item))
        return values
    return []


def _shape_list(value: Any) -> list[int] | None:
    if value is None:
        return None
    if hasattr(value, "shape"):
        value = getattr(value, "shape")
    if isinstance(value, int):
        return [int(value)]
    if isinstance(value, (list, tuple)):
        try:
            return [int(item) for item in value]
        except Exception:
            return None
    return None


def build_loading_code(context: dict[str, Any], variable: str) -> str:
    file_path = context.get("file") or context.get("file_path") or "path/to/file.nwb"
    object_path = context.get("object_path")
    if object_path:
        return (
            "from pynwb import NWBHDF5IO\n\n"
            f"with NWBHDF5IO({file_path!r}, 'r', load_namespaces=True) as io:\n"
            "    nwb = io.read()\n"
            "    obj = nwb\n"
            f"    for part in {object_path.strip('/').split('/')!r}:\n"
            "        obj = getattr(obj, part) if hasattr(obj, part) else obj[part]\n"
            "    data = obj.data[:] if hasattr(obj, 'data') else obj\n"
            "    print(obj)\n"
        )
    return (
        "# Metadata-only variable. Download/register the NWB asset for exact object-path loading.\n"
        f"variable_name = {variable!r}\n"
        "print(variable_name)\n"
    )


def _fallback_variable_explanation(
    *,
    variable: str,
    variable_context: dict[str, Any],
    evidence: list[dict[str, Any]],
    loading_code: str,
    reason: str,
) -> str:
    neurodata_type = variable_context.get("neurodata_type") or variable_context.get("kind") or "dataset variable"
    file_path = variable_context.get("file") or variable_context.get("file_path") or "the dataset file"
    object_path = variable_context.get("object_path") or "metadata-only"
    shape = variable_context.get("shape")
    rate = variable_context.get("rate")
    unit = variable_context.get("unit") or variable_context.get("units")
    description = variable_context.get("description")
    evidence_titles = [
        str(item.get("title") or item.get("source_type"))
        for item in evidence[:3]
        if item.get("title") or item.get("source_type")
    ]
    details = []
    if shape is not None:
        details.append(f"shape `{shape}`")
    if rate is not None:
        details.append(f"sampling rate `{rate}`")
    if unit:
        details.append(f"unit `{unit}`")
    detail_text = ", ".join(details) if details else "no explicit shape/rate/unit fields in the cached metadata"
    evidence_text = ", ".join(evidence_titles) if evidence_titles else "local DANDI/NWB metadata"
    desc_text = f" The NWB description says: {description}" if description else ""
    return (
        "### Meaning\n"
        f"`{variable}` is represented in the cached NWB metadata as a `{neurodata_type}` at "
        f"`{object_path}` in `{file_path}`. It has {detail_text}.{desc_text}\n\n"
        "### How to load it\n"
        "Use the bundled loading code or `scripts/load_variable.py` with the same NWB object path.\n\n"
        "```python\n"
        f"{loading_code}"
        "```\n\n"
        "### How it was likely generated or recorded\n"
        "This explanation is generated from the cached dataset metadata rather than a fresh model call. "
        "For behavior `IntervalSeries` variables, treat the values as annotated behavioral epochs. "
        "For `TimeSeries` variables such as neural traces, treat the values as processed signal data described by the NWB object metadata.\n\n"
        "### What to watch out for\n"
        "Confirm timestamp alignment, units, and interpretation against the source NWB file before analysis. "
        "The cache preserves the exact file and object path so code can be checked directly.\n\n"
        "### Evidence\n"
        f"This fallback used {evidence_text}. The live LLM call was skipped for demo readiness ({reason})."
    )


def _metadata_variables(summary: dict[str, Any]) -> list[dict[str, Any]]:
    variables: list[dict[str, Any]] = []
    for item in summary.get("variableMeasured") or []:
        variables.append(
            {
                "provider": "dandi",
                "name": _label(item),
                "kind": "metadata_variable",
                "source": "variableMeasured",
                "raw": item,
                "confidence_label": "metadata",
            }
        )
    for asset in (summary.get("assets") or {}).get("sample", []):
        path = asset.get("path") or ""
        if str(path).lower().endswith(".nwb"):
            variables.append(
                {
                    "provider": "dandi",
                    "name": Path(str(path)).stem,
                    "kind": "nwb_asset",
                    "file": path,
                    "size_bytes": _asset_size(asset),
                    "confidence_label": "metadata",
                }
            )
    return variables


def _normalize_local_signal(signal: dict[str, Any]) -> dict[str, Any]:
    name = signal.get("name") or signal.get("object_path") or signal.get("file")
    return {
        "provider": "dandi",
        "name": name,
        "kind": "nwb_signal",
        "confidence_label": "local",
        **signal,
    }


def _match_signal(
    signals: list[dict[str, Any]],
    *,
    variable: str,
    file_path: str | None,
    object_path: str | None,
) -> dict[str, Any] | None:
    if object_path:
        if file_path:
            for signal in signals:
                if signal.get("object_path") == object_path and signal.get("file") == file_path:
                    return signal
        for signal in signals:
            if signal.get("object_path") == object_path:
                return signal
    variable_lower = variable.lower()
    exact_name_matches = [
        signal
        for signal in signals
        if str(signal.get("name", "")).lower() == variable_lower
        or str(signal.get("object_path", "")).lower().endswith("/" + variable_lower)
    ]
    if file_path:
        for signal in exact_name_matches:
            if signal.get("file") == file_path:
                return signal
    if exact_name_matches:
        return exact_name_matches[0]
    for signal in signals:
        text = " ".join(str(signal.get(key, "")) for key in ["name", "object_path", "file", "neurodata_type"])
        if variable_lower in text.lower() and (not file_path or signal.get("file") == file_path):
            return signal
    return None


def _label(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("name") or value.get("identifier") or value.get("schemaKey") or json.dumps(value)[:80])
    return str(value)


def _asset_size(asset: dict[str, Any]) -> int | None:
    for key in ["size", "blobSize", "contentSize"]:
        value = asset.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, dict) and isinstance(value.get("value"), int):
            return value["value"]
    return None


def _safe_call(call: Any, default: Any) -> Any:
    try:
        return call()
    except Exception:
        return default
