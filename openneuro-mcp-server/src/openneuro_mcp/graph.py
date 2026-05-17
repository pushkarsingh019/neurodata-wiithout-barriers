from __future__ import annotations

from typing import Any

import networkx as nx

from openneuro_mcp.models import DatasetMetadata


class NeuroscienceKnowledgeGraph:
    """Internal graph connecting datasets, papers, authors, paradigms, modalities, and species."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    def ingest_dataset(self, dataset: DatasetMetadata) -> None:
        dataset_node = f"dataset:{dataset.id}"
        self.graph.add_node(dataset_node, type="dataset", label=dataset.name or dataset.id, **dataset.model_dump())
        for modality in dataset.modalities:
            node = f"modality:{modality.value}"
            self.graph.add_node(node, type="modality", label=modality.value)
            self.graph.add_edge(dataset_node, node, relationship="HAS_MODALITY")
        if dataset.species.value != "unknown":
            node = f"species:{dataset.species.value}"
            self.graph.add_node(node, type="species", label=dataset.species.value)
            self.graph.add_edge(dataset_node, node, relationship="HAS_SPECIES")
        for author in dataset.authors:
            node = f"author:{author}"
            self.graph.add_node(node, type="author", label=author)
            self.graph.add_edge(dataset_node, node, relationship="AUTHORED_BY")
        for paradigm in dataset.behavioral_paradigms:
            node = f"paradigm:{paradigm.normalized_name}"
            self.graph.add_node(
                node,
                type="paradigm",
                label=paradigm.name,
                category=paradigm.category,
                confidence=paradigm.confidence.value,
            )
            self.graph.add_edge(dataset_node, node, relationship="USES_PARADIGM")
        for citation in dataset.citations:
            identifier = citation.doi or citation.pubmed_id or citation.semantic_scholar_id or citation.title
            if not identifier:
                continue
            node = f"paper:{identifier}"
            self.graph.add_node(node, type="paper", label=citation.title or identifier, **citation.model_dump())
            self.graph.add_edge(dataset_node, node, relationship="CITED_BY_DATASET")

    def query(self, node_type: str | None = None, relationship: str | None = None, limit: int = 50) -> dict[str, Any]:
        nodes = [
            {"id": node, **attrs}
            for node, attrs in self.graph.nodes(data=True)
            if node_type is None or attrs.get("type") == node_type
        ][:limit]
        edges = [
            {"source": source, "target": target, **attrs}
            for source, target, attrs in self.graph.edges(data=True)
            if relationship is None or attrs.get("relationship") == relationship
        ][:limit]
        return {"nodes": nodes, "edges": edges, "node_count": self.graph.number_of_nodes(), "edge_count": self.graph.number_of_edges()}

    def related_datasets(self, dataset_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        source = f"dataset:{dataset_id}"
        if source not in self.graph:
            return []
        source_neighbors = set(self.graph.successors(source))
        scored: list[dict[str, Any]] = []
        for node, attrs in self.graph.nodes(data=True):
            if node == source or attrs.get("type") != "dataset":
                continue
            overlap = source_neighbors.intersection(set(self.graph.successors(node)))
            if overlap:
                scored.append({"dataset_id": node.replace("dataset:", ""), "score": len(overlap), "shared_nodes": sorted(overlap)})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]
