from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from openneuro_mcp import __version__
from openneuro_mcp.client import DEFAULT_GRAPHQL_URL, DEFAULT_RAW_DATASET_URL, OpenNeuroClient, OpenNeuroClientConfig
from openneuro_mcp.local_explorer import LocalOpenNeuroExplorer
from openneuro_mcp.service import OpenNeuroSemanticService


def build_server() -> FastMCP:
    mcp = FastMCP(
        "OpenNeuro Semantic OS",
        instructions=(
            "AI-native, BIDS-aware semantic interface for OpenNeuro. Use it to discover "
            "datasets, infer modalities/species/tasks/behavioral paradigms, retrieve BIDS "
            "metadata, link papers/code, build dataset embeddings, and traverse a neuroscience "
            "knowledge graph. This is read-only by default."
        ),
        json_response=True,
    )
    service = OpenNeuroSemanticService(_client_from_env())
    local = LocalOpenNeuroExplorer(service.storage)

    @mcp.tool()
    def get_storage_info() -> dict[str, Any]:
        """Return the standardized local storage paths and schema for this MCP server."""
        return service.storage.describe()

    @mcp.tool()
    def register_local_dataset(path: str | None = None, dataset_id: str | None = None, tag: str = "local") -> dict[str, Any]:
        """Register a downloaded local OpenNeuro/BIDS dataset by path or dataset id."""
        return local.register(path=path, dataset_id=dataset_id, tag=tag)

    @mcp.tool()
    def list_local_datasets() -> dict[str, Any]:
        """List downloaded OpenNeuro/BIDS datasets registered with the local explorer."""
        return local.list_registered()

    @mcp.tool()
    def summarize_local_dataset(dataset_key: str = "") -> dict[str, Any]:
        """Summarize a registered local BIDS dataset, including subjects, tasks, modalities, and events."""
        return local.summarize(dataset_key)

    @mcp.tool()
    def browse_local_dataset(dataset_key: str = "", path_prefix: str = "") -> dict[str, Any]:
        """Browse direct child files and folders inside a registered local BIDS dataset."""
        return local.browse(dataset_key, path_prefix=path_prefix)

    @mcp.tool()
    def list_local_files(
        dataset_key: str = "",
        glob: str | None = None,
        file_type: str | None = None,
        subject: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List local BIDS files with optional glob, type, and subject filters."""
        return local.list_files(dataset_key, glob=glob, file_type=file_type, subject=subject, limit=limit)

    @mcp.tool()
    def index_local_dataset(dataset_key: str = "") -> dict[str, Any]:
        """Build a local BIDS index over subjects, sessions, tasks, events, and modality inventory."""
        return local.index(dataset_key)

    @mcp.tool()
    def get_dataset_subjects(dataset_key: str = "") -> dict[str, Any]:
        """Return detected subjects for a registered local OpenNeuro dataset."""
        return local.subjects(dataset_key)

    @mcp.tool()
    def get_dataset_sessions(dataset_key: str = "") -> dict[str, Any]:
        """Return detected sessions for a registered local OpenNeuro dataset."""
        return local.sessions(dataset_key)

    @mcp.tool()
    def get_dataset_signal_inventory(dataset_key: str = "") -> dict[str, Any]:
        """Return local BIDS signal/file inventory with modality, suffix, task, and subject fields."""
        return local.signal_inventory(dataset_key)

    @mcp.tool()
    def extract_events_table(
        dataset_key: str = "",
        path: str = "",
        task: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """Extract a bounded preview of a local BIDS events.tsv file."""
        return local.extract_events(dataset_key, path=path, task=task, limit=limit)

    @mcp.tool()
    def generate_dataset_report(dataset_key: str = "") -> dict[str, Any]:
        """Generate a Markdown local dataset report under MCP artifact storage."""
        return local.report(dataset_key)

    @mcp.tool()
    def search_datasets(query: str | None = None, page_size: int = 25, after: str | None = None) -> dict[str, Any]:
        """Keyword search or list OpenNeuro datasets with cursor pagination."""
        return service.search_datasets(query, page_size=page_size, after=after)

    @mcp.tool()
    def semantic_search(query: str, limit: int = 10) -> dict[str, Any]:
        """Search datasets by semantic similarity over indexed descriptions, tasks, papers, and metadata."""
        return service.semantic_search(query, limit=limit)

    @mcp.tool()
    def ontology_search(
        query: str,
        modality: str | None = None,
        species: str | None = None,
        paradigm: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Ontology-guided dataset discovery over modality, species, and behavioral terms."""
        enriched_query = " ".join(value for value in [query, modality, species, paradigm] if value)
        return service.semantic_search(enriched_query, limit=limit)

    @mcp.tool()
    def modality_search(modality: str, limit: int = 10) -> dict[str, Any]:
        """Find indexed datasets associated with a modality such as fMRI, EEG, MEG, iEEG, PET, or video."""
        return service.semantic_search(modality, limit=limit)

    @mcp.tool()
    def species_search(species: str, limit: int = 10) -> dict[str, Any]:
        """Find indexed datasets for a species, for example human, mouse, rat, or macaque."""
        return service.semantic_search(species, limit=limit)

    @mcp.tool()
    def task_search(task: str, limit: int = 10) -> dict[str, Any]:
        """Find indexed datasets containing a named BIDS task or task-like metadata."""
        return service.semantic_search(task, limit=limit)

    @mcp.tool()
    def behavioral_paradigm_search(paradigm: str, limit: int = 10) -> dict[str, Any]:
        """Find indexed datasets matching behavioral paradigms such as 2AFC, go/no-go, reward learning, or social cognition."""
        return service.semantic_search(paradigm, limit=limit)

    @mcp.tool()
    def author_search(author: str, limit: int = 10) -> dict[str, Any]:
        """Find indexed datasets associated with an author."""
        return service.semantic_search(author, limit=limit)

    @mcp.tool()
    def institution_search(institution: str, limit: int = 10) -> dict[str, Any]:
        """Find indexed datasets associated with an institution or consortium."""
        return service.semantic_search(institution, limit=limit)

    @mcp.tool()
    def get_dataset_metadata(dataset_id: str, tag: str = "latest", include_files: bool = False) -> dict[str, Any]:
        """Fetch and enrich dataset_description.json, inferred modalities, species, paradigms, quality, and provenance."""
        return service.get_dataset_metadata(dataset_id, tag=tag, include_files=include_files)

    @mcp.tool()
    def get_dataset_files(dataset_id: str, tag: str = "latest", recursive: bool = False, tree: str | None = None) -> dict[str, Any]:
        """Retrieve OpenNeuro snapshot file trees and classify BIDS entities and modalities."""
        return service.get_dataset_files(dataset_id, tag=tag, tree=tree, recursive=recursive)

    @mcp.tool()
    def get_related_papers(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Return dataset DOI/reference links plus the enrichment plan for CrossRef, Semantic Scholar, and PubMed."""
        return service.get_related_papers(dataset_id, tag=tag)

    @mcp.tool()
    def find_similar_datasets(dataset_id: str, limit: int = 10) -> dict[str, Any]:
        """Find graph-related datasets sharing modalities, species, paradigms, authors, or papers."""
        return service.find_similar_datasets(dataset_id, limit=limit)

    @mcp.tool()
    def find_behavioral_paradigms(query: str, dataset_id: str | None = None, tag: str = "latest") -> dict[str, Any]:
        """Infer behavioral paradigms from natural language, BIDS task names, event paths, and metadata."""
        return service.find_behavioral_paradigms(query, dataset_id=dataset_id, tag=tag)

    @mcp.tool()
    def get_modalities(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Infer acquisition and derivative modalities from dataset files and metadata."""
        metadata = service.get_dataset_metadata(dataset_id, tag=tag, include_files=True)
        return {"dataset_id": dataset_id, "tag": tag, "modalities": metadata.get("modalities", []), "bids_summary": metadata.get("bids_summary", {})}

    @mcp.tool()
    def get_task_structure(dataset_id: str, task: str | None = None, tag: str = "latest") -> dict[str, Any]:
        """Summarize tasks, events.tsv paths, and inferred behavioral paradigms."""
        return service.get_task_structure(dataset_id, task=task, tag=tag)

    @mcp.tool()
    def get_subject_info(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Parse participants.tsv into structured subject counts, columns, species, and categorical fields."""
        return service.get_subject_info(dataset_id, tag=tag)

    @mcp.tool()
    def get_events(dataset_id: str, task: str, tag: str = "latest", path: str | None = None) -> dict[str, Any]:
        """Parse an events.tsv file into trial columns, trial types, timing ranges, and paradigm hints."""
        return service.get_events(dataset_id, task, tag=tag, path=path)

    @mcp.tool()
    def get_derivatives(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Discover derivative directories and preprocessing outputs."""
        return service.get_analysis_pipelines(dataset_id, tag=tag)

    @mcp.tool()
    def get_analysis_pipelines(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Infer analysis/preprocessing pipelines from derivatives such as fMRIPrep, FreeSurfer, or QSIPrep."""
        return service.get_analysis_pipelines(dataset_id, tag=tag)

    @mcp.tool()
    def get_associated_code(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Extract GitHub and code links from dataset references."""
        return service.get_associated_code(dataset_id, tag=tag)

    @mcp.tool()
    def get_dataset_embedding(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Return the configured dataset embedding vector for downstream agent similarity workflows."""
        return service.get_dataset_embedding(dataset_id, tag=tag)

    @mcp.tool()
    def query_knowledge_graph(node_type: str | None = None, relationship: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Traverse the internal dataset-paper-author-paradigm-modality-species knowledge graph."""
        return service.query_knowledge_graph(node_type=node_type, relationship=relationship, limit=limit)

    @mcp.tool()
    def get_openneuro_mcp_roadmap() -> dict[str, Any]:
        """Return the production architecture roadmap for OpenNeuro, DANDI, NWB, IBL, Brainlife, NeuroVault, and Allen integrations."""
        return {
            "version": __version__,
            "layers": [
                "OpenNeuro GraphQL ingestion",
                "BIDS/NIDM metadata parser",
                "ontology normalization",
                "paper/code enrichment",
                "pgvector or Qdrant semantic index",
                "Neo4j or NetworkX knowledge graph",
                "MCP tools for agent interoperability",
                "future cross-repository adapters",
            ],
            "future_repositories": ["DANDI", "NWB", "IBL", "Brainlife", "NeuroVault", "Allen Brain Atlas", "CRCNS"],
        }

    return mcp


def _client_from_env() -> OpenNeuroClient:
    return OpenNeuroClient(
        OpenNeuroClientConfig(
            graphql_url=os.getenv("OPENNEURO_GRAPHQL_URL", DEFAULT_GRAPHQL_URL),
            raw_dataset_url=os.getenv("OPENNEURO_RAW_DATASET_URL", DEFAULT_RAW_DATASET_URL),
            timeout=float(os.getenv("OPENNEURO_TIMEOUT", "30")),
            api_token=os.getenv("OPENNEURO_API_TOKEN"),
        )
    )


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
