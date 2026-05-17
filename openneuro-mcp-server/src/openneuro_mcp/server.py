from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from openneuro_mcp import __version__
from openneuro_mcp.client import DEFAULT_GRAPHQL_URL, DEFAULT_RAW_DATASET_URL, OpenNeuroClient, OpenNeuroClientConfig
from openneuro_mcp.local_explorer import LocalOpenNeuroExplorer
from openneuro_mcp.service import OpenNeuroSemanticService
from neurodata_literature import LiteratureService, build_dataset_explorer_html, stable_variable_id


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
    literature = LiteratureService(service.storage, "openneuro")

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
    def get_dataset_papers(dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        """Provider-compatible alias for papers and literature links associated with an OpenNeuro dataset."""
        return service.get_related_papers(dataset_id, tag=tag)

    @mcp.tool()
    def resolve_dataset_papers(
        dataset_id: str,
        version_or_tag: str = "latest",
        include_citation_graph: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Resolve OpenNeuro dataset paper links through real public literature APIs."""
        del include_citation_graph
        return literature.resolve_papers(
            dataset_id,
            _openneuro_paper_hints(service, dataset_id, version_or_tag),
            limit=limit,
            relationship="dataset",
        )

    @mcp.tool()
    def query_dataset_papers(
        dataset_id: str,
        question: str,
        version_or_tag: str = "latest",
        full_text_policy: str = "auto",
        limit: int = 8,
    ) -> dict[str, Any]:
        """Query OpenNeuro-associated papers and escalate to full text when uncertainty is high."""
        context = _safe_call(lambda: service.get_dataset_metadata(dataset_id, tag=version_or_tag), default={})
        return literature.query_papers(
            dataset_id=dataset_id,
            question=question,
            paper_hints=_openneuro_paper_hints(service, dataset_id, version_or_tag),
            dataset_context=context,
            full_text_policy=full_text_policy,
            limit=limit,
        )

    @mcp.tool()
    def explain_dataset_variable(
        dataset_key_or_id: str,
        variable: str,
        file_path: str | None = None,
        object_path: str | None = None,
        context: str | None = None,
        version_or_tag: str = "latest",
        full_text_policy: str = "auto",
    ) -> dict[str, Any]:
        """Explain a BIDS/OpenNeuro variable using metadata, papers, and uncertainty-aware full text."""
        del object_path
        variable_context = _openneuro_variable_context(
            local,
            service,
            dataset_key_or_id,
            variable,
            file_path=file_path,
            context=context,
            tag=version_or_tag,
        )
        return literature.explain_variable(
            dataset_id=dataset_key_or_id,
            variable=variable,
            variable_context=variable_context,
            paper_hints=_openneuro_paper_hints(service, dataset_key_or_id, version_or_tag),
            full_text_policy=full_text_policy,
        )

    @mcp.tool()
    def register_paper_pdf(
        dataset_id: str,
        pdf_path: str,
        doi: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Register a user-provided PDF for an OpenNeuro dataset and index it for future explanations."""
        return literature.register_pdf(dataset_id=dataset_id, pdf_path=pdf_path, doi=doi, title=title)

    @mcp.tool()
    def list_missing_paper_pdfs(dataset_id: str) -> dict[str, Any]:
        """List papers whose PDFs were needed but could not be retrieved automatically."""
        return literature.list_missing_pdfs(dataset_id)

    @mcp.tool()
    def generate_dataset_explorer(
        dataset_key_or_id: str,
        version_or_tag: str = "latest",
        include_papers: bool = True,
        open_in_browser: bool = True,
    ) -> dict[str, Any]:
        """Generate and optionally launch a static HTML explorer for an OpenNeuro/BIDS dataset."""
        summary, variables = _openneuro_explorer_data(local, service, dataset_key_or_id, version_or_tag)
        papers = (
            literature.resolve_papers(dataset_key_or_id, _openneuro_paper_hints(service, dataset_key_or_id, version_or_tag)).get("papers", [])
            if include_papers
            else []
        )
        explorer_id = stable_variable_id(dataset_key_or_id, {"kind": "explorer"}, "dataset")
        artifact_dir = service.storage.config.provider_dir / "artifacts" / dataset_key_or_id.replace("/", "_").replace(":", "_")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        html_path = artifact_dir / "dataset-explorer.html"
        html_path.write_text(
            build_dataset_explorer_html(
                provider="openneuro",
                dataset_id=dataset_key_or_id,
                title=str(summary.get("name") or dataset_key_or_id),
                summary=summary,
                variables=variables,
                papers=papers,
                missing_pdfs=literature.list_missing_pdfs(dataset_key_or_id).get("missing_pdfs", []),
            ),
            encoding="utf-8",
        )
        result = {
            "status": "created",
            "explorer_id": explorer_id,
            "dataset_key_or_id": dataset_key_or_id,
            "html_path": str(html_path),
            "file_url": html_path.resolve().as_uri(),
            "open_command": f"open {html_path}",
            "agent_instruction": (
                "If the user asked to visualize or explore the dataset, show/open this HTML explorer now. "
                "Use plotting only when the user explicitly asks for a plot or analysis figure."
            ),
            "opened": False,
            "summary": {
                "variable_count": len(variables),
                "paper_count": len(papers),
                "missing_pdf_count": len(literature.list_missing_pdfs(dataset_key_or_id).get("missing_pdfs", [])),
            },
        }
        if open_in_browser:
            result.update(_open_html_artifact(html_path))
        service.storage.upsert_record("dataset_explorer", explorer_id, result, source="neurodata_literature")
        return result

    @mcp.tool()
    def explain_visual_dataset_selection(
        explorer_id: str,
        variable_id: str,
        question: str | None = None,
        full_text_policy: str = "auto",
    ) -> dict[str, Any]:
        """Return guidance for explaining a variable selected in a generated OpenNeuro explorer."""
        return {
            "explorer_id": explorer_id,
            "variable_id": variable_id,
            "question": question,
            "next_action": "Call explain_dataset_variable with the dataset id, variable name, and file_path shown in the explorer row.",
            "full_text_policy": full_text_policy,
        }

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


def _safe_call(call: Any, default: Any = None) -> Any:
    try:
        return call()
    except Exception:
        return default


def _open_html_artifact(html_path: Path) -> dict[str, Any]:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(html_path)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        else:
            webbrowser.open(html_path.resolve().as_uri())
        return {"opened": True, "open_error": None}
    except Exception as exc:
        return {"opened": False, "open_error": str(exc)}


def _openneuro_paper_hints(
    service: OpenNeuroSemanticService,
    dataset_id: str,
    tag: str,
) -> list[Any]:
    hints: list[Any] = []
    metadata = _safe_call(lambda: service.get_dataset_metadata(dataset_id, tag=tag), default={})
    if metadata:
        hints.append(metadata.get("doi"))
        hints.append(metadata.get("name"))
        description = metadata.get("description") or {}
        hints.extend(description.get("ReferencesAndLinks") or [])
        hints.extend(metadata.get("citations") or [])
    related = _safe_call(lambda: service.get_related_papers(dataset_id, tag=tag), default={})
    hints.extend(related.get("papers", []) if isinstance(related, dict) else [])
    return [hint for hint in hints if hint]


def _openneuro_variable_context(
    local: LocalOpenNeuroExplorer,
    service: OpenNeuroSemanticService,
    dataset_key_or_id: str,
    variable: str,
    *,
    file_path: str | None,
    context: str | None,
    tag: str,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "provider": "openneuro",
        "dataset_id": dataset_key_or_id,
        "variable": variable,
        "file_path": file_path,
        "user_context": context,
    }
    inventory = _safe_call(lambda: local.signal_inventory(dataset_key_or_id), default={})
    for signal in inventory.get("signals", []) if isinstance(inventory, dict) else []:
        text = " ".join(str(signal.get(key, "")) for key in ["file", "suffix", "task", "modality"])
        if (file_path and signal.get("file") == file_path) or variable.lower() in text.lower():
            ctx.update(signal)
            ctx["kind"] = "bids_signal"
            break
    if file_path and file_path.endswith("_events.tsv"):
        events = _safe_call(lambda: local.extract_events(dataset_key_or_id, path=file_path), default={})
        if events:
            ctx.update(
                {
                    "kind": "bids_events",
                    "task": events.get("task"),
                    "columns": events.get("columns"),
                    "trial_type_values": events.get("trial_type_values"),
                    "onset_range_seconds": events.get("onset_range_seconds"),
                    "duration_range_seconds": events.get("duration_range_seconds"),
                }
            )
    metadata = _safe_call(lambda: service.get_dataset_metadata(dataset_key_or_id, tag=tag), default={})
    if metadata:
        ctx.update(
            {
                "name": metadata.get("name"),
                "description": metadata.get("description"),
                "modalities": metadata.get("modalities"),
                "species": metadata.get("species"),
                "behavioral_paradigms": metadata.get("behavioral_paradigms"),
            }
        )
    return ctx


def _openneuro_explorer_data(
    local: LocalOpenNeuroExplorer,
    service: OpenNeuroSemanticService,
    dataset_key_or_id: str,
    tag: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = _safe_call(lambda: local.summarize(dataset_key_or_id), default={})
    variables = []
    inventory = _safe_call(lambda: local.signal_inventory(dataset_key_or_id), default={})
    for signal in inventory.get("signals", []) if isinstance(inventory, dict) else []:
        variables.append({"provider": "openneuro", "confidence_label": "low", **signal})
    index = _safe_call(lambda: local.index(dataset_key_or_id), default={})
    for event in index.get("events", []) if isinstance(index, dict) else []:
        for column in event.get("columns", []):
            variables.append(
                {
                    "provider": "openneuro",
                    "kind": "events_column",
                    "name": column,
                    "column": column,
                    "file": event.get("path"),
                    "task": event.get("task"),
                    "confidence_label": "low",
                }
            )
    if not summary:
        summary = _safe_call(lambda: service.get_dataset_metadata(dataset_key_or_id, tag=tag), default={"name": dataset_key_or_id})
    return summary, variables


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
