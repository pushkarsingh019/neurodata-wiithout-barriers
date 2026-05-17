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

from ibl_mcp.storage import MCPStorage


@dataclass(frozen=True)
class ResolvedDataset:
    key: str
    path: Path
    manifest: dict[str, Any]


class LocalIBLExplorer:
    """Local IBL/ALF-style downloaded dataset explorer backed by MCP storage."""

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

    def register(self, path: str | None = None, session_id: str | None = None, dataset_id: str | None = None) -> dict[str, Any]:
        identifier = session_id or dataset_id
        root = self._resolve_registration_path(path, identifier)
        manifest = self._build_manifest(root, session_id=session_id, dataset_id=dataset_id)
        key = manifest["dataset_key"]
        dataset_dir = self.local_dir / key
        dataset_dir.mkdir(parents=True, exist_ok=True)
        _write_json(dataset_dir / "manifest.json", manifest)
        registry = self._registry()
        registry[key] = {
            "dataset_key": key,
            "session_id": manifest.get("session_id"),
            "dataset_id": manifest.get("dataset_id"),
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
            "session_id": manifest.get("session_id"),
            "dataset_id": manifest.get("dataset_id"),
            "root_path": manifest["root_path"],
            "file_count": manifest["file_count"],
            "total_size_bytes": manifest["total_size_bytes"],
            "file_type_counts": manifest["file_type_counts"],
            "subjects": index.get("subjects", manifest.get("subjects", [])),
            "sessions": index.get("sessions", manifest.get("sessions", [])),
            "collections": index.get("collections", manifest.get("collections", [])),
            "modalities": index.get("modalities", manifest.get("modalities", [])),
            "alf_objects": index.get("alf_objects", manifest.get("alf_objects", [])),
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
            if subject and record.get("subject") != subject:
                continue
            rows.append(record)
        return {"dataset_key": resolved.key, "count": len(rows), "returned": min(len(rows), max(limit, 0)), "files": rows[: max(limit, 0)]}

    def index(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        files = resolved.manifest["files"]
        subjects = sorted({record["subject"] for record in files if record.get("subject")})
        sessions = sorted({record["session"] for record in files if record.get("session")})
        collections = sorted({record["collection"] for record in files if record.get("collection")})
        modalities = sorted({record["modality"] for record in files if record.get("modality")})
        alf_objects = sorted({record["alf_object"] for record in files if record.get("alf_object")})
        signal_inventory = [
            {
                "file": record["path"],
                "collection": record.get("collection"),
                "alf_object": record.get("alf_object"),
                "alf_attribute": record.get("alf_attribute"),
                "modality": record.get("modality"),
                "size_bytes": record["size_bytes"],
            }
            for record in files
            if record.get("alf_object") or record.get("modality")
        ]
        index = {
            "dataset_key": resolved.key,
            "indexed_at": _now(),
            "subjects": subjects,
            "sessions": sessions,
            "collections": collections,
            "modalities": modalities,
            "alf_objects": alf_objects,
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

    def report(self, dataset_key: str = "") -> dict[str, Any]:
        resolved = self._resolve_dataset(dataset_key)
        summary = self.summarize(resolved.key)
        index = self._ensure_index(resolved.key)
        report_dir = self.artifacts_dir / resolved.key
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "dataset-report.md"
        lines = [
            f"# IBL Local Dataset {resolved.key}",
            "",
            f"- Dataset key: `{resolved.key}`",
            f"- Root path: `{summary['root_path']}`",
            f"- Files: {summary['file_count']}",
            f"- Subjects: {', '.join(index['subjects']) or 'none detected'}",
            f"- Sessions: {', '.join(index['sessions']) or 'none detected'}",
            f"- Collections: {', '.join(index['collections']) or 'none detected'}",
            f"- Modalities: {', '.join(index['modalities']) or 'none inferred'}",
            "",
            "## ALF Objects",
            "",
        ]
        for obj in index["alf_objects"]:
            lines.append(f"- `{obj}`")
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"dataset_key": resolved.key, "report_path": str(report_path), "summary": {"subjects": index["subjects"], "sessions": index["sessions"], "modalities": index["modalities"]}}

    def _build_manifest(self, root: Path, session_id: str | None, dataset_id: str | None) -> dict[str, Any]:
        files = []
        total_size = 0
        type_counts: Counter[str] = Counter()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            parsed = _parse_ibl_path(rel)
            record = {
                "path": rel,
                "absolute_path": str(path),
                "filename": path.name,
                "file_type": path.suffix.lower().lstrip(".") or "unknown",
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                **parsed,
            }
            files.append(record)
            total_size += stat.st_size
            type_counts[record["file_type"]] += 1
        return {
            "dataset_key": _dataset_key(session_id or dataset_id or root.name),
            "session_id": session_id,
            "dataset_id": dataset_id,
            "root_path": str(root),
            "registered_at": _now(),
            "last_scanned_at": _now(),
            "file_count": len(files),
            "total_size_bytes": total_size,
            "file_type_counts": dict(sorted(type_counts.items())),
            "subjects": sorted({record["subject"] for record in files if record.get("subject")}),
            "sessions": sorted({record["session"] for record in files if record.get("session")}),
            "collections": sorted({record["collection"] for record in files if record.get("collection")}),
            "modalities": sorted({record["modality"] for record in files if record.get("modality")}),
            "alf_objects": sorted({record["alf_object"] for record in files if record.get("alf_object")}),
            "files": files,
        }

    def _resolve_registration_path(self, path: str | None, identifier: str | None) -> Path:
        if path:
            root = Path(path).expanduser().resolve()
            if not root.is_dir():
                raise ValueError(f"Local dataset path does not exist: {root}")
            return root
        if not identifier:
            raise ValueError("Provide either path, session_id, or dataset_id")
        roots = [Path.cwd(), Path.cwd().parent, self.storage.config.downloads_dir]
        roots.extend(Path(part).expanduser() for part in os.environ.get("IBL_MCP_DATA_ROOTS", "").split(os.pathsep) if part)
        for root in roots:
            candidate = root / identifier
            if candidate.is_dir():
                return candidate.resolve()
        raise ValueError(f"Could not locate local IBL dataset {identifier}; provide path explicitly.")

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
            matches = [candidate for candidate, record in registry.items() if key in {record.get("session_id"), record.get("dataset_id")}]
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


def _parse_ibl_path(path: str) -> dict[str, Any]:
    parts = path.split("/")
    filename = parts[-1]
    subject = _path_token(path, "sub")
    session = _path_token(path, "ses") or _uuid_token(path)
    collection = "/".join(parts[:-1]) if len(parts) > 1 else ""
    alf_object = None
    alf_attribute = None
    match = re.match(r"_?([A-Za-z0-9]+)[._]([A-Za-z0-9_]+)", filename)
    if match:
        alf_object = match.group(1)
        alf_attribute = match.group(2)
    return {
        "subject": subject,
        "session": session,
        "collection": collection,
        "alf_object": alf_object,
        "alf_attribute": alf_attribute,
        "modality": _infer_modality(path, alf_object, alf_attribute),
    }


def _infer_modality(path: str, obj: str | None, attr: str | None) -> str | None:
    text = " ".join(part for part in [path.lower(), obj, attr] if part)
    if any(term in text for term in ["spike", "cluster", "channel", "probe", "ephys", "ap.", "lf."]):
        return "ecephys"
    if any(term in text for term in ["wheel", "lick", "trial", "reward", "behavior"]):
        return "behavior"
    if any(term in text for term in ["camera", "video", "dlc", "pupil"]):
        return "video"
    return None


def _path_token(path: str, token: str) -> str | None:
    match = re.search(rf"(?:^|[/_]){token}-([^/_]+)", path)
    return match.group(1) if match else None


def _uuid_token(path: str) -> str | None:
    match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", path)
    return match.group(0) if match else None


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
            entry.update({"file_type": record["file_type"], "modality": record.get("modality"), "alf_object": record.get("alf_object")})
    return {"dataset_key": dataset_key, "path_prefix": prefix, "children": sorted(children.values(), key=lambda item: (item["kind"], item["path"]))}


def _dataset_key(identifier: str) -> str:
    return "IBL_" + re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
