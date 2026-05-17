from __future__ import annotations

from typing import Any

from openneuro_mcp.bids import (
    classify_file,
    metadata_quality_score,
    parse_dataset_description,
    parse_events_tsv,
    parse_participants_tsv,
    summarize_bids_files,
)
from openneuro_mcp.client import OpenNeuroClient
from openneuro_mcp.embeddings import InMemoryVectorIndex, embed_text
from openneuro_mcp.graph import NeuroscienceKnowledgeGraph
from openneuro_mcp.models import Citation, DatasetMetadata, Modality, Species
from openneuro_mcp.ontology import infer_modalities, infer_paradigms, infer_species
from openneuro_mcp.storage import MCPStorage


class OpenNeuroSemanticService:
    def __init__(self, client: OpenNeuroClient, storage: MCPStorage | None = None) -> None:
        self.client = client
        self.storage = storage or MCPStorage.from_env("openneuro")
        self.vector_index = InMemoryVectorIndex()
        self.graph = NeuroscienceKnowledgeGraph()

    def search_datasets(self, query: str | None = None, *, page_size: int = 25, after: str | None = None) -> dict[str, Any]:
        return self.client.search_datasets(query, first=page_size, after=after)

    def semantic_search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        return {
            "query": query,
            "results": self.vector_index.search(query, limit=limit),
            "note": "This uses the configured vector index. The default development index only contains datasets enriched during this process lifetime.",
        }

    def get_dataset_metadata(self, dataset_id: str, *, tag: str = "latest", include_files: bool = False) -> dict[str, Any]:
        dataset = self.client.get_dataset(dataset_id)
        snapshot = self.client.get_snapshot(dataset_id, tag)
        files = self._files(dataset_id, tag=tag, recursive=include_files)
        metadata = self._metadata_from_raw(dataset_id, dataset, snapshot, files)
        self._index(metadata)
        output = metadata.model_dump(mode="json")
        output["bids_summary"] = summarize_bids_files(files)
        if include_files:
            output["files"] = [file.model_dump(mode="json") for file in files]
        return output

    def get_dataset_files(self, dataset_id: str, *, tag: str = "latest", tree: str | None = None, recursive: bool = False) -> dict[str, Any]:
        raw_files = self.client.list_files(dataset_id, tag=tag, tree=tree, recursive=recursive)
        files = [classify_file(file["filename"], file_id=file.get("id"), size=file.get("size")) for file in raw_files]
        return {
            "dataset_id": dataset_id,
            "tag": tag,
            "files": [file.model_dump(mode="json") for file in files],
            "summary": summarize_bids_files(files),
        }

    def get_subject_info(self, dataset_id: str, *, tag: str = "latest") -> dict[str, Any]:
        file_data = self.client.get_file_text(dataset_id, "participants.tsv", tag=tag)
        summary = parse_participants_tsv(file_data.get("text"))
        return {"dataset_id": dataset_id, "tag": tag, "subject_info": summary.model_dump(mode="json")}

    def get_events(self, dataset_id: str, task: str, *, tag: str = "latest", path: str | None = None) -> dict[str, Any]:
        event_path = path or f"sub-*/func/*task-{task}*_events.tsv"
        if "*" in event_path:
            return {
                "dataset_id": dataset_id,
                "tag": tag,
                "task": task,
                "path_pattern": event_path,
                "note": "Resolve concrete event paths with get_dataset_files(recursive=true), then call get_events with path.",
            }
        file_data = self.client.get_file_text(dataset_id, event_path, tag=tag)
        structure = parse_events_tsv(task, file_data.get("text"))
        return {"dataset_id": dataset_id, "tag": tag, "path": event_path, "task_structure": structure.model_dump(mode="json")}

    def get_task_structure(self, dataset_id: str, task: str | None = None, *, tag: str = "latest") -> dict[str, Any]:
        files = self._files(dataset_id, tag=tag, recursive=True)
        tasks = sorted({file.bids_entity["task"] for file in files if "task" in file.bids_entity})
        selected = [task] if task else tasks
        paradigms = infer_paradigms(selected + [file.path for file in files if file.filename.endswith("_events.tsv")])
        return {
            "dataset_id": dataset_id,
            "tag": tag,
            "tasks": selected,
            "inferred_paradigms": [paradigm.model_dump(mode="json") for paradigm in paradigms],
            "event_files": [file.path for file in files if file.filename.endswith("_events.tsv")],
        }

    def find_behavioral_paradigms(self, query: str, *, dataset_id: str | None = None, tag: str = "latest") -> dict[str, Any]:
        texts = [query]
        if dataset_id:
            files = self._files(dataset_id, tag=tag, recursive=True)
            texts.extend(file.path for file in files)
        paradigms = infer_paradigms(texts)
        return {"query": query, "dataset_id": dataset_id, "paradigms": [item.model_dump(mode="json") for item in paradigms]}

    def find_similar_datasets(self, dataset_id: str, *, limit: int = 10) -> dict[str, Any]:
        return {"dataset_id": dataset_id, "related": self.graph.related_datasets(dataset_id, limit=limit)}

    def get_dataset_embedding(self, dataset_id: str, *, tag: str = "latest") -> dict[str, Any]:
        metadata = self.get_dataset_metadata(dataset_id, tag=tag, include_files=False)
        text = " ".join(
            str(value)
            for value in [
                metadata.get("name"),
                metadata.get("description"),
                metadata.get("keywords"),
                metadata.get("modalities"),
                metadata.get("behavioral_paradigms"),
            ]
        )
        return {"dataset_id": dataset_id, "tag": tag, "embedding": embed_text(text), "dimensions": 384}

    def get_related_papers(self, dataset_id: str, *, tag: str = "latest") -> dict[str, Any]:
        metadata = self.get_dataset_metadata(dataset_id, tag=tag, include_files=False)
        return {
            "dataset_id": dataset_id,
            "papers": metadata.get("citations", []),
            "enrichment_plan": [
                "Resolve DatasetDOI and ReferencesAndLinks through CrossRef.",
                "Expand DOI/title through Semantic Scholar for citations and references.",
                "Use PubMed E-utilities when PMID or biomedical DOI metadata is present.",
            ],
        }

    def query_knowledge_graph(self, node_type: str | None = None, relationship: str | None = None, limit: int = 50) -> dict[str, Any]:
        return self.graph.query(node_type=node_type, relationship=relationship, limit=limit)

    def get_analysis_pipelines(self, dataset_id: str, *, tag: str = "latest") -> dict[str, Any]:
        files = self._files(dataset_id, tag=tag, recursive=True)
        derivative_files = [file for file in files if file.path.startswith("derivatives/")]
        pipeline_names = sorted(
            {
                file.path.split("/")[1]
                for file in derivative_files
                if len(file.path.split("/")) > 1
            }
        )
        return {
            "dataset_id": dataset_id,
            "tag": tag,
            "pipelines": pipeline_names,
            "derivative_file_count": len(derivative_files),
            "confidence": 0.8 if pipeline_names else 0.2,
        }

    def get_associated_code(self, dataset_id: str, *, tag: str = "latest") -> dict[str, Any]:
        snapshot = self.client.get_snapshot(dataset_id, tag)
        description = parse_dataset_description(snapshot.get("description"))
        links = description.get("ReferencesAndLinks") or []
        github = [link for link in links if isinstance(link, str) and "github.com" in link.lower()]
        return {"dataset_id": dataset_id, "tag": tag, "github_repositories": github, "all_references": links}

    def _metadata_from_raw(
        self,
        dataset_id: str,
        dataset: dict[str, Any],
        snapshot: dict[str, Any],
        files: list[Any],
    ) -> DatasetMetadata:
        description = parse_dataset_description(snapshot.get("description"))
        text_fields = [
            dataset.get("name", ""),
            description.get("Name", ""),
            description.get("DatasetType", ""),
            " ".join(description.get("Keywords") or []),
            " ".join(description.get("ReferencesAndLinks") or []),
            " ".join(file.path for file in files),
        ]
        species, _confidence = infer_species(text_fields)
        modalities = infer_modalities(text_fields, [file.path for file in files])
        paradigms = infer_paradigms(text_fields)
        citations = self._citations(description)
        authors = [str(author) for author in description.get("Authors") or []]
        return DatasetMetadata(
            id=dataset_id,
            name=dataset.get("name") or description.get("Name"),
            version=snapshot.get("tag"),
            description=description,
            doi=description.get("DatasetDOI"),
            authors=authors,
            keywords=[str(value) for value in description.get("Keywords") or []],
            modalities=[modality for modality in modalities if modality != Modality.UNKNOWN],
            species=species if species != Species.UNKNOWN else Species.HUMAN,
            behavioral_paradigms=paradigms,
            citations=citations,
            quality=metadata_quality_score(description, files),
            provenance=["OpenNeuro GraphQL snapshot metadata", "BIDS filename ontology inference"],
        )

    def _files(self, dataset_id: str, *, tag: str, recursive: bool) -> list[Any]:
        raw_files = self.client.list_files(dataset_id, tag=tag, recursive=recursive)
        return [classify_file(file["filename"], file_id=file.get("id"), size=file.get("size")) for file in raw_files]

    def _citations(self, description: dict[str, Any]) -> list[Citation]:
        citations: list[Citation] = []
        doi = description.get("DatasetDOI")
        if doi:
            citations.append(Citation(doi=str(doi).replace("doi:", ""), relationship="primary", provenance=["dataset_description.json:DatasetDOI"]))
        for link in description.get("ReferencesAndLinks") or []:
            if not isinstance(link, str):
                continue
            relationship = "methods" if "doi" in link.lower() or "pubmed" in link.lower() else "related"
            citations.append(Citation(url=link if link.startswith(("http://", "https://")) else None, relationship=relationship, provenance=["dataset_description.json:ReferencesAndLinks"]))
        return citations

    def _index(self, metadata: DatasetMetadata) -> None:
        text = " ".join(
            [
                metadata.name or "",
                str(metadata.description),
                " ".join(metadata.keywords),
                " ".join(paradigm.normalized_name for paradigm in metadata.behavioral_paradigms),
                " ".join(modality.value for modality in metadata.modalities),
            ]
        )
        payload = {"name": metadata.name, "modalities": [item.value for item in metadata.modalities]}
        self.vector_index.upsert(metadata.id, text, payload)
        self.storage.upsert_record(
            "dataset",
            metadata.id,
            metadata.model_dump(mode="json"),
            source="OpenNeuro GraphQL and BIDS metadata",
            version=metadata.version,
        )
        self.storage.upsert_embedding(
            "dataset",
            metadata.id,
            embed_text(text),
            model="local-hashing-384",
            payload=payload,
        )
        self.graph.ingest_dataset(metadata)
        graph = self.graph.query(limit=10_000)
        self.storage.replace_graph("openneuro:semantic", graph.get("nodes", []), graph.get("edges", []))
