from __future__ import annotations

from collections import Counter
from io import BytesIO
from statistics import median
from typing import Any

import numpy as np

from ibl_mcp.client import IBLClient
from ibl_mcp.knowledge import DATASET_ONTOLOGY, lexical_semantic_search, query_static_graph, related_publications
from ibl_mcp.schemas import Provenance, QCWarning, ToolEnvelope


TRIAL_DATASETS = {
    "choice": "_ibl_trials.choice.npy",
    "contrast_left": "_ibl_trials.contrastLeft.npy",
    "contrast_right": "_ibl_trials.contrastRight.npy",
    "feedback_type": "_ibl_trials.feedbackType.npy",
    "feedback_times": "_ibl_trials.feedback_times.npy",
    "first_movement_times": "_ibl_trials.firstMovement_times.npy",
    "go_cue_times": "_ibl_trials.goCue_times.npy",
    "intervals": "_ibl_trials.intervals.npy",
    "probability_left": "_ibl_trials.probabilityLeft.npy",
    "response_times": "_ibl_trials.response_times.npy",
    "reward_volume": "_ibl_trials.rewardVolume.npy",
    "stim_on_times": "_ibl_trials.stimOn_times.npy",
}

WHEEL_DATASETS = {
    "position": "_ibl_wheel.position.npy",
    "timestamps": "_ibl_wheel.timestamps.npy",
    "moves_intervals": "_ibl_wheelMoves.intervals.npy",
}

LICK_DATASETS = {
    "times": "licks.times.npy",
    "piezo_times": "_ibl_lickPiezo.times.npy",
}

SPIKE_DATASETS = {
    "times": "spikes.times.npy",
    "clusters": "spikes.clusters.npy",
    "amps": "spikes.amps.npy",
    "depths": "spikes.depths.npy",
}

CLUSTER_DATASETS = {
    "label": "clusters.label.npy",
    "channels": "clusters.channels.npy",
    "acronym": "clusters.acronym.npy",
    "metrics": "clusters.metrics.pqt",
}


class IBLDomainService:
    """AI-native neuroscience layer on top of the Alyx REST client."""

    def __init__(self, client: IBLClient) -> None:
        self.client = client

    def get_session_metadata(self, session_id: str) -> dict[str, Any]:
        session = self.client.get_session(session_id)
        datasets = self.client.list_datasets(session=session_id, exists=True, page_size=500)
        insertions = self.client.list_insertions(session=session_id)
        dataset_rows = _rows(datasets)
        insertion_rows = _rows(insertions)
        modalities = infer_modalities(dataset_rows)
        qc = session_qc_warnings(session, dataset_rows, insertion_rows)
        subject = self._subject_from_session(session)
        data = {
            "session": session,
            "subject": subject,
            "datasets": summarize_dataset_inventory(dataset_rows),
            "modalities": modalities,
            "probe_insertions": insertion_rows,
            "recording_modality": infer_recording_modality(modalities, insertion_rows),
            "behavioral_modalities": sorted(mod for mod in modalities if mod in {"trials", "wheel", "licks", "video", "pose", "pupil"}),
            "knowledge_graph_edges": session_graph_edges(session, dataset_rows, insertion_rows),
        }
        self.client.storage.upsert_record("session", session_id, data, source="OpenAlyx sessions/datasets/insertions")
        return self._envelope(data, endpoint="sessions/datasets/insertions", session_id=session_id, qc=qc).model_dump_plain()

    def get_session_datasets(self, session_id: str, modality: str | None = None) -> dict[str, Any]:
        datasets = _rows(self.client.list_datasets(session=session_id, exists=True, page_size=1000))
        if modality:
            patterns = DATASET_ONTOLOGY.get(modality, {}).get("patterns", [])
            datasets = [row for row in datasets if dataset_matches_any(row, patterns)]
        data = {
            "session_id": session_id,
            "modality_filter": modality,
            "inventory": summarize_dataset_inventory(datasets),
            "datasets": datasets,
        }
        self.client.storage.upsert_record("session_datasets", session_id, data, source="OpenAlyx datasets")
        warnings = availability_warnings(datasets, modality=modality)
        return self._envelope(data, endpoint="datasets", session_id=session_id, qc=warnings).model_dump_plain()

    def get_trials(self, session_id: str, limit: int = 200, include_arrays: bool = False) -> dict[str, Any]:
        arrays, warnings, dataset_ids = self._load_named_arrays(session_id, TRIAL_DATASETS)
        rows = trial_rows(arrays, limit=limit)
        data = {
            "session_id": session_id,
            "n_trials_available": array_length(arrays),
            "rows_returned": len(rows),
            "trials": rows,
            "arrays": {key: value.tolist() for key, value in arrays.items()} if include_arrays else None,
        }
        warnings.extend(required_missing_warnings(TRIAL_DATASETS, arrays, "trials"))
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=dataset_ids, dataset_names=list(TRIAL_DATASETS.values()), qc=warnings).model_dump_plain()

    def get_behavior_summary(self, session_id: str) -> dict[str, Any]:
        arrays, warnings, dataset_ids = self._load_named_arrays(session_id, TRIAL_DATASETS)
        summary = behavior_summary_from_trials(arrays)
        warnings.extend(required_missing_warnings(TRIAL_DATASETS, arrays, "behavior_summary"))
        warnings.extend(behavior_qc_warnings(summary))
        return self._envelope(summary, endpoint="datasets/files", session_id=session_id, dataset_ids=dataset_ids, dataset_names=list(TRIAL_DATASETS.values()), qc=warnings).model_dump_plain()

    def get_psychometric_summary(self, session_id: str) -> dict[str, Any]:
        arrays, warnings, dataset_ids = self._load_named_arrays(session_id, TRIAL_DATASETS)
        data = psychometric_summary_from_trials(arrays)
        warnings.extend(required_missing_warnings({"choice": TRIAL_DATASETS["choice"], "contrast_left": TRIAL_DATASETS["contrast_left"], "contrast_right": TRIAL_DATASETS["contrast_right"]}, arrays, "psychometric"))
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=dataset_ids, dataset_names=list(TRIAL_DATASETS.values()), qc=warnings).model_dump_plain()

    def get_wheel_data(self, session_id: str, limit: int = 1000, include_arrays: bool = False) -> dict[str, Any]:
        arrays, warnings, dataset_ids = self._load_named_arrays(session_id, WHEEL_DATASETS)
        data = {
            "session_id": session_id,
            "samples_available": array_length(arrays),
            "samples_returned": min(array_length(arrays), limit),
            "summary": wheel_summary(arrays),
            "arrays": limited_arrays(arrays, limit) if include_arrays else None,
        }
        warnings.extend(required_missing_warnings({"position": WHEEL_DATASETS["position"], "timestamps": WHEEL_DATASETS["timestamps"]}, arrays, "wheel"))
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=dataset_ids, dataset_names=list(WHEEL_DATASETS.values()), qc=warnings).model_dump_plain()

    def get_lick_data(self, session_id: str, limit: int = 1000) -> dict[str, Any]:
        arrays, warnings, dataset_ids = self._load_named_arrays(session_id, LICK_DATASETS, require_all=False)
        key = "times" if "times" in arrays else "piezo_times"
        times = arrays.get(key, np.array([]))
        data = {
            "session_id": session_id,
            "source": key if key in arrays else None,
            "n_licks": int(len(times)),
            "first_lick_time": _safe_float(times[0]) if len(times) else None,
            "last_lick_time": _safe_float(times[-1]) if len(times) else None,
            "lick_times": times[:limit].tolist(),
        }
        if not len(times):
            warnings.append(QCWarning(risk="warning", code="licks_missing", message="No lick timestamp dataset was found.", affected=list(LICK_DATASETS.values())))
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=dataset_ids, dataset_names=list(LICK_DATASETS.values()), qc=warnings).model_dump_plain()

    def get_video_metadata(self, session_id: str) -> dict[str, Any]:
        datasets = _rows(self.client.list_datasets(session=session_id, exists=True, page_size=1000))
        video = [row for row in datasets if dataset_matches_any(row, DATASET_ONTOLOGY["video"]["patterns"])]
        pose = [row for row in datasets if dataset_matches_any(row, DATASET_ONTOLOGY["pose"]["patterns"])]
        pupil = [row for row in datasets if dataset_matches_any(row, DATASET_ONTOLOGY["pupil"]["patterns"])]
        warnings = availability_warnings(video, modality="video")
        data = {"session_id": session_id, "video_datasets": video, "pose_datasets": pose, "pupil_datasets": pupil}
        return self._envelope(data, endpoint="datasets", session_id=session_id, qc=warnings).model_dump_plain()

    def get_spike_metadata(self, session_id: str, probe: str | None = None) -> dict[str, Any]:
        datasets = _rows(self.client.list_datasets(session=session_id, exists=True, page_size=1000))
        spike_rows = [row for row in datasets if dataset_matches_any(row, DATASET_ONTOLOGY["spikes"]["patterns"] + DATASET_ONTOLOGY["clusters"]["patterns"])]
        if probe:
            spike_rows = [row for row in spike_rows if probe in str(row.get("collection", ""))]
        insertions = _rows(self.client.list_insertions(session=session_id, name=probe) if probe else self.client.list_insertions(session=session_id))
        data = {
            "session_id": session_id,
            "probe": probe,
            "insertions": insertions,
            "spike_and_cluster_datasets": spike_rows,
            "inventory": summarize_dataset_inventory(spike_rows),
        }
        warnings = availability_warnings(spike_rows, modality="spikes")
        return self._envelope(data, endpoint="datasets/insertions", session_id=session_id, qc=warnings).model_dump_plain()

    def get_cluster_qc(self, session_id: str, probe: str | None = None) -> dict[str, Any]:
        arrays, warnings, dataset_ids = self._load_named_arrays(session_id, {k: v for k, v in CLUSTER_DATASETS.items() if v.endswith(".npy")}, collection_contains=probe, require_all=False)
        labels = arrays.get("label")
        acronyms = arrays.get("acronym")
        data = {
            "session_id": session_id,
            "probe": probe,
            "n_clusters": int(len(labels)) if labels is not None else None,
            "label_counts": Counter(labels.astype(str)).most_common() if labels is not None else [],
            "brain_region_counts": Counter(acronyms.astype(str)).most_common(25) if acronyms is not None else [],
            "good_cluster_count": count_good_clusters(labels),
        }
        if labels is None:
            warnings.append(QCWarning(risk="warning", code="cluster_labels_missing", message="clusters.label.npy was not available; good-unit filtering is incomplete.", affected=["clusters.label.npy"]))
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=dataset_ids, dataset_names=list(CLUSTER_DATASETS.values()), qc=warnings).model_dump_plain()

    def align_behavior_to_events(
        self,
        session_id: str,
        signal: str,
        event: str = "stim_on_times",
        window: tuple[float, float] = (-0.5, 1.0),
        max_events: int = 100,
    ) -> dict[str, Any]:
        if signal not in {"wheel_position", "licks"}:
            warning = QCWarning(risk="warning", code="unsupported_signal", message="Only wheel_position and licks are currently implemented for behavior alignment.", affected=[signal])
            return self._envelope({"session_id": session_id, "aligned": []}, endpoint="datasets/files", session_id=session_id, qc=[warning]).model_dump_plain()
        trial_arrays, warnings, trial_ids = self._load_named_arrays(session_id, {event: TRIAL_DATASETS.get(event, event)})
        events = trial_arrays.get(event, np.array([]))[:max_events]
        if signal == "wheel_position":
            signal_arrays, signal_warnings, signal_ids = self._load_named_arrays(session_id, {"values": WHEEL_DATASETS["position"], "times": WHEEL_DATASETS["timestamps"]})
        else:
            signal_arrays, signal_warnings, signal_ids = self._load_named_arrays(session_id, {"times": LICK_DATASETS["times"]}, require_all=False)
            signal_arrays["values"] = signal_arrays.get("times", np.array([]))
        warnings.extend(signal_warnings)
        aligned = align_timeseries(events, signal_arrays.get("times", np.array([])), signal_arrays.get("values", np.array([])), window)
        data = {"session_id": session_id, "signal": signal, "event": event, "window": window, "n_events": int(len(events)), "aligned": aligned}
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=trial_ids + signal_ids, qc=warnings).model_dump_plain()

    def align_spikes_to_events(
        self,
        session_id: str,
        event: str = "stim_on_times",
        window: tuple[float, float] = (-0.2, 0.5),
        probe: str | None = None,
        max_events: int = 100,
    ) -> dict[str, Any]:
        trial_arrays, warnings, trial_ids = self._load_named_arrays(session_id, {event: TRIAL_DATASETS.get(event, event)})
        spike_arrays, spike_warnings, spike_ids = self._load_named_arrays(session_id, SPIKE_DATASETS, collection_contains=probe, require_all=False)
        warnings.extend(spike_warnings)
        events = trial_arrays.get(event, np.array([]))[:max_events]
        spike_times = spike_arrays.get("times", np.array([]))
        spike_clusters = spike_arrays.get("clusters")
        data = spike_count_alignment(events, spike_times, spike_clusters, window)
        data.update({"session_id": session_id, "probe": probe, "event": event, "window": window})
        if len(spike_times) == 0:
            warnings.append(QCWarning(risk="warning", code="spikes_missing", message="No spike times were available for alignment.", affected=["spikes.times.npy"]))
        return self._envelope(data, endpoint="datasets/files", session_id=session_id, dataset_ids=trial_ids + spike_ids, qc=warnings).model_dump_plain()

    def get_related_papers(self, query: str = "", project: str = "", dataset_type: str = "") -> dict[str, Any]:
        data = {"papers": related_publications(query=query, project=project, dataset_type=dataset_type)}
        self.client.storage.upsert_record(
            "papers",
            f"{query}:{project}:{dataset_type}",
            data,
            source="IBL static publication registry",
        )
        return self._envelope(data, endpoint="static_publication_registry").model_dump_plain()

    def get_associated_code(self, query: str = "", project: str = "") -> dict[str, Any]:
        papers = related_publications(query=query, project=project)
        repos = sorted({repo for paper in papers for repo in paper.get("code", [])})
        data = {"repositories": repos, "papers": papers}
        return self._envelope(data, endpoint="static_publication_registry").model_dump_plain()

    def semantic_search(self, query: str, limit: int = 10) -> dict[str, Any]:
        data = lexical_semantic_search(query, limit=limit)
        self.client.storage.upsert_record("semantic_search", query, data, source="IBL lexical semantic index")
        return self._envelope(data, endpoint="local_semantic_index").model_dump_plain()

    def query_knowledge_graph(self, entity_type: str | None = None, predicate: str | None = None, value: str | None = None, limit: int = 25) -> dict[str, Any]:
        data = query_static_graph(entity_type=entity_type, predicate=predicate, value=value, limit=limit)
        self.client.storage.replace_graph(
            "ibl:static",
            data.get("nodes", []),
            data.get("edges", []),
        )
        return self._envelope(data, endpoint="local_knowledge_graph").model_dump_plain()

    def _subject_from_session(self, session: dict[str, Any]) -> Any:
        subject = session.get("subject")
        if isinstance(subject, dict):
            return subject
        if isinstance(subject, str):
            try:
                rows = _rows(self.client.list_subjects(nickname=subject))
                return rows[0] if rows else {"nickname": subject}
            except Exception:
                return {"nickname": subject}
        return None

    def _load_named_arrays(
        self,
        session_id: str,
        names: dict[str, str],
        *,
        collection_contains: str | None = None,
        require_all: bool = True,
    ) -> tuple[dict[str, np.ndarray], list[QCWarning], list[str]]:
        datasets = _rows(self.client.list_datasets(session=session_id, exists=True, page_size=1000))
        arrays: dict[str, np.ndarray] = {}
        warnings: list[QCWarning] = []
        dataset_ids: list[str] = []
        for key, pattern in names.items():
            row = find_dataset(datasets, pattern, collection_contains=collection_contains)
            if not row:
                if require_all:
                    warnings.append(QCWarning(risk="warning", code="dataset_missing", message=f"Missing expected dataset {pattern}.", affected=[pattern]))
                continue
            dataset_id = record_id(row)
            if dataset_id:
                dataset_ids.append(dataset_id)
            urls = self.client.get_dataset_download_urls(dataset_id).get("download_urls", []) if dataset_id else []
            if not urls:
                warnings.append(QCWarning(risk="warning", code="download_url_missing", message=f"No download URL found for {pattern}.", affected=[dataset_id or pattern]))
                continue
            try:
                payload, _ = self.client.get_url_bytes(urls[0])
                arrays[key] = np.load(BytesIO(payload), allow_pickle=False)
            except Exception as exc:
                warnings.append(QCWarning(risk="warning", code="array_load_failed", message=f"Could not load {pattern}: {exc}", affected=[dataset_id or pattern]))
        return arrays, warnings, dataset_ids

    def _envelope(
        self,
        data: Any,
        *,
        endpoint: str | None = None,
        session_id: str | None = None,
        dataset_ids: list[str] | None = None,
        dataset_names: list[str] | None = None,
        qc: list[QCWarning] | None = None,
    ) -> ToolEnvelope:
        warnings = qc or []
        return ToolEnvelope(
            ok=not any(w.risk == "critical" for w in warnings),
            data=data,
            qc=warnings,
            provenance=Provenance(
                alyx_base_url=self.client.config.alyx_base_url,
                endpoint=endpoint,
                session_id=session_id,
                dataset_ids=dataset_ids or [],
                dataset_names=dataset_names or [],
            ),
            next_actions=default_next_actions(data),
        )


def _rows(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    results = payload.get("results", payload)
    if isinstance(results, list):
        return [row for row in results if isinstance(row, dict)]
    if isinstance(results, dict):
        return [results]
    return []


def dataset_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("dataset_type") or row.get("file_records", "") or "")


def record_id(row: dict[str, Any]) -> str:
    value = row.get("id")
    if value:
        return str(value)
    url = str(row.get("url", "")).rstrip("/")
    if url:
        return url.rsplit("/", 1)[-1]
    return ""


def dataset_matches_any(row: dict[str, Any], patterns: list[str]) -> bool:
    text = " ".join(str(row.get(key, "")) for key in ["name", "dataset_type", "collection", "rel_path", "file_records"]).lower()
    return any(pattern.lower() in text for pattern in patterns)


def find_dataset(datasets: list[dict[str, Any]], pattern: str, *, collection_contains: str | None = None) -> dict[str, Any] | None:
    for row in datasets:
        if collection_contains and collection_contains not in str(row.get("collection", "")):
            continue
        if dataset_matches_any(row, [pattern]):
            return row
    return None


def infer_modalities(datasets: list[dict[str, Any]]) -> list[str]:
    modalities = []
    for modality, spec in DATASET_ONTOLOGY.items():
        if any(dataset_matches_any(row, spec["patterns"]) for row in datasets):
            modalities.append(modality)
    return sorted(set(modalities))


def infer_recording_modality(modalities: list[str], insertions: list[dict[str, Any]]) -> list[str]:
    recording = []
    if "spikes" in modalities or "clusters" in modalities or insertions:
        recording.append("Neuropixels electrophysiology")
    if "lfp" in modalities:
        recording.append("LFP")
    if "video" in modalities or "pose" in modalities or "pupil" in modalities:
        recording.append("behavioral video")
    if "trials" in modalities:
        recording.append("behavior")
    return recording


def summarize_dataset_inventory(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    by_collection = Counter(str(row.get("collection", "") or "root") for row in datasets)
    by_modality = {modality: 0 for modality in DATASET_ONTOLOGY}
    for row in datasets:
        for modality, spec in DATASET_ONTOLOGY.items():
            if dataset_matches_any(row, spec["patterns"]):
                by_modality[modality] += 1
    return {
        "count": len(datasets),
        "collections": dict(by_collection.most_common()),
        "modalities": {key: value for key, value in by_modality.items() if value},
        "sample_dataset_names": [dataset_name(row) for row in datasets[:25]],
    }


def session_qc_warnings(session: dict[str, Any], datasets: list[dict[str, Any]], insertions: list[dict[str, Any]]) -> list[QCWarning]:
    warnings: list[QCWarning] = []
    qc = str(session.get("qc", session.get("extended_qc", "unknown")))
    if qc and qc.upper() in {"CRITICAL", "ERROR", "FAIL"}:
        warnings.append(QCWarning(risk="critical", code="session_qc_bad", message=f"Session QC is {qc}.", affected=[str(session.get("id", ""))]))
    if not datasets:
        warnings.append(QCWarning(risk="warning", code="no_datasets", message="No existing datasets were returned for this session."))
    if not any(dataset_matches_any(row, DATASET_ONTOLOGY["trials"]["patterns"]) for row in datasets):
        warnings.append(QCWarning(risk="warning", code="trials_missing", message="No trial datasets detected; behavioral summaries may be impossible."))
    if insertions and not any(dataset_matches_any(row, DATASET_ONTOLOGY["spikes"]["patterns"]) for row in datasets):
        warnings.append(QCWarning(risk="warning", code="spikes_not_detected", message="Probe insertions exist but spike datasets were not detected in the page."))
    return warnings


def availability_warnings(datasets: list[dict[str, Any]], modality: str | None = None) -> list[QCWarning]:
    if modality and not datasets:
        return [QCWarning(risk="warning", code="modality_missing", message=f"No datasets matched modality {modality}.", affected=[modality])]
    return []


def required_missing_warnings(expected: dict[str, str], arrays: dict[str, np.ndarray], context: str) -> list[QCWarning]:
    return [
        QCWarning(risk="warning", code=f"{context}_array_missing", message=f"Missing array {name}; derived output is partial.", affected=[name])
        for key, name in expected.items()
        if key not in arrays
    ]


def behavior_qc_warnings(summary: dict[str, Any]) -> list[QCWarning]:
    warnings: list[QCWarning] = []
    if summary.get("n_trials", 0) < 50:
        warnings.append(QCWarning(risk="warning", code="few_trials", message="Fewer than 50 trials; behavioral metrics are unstable."))
    perf = summary.get("performance_correct")
    if perf is not None and perf < 0.6:
        warnings.append(QCWarning(risk="warning", code="low_performance", message=f"Performance is low ({perf:.3f}); interpret behavior carefully."))
    bias = summary.get("choice_side_bias_abs")
    if bias is not None and bias > 0.3:
        warnings.append(QCWarning(risk="warning", code="strong_side_bias", message=f"Strong choice side bias detected ({bias:.3f})."))
    return warnings


def trial_rows(arrays: dict[str, np.ndarray], *, limit: int) -> list[dict[str, Any]]:
    n = min(array_length(arrays), limit)
    rows = []
    for i in range(n):
        rows.append({key: numpy_value(value[i]) for key, value in arrays.items() if len(value) > i and value.ndim <= 2})
    return rows


def behavior_summary_from_trials(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    n = array_length(arrays)
    choice = arrays.get("choice", np.array([]))
    feedback = arrays.get("feedback_type", np.array([]))
    response = arrays.get("response_times")
    stim = arrays.get("stim_on_times")
    first_move = arrays.get("first_movement_times")
    reaction = None
    if first_move is not None and stim is not None and len(first_move) and len(stim):
        reaction = first_move[: min(len(first_move), len(stim))] - stim[: min(len(first_move), len(stim))]
    return {
        "n_trials": int(n),
        "performance_correct": float(np.mean(feedback == 1)) if len(feedback) else None,
        "n_correct": int(np.sum(feedback == 1)) if len(feedback) else None,
        "n_error": int(np.sum(feedback == -1)) if len(feedback) else None,
        "fraction_left_choices": float(np.mean(choice == -1)) if len(choice) else None,
        "fraction_right_choices": float(np.mean(choice == 1)) if len(choice) else None,
        "choice_side_bias_abs": float(abs(np.mean(choice == 1) - 0.5)) if len(choice) else None,
        "median_response_time": safe_median(response),
        "median_reaction_time": safe_median(reaction),
        "probability_left_values": sorted({float(x) for x in arrays.get("probability_left", np.array([])) if np.isfinite(x)}),
    }


def psychometric_summary_from_trials(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    choice = arrays.get("choice")
    left = arrays.get("contrast_left")
    right = arrays.get("contrast_right")
    if choice is None or left is None or right is None:
        return {"available": False, "curve": []}
    n = min(len(choice), len(left), len(right))
    signed = np.nan_to_num(right[:n], nan=0.0) - np.nan_to_num(left[:n], nan=0.0)
    curve = []
    for contrast in sorted(set(float(x) for x in signed)):
        mask = signed == contrast
        curve.append(
            {
                "signed_contrast": contrast,
                "n_trials": int(np.sum(mask)),
                "p_right": float(np.mean(choice[:n][mask] == 1)),
            }
        )
    return {"available": True, "curve": curve}


def wheel_summary(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    position = arrays.get("position", np.array([]))
    timestamps = arrays.get("timestamps", np.array([]))
    if len(position) < 2 or len(timestamps) < 2:
        return {"available": False}
    n = min(len(position), len(timestamps))
    dt = np.diff(timestamps[:n])
    dp = np.diff(position[:n])
    velocity = np.divide(dp, dt, out=np.zeros_like(dp, dtype=float), where=dt != 0)
    return {
        "available": True,
        "n_samples": int(n),
        "duration": float(timestamps[n - 1] - timestamps[0]),
        "median_abs_velocity": safe_median(np.abs(velocity)),
        "max_abs_velocity": float(np.nanmax(np.abs(velocity))) if len(velocity) else None,
    }


def align_timeseries(events: np.ndarray, times: np.ndarray, values: np.ndarray, window: tuple[float, float]) -> list[dict[str, Any]]:
    aligned = []
    for idx, event_time in enumerate(events):
        mask = (times >= event_time + window[0]) & (times <= event_time + window[1])
        aligned.append(
            {
                "event_index": idx,
                "event_time": _safe_float(event_time),
                "n_samples": int(np.sum(mask)),
                "relative_times": (times[mask] - event_time).tolist(),
                "values": values[mask].tolist(),
            }
        )
    return aligned


def spike_count_alignment(events: np.ndarray, spike_times: np.ndarray, spike_clusters: np.ndarray | None, window: tuple[float, float]) -> dict[str, Any]:
    counts = []
    for idx, event_time in enumerate(events):
        mask = (spike_times >= event_time + window[0]) & (spike_times <= event_time + window[1])
        row = {"event_index": idx, "event_time": _safe_float(event_time), "total_spikes": int(np.sum(mask))}
        if spike_clusters is not None and len(spike_clusters) == len(spike_times):
            row["clusters"] = dict(Counter(spike_clusters[mask].astype(str)))
        counts.append(row)
    return {"n_events": int(len(events)), "aligned_counts": counts}


def count_good_clusters(labels: np.ndarray | None) -> int | None:
    if labels is None:
        return None
    text = labels.astype(str)
    return int(np.sum((text == "1") | (np.char.lower(text) == "good")))


def session_graph_edges(session: dict[str, Any], datasets: list[dict[str, Any]], insertions: list[dict[str, Any]]) -> list[dict[str, str]]:
    session_id = str(session.get("id", "session"))
    edges = []
    for key in ["subject", "lab", "task_protocol"]:
        if session.get(key):
            edges.append({"source": f"session:{session_id}", "predicate": f"has_{key}", "target": str(session[key])})
    for row in datasets[:200]:
        dataset_id = record_id(row)
        if dataset_id:
            edges.append({"source": f"session:{session_id}", "predicate": "has_dataset", "target": f"dataset:{dataset_id}"})
    for row in insertions:
        if row.get("id"):
            edges.append({"source": f"session:{session_id}", "predicate": "has_probe_insertion", "target": f"insertion:{row['id']}"})
    return edges


def array_length(arrays: dict[str, np.ndarray]) -> int:
    lengths = [len(value) for value in arrays.values() if hasattr(value, "__len__")]
    return min(lengths) if lengths else 0


def limited_arrays(arrays: dict[str, np.ndarray], limit: int) -> dict[str, Any]:
    return {key: value[:limit].tolist() for key, value in arrays.items()}


def safe_median(values: Any) -> float | None:
    if values is None:
        return None
    clean = [float(x) for x in np.asarray(values).flatten() if np.isfinite(x)]
    return float(median(clean)) if clean else None


def numpy_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def default_next_actions(data: Any) -> list[str]:
    if isinstance(data, dict) and data.get("session_id"):
        return [
            "Inspect QC warnings before analysis.",
            "Call get_session_datasets for exact dataset availability.",
            "Use get_related_papers or get_associated_code to connect results to IBL methods.",
        ]
    return []
