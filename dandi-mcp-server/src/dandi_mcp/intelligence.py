from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+\-.]*", re.IGNORECASE)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

ONTOLOGY: dict[str, dict[str, tuple[str, ...]]] = {
    "species": {
        "mouse": ("mouse", "mice", "mus musculus"),
        "rat": ("rat", "rats", "rattus"),
        "human": ("human", "humans", "homo sapiens", "participant"),
        "macaque": ("macaque", "macaca", "non-human primate", "nonhuman primate"),
        "zebrafish": ("zebrafish", "danio rerio"),
        "drosophila": ("drosophila", "fruit fly"),
    },
    "modalities": {
        "intracellular electrophysiology": ("patch clamp", "intracellular", "whole-cell"),
        "extracellular electrophysiology": (
            "electrophysiology",
            "ephys",
            "extracellular",
            "spike sorting",
            "neuropixels",
            "lfp",
            "ecephys",
        ),
        "calcium imaging": (
            "calcium imaging",
            "two-photon",
            "2-photon",
            "ophys",
            "gcamp",
            "fluorescence",
        ),
        "optogenetics": ("optogenetic", "optogenetics", "photostimulation", "chr2", "halorhodopsin"),
        "behavior video": ("video", "videography", "pose", "deeplabcut", "sleap", "tracking"),
        "fmri": ("fmri", "bold", "functional mri"),
        "microscopy": ("microscopy", "confocal", "lightsheet", "light-sheet"),
    },
    "behaviors": {
        "decision making": ("decision", "choice", "go/no-go", "go nogo", "2afc", "two-alternative"),
        "reinforcement learning": (
            "reward",
            "reinforcement",
            "punishment",
            "conditioning",
            "operant",
        ),
        "locomotion": ("locomotion", "running", "wheel", "treadmill", "speed"),
        "licking": ("lick", "licking", "water reward", "spout"),
        "social behavior": ("social", "interaction", "aggression", "courtship"),
        "grooming": ("grooming", "self-groom", "self grooming"),
        "navigation": ("navigation", "maze", "spatial", "virtual reality", "vr"),
        "sensory stimulation": ("stimulus", "stimuli", "visual", "auditory", "odor", "somatosensory"),
    },
    "brain_regions": {
        "hippocampus": ("hippocampus", "ca1", "ca3", "dentate gyrus"),
        "visual cortex": ("visual cortex", "v1", "visp"),
        "motor cortex": ("motor cortex", "primary motor cortex", "secondary motor cortex"),
        "prefrontal cortex": ("prefrontal", "pfc", "frontal cortex"),
        "striatum": ("striatum", "caudate", "putamen", "nucleus accumbens"),
        "thalamus": ("thalamus", "thalamic"),
        "cerebellum": ("cerebellum", "cerebellar"),
        "amygdala": ("amygdala", "bLA", "central amygdala"),
    },
}


@dataclass(frozen=True)
class SemanticMatch:
    record: dict[str, Any]
    score: float
    matched_terms: list[str]
    explanation: str


def summarize_neuroscience_metadata(
    metadata: dict[str, Any],
    assets: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract agent-friendly neuroscience signals from DANDI metadata and asset listings."""
    assets_list = list(assets or [])
    text = searchable_text(metadata, assets_list)
    ontology_hits = extract_ontology_terms(text)
    nwb_summary = summarize_nwb_assets(assets_list)
    literature = extract_literature_links(metadata)
    confidence = _confidence_score(ontology_hits, nwb_summary, literature)
    return {
        "dandiset_id": _metadata_identifier(metadata),
        "name": metadata.get("name"),
        "version": metadata.get("version"),
        "species": ontology_hits["species"],
        "modalities": ontology_hits["modalities"],
        "behaviors": ontology_hits["behaviors"],
        "brain_regions": ontology_hits["brain_regions"],
        "nwb": nwb_summary,
        "literature": literature,
        "confidence": confidence,
        "provenance": {
            "metadata_fields": sorted(k for k in metadata.keys() if metadata.get(k) not in (None, "", [])),
            "asset_count_examined": len(assets_list),
            "method": "heuristic_metadata_and_path_extraction",
            "limitations": (
                "Does not download or parse NWB payloads; results are inferred from DANDI metadata "
                "and asset paths until a local NWB/Zarr inspection backend is added."
            ),
        },
    }


def semantic_rank(
    query: str,
    records: Iterable[dict[str, Any]],
    *,
    limit: int = 10,
) -> list[SemanticMatch]:
    query_tokens = _weighted_tokens(query)
    matches: list[SemanticMatch] = []
    for record in records:
        record_text = searchable_text(record)
        record_tokens = _weighted_tokens(record_text)
        score = _cosine(query_tokens, record_tokens)
        ontology_bonus, ontology_terms = _ontology_query_bonus(query, record_text)
        final_score = min(1.0, score + ontology_bonus)
        if final_score > 0:
            matched = sorted((set(query_tokens) & set(record_tokens)) | set(ontology_terms))
            matches.append(
                SemanticMatch(
                    record=record,
                    score=round(final_score, 4),
                    matched_terms=matched[:20],
                    explanation=_semantic_explanation(matched, ontology_terms),
                )
            )
    matches.sort(key=lambda item: item.score, reverse=True)
    return matches[:limit]


def extract_literature_links(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    text = searchable_text(metadata)
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for doi in DOI_RE.findall(text):
        clean = doi.rstrip(".,;")
        links[("doi", clean.lower())] = {
            "kind": "doi",
            "identifier": clean,
            "url": f"https://doi.org/{clean}",
            "confidence": 0.95,
            "source": "metadata_text",
        }
    for url in URL_RE.findall(text):
        clean_url = url.rstrip(".,;")
        host = urlparse(clean_url).netloc.lower()
        kind = _literature_url_kind(host)
        if kind:
            links[(kind, clean_url)] = {
                "kind": kind,
                "identifier": clean_url,
                "url": clean_url,
                "confidence": 0.8,
                "source": "metadata_url",
            }
    for related in _as_list(metadata.get("relatedResource")):
        if isinstance(related, dict):
            identifier = related.get("identifier") or related.get("url")
            if identifier:
                key = ("relatedResource", str(identifier))
                links[key] = {
                    "kind": str(related.get("relation") or related.get("resourceType") or "relatedResource"),
                    "identifier": identifier,
                    "url": related.get("url") or _identifier_to_url(str(identifier)),
                    "confidence": 0.9,
                    "source": "relatedResource",
                    "relation": related.get("relation"),
                }
    return sorted(links.values(), key=lambda item: (-item["confidence"], item["kind"]))


def summarize_nwb_assets(assets: Iterable[dict[str, Any]]) -> dict[str, Any]:
    paths = [str(asset.get("path") or asset.get("blob", {}).get("name") or "") for asset in assets]
    nwb_paths = [path for path in paths if path.lower().endswith(".nwb")]
    zarr_paths = [path for path in paths if ".zarr" in path.lower() or path.lower().endswith(".zarr")]
    path_text = "\n".join(paths)
    likely_subjects = sorted(set(re.findall(r"sub-[A-Za-z0-9-]+", path_text)))[:25]
    likely_sessions = sorted(set(re.findall(r"ses-[A-Za-z0-9-]+", path_text)))[:25]
    likely_tasks = sorted(set(re.findall(r"task-[A-Za-z0-9-]+", path_text)))[:25]
    return {
        "nwb_asset_count": len(nwb_paths),
        "zarr_asset_count": len(zarr_paths),
        "sample_nwb_paths": nwb_paths[:10],
        "sample_zarr_paths": zarr_paths[:10],
        "likely_subjects_from_paths": likely_subjects,
        "likely_sessions_from_paths": likely_sessions,
        "likely_tasks_from_paths": likely_tasks,
        "has_behavioral_task_hints": bool(likely_tasks),
    }


def build_knowledge_graph(
    metadata: dict[str, Any],
    assets: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary = summarize_neuroscience_metadata(metadata, assets)
    dandiset_id = summary.get("dandiset_id") or "unknown"
    dataset_node = {
        "id": f"dandiset:{dandiset_id}",
        "type": "dataset",
        "label": summary.get("name") or dandiset_id,
    }
    nodes = [dataset_node]
    edges: list[dict[str, Any]] = []
    for group, relation in [
        ("species", "HAS_SPECIES"),
        ("modalities", "USES_MODALITY"),
        ("behaviors", "STUDIES_BEHAVIOR"),
        ("brain_regions", "TARGETS_REGION"),
    ]:
        for value in summary[group]:
            node_id = f"{group}:{value}"
            nodes.append({"id": node_id, "type": group[:-1], "label": value})
            edges.append({"source": dataset_node["id"], "target": node_id, "type": relation})
    for link in summary["literature"]:
        node_id = f"paper:{link['identifier']}"
        nodes.append({"id": node_id, "type": "paper", "label": link["identifier"], "url": link.get("url")})
        edges.append({"source": dataset_node["id"], "target": node_id, "type": "CITES_OR_RELATES_TO"})
    return {
        "nodes": _dedupe_nodes(nodes),
        "edges": edges,
        "summary": {
            "dataset": dataset_node["id"],
            "node_count": len(_dedupe_nodes(nodes)),
            "edge_count": len(edges),
            "confidence": summary["confidence"],
        },
        "provenance": summary["provenance"],
    }


def query_graph(graph: dict[str, Any], query: str, *, limit: int = 20) -> dict[str, Any]:
    matches = semantic_rank(query, graph.get("nodes", []), limit=limit)
    matched_ids = {match.record.get("id") for match in matches}
    edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("source") in matched_ids or edge.get("target") in matched_ids
    ]
    return {
        "query": query,
        "nodes": [
            {
                "id": match.record.get("id"),
                "type": match.record.get("type"),
                "label": match.record.get("label"),
                "score": match.score,
                "matched_terms": match.matched_terms,
            }
            for match in matches
        ],
        "edges": edges,
    }


def searchable_text(*items: Any) -> str:
    parts: list[str] = []
    _collect_text(items, parts)
    return "\n".join(parts)


def extract_ontology_terms(text: str) -> dict[str, list[str]]:
    lower = text.lower()
    hits: dict[str, list[str]] = {}
    for group, concepts in ONTOLOGY.items():
        group_hits = []
        for concept, synonyms in concepts.items():
            if any(_contains_phrase(lower, synonym) for synonym in synonyms):
                group_hits.append(concept)
        hits[group] = sorted(group_hits)
    return hits


def _collect_text(value: Any, parts: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            parts.append(value)
        return
    if isinstance(value, (int, float, bool)):
        parts.append(str(value))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            parts.append(str(key))
            _collect_text(item, parts)
        return
    if isinstance(value, Iterable):
        for item in value:
            _collect_text(item, parts)


def _weighted_tokens(text: str) -> Counter[str]:
    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    return Counter(token for token in tokens if token not in STOPWORDS and len(token) > 1)


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _ontology_query_bonus(query: str, record_text: str) -> tuple[float, list[str]]:
    query_hits = extract_ontology_terms(query)
    record_hits = extract_ontology_terms(record_text)
    overlap: list[str] = []
    for group, values in query_hits.items():
        overlap.extend(sorted(set(values) & set(record_hits[group])))
    return min(0.35, 0.07 * len(overlap)), overlap


def _semantic_explanation(matched: list[str], ontology_terms: list[str]) -> str:
    if ontology_terms:
        return "Matched ontology concepts plus lexical query terms."
    if matched:
        return "Matched lexical query terms in DANDI metadata."
    return "Low-confidence fallback match."


def _contains_phrase(text: str, phrase: str) -> bool:
    if " " in phrase or "-" in phrase or "+" in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _confidence_score(
    ontology_hits: dict[str, list[str]],
    nwb_summary: dict[str, Any],
    literature: list[dict[str, Any]],
) -> dict[str, Any]:
    signal_count = sum(bool(values) for values in ontology_hits.values())
    signal_count += int(nwb_summary["nwb_asset_count"] > 0)
    signal_count += int(bool(literature))
    score = min(1.0, signal_count / 6)
    if score >= 0.67:
        label = "high"
    elif score >= 0.34:
        label = "medium"
    else:
        label = "low"
    return {"score": round(score, 2), "label": label}


def _metadata_identifier(metadata: dict[str, Any]) -> str | None:
    identifier = metadata.get("identifier") or metadata.get("id")
    if isinstance(identifier, str):
        return identifier.removeprefix("DANDI:")
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _literature_url_kind(host: str) -> str | None:
    if "doi.org" in host:
        return "doi_url"
    if "pubmed" in host or "ncbi.nlm.nih.gov" in host:
        return "pubmed"
    if "semanticscholar.org" in host:
        return "semantic_scholar"
    if "github.com" in host:
        return "github"
    if "protocols.io" in host:
        return "protocols_io"
    if "biorxiv.org" in host or "medrxiv.org" in host:
        return "preprint"
    return None


def _identifier_to_url(identifier: str) -> str | None:
    if DOI_RE.search(identifier):
        return f"https://doi.org/{DOI_RE.search(identifier).group(0)}"
    if identifier.startswith("http://") or identifier.startswith("https://"):
        return identifier
    return None


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for node in nodes:
        seen.setdefault(str(node["id"]), node)
    return list(seen.values())
