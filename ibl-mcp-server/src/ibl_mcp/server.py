from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ibl_mcp.client import (
    DEFAULT_ALYX_BASE_URL,
    DEFAULT_PUBLIC_PASSWORD,
    DEFAULT_PUBLIC_USERNAME,
    IBLClient,
    IBLClientConfig,
)
from ibl_mcp.local_explorer import LocalIBLExplorer
from ibl_mcp.services import IBLDomainService
from ibl_mcp.storage import MCPStorage
from neurodata_literature import LiteratureService, build_dataset_explorer_html, stable_variable_id


def build_server() -> FastMCP:
    mcp = FastMCP(
        "International Brain Laboratory OpenAlyx",
        instructions=(
            "One-stop MCP access to public International Brain Laboratory data via "
            "OpenAlyx/Alyx REST endpoints. Use this server to discover sessions, "
            "subjects, datasets, Neuropixels insertions, brain regions, file records, "
            "cache metadata, and download URLs. Prefer read-only tools; mutating Alyx "
            "calls are guarded behind explicit confirmation."
        ),
        json_response=True,
    )
    client = _client_from_env()
    service = IBLDomainService(client)
    local = LocalIBLExplorer(client.storage)
    literature = LiteratureService(client.storage, "ibl")

    @mcp.tool()
    def get_storage_info() -> dict[str, Any]:
        """Return the standardized local storage paths and schema for this MCP server."""
        return client.storage.describe()

    @mcp.tool()
    def register_local_dataset(
        path: str | None = None,
        session_id: str | None = None,
        dataset_id: str | None = None,
    ) -> dict[str, Any]:
        """Register a downloaded local IBL/ALF dataset by path, session id, or dataset id."""
        return local.register(path=path, session_id=session_id, dataset_id=dataset_id)

    @mcp.tool()
    def list_local_datasets() -> dict[str, Any]:
        """List downloaded IBL datasets registered with the local explorer."""
        return local.list_registered()

    @mcp.tool()
    def summarize_local_dataset(dataset_key: str = "") -> dict[str, Any]:
        """Summarize a registered local IBL dataset, including collections, ALF objects, and modalities."""
        return local.summarize(dataset_key)

    @mcp.tool()
    def browse_local_dataset(dataset_key: str = "", path_prefix: str = "") -> dict[str, Any]:
        """Browse direct child files and folders inside a registered local IBL dataset."""
        return local.browse(dataset_key, path_prefix=path_prefix)

    @mcp.tool()
    def list_local_files(
        dataset_key: str = "",
        glob: str | None = None,
        file_type: str | None = None,
        subject: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List local IBL files with optional glob, type, and subject filters."""
        return local.list_files(dataset_key, glob=glob, file_type=file_type, subject=subject, limit=limit)

    @mcp.tool()
    def index_local_dataset(dataset_key: str = "") -> dict[str, Any]:
        """Build a local IBL index over subjects, sessions, collections, ALF objects, and modalities."""
        return local.index(dataset_key)

    @mcp.tool()
    def get_dataset_subjects(dataset_key: str = "") -> dict[str, Any]:
        """Return detected subjects for a registered local IBL dataset."""
        return local.subjects(dataset_key)

    @mcp.tool()
    def get_dataset_sessions(dataset_key: str = "") -> dict[str, Any]:
        """Return detected sessions for a registered local IBL dataset."""
        return local.sessions(dataset_key)

    @mcp.tool()
    def get_dataset_signal_inventory(dataset_key: str = "") -> dict[str, Any]:
        """Return local IBL signal inventory with collection, ALF object, attribute, and modality fields."""
        return local.signal_inventory(dataset_key)

    @mcp.tool()
    def generate_dataset_report(dataset_key: str = "") -> dict[str, Any]:
        """Generate a Markdown local IBL dataset report under MCP artifact storage."""
        return local.report(dataset_key)

    @mcp.tool()
    def list_alyx_endpoints() -> dict[str, Any]:
        """List all REST endpoints advertised by the configured OpenAlyx/Alyx server."""
        return client.list_endpoints()

    @mcp.tool()
    def describe_alyx_endpoint(endpoint: str) -> dict[str, Any]:
        """Fetch OPTIONS/schema metadata for an Alyx endpoint, e.g. sessions or datasets."""
        return client.describe_endpoint(endpoint)

    @mcp.tool()
    def search_sessions(
        subject: str | None = None,
        lab: str | None = None,
        project: str | None = None,
        task_protocol: str | None = None,
        date_range: str | None = None,
        datasets: str | None = None,
        dataset_types: str | None = None,
        brain_region: str | None = None,
        atlas_acronym: str | None = None,
        atlas_id: str | int | None = None,
        qc: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Search IBL sessions with common ONE/Alyx filters and generic Django lookups."""
        return client.list_sessions(**locals())

    @mcp.tool()
    def get_session(session_id: str) -> dict[str, Any]:
        """Read one session by experiment UUID/eID."""
        return client.get_session(session_id)

    @mcp.tool()
    def summarize_session(session_id: str, dataset_limit: int = 25) -> dict[str, Any]:
        """Return session metadata plus sample datasets and probe insertions for orientation."""
        return client.summarize_session(session_id, dataset_limit=dataset_limit)

    @mcp.tool()
    def get_session_metadata(session_id: str) -> dict[str, Any]:
        """Return AI-native session metadata, modality inventory, QC warnings, provenance, and graph edges."""
        return service.get_session_metadata(session_id)

    @mcp.tool()
    def get_session_datasets(session_id: str, modality: str | None = None) -> dict[str, Any]:
        """Return QC-aware dataset inventory for a session, optionally filtered by modality."""
        return service.get_session_datasets(session_id, modality=modality)

    @mcp.tool()
    def list_datasets(
        session: str | None = None,
        name: str | None = None,
        collection: str | None = None,
        dataset_type: str | None = None,
        tag: str | None = None,
        exists: bool | None = True,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List dataset records, usually filtered by session/eID, collection, name, or tag."""
        return client.list_datasets(**locals())

    @mcp.tool()
    def get_dataset(dataset_id: str) -> dict[str, Any]:
        """Read one dataset record by UUID."""
        return client.get_dataset(dataset_id)

    @mcp.tool()
    def list_files(
        dataset: str | None = None,
        session: str | None = None,
        exists: bool | None = True,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List physical file records and object-store locations for datasets/sessions."""
        return client.list_files(**locals())

    @mcp.tool()
    def get_dataset_download_urls(dataset_id: str) -> dict[str, Any]:
        """Collect direct object-store URLs embedded in a dataset and its file records."""
        return client.get_dataset_download_urls(dataset_id)

    @mcp.tool()
    def download_url(url: str, filename: str | None = None, max_bytes: int = 2_000_000_000) -> dict[str, Any]:
        """Download an explicit http(s) URL into IBL_MCP_DOWNLOAD_DIR and return the local path."""
        return client.download_url(url, filename=filename, max_bytes=max_bytes)

    @mcp.tool()
    def list_insertions(
        session: str | None = None,
        name: str | None = None,
        project: str | None = None,
        atlas_acronym: str | None = None,
        atlas_id: str | int | None = None,
        atlas_name: str | None = None,
        dataset: str | None = None,
        datasets: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Search Neuropixels/ephys probe insertion records."""
        return client.list_insertions(**locals())

    @mcp.tool()
    def get_insertion(insertion_id: str) -> dict[str, Any]:
        """Read a probe insertion record by UUID."""
        return client.get_insertion(insertion_id)

    @mcp.tool()
    def list_trajectories(
        probe_insertion: str | None = None,
        provenance: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List insertion trajectory/alignment records, including histology provenance."""
        return client.list_trajectories(**locals())

    @mcp.tool()
    def list_channels(
        probe_insertion: str | None = None,
        session: str | None = None,
        atlas_acronym: str | None = None,
        atlas_id: str | int | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List electrophysiology channels and Allen atlas assignments."""
        return client.list_channels(**locals())

    @mcp.tool()
    def list_subjects(
        nickname: str | None = None,
        lab: str | None = None,
        project: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List IBL subjects/mice with optional lab/project filters."""
        return client.list_subjects(**locals())

    @mcp.tool()
    def search_subjects(
        nickname: str | None = None,
        lab: str | None = None,
        project: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Alias for list_subjects with a search-oriented name."""
        return client.list_subjects(**locals())

    @mcp.tool()
    def list_brain_regions(
        acronym: str | None = None,
        name: str | None = None,
        id: str | int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List Allen CCF brain regions known to Alyx."""
        return client.list_brain_regions(**locals())

    @mcp.tool()
    def list_dataset_types(
        name: str | None = None,
        filename: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List dataset type definitions used by IBL/ONE."""
        return client.list_dataset_types(**locals())

    @mcp.tool()
    def list_data_formats(
        name: str | None = None,
        file_extension: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List registered data formats/file extensions."""
        return client.list_data_formats(**locals())

    @mcp.tool()
    def list_tags(name: str | None = None) -> dict[str, Any] | list[Any]:
        """List release tags, including public release collections."""
        return client.list_tags(name=name)

    @mcp.tool()
    def list_labs(name: str | None = None) -> dict[str, Any] | list[Any]:
        """List labs represented in Alyx."""
        return client.list_labs(name=name)

    @mcp.tool()
    def list_projects(name: str | None = None) -> dict[str, Any] | list[Any]:
        """List IBL project names."""
        return client.list_projects(name=name)

    @mcp.tool()
    def search_labs(name: str | None = None) -> dict[str, Any] | list[Any]:
        """Search labs represented in Alyx."""
        return client.list_labs(name=name)

    @mcp.tool()
    def search_projects(name: str | None = None) -> dict[str, Any] | list[Any]:
        """Search IBL projects."""
        return client.list_projects(name=name)

    @mcp.tool()
    def search_task_protocols(
        search: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """Derive task protocol names from matching sessions."""
        return client.list_task_protocols(search=search, page=page, page_size=page_size)

    @mcp.tool()
    def search_probe_insertions(
        session: str | None = None,
        name: str | None = None,
        project: str | None = None,
        atlas_acronym: str | None = None,
        atlas_id: str | int | None = None,
        atlas_name: str | None = None,
        dataset: str | None = None,
        datasets: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Alias for list_insertions with a neuroscience-search name."""
        return client.list_insertions(**locals())

    @mcp.tool()
    def get_probe_metadata(session_id: str, probe: str | None = None) -> dict[str, Any]:
        """Return probe insertion plus spike/cluster dataset metadata for a session/probe."""
        return service.get_spike_metadata(session_id, probe=probe)

    @mcp.tool()
    def get_brain_regions(
        acronym: str | None = None,
        name: str | None = None,
        id: str | int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Search Allen CCF brain regions known to Alyx."""
        return client.list_brain_regions(acronym=acronym, name=name, id=id, page=page, page_size=page_size)

    @mcp.tool()
    def search_behavioral_sessions(
        subject: str | None = None,
        lab: str | None = None,
        project: str | None = None,
        task_protocol: str | None = None,
        qc: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Find sessions likely to support behavioral analysis by requiring trial datasets."""
        return client.list_sessions(subject=subject, lab=lab, project=project, task_protocol=task_protocol, datasets="_ibl_trials.choice.npy", qc=qc, page=page, page_size=page_size)

    @mcp.tool()
    def search_neural_recording_sessions(
        subject: str | None = None,
        lab: str | None = None,
        project: str | None = None,
        atlas_acronym: str | None = None,
        qc: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Find sessions likely to support Neuropixels analysis by requiring spike times."""
        return client.list_sessions(subject=subject, lab=lab, project=project, atlas_acronym=atlas_acronym, datasets="spikes.times.npy", qc=qc, page=page, page_size=page_size)

    @mcp.tool()
    def get_trials(session_id: str, limit: int = 200, include_arrays: bool = False) -> dict[str, Any]:
        """Load trial ALF arrays and return row-oriented trial records with QC/provenance."""
        return service.get_trials(session_id, limit=limit, include_arrays=include_arrays)

    @mcp.tool()
    def get_behavior_summary(session_id: str) -> dict[str, Any]:
        """Compute behavioral performance, choice bias, reaction time, and trial-count warnings."""
        return service.get_behavior_summary(session_id)

    @mcp.tool()
    def get_psychometric_summary(session_id: str) -> dict[str, Any]:
        """Compute a simple psychometric summary: p(right) by signed contrast."""
        return service.get_psychometric_summary(session_id)

    @mcp.tool()
    def get_wheel_data(session_id: str, limit: int = 1000, include_arrays: bool = False) -> dict[str, Any]:
        """Load wheel arrays and return movement summaries with optional samples."""
        return service.get_wheel_data(session_id, limit=limit, include_arrays=include_arrays)

    @mcp.tool()
    def get_lick_data(session_id: str, limit: int = 1000) -> dict[str, Any]:
        """Load lick timestamps where available."""
        return service.get_lick_data(session_id, limit=limit)

    @mcp.tool()
    def get_video_metadata(session_id: str) -> dict[str, Any]:
        """Return video, pose/DLC, and pupil dataset availability for a session."""
        return service.get_video_metadata(session_id)

    @mcp.tool()
    def get_pose_data(session_id: str) -> dict[str, Any]:
        """Return pose-tracking dataset metadata; tabular pose loading is a planned parquet extension."""
        return service.get_video_metadata(session_id)

    @mcp.tool()
    def get_pupil_data(session_id: str) -> dict[str, Any]:
        """Return pupil-related dataset metadata; tabular pupil loading is a planned parquet extension."""
        return service.get_video_metadata(session_id)

    @mcp.tool()
    def get_spike_metadata(session_id: str, probe: str | None = None) -> dict[str, Any]:
        """Return spike, cluster, and insertion metadata for a session/probe."""
        return service.get_spike_metadata(session_id, probe=probe)

    @mcp.tool()
    def get_spike_times(session_id: str, probe: str | None = None) -> dict[str, Any]:
        """Return spike metadata and exact spike dataset records; use align_spikes_to_events for counts."""
        return service.get_spike_metadata(session_id, probe=probe)

    @mcp.tool()
    def get_cluster_qc(session_id: str, probe: str | None = None) -> dict[str, Any]:
        """Load cluster QC arrays where available and summarize good-unit/region counts."""
        return service.get_cluster_qc(session_id, probe=probe)

    @mcp.tool()
    def align_behavior_to_events(
        session_id: str,
        signal: str,
        event: str = "stim_on_times",
        window_start: float = -0.5,
        window_end: float = 1.0,
        max_events: int = 100,
    ) -> dict[str, Any]:
        """Align wheel position or licks to trial events such as stim_on_times or feedback_times."""
        return service.align_behavior_to_events(session_id, signal=signal, event=event, window=(window_start, window_end), max_events=max_events)

    @mcp.tool()
    def align_spikes_to_events(
        session_id: str,
        event: str = "stim_on_times",
        window_start: float = -0.2,
        window_end: float = 0.5,
        probe: str | None = None,
        max_events: int = 100,
    ) -> dict[str, Any]:
        """Count spikes in peri-event windows, optionally filtered by probe collection."""
        return service.align_spikes_to_events(session_id, event=event, window=(window_start, window_end), probe=probe, max_events=max_events)

    @mcp.tool()
    def find_similar_sessions(query: str, limit: int = 10) -> dict[str, Any]:
        """Semantic scaffold for finding sessions via ontology/publication terms; live embeddings are planned."""
        return service.semantic_search(query, limit=limit)

    @mcp.tool()
    def semantic_search(query: str, limit: int = 10) -> dict[str, Any]:
        """Search the local IBL ontology/publication semantic index."""
        return service.semantic_search(query, limit=limit)

    @mcp.tool()
    def get_related_papers(query: str = "", project: str = "", dataset_type: str = "") -> dict[str, Any]:
        """Return IBL publications related to a project, dataset type, modality, or topic."""
        return service.get_related_papers(query=query, project=project, dataset_type=dataset_type)

    @mcp.tool()
    def get_dataset_papers(dataset_id: str, include_session_context: bool = True) -> dict[str, Any]:
        """Infer IBL publications associated with a concrete Alyx dataset record."""
        return service.get_dataset_papers(dataset_id, include_session_context=include_session_context)

    @mcp.tool()
    def resolve_dataset_papers(
        dataset_id: str,
        version_or_tag: str = "latest",
        include_citation_graph: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Resolve IBL dataset/session paper links through real public literature APIs."""
        del version_or_tag, include_citation_graph
        return literature.resolve_papers(
            dataset_id,
            _ibl_paper_hints(service, dataset_id),
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
        """Query IBL-associated papers and escalate to full text when uncertainty is high."""
        del version_or_tag
        context = _safe_call(lambda: client.get_dataset(dataset_id), default={})
        return literature.query_papers(
            dataset_id=dataset_id,
            question=question,
            paper_hints=_ibl_paper_hints(service, dataset_id),
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
        """Explain an IBL/ALF variable using metadata, papers, and uncertainty-aware full text."""
        del object_path, version_or_tag
        variable_context = _ibl_variable_context(
            local,
            client,
            dataset_key_or_id,
            variable,
            file_path=file_path,
            context=context,
        )
        return literature.explain_variable(
            dataset_id=dataset_key_or_id,
            variable=variable,
            variable_context=variable_context,
            paper_hints=_ibl_paper_hints(service, dataset_key_or_id),
            full_text_policy=full_text_policy,
        )

    @mcp.tool()
    def register_paper_pdf(
        dataset_id: str,
        pdf_path: str,
        doi: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Register a user-provided PDF for an IBL dataset/session and index it for future explanations."""
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
    ) -> dict[str, Any]:
        """Generate a static HTML explorer for an IBL/ALF dataset and its variables."""
        del version_or_tag
        summary, variables = _ibl_explorer_data(local, client, dataset_key_or_id)
        papers = (
            literature.resolve_papers(dataset_key_or_id, _ibl_paper_hints(service, dataset_key_or_id)).get("papers", [])
            if include_papers
            else []
        )
        explorer_id = stable_variable_id(dataset_key_or_id, {"kind": "explorer"}, "dataset")
        artifact_dir = client.storage.config.provider_dir / "artifacts" / dataset_key_or_id.replace("/", "_").replace(":", "_")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        html_path = artifact_dir / "dataset-explorer.html"
        html_path.write_text(
            build_dataset_explorer_html(
                provider="ibl",
                dataset_id=dataset_key_or_id,
                title=str(summary.get("name") or summary.get("session_id") or dataset_key_or_id),
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
            "summary": {
                "variable_count": len(variables),
                "paper_count": len(papers),
                "missing_pdf_count": len(literature.list_missing_pdfs(dataset_key_or_id).get("missing_pdfs", [])),
            },
        }
        client.storage.upsert_record("dataset_explorer", explorer_id, result, source="neurodata_literature")
        return result

    @mcp.tool()
    def explain_visual_dataset_selection(
        explorer_id: str,
        variable_id: str,
        question: str | None = None,
        full_text_policy: str = "auto",
    ) -> dict[str, Any]:
        """Return guidance for explaining a variable selected in a generated IBL explorer."""
        return {
            "explorer_id": explorer_id,
            "variable_id": variable_id,
            "question": question,
            "next_action": "Call explain_dataset_variable with the dataset/session id, variable name, and file_path shown in the explorer row.",
            "full_text_policy": full_text_policy,
        }

    @mcp.tool()
    def get_associated_code(query: str = "", project: str = "") -> dict[str, Any]:
        """Return IBL code repositories associated with publications/projects/topics."""
        return service.get_associated_code(query=query, project=project)

    @mcp.tool()
    def query_knowledge_graph(
        entity_type: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Query the local IBL knowledge graph scaffold over modalities, papers, code, and dataset patterns."""
        return service.query_knowledge_graph(entity_type=entity_type, predicate=predicate, value=value, limit=limit)

    @mcp.tool()
    def list_revisions(
        dataset: str | None = None,
        session: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List Alyx revision records for datasets/sessions when exposed by the server."""
        return client.list_revisions(dataset=dataset, session=session, page=page, page_size=page_size)

    @mcp.tool()
    def list_downloads(
        dataset: str | None = None,
        session: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List Alyx download records when exposed by the server."""
        return client.list_downloads(dataset=dataset, session=session, page=page, page_size=page_size)

    @mcp.tool()
    def list_tasks(
        session: str | None = None,
        lab: str | None = None,
        name: str | None = None,
        status: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """List Alyx task records for pipeline/QC diagnostics."""
        return client.list_tasks(session=session, lab=lab, name=name, status=status, django=django, page=page, page_size=page_size)

    @mcp.tool()
    def get_cache_info() -> dict[str, Any]:
        """Inspect public ONE cache metadata advertised by Alyx."""
        return client.get_cache_info()

    @mcp.tool()
    def get_cache_zip_url() -> dict[str, Any]:
        """Return the cache.zip URL/redirect used by ONE for local cache workflows."""
        return client.get_cache_zip_url()

    @mcp.tool()
    def call_alyx_api(
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        allow_mutation: bool = False,
    ) -> dict[str, Any] | list[Any]:
        """Call any Alyx REST path. Mutating methods require allow_mutation=True."""
        return client.call_alyx_api(method, path, query=query, body=body, allow_mutation=allow_mutation)

    @mcp.tool()
    def confirmed_mutating_alyx_api(
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        confirm: bool = False,
    ) -> dict[str, Any] | list[Any]:
        """Authenticated Alyx mutation escape hatch, blocked unless confirm=True."""
        if not confirm:
            return {
                "blocked": True,
                "reason": "This can change Alyx state. Re-run with confirm=True intentionally.",
                "method": method,
                "path": path,
            }
        return client.call_alyx_api(method, path, query=query, body=body, allow_mutation=True)

    @mcp.resource("ibl://endpoints")
    def endpoints_resource() -> dict[str, Any]:
        """All advertised Alyx REST endpoints."""
        return client.list_endpoints()

    @mcp.resource("ibl://sessions")
    def sessions_resource() -> dict[str, Any] | list[Any]:
        """First page/list of public IBL sessions."""
        return client.list_sessions(page_size=25)

    @mcp.resource("ibl://session/{session_id}")
    def session_resource(session_id: str) -> dict[str, Any]:
        """One IBL session."""
        return client.get_session(session_id)

    @mcp.resource("ibl://session/{session_id}/datasets")
    def session_datasets_resource(session_id: str) -> dict[str, Any] | list[Any]:
        """Datasets for one IBL session."""
        return client.list_datasets(session=session_id, exists=True, page_size=100)

    @mcp.resource("ibl://session/{session_id}/insertions")
    def session_insertions_resource(session_id: str) -> dict[str, Any] | list[Any]:
        """Probe insertions for one session."""
        return client.list_insertions(session=session_id)

    @mcp.resource("ibl://dataset/{dataset_id}")
    def dataset_resource(dataset_id: str) -> dict[str, Any]:
        """One dataset record."""
        return client.get_dataset(dataset_id)

    @mcp.resource("ibl://cache")
    def cache_resource() -> dict[str, Any]:
        """ONE cache metadata."""
        return client.get_cache_info()

    @mcp.prompt(title="Find IBL Data")
    def find_ibl_data(topic: str, species_or_subject: str = "", modality: str = "") -> str:
        """Guide an agent through finding IBL sessions and datasets."""
        constraints = ", ".join(part for part in [species_or_subject, modality] if part) or "no extra constraints"
        return (
            f"Find International Brain Laboratory data about {topic}; constraints: {constraints}.\n"
            "First use list_alyx_endpoints if you need to inspect the live surface. Search sessions "
            "with search_sessions using project, task_protocol, date_range, atlas_acronym, brain_region, "
            "datasets, dataset_types, or django filters. Then call summarize_session on promising eIDs. "
            "Use list_datasets and list_files to identify exact dataset UUIDs, collections, names, sizes, "
            "and object-store URLs before recommending downloads."
        )

    @mcp.prompt(title="Download IBL Dataset")
    def download_ibl_dataset(session_id: str, dataset_hint: str = "") -> str:
        """Guide an agent through a careful download workflow."""
        hint = dataset_hint or "the dataset requested by the user"
        return (
            f"Download {hint} from IBL session {session_id}.\n"
            "Use list_datasets(session=...) with name, collection, dataset_type, tag, or django filters. "
            "Read the chosen dataset with get_dataset, resolve file URLs with get_dataset_download_urls, "
            "and only then call download_url for explicit URLs that match the user's goal. Report local "
            "paths, byte counts, dataset UUIDs, and any missing files or absent URLs."
        )

    @mcp.prompt(title="Explain IBL Session")
    def explain_ibl_session(session_id: str, research_question: str = "") -> str:
        """Guide an agent through explaining a session for analysis reuse."""
        question = research_question or "the user's analysis goal"
        return (
            f"Explain IBL session {session_id} for {question}.\n"
            "Use summarize_session, then inspect datasets, insertions, trajectories, and channels as needed. "
            "Explain subject/lab/date/task protocol, available modalities, QC where present, relevant datasets, "
            "and exact next calls needed to load or download the data."
        )

    return mcp


def _client_from_env() -> IBLClient:
    storage = MCPStorage.from_env("ibl")
    download_dir = Path(os.environ.get("IBL_MCP_DOWNLOAD_DIR", str(storage.config.downloads_dir)))
    config = IBLClientConfig(
        alyx_base_url=os.environ.get("IBL_ALYX_BASE_URL", DEFAULT_ALYX_BASE_URL),
        timeout=float(os.environ.get("IBL_ALYX_TIMEOUT", "45")),
        username=os.environ.get("IBL_ALYX_USERNAME", DEFAULT_PUBLIC_USERNAME),
        password=os.environ.get("IBL_ALYX_PASSWORD", DEFAULT_PUBLIC_PASSWORD),
        token=os.environ.get("IBL_ALYX_TOKEN"),
        download_dir=download_dir,
        storage=storage,
    )
    return IBLClient(config)


def _safe_call(call: Any, default: Any = None) -> Any:
    try:
        return call()
    except Exception:
        return default


def _ibl_paper_hints(service: IBLDomainService, dataset_id: str) -> list[Any]:
    hints: list[Any] = []
    related = _safe_call(lambda: service.get_dataset_papers(dataset_id), default={})
    data = related.get("data", related) if isinstance(related, dict) else {}
    hints.extend(data.get("papers", []) if isinstance(data, dict) else [])
    hints.extend([data.get("project"), data.get("dataset_type"), data.get("query_terms")] if isinstance(data, dict) else [])
    if not hints:
        fallback = _safe_call(lambda: service.get_related_papers(query=dataset_id), default={})
        fallback_data = fallback.get("data", fallback) if isinstance(fallback, dict) else {}
        hints.extend(fallback_data.get("papers", []) if isinstance(fallback_data, dict) else [])
    return [hint for hint in hints if hint]


def _ibl_variable_context(
    local: LocalIBLExplorer,
    client: IBLClient,
    dataset_key_or_id: str,
    variable: str,
    *,
    file_path: str | None,
    context: str | None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "provider": "ibl",
        "dataset_id": dataset_key_or_id,
        "variable": variable,
        "file_path": file_path,
        "user_context": context,
    }
    inventory = _safe_call(lambda: local.signal_inventory(dataset_key_or_id), default={})
    for signal in inventory.get("signals", []) if isinstance(inventory, dict) else []:
        text = " ".join(str(signal.get(key, "")) for key in ["file", "collection", "alf_object", "alf_attribute", "modality"])
        if (file_path and signal.get("file") == file_path) or variable.lower() in text.lower():
            ctx.update(signal)
            ctx["kind"] = "alf_variable"
            return ctx
    dataset = _safe_call(lambda: client.get_dataset(dataset_key_or_id), default={})
    if dataset:
        ctx.update(
            {
                "name": dataset.get("name"),
                "collection": dataset.get("collection"),
                "dataset_type": dataset.get("dataset_type"),
                "session": dataset.get("session"),
            }
        )
    return ctx


def _ibl_explorer_data(
    local: LocalIBLExplorer,
    client: IBLClient,
    dataset_key_or_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = _safe_call(lambda: local.summarize(dataset_key_or_id), default={})
    variables = []
    inventory = _safe_call(lambda: local.signal_inventory(dataset_key_or_id), default={})
    for signal in inventory.get("signals", []) if isinstance(inventory, dict) else []:
        name = ".".join(part for part in [signal.get("alf_object"), signal.get("alf_attribute")] if part)
        variables.append({"provider": "ibl", "name": name, "confidence_label": "low", **signal})
    if not summary:
        dataset = _safe_call(lambda: client.get_dataset(dataset_key_or_id), default={})
        summary = dataset or {"name": dataset_key_or_id}
        if dataset:
            variables.append(
                {
                    "provider": "ibl",
                    "kind": "alyx_dataset",
                    "name": dataset.get("name") or dataset_key_or_id,
                    "collection": dataset.get("collection"),
                    "dataset_type": dataset.get("dataset_type"),
                    "confidence_label": "low",
                }
            )
    return summary, variables


mcp = build_server()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
