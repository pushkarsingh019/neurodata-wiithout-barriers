from __future__ import annotations

import fnmatch
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dandi_mcp.storage import MCPStorage


NWB_DEPENDENCY_ERROR = (
    "Local NWB inspection requires pynwb and nwbinspector. Install the analysis extra "
    "or add those packages to the MCP runtime."
)


@dataclass(frozen=True)
class ResolvedDataset:
    key: str
    path: Path
    manifest: dict[str, Any]


class LocalDandisetExplorer:
    """Local DANDI/NWB explorer backed by the MCP storage directory."""

    def __init__(self, storage: MCPStorage) -> None:
        self.storage = storage
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def local_dir(self) -> Path:
        return self.storage.config.provider_dir / "local-dandisets"

    @property
    def registry_path(self) -> Path:
        return self.local_dir / "registry.json"

    @property
    def artifacts_dir(self) -> Path:
        return self.storage.config.provider_dir / "artifacts"

    def register(
        self,
        *,
        path: str | None = None,
        dandiset_id: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        root = self._resolve_registration_path(path=path, dandiset_id=dandiset_id)
        manifest = self._build_manifest(root, dandiset_id=dandiset_id, version=version)
        key = manifest["dataset_key"]
        dataset_dir = self.local_dir / key
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_json(dataset_dir / "manifest.json", manifest)

        registry = self._registry()
        registry[key] = {
            "dataset_key": key,
            "dandiset_id": manifest.get("dandiset_id"),
            "version": manifest.get("version"),
            "name": manifest.get("name"),
            "root_path": manifest["root_path"],
            "file_count": manifest["file_count"],
            "nwb_file_count": manifest["file_type_counts"].get("nwb", 0),
            "registered_at": manifest["registered_at"],
            "last_scanned_at": manifest["last_scanned_at"],
        }
        _write_json(self.registry_path, registry)
        return {
            **registry[key],
            "manifest_path": str(dataset_dir / "manifest.json"),
            "next_steps": [
                "Call summarize_local_dandiset for a dataset-level overview.",
                "Call index_local_dandiset to inspect NWB files and build the analysis inventory.",
                "Call generate_dataset_report to create a shareable Markdown report.",
            ],
        }

    def list_registered(self) -> dict[str, Any]:
        registry = self._registry()
        return {"count": len(registry), "datasets": list(registry.values())}

    def summarize(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        manifest = resolved.manifest
        index = self._read_index(resolved.key)
        sample_files = manifest["files"][:10]
        return {
            "dataset_key": resolved.key,
            "dandiset_id": manifest.get("dandiset_id"),
            "version": manifest.get("version"),
            "name": manifest.get("name"),
            "citation": manifest.get("citation"),
            "license": manifest.get("license"),
            "root_path": manifest["root_path"],
            "file_count": manifest["file_count"],
            "total_size_bytes": manifest["total_size_bytes"],
            "file_type_counts": manifest["file_type_counts"],
            "subjects": index.get("subjects", manifest.get("subjects", [])),
            "sessions": index.get("sessions", []),
            "modalities": index.get("modalities", manifest.get("modalities", [])),
            "nwb_files": index.get("nwb_file_count", manifest["file_type_counts"].get("nwb", 0)),
            "validation": index.get("validation_summary", {"status": "not_run"}),
            "sample_files": sample_files,
            "index_status": "indexed" if index else "not_indexed",
            "recommended_tools": [
                "browse_local_dandiset",
                "inspect_nwb_file",
                "index_local_dandiset",
                "extract_trials_table",
                "generate_dataset_report",
            ],
        }

    def browse(self, dataset_key: str = "", path_prefix: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        prefix = path_prefix.strip("/")
        children: dict[str, dict[str, Any]] = {}
        for file_record in resolved.manifest["files"]:
            rel = file_record["path"]
            if prefix:
                if rel != prefix and not rel.startswith(prefix + "/"):
                    continue
                remainder = rel[len(prefix) :].lstrip("/")
            else:
                remainder = rel
            if not remainder:
                continue
            first = remainder.split("/", 1)[0]
            child_path = f"{prefix}/{first}".strip("/")
            entry = children.setdefault(
                child_path,
                {"path": child_path, "kind": "file", "file_count": 0, "size_bytes": 0},
            )
            entry["file_count"] += 1
            entry["size_bytes"] += file_record["size_bytes"]
            if "/" in remainder:
                entry["kind"] = "directory"
            else:
                entry.update(
                    {
                        "file_type": file_record["file_type"],
                        "subject": file_record.get("subject"),
                        "session": file_record.get("session"),
                    }
                )
        return {
            "dataset_key": resolved.key,
            "path_prefix": prefix,
            "children": sorted(children.values(), key=lambda item: (item["kind"], item["path"])),
        }

    def list_files(
        self,
        dataset_key: str = "",
        *,
        glob: str | None = None,
        file_type: str | None = None,
        subject: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        rows = []
        for file_record in resolved.manifest["files"]:
            if glob and not fnmatch.fnmatch(file_record["path"], glob):
                continue
            if file_type and file_record["file_type"] != file_type.lower().lstrip("."):
                continue
            if subject and file_record.get("subject") != subject:
                continue
            rows.append(file_record)
        return {
            "dataset_key": resolved.key,
            "count": len(rows),
            "returned": min(len(rows), max(limit, 0)),
            "files": rows[: max(limit, 0)],
        }

    def inspect_nwb(self, dataset_key: str = "", path: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        nwb_path = self._resolve_file_path(resolved, path, required_type="nwb")
        return inspect_nwb_file(nwb_path, dataset_key=resolved.key, root_path=resolved.path)

    def validate_nwb(self, dataset_key: str = "", path: str = "", limit: int = 100) -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        nwb_path = self._resolve_file_path(resolved, path, required_type="nwb")
        return validate_nwb_file(nwb_path, dataset_key=resolved.key, root_path=resolved.path, limit=limit)

    def index(self, dataset_key: str = "", inspect_limit: int = 100) -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        nwb_files = [item for item in resolved.manifest["files"] if item["file_type"] == "nwb"]
        summaries = []
        validation_counts: Counter[str] = Counter()
        for file_record in nwb_files[: max(inspect_limit, 0)]:
            summary = self.inspect_nwb(resolved.key, file_record["path"])
            summaries.append(summary)
            validation = self.validate_nwb(resolved.key, file_record["path"], limit=25)
            validation_counts[validation["status"]] += 1

        subjects = sorted(
            {
                str(summary.get("subject", {}).get("subject_id") or file_record.get("subject"))
                for summary, file_record in zip(summaries, nwb_files)
                if summary.get("subject", {}).get("subject_id") or file_record.get("subject")
            }
        )
        sessions = sorted(
            {
                str(summary.get("session_id") or file_record.get("session") or summary["relative_path"])
                for summary, file_record in zip(summaries, nwb_files)
            }
        )
        modalities = sorted({modality for summary in summaries for modality in summary.get("modalities", [])})
        signal_inventory = []
        for summary in summaries:
            for ts in summary.get("timeseries", []):
                signal_inventory.append(
                    {
                        "file": summary["relative_path"],
                        "object_path": ts["object_path"],
                        "name": ts["name"],
                        "neurodata_type": ts["neurodata_type"],
                        "shape": ts.get("shape"),
                        "rate": ts.get("rate"),
                        "unit": ts.get("unit"),
                    }
                )

        index = {
            "dataset_key": resolved.key,
            "dandiset_id": resolved.manifest.get("dandiset_id"),
            "version": resolved.manifest.get("version"),
            "indexed_at": _now(),
            "root_path": str(resolved.path),
            "file_count": resolved.manifest["file_count"],
            "nwb_file_count": len(nwb_files),
            "inspected_nwb_file_count": len(summaries),
            "subjects": subjects,
            "sessions": sessions,
            "modalities": modalities,
            "nwb_summaries": summaries,
            "signal_inventory": signal_inventory,
            "trial_tables": [
                {
                    "file": summary["relative_path"],
                    **summary["trials"],
                }
                for summary in summaries
                if summary.get("trials", {}).get("present")
            ],
            "unit_tables": [
                {
                    "file": summary["relative_path"],
                    **summary["units"],
                }
                for summary in summaries
                if summary.get("units", {}).get("present")
            ],
            "validation_summary": dict(validation_counts) or {"status": "not_run"},
        }
        _write_json(self.local_dir / resolved.key / "index.json", index)
        return index

    def subjects(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        index = self._ensure_index(resolved.key)
        return {"dataset_key": resolved.key, "count": len(index["subjects"]), "subjects": index["subjects"]}

    def sessions(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        index = self._ensure_index(resolved.key)
        return {"dataset_key": resolved.key, "count": len(index["sessions"]), "sessions": index["sessions"]}

    def signal_inventory(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        index = self._ensure_index(resolved.key)
        return {
            "dataset_key": resolved.key,
            "count": len(index["signal_inventory"]),
            "signals": index["signal_inventory"],
        }

    def extract_trials(self, dataset_key: str = "", path: str = "", limit: int = 1000) -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        nwb_path = self._resolve_file_path(resolved, path, required_type="nwb")
        return extract_trials_table(nwb_path, dataset_key=resolved.key, root_path=resolved.path, limit=limit)

    def report(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        summary = self.summarize(resolved.key)
        index = self._ensure_index(resolved.key)
        report_dir = self.artifacts_dir / resolved.key
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "dataset-report.md"
        lines = [
            f"# {summary.get('name') or resolved.key}",
            "",
            f"- Dataset key: `{resolved.key}`",
            f"- DANDI ID: `{summary.get('dandiset_id') or 'unknown'}`",
            f"- Version: `{summary.get('version') or 'unknown'}`",
            f"- Root path: `{summary['root_path']}`",
            f"- Files: {summary['file_count']}",
            f"- NWB files: {summary['nwb_files']}",
            f"- Subjects: {', '.join(index['subjects']) or 'none detected'}",
            f"- Modalities: {', '.join(index['modalities']) or 'none inferred'}",
            "",
            "## Citation",
            "",
            str(summary.get("citation") or "No citation found in local metadata."),
            "",
            "## File Types",
            "",
        ]
        for file_type, count in sorted(summary["file_type_counts"].items()):
            lines.append(f"- `{file_type}`: {count}")
        lines.extend(["", "## Signals", ""])
        for signal in index["signal_inventory"][:100]:
            lines.append(
                f"- `{signal['file']}` `{signal['object_path']}` "
                f"shape={signal.get('shape')} rate={signal.get('rate')} unit={signal.get('unit')}"
            )
        lines.extend(["", "## Trial Tables", ""])
        for table in index["trial_tables"]:
            lines.append(f"- `{table['file']}` rows={table.get('row_count')} columns={table.get('columns')}")
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {
            "dataset_key": resolved.key,
            "report_path": str(report_path),
            "summary": {
                "file_count": summary["file_count"],
                "nwb_files": summary["nwb_files"],
                "subjects": index["subjects"],
                "modalities": index["modalities"],
                "signals": len(index["signal_inventory"]),
            },
        }

    def _registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _resolve_registration_path(self, *, path: str | None, dandiset_id: str | None) -> Path:
        if path:
            root = Path(path).expanduser().resolve()
            if not root.exists() or not root.is_dir():
                raise ValueError(f"Local Dandiset path does not exist or is not a directory: {root}")
            return root
        if not dandiset_id:
            raise ValueError("Provide either path or dandiset_id")
        candidates = self._candidate_roots(dandiset_id)
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate.resolve()
        raise ValueError(
            "Could not locate a local Dandiset directory for "
            f"{dandiset_id}. Provide path explicitly or set DANDI_MCP_DATA_ROOTS."
        )

    def _candidate_roots(self, dandiset_id: str) -> list[Path]:
        clean = _clean_dandiset_id(dandiset_id)
        names = [clean, f"DANDI-{clean}", f"DANDI_{clean}"]
        search_roots = [Path.cwd(), Path.cwd().parent, self.storage.config.downloads_dir]
        env_roots = os.environ.get("DANDI_MCP_DATA_ROOTS", "")
        search_roots.extend(Path(part).expanduser() for part in env_roots.split(os.pathsep) if part)
        return [root / name for root in search_roots for name in names]

    def _build_manifest(
        self, root: Path, *, dandiset_id: str | None = None, version: str | None = None
    ) -> dict[str, Any]:
        dandiset_yaml = root / "dandiset.yaml"
        metadata = _read_yaml(dandiset_yaml) if dandiset_yaml.exists() else {}
        inferred_id = _clean_dandiset_id(
            dandiset_id
            or str(metadata.get("identifier") or metadata.get("id") or root.name).split("/")[-1]
        )
        inferred_version = version or _version_from_metadata(metadata)
        dataset_key = _dataset_key(inferred_id, inferred_version)
        files = []
        type_counts: Counter[str] = Counter()
        subjects: set[str] = set()
        sessions: set[str] = set()
        modalities: set[str] = set()
        total_size = 0
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            file_type = _file_type(path)
            subject = _path_token(rel, "sub")
            session = _path_token(rel, "ses")
            modality = _infer_modality(rel, file_type)
            record = {
                "path": rel,
                "absolute_path": str(path),
                "file_type": file_type,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "subject": subject,
                "session": session,
                "modality": modality,
            }
            files.append(record)
            type_counts[file_type] += 1
            total_size += stat.st_size
            if subject:
                subjects.add(subject)
            if session:
                sessions.add(session)
            if modality:
                modalities.add(modality)
        return {
            "dataset_key": dataset_key,
            "dandiset_id": inferred_id,
            "version": inferred_version,
            "name": metadata.get("name"),
            "description": metadata.get("description"),
            "citation": metadata.get("citation"),
            "license": metadata.get("license"),
            "doi": metadata.get("doi"),
            "url": metadata.get("url"),
            "root_path": str(root),
            "registered_at": _now(),
            "last_scanned_at": _now(),
            "file_count": len(files),
            "total_size_bytes": total_size,
            "file_type_counts": dict(sorted(type_counts.items())),
            "subjects": sorted(subjects),
            "sessions": sorted(sessions),
            "modalities": sorted(modalities),
            "files": files,
        }

    def _resolve_dataset(self, dataset_key: str = "") -> ResolvedDataset:
        registry = self._registry()
        key = dataset_key.strip()
        if not key:
            if len(registry) != 1:
                raise ValueError("dataset_key is required when zero or multiple local Dandisets are registered")
            key = next(iter(registry))
        else:
            key = self._match_dataset_key(key, registry)
        manifest_path = self.local_dir / key / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"No local manifest found for dataset_key: {dataset_key}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        root = Path(manifest["root_path"])
        return ResolvedDataset(key=key, path=root, manifest=manifest)

    def _match_dataset_key(self, value: str, registry: dict[str, Any]) -> str:
        if value in registry:
            return value
        clean = _clean_dandiset_id(value)
        matches = [
            key
            for key, record in registry.items()
            if record.get("dandiset_id") == clean or key.startswith(f"DANDI_{clean}")
        ]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ValueError(f"Multiple local versions match {value}: {matches}")
        raise ValueError(f"No registered local Dandiset matches {value}")

    def _resolve_file_path(
        self, resolved: ResolvedDataset, path: str = "", *, required_type: str | None = None
    ) -> Path:
        files = resolved.manifest["files"]
        if path:
            matches = [item for item in files if item["path"] == path or item["path"].endswith(path)]
        else:
            matches = [item for item in files if not required_type or item["file_type"] == required_type]
        if required_type:
            matches = [item for item in matches if item["file_type"] == required_type]
        if len(matches) != 1:
            label = path or f"single {required_type or 'file'}"
            raise ValueError(f"Expected one match for {label}, found {len(matches)}")
        return resolved.path / matches[0]["path"]

    def _read_index(self, dataset_key: str) -> dict[str, Any]:
        index_path = self.local_dir / dataset_key / "index.json"
        if not index_path.exists():
            return {}
        return json.loads(index_path.read_text(encoding="utf-8"))

    def _ensure_index(self, dataset_key: str) -> dict[str, Any]:
        index = self._read_index(dataset_key)
        if index:
            return index
        return self.index(dataset_key)


def inspect_nwb_file(path: Path, *, dataset_key: str, root_path: Path) -> dict[str, Any]:
    try:
        from pynwb import NWBHDF5IO
    except ImportError:
        return {"status": "dependency_missing", "message": NWB_DEPENDENCY_ERROR}

    with NWBHDF5IO(str(path), "r", load_namespaces=True) as io:
        nwb = io.read()
        subject = _subject_summary(getattr(nwb, "subject", None))
        acquisition = _container_summary(getattr(nwb, "acquisition", {}), "acquisition")
        stimulus = _container_summary(getattr(nwb, "stimulus", {}), "stimulus")
        processing = []
        timeseries = []
        modalities = set()
        for module_name, module in getattr(nwb, "processing", {}).items():
            interfaces = []
            for interface_name, interface in module.data_interfaces.items():
                object_path = f"/processing/{module_name}/{interface_name}"
                interfaces.append(_object_summary(interface, object_path))
                timeseries.extend(_timeseries_from_object(interface, object_path))
                modalities.update(_modalities_from_name(module_name, interface_name, type(interface).__name__))
            processing.append(
                {
                    "name": module_name,
                    "description": getattr(module, "description", None),
                    "interfaces": interfaces,
                }
            )
        for item in acquisition:
            modalities.update(_modalities_from_name(item["name"], item["neurodata_type"]))
        for item in stimulus:
            modalities.update(_modalities_from_name(item["name"], item["neurodata_type"]))
        timeseries.extend(_timeseries_from_container(getattr(nwb, "acquisition", {}), "/acquisition"))
        timeseries.extend(_timeseries_from_container(getattr(nwb, "stimulus", {}), "/stimulus"))
        return {
            "status": "ok",
            "dataset_key": dataset_key,
            "path": str(path),
            "relative_path": path.relative_to(root_path).as_posix(),
            "session_description": getattr(nwb, "session_description", None),
            "identifier": getattr(nwb, "identifier", None),
            "session_id": getattr(nwb, "session_id", None),
            "session_start_time": _jsonable(getattr(nwb, "session_start_time", None)),
            "institution": getattr(nwb, "institution", None),
            "lab": getattr(nwb, "lab", None),
            "experimenter": _jsonable(getattr(nwb, "experimenter", None)),
            "subject": subject,
            "devices": sorted(getattr(nwb, "devices", {}).keys()),
            "acquisition": acquisition,
            "stimulus": stimulus,
            "processing": processing,
            "trials": _dynamic_table_summary(getattr(nwb, "trials", None)),
            "units": _dynamic_table_summary(getattr(nwb, "units", None)),
            "intervals": sorted(getattr(nwb, "intervals", {}).keys()),
            "timeseries": timeseries,
            "modalities": sorted(modalities),
        }


def validate_nwb_file(path: Path, *, dataset_key: str, root_path: Path, limit: int = 100) -> dict[str, Any]:
    try:
        from nwbinspector import inspect_nwbfile
    except ImportError:
        return {"status": "dependency_missing", "message": NWB_DEPENDENCY_ERROR}

    messages = []
    for message in inspect_nwbfile(path):
        if message is None:
            continue
        messages.append(
            {
                "importance": str(getattr(message, "importance", "")),
                "check_function_name": getattr(message, "check_function_name", None),
                "object_type": getattr(message, "object_type", None),
                "object_name": getattr(message, "object_name", None),
                "message": getattr(message, "message", str(message)),
            }
        )
        if len(messages) >= max(limit, 0):
            break
    return {
        "dataset_key": dataset_key,
        "path": str(path),
        "relative_path": path.relative_to(root_path).as_posix(),
        "status": "ok" if not messages else "issues_found",
        "issue_count_returned": len(messages),
        "issues": messages,
    }


def extract_trials_table(path: Path, *, dataset_key: str, root_path: Path, limit: int = 1000) -> dict[str, Any]:
    try:
        from pynwb import NWBHDF5IO
    except ImportError:
        return {"status": "dependency_missing", "message": NWB_DEPENDENCY_ERROR}

    with NWBHDF5IO(str(path), "r", load_namespaces=True) as io:
        nwb = io.read()
        trials = getattr(nwb, "trials", None)
        summary = _dynamic_table_summary(trials)
        if not summary["present"]:
            return {
                "status": "not_found",
                "dataset_key": dataset_key,
                "relative_path": path.relative_to(root_path).as_posix(),
                "trials": summary,
                "rows": [],
            }
        frame = trials.to_dataframe()
        rows = _jsonable(frame.head(max(limit, 0)).reset_index().to_dict(orient="records"))
        return {
            "status": "ok",
            "dataset_key": dataset_key,
            "path": str(path),
            "relative_path": path.relative_to(root_path).as_posix(),
            "row_count": len(frame),
            "returned": len(rows),
            "columns": list(frame.columns),
            "rows": rows,
        }


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_dandiset_id(value: str) -> str:
    match = re.search(r"(\d{6})", value)
    if not match:
        raise ValueError(f"Could not infer a six-digit DANDI identifier from: {value}")
    return match.group(1)


def _version_from_metadata(metadata: dict[str, Any]) -> str:
    identifier = str(metadata.get("id") or "")
    if "/" in identifier:
        return identifier.rsplit("/", 1)[-1]
    version = metadata.get("version")
    return str(version) if version else "unknown"


def _dataset_key(dandiset_id: str, version: str | None) -> str:
    suffix = re.sub(r"[^A-Za-z0-9_.-]+", "_", version or "unknown")
    return f"DANDI_{dandiset_id}_{suffix}"


def _file_type(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".zarr") or ".zarr/" in path.as_posix().lower():
        return "zarr"
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def _path_token(path: str, token: str) -> str | None:
    match = re.search(rf"(?:^|[/_]){token}-([^/_]+)", path)
    return match.group(1) if match else None


def _infer_modality(path: str, file_type: str) -> str | None:
    lowered = path.lower()
    if file_type == "nwb":
        if "ophys" in lowered or "calcium" in lowered:
            return "ophys"
        if "ecephys" in lowered or "spike" in lowered:
            return "ecephys"
        if "behavior" in lowered or "behav" in lowered:
            return "behavior"
        return "nwb"
    if file_type == "zarr":
        return "zarr"
    if file_type in {"mp4", "avi", "mov"}:
        return "video"
    return None


def _subject_summary(subject: Any) -> dict[str, Any]:
    if subject is None:
        return {}
    fields = ["subject_id", "species", "sex", "age", "age__reference", "description", "genotype", "strain"]
    return {field: _jsonable(getattr(subject, field, None)) for field in fields if getattr(subject, field, None) is not None}


def _container_summary(container: Any, root: str) -> list[dict[str, Any]]:
    return [_object_summary(obj, f"/{root}/{name}") for name, obj in container.items()]


def _object_summary(obj: Any, object_path: str) -> dict[str, Any]:
    return {
        "name": getattr(obj, "name", object_path.rsplit("/", 1)[-1]),
        "object_path": object_path,
        "neurodata_type": type(obj).__name__,
        "description": getattr(obj, "description", None),
        "shape": _shape(getattr(obj, "data", None)),
        "rate": _jsonable(getattr(obj, "rate", None)),
        "unit": getattr(obj, "unit", None),
    }


def _timeseries_from_container(container: Any, root: str) -> list[dict[str, Any]]:
    rows = []
    for name, obj in container.items():
        rows.extend(_timeseries_from_object(obj, f"{root}/{name}"))
    return rows


def _timeseries_from_object(obj: Any, object_path: str) -> list[dict[str, Any]]:
    rows = []
    if hasattr(obj, "data") and (hasattr(obj, "rate") or hasattr(obj, "timestamps")):
        rows.append(_object_summary(obj, object_path))
    for attr in ("time_series", "spatial_series", "interval_series"):
        collection = getattr(obj, attr, None)
        if isinstance(collection, dict):
            for name, child in collection.items():
                rows.extend(_timeseries_from_object(child, f"{object_path}/{name}"))
    return rows


def _modalities_from_name(*parts: str) -> set[str]:
    text = " ".join(str(part).lower() for part in parts)
    modalities = set()
    if any(term in text for term in ["ophys", "fluorescence", "calcium", "imaging"]):
        modalities.add("ophys")
    if any(term in text for term in ["behavior", "epoch", "lick", "trial", "stimulus"]):
        modalities.add("behavior")
    if any(term in text for term in ["ecephys", "spike", "unit", "electrode"]):
        modalities.add("ecephys")
    return modalities or {"nwb"}


def _dynamic_table_summary(table: Any) -> dict[str, Any]:
    if table is None:
        return {"present": False, "row_count": 0, "columns": []}
    columns = list(getattr(table, "colnames", []) or [])
    try:
        row_count = len(table)
    except Exception:
        row_count = None
    return {"present": True, "row_count": row_count, "columns": columns}


def _shape(data: Any) -> list[int] | None:
    shape = getattr(data, "shape", None)
    if shape is None:
        try:
            return [len(data)]
        except Exception:
            return None
    return [int(item) for item in shape]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
