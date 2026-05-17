from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict
from typing import Any

from openneuro_mcp.models import DatasetFile, Modality, SubjectSummary, TaskStructure
from openneuro_mcp.ontology import infer_modalities, infer_paradigms, infer_species

BIDS_ENTITY_RE = re.compile(r"(?P<key>sub|ses|task|acq|run|mod|space|desc|suffix)-(?P<value>[^_/]+)")


def classify_file(path: str, *, file_id: str | None = None, size: int | None = None) -> DatasetFile:
    filename = path.rstrip("/").split("/")[-1]
    modality = infer_modalities([], [path])[0]
    return DatasetFile(
        id=file_id,
        path=path,
        filename=filename,
        size=size,
        directory=path.endswith("/"),
        modality=modality,
        bids_entity=parse_bids_entities(path),
    )


def parse_bids_entities(path: str) -> dict[str, str]:
    entities: dict[str, str] = {}
    for match in BIDS_ENTITY_RE.finditer(path):
        entities[match.group("key")] = match.group("value")
    suffix = path.rsplit("/", 1)[-1].split(".")[0].split("_")[-1]
    if suffix and "-" not in suffix:
        entities.setdefault("suffix", suffix)
    return entities


def parse_dataset_description(content: str | dict[str, Any] | None) -> dict[str, Any]:
    if content is None:
        return {}
    if isinstance(content, dict):
        return content
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {"_parse_error": "dataset_description.json is not valid JSON"}
    return parsed if isinstance(parsed, dict) else {"_parse_error": "dataset_description.json root is not an object"}


def parse_participants_tsv(content: str | None) -> SubjectSummary:
    if not content:
        return SubjectSummary()
    rows = _read_tsv(content)
    columns = list(rows[0].keys()) if rows else []
    categorical: dict[str, list[str]] = {}
    for column in columns:
        values = sorted({row[column] for row in rows if row.get(column)})
        if 0 < len(values) <= 25:
            categorical[column] = values
    species, confidence = infer_species([content, " ".join(columns)])
    return SubjectSummary(
        participant_count=len(rows),
        species=species,
        species_confidence=confidence,
        columns=columns,
        categorical_fields=categorical,
    )


def parse_events_tsv(task_name: str, content: str | None) -> TaskStructure:
    if not content:
        return TaskStructure(task_name=task_name)
    rows = _read_tsv(content)
    columns = list(rows[0].keys()) if rows else []
    trial_values = sorted({row["trial_type"] for row in rows if row.get("trial_type")})[:100]
    onsets = _float_values(row.get("onset") for row in rows)
    durations = _float_values(row.get("duration") for row in rows)
    text = [task_name, " ".join(columns), " ".join(trial_values)]
    return TaskStructure(
        task_name=task_name,
        event_columns=columns,
        trial_type_values=trial_values,
        onset_range_seconds=_minmax(onsets),
        duration_range_seconds=_minmax(durations),
        inferred_paradigms=infer_paradigms(text),
    )


def summarize_bids_files(files: list[DatasetFile]) -> dict[str, Any]:
    modalities = Counter(file.modality.value for file in files if file.modality != Modality.UNKNOWN)
    tasks = sorted({file.bids_entity["task"] for file in files if "task" in file.bids_entity})
    suffixes = Counter(file.bids_entity.get("suffix", "unknown") for file in files)
    sessions_by_subject: dict[str, set[str]] = defaultdict(set)
    for file in files:
        subject = file.bids_entity.get("sub")
        session = file.bids_entity.get("ses")
        if subject and session:
            sessions_by_subject[subject].add(session)
    return {
        "file_count": len(files),
        "modalities": dict(modalities),
        "tasks": tasks,
        "suffixes": dict(suffixes.most_common(30)),
        "subjects": sorted({file.bids_entity["sub"] for file in files if "sub" in file.bids_entity}),
        "sessions_by_subject": {key: sorted(value) for key, value in sessions_by_subject.items()},
        "has_derivatives": any(file.path.startswith("derivatives/") for file in files),
    }


def metadata_quality_score(description: dict[str, Any], files: list[DatasetFile]) -> dict[str, Any]:
    required = ["Name", "BIDSVersion", "DatasetType", "Authors"]
    missing = [field for field in required if not description.get(field)]
    has_participants = any(file.filename == "participants.tsv" for file in files)
    has_events = any(file.filename.endswith("_events.tsv") for file in files)
    score = 1.0
    score -= 0.12 * len(missing)
    score -= 0.08 if not has_participants else 0.0
    score -= 0.05 if not has_events else 0.0
    score = max(0.0, round(score, 3))
    return {
        "score": score,
        "missing_required_description_fields": missing,
        "has_participants_tsv": has_participants,
        "has_events_tsv": has_events,
        "bids_validation_hook": "Run bids-validator in the indexing worker for full validation.",
    }


def _read_tsv(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content), delimiter="\t"))


def _float_values(values: Any) -> list[float]:
    parsed: list[float] = []
    for value in values:
        try:
            parsed.append(float(value))
        except (TypeError, ValueError):
            continue
    return parsed


def _minmax(values: list[float]) -> tuple[float, float] | None:
    return (min(values), max(values)) if values else None
