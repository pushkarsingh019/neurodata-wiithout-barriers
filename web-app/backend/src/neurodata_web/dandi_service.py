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
        cache_key = json.dumps(
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
        cached = self.cache.read_model("variable_explanation", cache_key, VariableExplainResponse)
        if cached:
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
            ai_status = "unavailable"
            ai_error = str(exc)
            explanation = evidence_payload.get("interpretation") if isinstance(evidence_payload, dict) else None
        except Exception as exc:  # pragma: no cover - runtime resilience
            ai_status = "error"
            ai_error = str(exc)
            explanation = evidence_payload.get("interpretation") if isinstance(evidence_payload, dict) else None
        response = VariableExplainResponse(
            dataset_id=dataset_id,
            variable=variable,
            loading_code=loading_code,
            explanation=explanation,
            evidence=evidence,
            context=variable_context,
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
        page = self.dataset_page(dataset_id, version=version)
        variables = self.variables(dataset_id, version=version).variables
        return {
            "summary": page.summary,
            "variables": variables,
            "papers": page.papers,
            "overview": page.ai_overview,
        }

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
