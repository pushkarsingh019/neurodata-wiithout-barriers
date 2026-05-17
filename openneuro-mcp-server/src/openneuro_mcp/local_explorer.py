from __future__ import annotations

import csv
import fnmatch
import io
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openneuro_mcp.bids import classify_file, parse_bids_entities, parse_dataset_description, parse_events_tsv, parse_participants_tsv, summarize_bids_files
from openneuro_mcp.storage import MCPStorage


@dataclass(frozen=True)
class ResolvedDataset:
    key: str
    path: Path
    manifest: dict[str, Any]


class LocalOpenNeuroExplorer:
    """Local BIDS/OpenNeuro dataset explorer backed by MCP storage."""

    def __init__(self, storage: MCPStorage) -> None:
        self.storage = storage
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def local_dir(self) -> Path:
        return self.storage.config.provider_dir / "local-datasets"

    @property
    def registry_path(self) -> Path:
        return self.local_dir / "registry.json"

    @property
    def artifacts_dir(self) -> Path:
        return self.storage.config.provider_dir / "artifacts"

    def register(self, path: str | None = None, dataset_id: str | None = None, tag: str = "local") -> dict[str, Any]:
        root = self._resolve_registration_path(path, dataset_id)
        manifest = self._build_manifest(root, dataset_id=dataset_id, tag=tag)
        key = manifest["dataset_key"]
        dataset_dir = self.local_dir / key
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_json(dataset_dir / "manifest.json", manifest)
        registry = self._registry()
        registry[key] = {
            "dataset_key": key,
            "dataset_id": manifest["dataset_id"],
            "tag": manifest["tag"],
            "name": manifest.get("name"),
            "root_path": manifest["root_path"],
            "file_count": manifest["file_count"],
            "registered_at": manifest["registered_at"],
            "last_scanned_at": manifest["last_scanned_at"],
        }
        _write_json(self.registry_path, registry)
        return {**registry[key], "manifest_path": str(dataset_dir / "manifest.json")}

    def list_registered(self) -> dict[str, Any]:
        registry = self._registry()
        return {"count": len(registry), "datasets": list(registry.values())}

    def summarize(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        manifest = resolved.manifest
        index = self._read_index(resolved.key)
        return {
            "dataset_key": resolved.key,
            "dataset_id": manifest["dataset_id"],
            "tag": manifest["tag"],
            "name": manifest.get("name"),
            "bids_version": manifest.get("bids_version"),
            "root_path": manifest["root_path"],
            "file_count": manifest["file_count"],
            "total_size_bytes": manifest["total_size_bytes"],
            "file_type_counts": manifest["file_type_counts"],
            "subjects": index.get("subjects", manifest.get("subjects", [])),
            "sessions": index.get("sessions", manifest.get("sessions", [])),
            "tasks": index.get("tasks", manifest.get("tasks", [])),
            "modalities": index.get("modalities", manifest.get("modalities", [])),
            "events_files": index.get("events_file_count", manifest.get("events_file_count", 0)),
            "participants": index.get("participants", manifest.get("participants", {})),
            "index_status": "indexed" if index else "not_indexed",
            "sample_files": manifest["files"][:10],
        }

    def browse(self, dataset_key: str = "", path_prefix: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        return _browse_manifest(resolved.key, resolved.manifest["files"], path_prefix)

    def list_files(self, dataset_key: str = "", glob: str | None = None, file_type: str | None = None, subject: str | None = None, limit: int = 100) -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        rows = []
        for record in resolved.manifest["files"]:
            if glob and not fnmatch.fnmatch(record["path"], glob):
                continue
            if file_type and record["file_type"] != file_type.lower().lstrip("."):
                continue
            if subject and record.get("entities", {}).get("sub") != subject:
                continue
            rows.append(record)
        return {"dataset_key": resolved.key, "count": len(rows), "returned": min(len(rows), max(limit, 0)), "files": rows[: max(limit, 0)]}

    def index(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        files = resolved.manifest["files"]
        participants = self._participants_summary(resolved)
        events = [self._events_summary(resolved, record) for record in files if record["path"].endswith("_events.tsv")]
        tasks = sorted({record.get("entities", {}).get("task") for record in files if record.get("entities", {}).get("task")})
        subjects = sorted({record.get("entities", {}).get("sub") for record in files if record.get("entities", {}).get("sub")})
        sessions = sorted({record.get("entities", {}).get("ses") for record in files if record.get("entities", {}).get("ses")})
        modalities = sorted({record["modality"] for record in files if record.get("modality") and record["modality"] != "unknown"})
        signal_inventory = [
            {
                "file": record["path"],
                "modality": record.get("modality"),
                "suffix": record.get("entities", {}).get("suffix"),
                "task": record.get("entities", {}).get("task"),
                "subject": record.get("entities", {}).get("sub"),
                "size_bytes": record["size_bytes"],
            }
            for record in files
            if record.get("modality") and record["modality"] != "unknown"
        ]
        index = {
            "dataset_key": resolved.key,
            "dataset_id": resolved.manifest["dataset_id"],
            "indexed_at": _now(),
            "subjects": subjects,
            "sessions": sessions,
            "tasks": tasks,
            "modalities": modalities,
            "participants": participants,
            "events_file_count": len(events),
            "events": events,
            "signal_inventory": signal_inventory,
        }
        _write_json(self.local_dir / resolved.key / "index.json", index)
        return index

    def subjects(self, dataset_key: str = "") -> dict[str, Any]:
        index = self._ensure_index(self._resolve_dataset(dataset_key).key)
        return {"count": len(index["subjects"]), "subjects": index["subjects"]}

    def sessions(self, dataset_key: str = "") -> dict[str, Any]:
        index = self._ensure_index(self._resolve_dataset(dataset_key).key)
        return {"count": len(index["sessions"]), "sessions": index["sessions"]}

    def signal_inventory(self, dataset_key: str = "") -> dict[str, Any]:
        index = self._ensure_index(self._resolve_dataset(dataset_key).key)
        return {"count": len(index["signal_inventory"]), "signals": index["signal_inventory"]}

    def extract_events(self, dataset_key: str = "", path: str = "", task: str | None = None, limit: int = 1000) -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        matches = [record for record in resolved.manifest["files"] if record["path"].endswith("_events.tsv")]
        if path:
            matches = [record for record in matches if record["path"] == path or record["path"].endswith(path)]
        if task:
            matches = [record for record in matches if record.get("entities", {}).get("task") == task]
        if len(matches) != 1:
            raise ValueError(f"Expected one events.tsv match, found {len(matches)}")
        event_path = resolved.path / matches[0]["path"]
        rows = list(csv.DictReader(io.StringIO(event_path.read_text(encoding="utf-8")), delimiter="\t"))
        task_name = matches[0].get("entities", {}).get("task") or task or "unknown"
        structure = parse_events_tsv(task_name, event_path.read_text(encoding="utf-8"))
        return {
            "dataset_key": resolved.key,
            "path": matches[0]["path"],
            "task": task_name,
            "row_count": len(rows),
            "returned": min(len(rows), max(limit, 0)),
            "columns": structure.event_columns,
            "trial_type_values": structure.trial_type_values,
            "onset_range_seconds": structure.onset_range_seconds,
            "duration_range_seconds": structure.duration_range_seconds,
            "rows": rows[: max(limit, 0)],
        }

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
            f"- OpenNeuro ID: `{summary['dataset_id']}`",
            f"- Root path: `{summary['root_path']}`",
            f"- Files: {summary['file_count']}",
            f"- Subjects: {', '.join(index['subjects']) or 'none detected'}",
            f"- Tasks: {', '.join(index['tasks']) or 'none detected'}",
            f"- Modalities: {', '.join(index['modalities']) or 'none inferred'}",
            "",
            "## Events",
            "",
        ]
        for event in index["events"]:
            lines.append(f"- `{event['path']}` task={event['task']} rows={event['row_count']} columns={event['columns']}")
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"dataset_key": resolved.key, "report_path": str(report_path), "summary": {"subjects": index["subjects"], "tasks": index["tasks"], "modalities": index["modalities"]}}

    def _build_manifest(self, root: Path, dataset_id: str | None, tag: str) -> dict[str, Any]:
        description_path = root / "dataset_description.json"
        description = parse_dataset_description(description_path.read_text(encoding="utf-8") if description_path.exists() else None)
        inferred_id = dataset_id or root.name
        files = []
        total_size = 0
        type_counts: Counter[str] = Counter()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            classified = classify_file(rel, size=stat.st_size)
            record = {
                "path": rel,
                "absolute_path": str(path),
                "filename": path.name,
                "file_type": path.suffix.lower().lstrip(".") or "unknown",
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "entities": parse_bids_entities(rel),
                "modality": classified.modality.value,
            }
            files.append(record)
            total_size += stat.st_size
            type_counts[record["file_type"]] += 1
        bids_files = [classify_file(record["path"], size=record["size_bytes"]) for record in files]
        bids_summary = summarize_bids_files(bids_files)
        return {
            "dataset_key": _dataset_key(inferred_id, tag),
            "dataset_id": inferred_id,
            "tag": tag,
            "name": description.get("Name"),
            "bids_version": description.get("BIDSVersion"),
            "root_path": str(root),
            "registered_at": _now(),
            "last_scanned_at": _now(),
            "file_count": len(files),
            "total_size_bytes": total_size,
            "file_type_counts": dict(sorted(type_counts.items())),
            "subjects": bids_summary["subjects"],
            "sessions": sorted({session for sessions in bids_summary["sessions_by_subject"].values() for session in sessions}),
            "tasks": bids_summary["tasks"],
            "modalities": sorted(bids_summary["modalities"]),
            "events_file_count": sum(1 for record in files if record["path"].endswith("_events.tsv")),
            "participants": self._participants_summary_from_path(root),
            "description": description,
            "files": files,
        }

    def _participants_summary(self, resolved: ResolvedDataset) -> dict[str, Any]:
        return self._participants_summary_from_path(resolved.path)

    def _participants_summary_from_path(self, root: Path) -> dict[str, Any]:
        path = root / "participants.tsv"
        if not path.exists():
            return {"participant_count": 0, "columns": []}
        summary = parse_participants_tsv(path.read_text(encoding="utf-8"))
        return summary.model_dump()

    def _events_summary(self, resolved: ResolvedDataset, record: dict[str, Any]) -> dict[str, Any]:
        path = resolved.path / record["path"]
        task = record.get("entities", {}).get("task") or "unknown"
        structure = parse_events_tsv(task, path.read_text(encoding="utf-8"))
        return {"path": record["path"], "task": task, "row_count": _tsv_row_count(path), "columns": structure.event_columns, "trial_type_values": structure.trial_type_values}

    def _resolve_registration_path(self, path: str | None, dataset_id: str | None) -> Path:
        if path:
            root = Path(path).expanduser().resolve()
            if not root.is_dir():
                raise ValueError(f"Local dataset path does not exist: {root}")
            return root
        if not dataset_id:
            raise ValueError("Provide either path or dataset_id")
        roots = [Path.cwd(), Path.cwd().parent, self.storage.config.downloads_dir]
        roots.extend(Path(part).expanduser() for part in os.environ.get("OPENNEURO_MCP_DATA_ROOTS", "").split(os.pathsep) if part)
        for root in roots:
            for name in [dataset_id, dataset_id.replace(":", "_")]:
                candidate = root / name
                if candidate.is_dir():
                    return candidate.resolve()
        raise ValueError(f"Could not locate local OpenNeuro dataset {dataset_id}; provide path explicitly.")

    def _registry(self) -> dict[str, Any]:
        return json.loads(self.registry_path.read_text(encoding="utf-8")) if self.registry_path.exists() else {}

    def _resolve_dataset(self, dataset_key: str = "") -> ResolvedDataset:
        registry = self._registry()
        key = dataset_key.strip()
        if not key:
            if len(registry) != 1:
                raise ValueError("dataset_key is required when zero or multiple local datasets are registered")
            key = next(iter(registry))
        elif key not in registry:
            matches = [candidate for candidate, record in registry.items() if record.get("dataset_id") == key]
            if len(matches) != 1:
                raise ValueError(f"No unique registered local dataset matches {key}")
            key = matches[0]
        manifest = json.loads((self.local_dir / key / "manifest.json").read_text(encoding="utf-8"))
        return ResolvedDataset(key=key, path=Path(manifest["root_path"]), manifest=manifest)

    def _read_index(self, dataset_key: str) -> dict[str, Any]:
        path = self.local_dir / dataset_key / "index.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _ensure_index(self, dataset_key: str) -> dict[str, Any]:
        return self._read_index(dataset_key) or self.index(dataset_key)


def _browse_manifest(dataset_key: str, files: list[dict[str, Any]], path_prefix: str) -> dict[str, Any]:
    prefix = path_prefix.strip("/")
    children: dict[str, dict[str, Any]] = {}
    for record in files:
        rel = record["path"]
        if prefix and rel != prefix and not rel.startswith(prefix + "/"):
            continue
        remainder = rel[len(prefix):].lstrip("/") if prefix else rel
        if not remainder:
            continue
        first = remainder.split("/", 1)[0]
        child_path = f"{prefix}/{first}".strip("/")
        entry = children.setdefault(child_path, {"path": child_path, "kind": "file", "file_count": 0, "size_bytes": 0})
        entry["file_count"] += 1
        entry["size_bytes"] += record["size_bytes"]
        if "/" in remainder:
            entry["kind"] = "directory"
        else:
            entry.update({"file_type": record["file_type"], "modality": record.get("modality"), "entities": record.get("entities", {})})
    return {"dataset_key": dataset_key, "path_prefix": prefix, "children": sorted(children.values(), key=lambda item: (item["kind"], item["path"]))}


def _dataset_key(dataset_id: str, tag: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", dataset_id)
    clean_tag = re.sub(r"[^A-Za-z0-9_.-]+", "_", tag)
    return f"OPENNEURO_{clean}_{clean_tag}"


def _tsv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as stream:
        return max(sum(1 for _ in stream) - 1, 0)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
