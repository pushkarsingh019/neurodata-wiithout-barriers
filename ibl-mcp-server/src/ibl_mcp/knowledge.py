from __future__ import annotations

from dataclasses import dataclass
from typing import Any


IBL_PUBLICATIONS: list[dict[str, Any]] = [
    {
        "id": "ibl-2021-standardized-decision-making",
        "title": "Standardized and reproducible measurement of decision-making in mice",
        "year": 2021,
        "venue": "eLife",
        "topics": ["biasedChoiceWorld", "behavior", "decision-making", "training", "reproducibility"],
        "projects": ["ibl_neuropixel_brainwide_01", "ibl_behavior"],
        "url": "https://elifesciences.org/articles/63711",
        "code": ["https://github.com/int-brain-lab/ibllib", "https://github.com/int-brain-lab/paper-behavior"],
    },
    {
        "id": "ibl-2023-brain-wide-map",
        "title": "A brain-wide map of neural activity during complex behaviour",
        "year": 2023,
        "venue": "Nature",
        "topics": ["brainwide", "Neuropixels", "biasedChoiceWorld", "ephys", "spikes", "trials"],
        "projects": ["brainwide", "ibl_neuropixel_brainwide_01"],
        "url": "https://www.nature.com/articles/s41586-023-06812-z",
        "code": ["https://github.com/int-brain-lab/paper-brain-wide-map", "https://github.com/int-brain-lab/ibllib"],
    },
    {
        "id": "ibl-repeated-site-benchmark",
        "title": "Repeated-site benchmark recordings from the International Brain Laboratory",
        "year": 2022,
        "venue": "IBL public release",
        "topics": ["repeated-site", "benchmark", "Neuropixels", "QC", "reproducibility"],
        "projects": ["repeated site", "2022_Q2_IBL_et_al_RepeatedSite"],
        "url": "https://www.internationalbrainlab.com/data",
        "code": ["https://github.com/int-brain-lab/ibllib"],
    },
]


DATASET_ONTOLOGY: dict[str, dict[str, Any]] = {
    "trials": {
        "description": "Behavioral trial table split across ALF arrays.",
        "patterns": [
            "_ibl_trials.choice.npy",
            "_ibl_trials.contrastLeft.npy",
            "_ibl_trials.contrastRight.npy",
            "_ibl_trials.feedbackType.npy",
            "_ibl_trials.feedback_times.npy",
            "_ibl_trials.firstMovement_times.npy",
            "_ibl_trials.goCue_times.npy",
            "_ibl_trials.intervals.npy",
            "_ibl_trials.probabilityLeft.npy",
            "_ibl_trials.response_times.npy",
            "_ibl_trials.rewardVolume.npy",
            "_ibl_trials.stimOn_times.npy",
        ],
    },
    "wheel": {
        "description": "Wheel position, timestamps, moves, and velocity-derived behavior.",
        "patterns": ["_ibl_wheel.position.npy", "_ibl_wheel.timestamps.npy", "_ibl_wheelMoves.intervals.npy"],
    },
    "licks": {
        "description": "Lick timestamps and derived licking events.",
        "patterns": ["licks.times.npy", "_ibl_lickPiezo.times.npy"],
    },
    "video": {
        "description": "Raw and compressed behavioral camera streams.",
        "patterns": ["_iblrig_leftCamera.raw.mp4", "_iblrig_rightCamera.raw.mp4", "_iblrig_bodyCamera.raw.mp4"],
    },
    "pose": {
        "description": "DeepLabCut / pose tracking outputs for cameras.",
        "patterns": ["_ibl_leftCamera.dlc.pqt", "_ibl_rightCamera.dlc.pqt", "_ibl_bodyCamera.dlc.pqt"],
    },
    "pupil": {
        "description": "Pupil and eye tracking outputs.",
        "patterns": ["_ibl_leftCamera.features.pqt", "_ibl_rightCamera.features.pqt", "pupil"],
    },
    "spikes": {
        "description": "Spike sorting arrays.",
        "patterns": ["spikes.times.npy", "spikes.clusters.npy", "spikes.amps.npy", "spikes.depths.npy"],
    },
    "clusters": {
        "description": "Cluster metadata, QC labels, metrics, and brain region assignments.",
        "patterns": ["clusters.channels.npy", "clusters.metrics.pqt", "clusters.label.npy", "clusters.acronym.npy"],
    },
    "lfp": {
        "description": "Local field potential and ephys spectral data.",
        "patterns": ["ephysData.raw.lf", "lfp"],
    },
}


def related_publications(query: str = "", project: str = "", dataset_type: str = "") -> list[dict[str, Any]]:
    terms = _terms(" ".join([query, project, dataset_type]))
    scored: list[tuple[int, dict[str, Any]]] = []
    for paper in IBL_PUBLICATIONS:
        haystack = _terms(" ".join([paper["title"], paper["venue"], " ".join(paper["topics"]), " ".join(paper["projects"])]))
        score = len(terms & haystack) if terms else 1
        if score:
            scored.append((score, paper))
    return [paper for _, paper in sorted(scored, key=lambda item: item[0], reverse=True)]


def semantic_records() -> list[dict[str, Any]]:
    records = []
    for modality, spec in DATASET_ONTOLOGY.items():
        records.append(
            {
                "type": "dataset_modality",
                "id": modality,
                "text": f"{modality}: {spec['description']} patterns {' '.join(spec['patterns'])}",
                "payload": spec,
            }
        )
    for paper in IBL_PUBLICATIONS:
        records.append(
            {
                "type": "publication",
                "id": paper["id"],
                "text": f"{paper['title']} {' '.join(paper['topics'])} {' '.join(paper['projects'])}",
                "payload": paper,
            }
        )
    return records


def lexical_semantic_search(query: str, *, limit: int = 10) -> dict[str, Any]:
    terms = _terms(query)
    results = []
    for record in semantic_records():
        haystack = _terms(record["text"])
        score = len(terms & haystack) / max(len(terms), 1)
        if score:
            results.append({**record, "score": round(score, 4)})
    results.sort(key=lambda item: item["score"], reverse=True)
    return {
        "query": query,
        "mode": "lexical-semantic-fallback",
        "results": results[:limit],
        "note": "This is a deterministic lexical semantic scaffold. Plug in embeddings/vector storage for cross-session semantic retrieval at scale.",
    }


@dataclass(frozen=True)
class GraphEdge:
    source: str
    predicate: str
    target: str
    evidence: str


def static_graph_edges() -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for modality, spec in DATASET_ONTOLOGY.items():
        for pattern in spec["patterns"]:
            edges.append(GraphEdge(f"modality:{modality}", "expects_dataset", f"dataset_pattern:{pattern}", "IBL ALF convention"))
    for paper in IBL_PUBLICATIONS:
        for project in paper["projects"]:
            edges.append(GraphEdge(f"project:{project}", "linked_to_paper", f"paper:{paper['id']}", paper["url"]))
        for repo in paper["code"]:
            edges.append(GraphEdge(f"paper:{paper['id']}", "has_code", f"repo:{repo}", paper["url"]))
    return edges


def query_static_graph(entity_type: str | None = None, predicate: str | None = None, value: str | None = None, limit: int = 25) -> dict[str, Any]:
    edges = static_graph_edges()
    value_lower = value.lower() if value else None
    rows = []
    for edge in edges:
        if predicate and edge.predicate != predicate:
            continue
        if entity_type and not edge.source.startswith(f"{entity_type}:"):
            continue
        text = " ".join([edge.source, edge.predicate, edge.target, edge.evidence]).lower()
        if value_lower and value_lower not in text:
            continue
        rows.append(edge.__dict__)
    return {
        "edges": rows[:limit],
        "count": len(rows),
        "scope": "static IBL ontology/publication graph plus live session graph in high-level session tools",
    }


def _terms(text: str) -> set[str]:
    return {part.lower() for part in text.replace("_", " ").replace("-", " ").replace(".", " ").split() if len(part) > 2}
