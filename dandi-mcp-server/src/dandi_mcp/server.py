from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from dandi_mcp import __version__
from dandi_mcp.client import DEFAULT_API_BASE_URL, DandiClient, DandiClientConfig
from dandi_mcp.local_explorer import LocalDandisetExplorer
from neurodata_literature import LiteratureService, build_dataset_explorer_html, stable_variable_id


def build_server() -> FastMCP:
    mcp = FastMCP(
        "DANDI Archive",
        instructions=(
            "Neuroscience data infrastructure for DANDI Archive datasets. Provides "
            "DANDI API access plus semantic discovery, neuroscience metadata "
            "extraction, behavioral paradigm hints, literature linkage, and "
            "knowledge-graph shaped outputs for AI agents."
        ),
        json_response=True,
    )
    client = _client_from_env()
    local = LocalDandisetExplorer(client.storage)
    literature = LiteratureService(client.storage, "dandi")

    @mcp.tool()
    def get_storage_info() -> dict[str, Any]:
        """Return the standardized local storage paths and schema for this MCP server."""
        return client.storage.describe()

    @mcp.tool()
    def register_local_dandiset(
        path: str | None = None,
        dandiset_id: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Register a downloaded local Dandiset by path or by DANDI id if it can be found locally."""
        return local.register(path=path, dandiset_id=dandiset_id, version=version)

    @mcp.tool()
    def register_local_dataset(
        path: str | None = None,
        dataset_id: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Provider-compatible alias for registering a downloaded local DANDI dataset."""
        return local.register(path=path, dandiset_id=dataset_id, version=version)

    @mcp.tool()
    def list_local_dandisets() -> dict[str, Any]:
        """List downloaded Dandisets registered with the local analysis engine."""
        return local.list_registered()

    @mcp.tool()
    def list_local_datasets() -> dict[str, Any]:
        """Provider-compatible alias for listing registered downloaded DANDI datasets."""
        return local.list_registered()

    @mcp.tool()
    def summarize_local_dandiset(dataset_key: str = "") -> dict[str, Any]:
        """Summarize a registered local Dandiset, including file types, subjects, and index status."""
        return local.summarize(dataset_key)

    @mcp.tool()
    def summarize_local_dataset(dataset_key: str = "") -> dict[str, Any]:
        """Provider-compatible alias for summarizing a registered local DANDI dataset."""
        return local.summarize(dataset_key)

    @mcp.tool()
    def browse_local_dandiset(dataset_key: str = "", path_prefix: str = "") -> dict[str, Any]:
        """Browse direct child files and folders inside a registered local Dandiset."""
        return local.browse(dataset_key, path_prefix=path_prefix)

    @mcp.tool()
    def browse_local_dataset(dataset_key: str = "", path_prefix: str = "") -> dict[str, Any]:
        """Provider-compatible alias for browsing a registered local DANDI dataset."""
        return local.browse(dataset_key, path_prefix=path_prefix)

    @mcp.tool()
    def list_local_files(
        dataset_key: str = "",
        glob: str | None = None,
        file_type: str | None = None,
        subject: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List local Dandiset files with optional glob, type, and subject filters."""
        return local.list_files(
            dataset_key,
            glob=glob,
            file_type=file_type,
            subject=subject,
            limit=limit,
        )

    @mcp.tool()
    def inspect_nwb_file(dataset_key: str = "", path: str = "") -> dict[str, Any]:
        """Lazily inspect a local NWB file and summarize subjects, modules, tables, and signals."""
        return local.inspect_nwb(dataset_key, path)

    @mcp.tool()
    def validate_nwb_file(dataset_key: str = "", path: str = "", limit: int = 100) -> dict[str, Any]:
        """Run NWBInspector on a local NWB file and return bounded validation messages."""
        return local.validate_nwb(dataset_key, path, limit=limit)

    @mcp.tool()
    def index_local_dandiset(dataset_key: str = "", inspect_limit: int = 100) -> dict[str, Any]:
        """Inspect local NWB files and build a cross-file subject/session/signal/trial index."""
        return local.index(dataset_key, inspect_limit=inspect_limit)

    @mcp.tool()
    def index_local_dataset(dataset_key: str = "", inspect_limit: int = 100) -> dict[str, Any]:
        """Provider-compatible alias for indexing a registered local DANDI dataset."""
        return local.index(dataset_key, inspect_limit=inspect_limit)

    @mcp.tool()
    def get_dataset_subjects(dataset_key: str = "") -> dict[str, Any]:
        """Return detected subjects for a registered local Dandiset."""
        return local.subjects(dataset_key)

    @mcp.tool()
    def get_dataset_sessions(dataset_key: str = "") -> dict[str, Any]:
        """Return detected sessions/files for a registered local Dandiset."""
        return local.sessions(dataset_key)

    @mcp.tool()
    def get_dataset_signal_inventory(dataset_key: str = "") -> dict[str, Any]:
        """Return analysis-ready local NWB signal inventory with object paths, shapes, rates, and units."""
        return local.signal_inventory(dataset_key)

    @mcp.tool()
    def extract_trials_table(dataset_key: str = "", path: str = "", limit: int = 1000) -> dict[str, Any]:
        """Extract a bounded preview of a local NWB trials table, when present."""
        return local.extract_trials(dataset_key, path, limit=limit)

    @mcp.tool()
    def generate_dataset_report(dataset_key: str = "") -> dict[str, Any]:
        """Generate a Markdown report for a registered local Dandiset under MCP artifact storage."""
        return local.report(dataset_key)

    @mcp.tool()
    def search_dandisets(
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
        ordering: str = "-modified",
        draft: bool = True,
        empty: bool = False,
        embargoed: bool = False,
    ) -> dict[str, Any]:
        """Search or list DANDI Dandisets with pagination and archive ordering."""
        return client.search_dandisets(
            search=search,
            page=page,
            page_size=page_size,
            ordering=ordering,
            draft=draft,
            empty=empty,
            embargoed=embargoed,
        )

    @mcp.tool()
    def get_dandiset(dandiset_id: str) -> dict[str, Any]:
        """Fetch the Dandiset record with draft and recent published version summaries."""
        return client.get_dandiset(dandiset_id)

    @mcp.tool()
    def list_dandiset_versions(
        dandiset_id: str,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """List draft and published versions for a Dandiset."""
        return client.list_versions(dandiset_id, page=page, page_size=page_size)

    @mcp.tool()
    def get_dandiset_version_metadata(dandiset_id: str, version: str = "draft") -> dict[str, Any]:
        """Fetch full DANDI schema metadata for a specific Dandiset version."""
        return client.get_version_metadata(dandiset_id, version)

    @mcp.tool()
    def list_assets(
        dandiset_id: str,
        version: str = "draft",
        path: str | None = None,
        glob: str | None = None,
        metadata: bool = False,
        zarr: bool = False,
        page: int = 1,
        page_size: int = 50,
        order: str | None = None,
    ) -> dict[str, Any]:
        """List assets in a Dandiset version with optional path, glob, metadata, and zarr filters."""
        return client.list_assets(
            dandiset_id,
            version,
            path=path,
            glob=glob,
            metadata=metadata,
            zarr=zarr,
            page=page,
            page_size=page_size,
            order=order,
        )

    @mcp.tool()
    def list_asset_paths(
        dandiset_id: str,
        version: str = "draft",
        path_prefix: str = "",
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Browse direct child files and folders under a Dandiset path prefix."""
        return client.list_asset_paths(
            dandiset_id,
            version,
            path_prefix=path_prefix,
            page=page,
            page_size=page_size,
        )

    @mcp.tool()
    def get_asset_metadata(asset_id: str) -> dict[str, Any]:
        """Fetch public metadata for a DANDI asset UUID."""
        return client.get_asset_metadata(asset_id)

    @mcp.tool()
    def get_asset_info_by_id(asset_id: str) -> dict[str, Any]:
        """Fetch Django-serialized asset information by global asset UUID."""
        return client.get_asset_info_by_id(asset_id)

    @mcp.tool()
    def get_asset_info(dandiset_id: str, version: str, asset_id: str) -> dict[str, Any]:
        """Fetch version-scoped detailed asset information for a DANDI asset UUID."""
        return client.get_asset_info(dandiset_id, version, asset_id)

    @mcp.tool()
    def get_version_asset_metadata(
        dandiset_id: str, version: str, asset_id: str
    ) -> dict[str, Any]:
        """Fetch version-scoped asset metadata for a DANDI asset UUID."""
        return client.get_version_asset_metadata(dandiset_id, version, asset_id)

    @mcp.tool()
    def get_asset_validation(dandiset_id: str, version: str, asset_id: str) -> dict[str, Any]:
        """Fetch validation errors or validation state for an asset in a version."""
        return client.get_asset_validation(dandiset_id, version, asset_id)

    @mcp.tool()
    def get_asset_download_url(
        asset_id: str,
        content_disposition: str = "attachment",
    ) -> dict[str, Any]:
        """Return a time-limited object-store URL for downloading an asset."""
        return client.get_asset_download_url(asset_id, content_disposition=content_disposition)

    @mcp.tool()
    def get_version_asset_download_url(
        dandiset_id: str,
        version: str,
        asset_id: str,
    ) -> dict[str, Any]:
        """Return a time-limited download URL for an asset scoped to a Dandiset version."""
        return client.get_version_asset_download_url(dandiset_id, version, asset_id)

    @mcp.tool()
    def get_dandiset_version_info(dandiset_id: str, version: str = "draft") -> dict[str, Any]:
        """Fetch Django-serialized information for a Dandiset version."""
        return client.get_version_info(dandiset_id, version)

    @mcp.tool()
    def list_dandiset_uploads(
        dandiset_id: str,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """List active or incomplete uploads in a Dandiset. Usually requires ownership/auth."""
        return client.list_uploads(dandiset_id, page=page, page_size=page_size)

    @mcp.tool()
    def list_dandiset_users(dandiset_id: str) -> dict[str, Any]:
        """List owners/users for a Dandiset. May require authentication depending on archive policy."""
        return client.list_dandiset_users(dandiset_id)

    @mcp.tool()
    def get_archive_info() -> dict[str, Any]:
        """Fetch DANDI archive service information."""
        return client.get_archive_info()

    @mcp.tool()
    def get_archive_stats() -> dict[str, Any]:
        """Fetch archive-wide DANDI statistics."""
        return client.get_stats()

    @mcp.tool()
    def get_schema(model: str) -> dict[str, Any]:
        """Fetch a DANDI schema model: Dandiset, Asset, PublishedDandiset, or PublishedAsset."""
        return client.list_schemas(model)

    @mcp.tool()
    def list_available_schemas() -> dict[str, Any]:
        """List DANDI schema models available from the API."""
        return client.list_available_schemas()

    @mcp.tool()
    def list_users(approved_only: bool = False) -> dict[str, Any]:
        """List registered DANDI users. Availability depends on archive policy/auth."""
        return client.list_users(approved_only=approved_only)

    @mcp.tool()
    def get_current_user() -> dict[str, Any]:
        """Fetch the authenticated DANDI user for DANDI_API_TOKEN."""
        return client.get_current_user()

    @mcp.tool()
    def get_user_questionnaire_form() -> dict[str, Any]:
        """Fetch the DANDI user questionnaire form definition."""
        return client.get_user_questionnaire_form()

    @mcp.tool()
    def search_users(username: str) -> dict[str, Any]:
        """Search DANDI users by username."""
        return client.search_users(username)

    @mcp.tool()
    def list_zarr_archives(
        page: int = 1,
        page_size: int = 25,
        dandiset: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """List DANDI Zarr archives, optionally filtered by Dandiset or name."""
        return client.list_zarr_archives(page=page, page_size=page_size, dandiset=dandiset, name=name)

    @mcp.tool()
    def get_zarr_archive(zarr_id: str) -> dict[str, Any]:
        """Fetch metadata for a DANDI Zarr archive."""
        return client.get_zarr_archive(zarr_id)

    @mcp.tool()
    def list_zarr_files(
        zarr_id: str,
        after: str = "",
        prefix: str = "",
        limit: int = 1000,
        download: bool = False,
    ) -> dict[str, Any]:
        """List files in a DANDI Zarr archive, optionally returning download URLs."""
        return client.list_zarr_files(
            zarr_id, after=after, prefix=prefix, limit=limit, download=download
        )

    @mcp.tool()
    def get_auth_token() -> dict[str, Any]:
        """Fetch token information for the configured DANDI_API_TOKEN, if authenticated."""
        return client.get_auth_token()

    @mcp.tool()
    def call_dandi_api(
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        allow_mutation: bool = False,
    ) -> dict[str, Any]:
        """Call any DANDI API path. Non-GET calls require allow_mutation=True and DANDI_API_TOKEN."""
        return client.call_api(
            method,
            path,
            query=query,
            body=body,
            allow_mutation=allow_mutation,
        )

    def _mutating(
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not confirm:
            return {
                "blocked": True,
                "reason": "This DANDI operation can change archive state or requires auth. Re-run with confirm=True intentionally.",
                "method": method,
                "path": path,
            }
        return client.call_api(method, path, query=query, body=body, allow_mutation=True)

    @mcp.tool()
    def create_auth_token(confirm: bool = False) -> dict[str, Any]:
        """Create a DANDI auth token using the configured authenticated session. Requires confirm=True."""
        return _mutating("POST", "auth/token/", confirm=confirm)

    @mcp.tool()
    def lookup_blob_by_digest(digest: dict[str, Any], confirm: bool = False) -> dict[str, Any]:
        """Fetch an existing asset blob by digest. Requires confirm=True because the API exposes it as POST."""
        return _mutating("POST", "blobs/digest/", body=digest, confirm=confirm)

    @mcp.tool()
    def create_dandiset(
        metadata: dict[str, Any],
        embargo: bool = False,
        funding_source: str | None = None,
        award_number: str | None = None,
        embargo_end_date: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Create a Dandiset. Requires ownership/auth and confirm=True."""
        query: dict[str, Any] = {"embargo": embargo}
        if funding_source:
            query["funding_source"] = funding_source
        if award_number:
            query["award_number"] = award_number
        if embargo_end_date:
            query["embargo_end_date"] = embargo_end_date
        return _mutating("POST", "dandisets/", query=query, body=metadata, confirm=confirm)

    @mcp.tool()
    def delete_dandiset(dandiset_id: str, confirm: bool = False) -> dict[str, Any]:
        """Delete a Dandiset. Requires ownership/auth and confirm=True."""
        return _mutating("DELETE", f"dandisets/{dandiset_id}/", confirm=confirm)

    @mcp.tool()
    def star_dandiset(dandiset_id: str, confirm: bool = False) -> dict[str, Any]:
        """Star a Dandiset for the authenticated user. Requires confirm=True."""
        return _mutating("POST", f"dandisets/{dandiset_id}/star/", confirm=confirm)

    @mcp.tool()
    def unstar_dandiset(dandiset_id: str, confirm: bool = False) -> dict[str, Any]:
        """Unstar a Dandiset for the authenticated user. Requires confirm=True."""
        return _mutating("DELETE", f"dandisets/{dandiset_id}/star/", confirm=confirm)

    @mcp.tool()
    def unembargo_dandiset(dandiset_id: str, confirm: bool = False) -> dict[str, Any]:
        """Unembargo a Dandiset. Requires ownership/auth and confirm=True."""
        return _mutating("POST", f"dandisets/{dandiset_id}/unembargo/", confirm=confirm)

    @mcp.tool()
    def delete_dandiset_uploads(dandiset_id: str, confirm: bool = False) -> dict[str, Any]:
        """Delete all active/incomplete uploads in a Dandiset. Requires ownership/auth and confirm=True."""
        return _mutating("DELETE", f"dandisets/{dandiset_id}/uploads/", confirm=confirm)

    @mcp.tool()
    def set_dandiset_users(
        dandiset_id: str, users: dict[str, Any], confirm: bool = False
    ) -> dict[str, Any]:
        """Set owners/users for a Dandiset. Requires ownership/auth and confirm=True."""
        return _mutating("PUT", f"dandisets/{dandiset_id}/users/", body=users, confirm=confirm)

    @mcp.tool()
    def update_dandiset_version_metadata(
        dandiset_id: str,
        version: str,
        metadata: dict[str, Any],
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Update Dandiset version metadata. Requires ownership/auth and confirm=True."""
        return _mutating(
            "PUT",
            f"dandisets/{dandiset_id}/versions/{version}/",
            body=metadata,
            confirm=confirm,
        )

    @mcp.tool()
    def delete_dandiset_version(
        dandiset_id: str, version: str, confirm: bool = False
    ) -> dict[str, Any]:
        """Delete a Dandiset version. Requires ownership/auth and confirm=True."""
        return _mutating("DELETE", f"dandisets/{dandiset_id}/versions/{version}/", confirm=confirm)

    @mcp.tool()
    def publish_dandiset_version(
        dandiset_id: str, version: str = "draft", confirm: bool = False
    ) -> dict[str, Any]:
        """Publish a Dandiset version. Requires ownership/auth and confirm=True."""
        return _mutating(
            "POST", f"dandisets/{dandiset_id}/versions/{version}/publish/", confirm=confirm
        )

    @mcp.tool()
    def create_version_asset(
        dandiset_id: str,
        version: str,
        asset_request: dict[str, Any],
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Create an asset in a Dandiset version. Requires ownership/auth and confirm=True."""
        return _mutating(
            "POST",
            f"dandisets/{dandiset_id}/versions/{version}/assets/",
            body=asset_request,
            confirm=confirm,
        )

    @mcp.tool()
    def update_version_asset(
        dandiset_id: str,
        version: str,
        asset_id: str,
        asset_request: dict[str, Any],
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Update asset metadata in a Dandiset version. Requires ownership/auth and confirm=True."""
        return _mutating(
            "PUT",
            f"dandisets/{dandiset_id}/versions/{version}/assets/{asset_id}/",
            body=asset_request,
            confirm=confirm,
        )

    @mcp.tool()
    def delete_version_asset(
        dandiset_id: str, version: str, asset_id: str, confirm: bool = False
    ) -> dict[str, Any]:
        """Remove an asset from a Dandiset version. Requires ownership/auth and confirm=True."""
        return _mutating(
            "DELETE",
            f"dandisets/{dandiset_id}/versions/{version}/assets/{asset_id}/",
            confirm=confirm,
        )

    @mcp.tool()
    def initialize_upload(upload_request: dict[str, Any], confirm: bool = False) -> dict[str, Any]:
        """Initialize a multipart upload. Requires auth and confirm=True."""
        return _mutating("POST", "uploads/initialize/", body=upload_request, confirm=confirm)

    @mcp.tool()
    def complete_upload(
        upload_id: str, completion_request: dict[str, Any], confirm: bool = False
    ) -> dict[str, Any]:
        """Complete a multipart upload. Requires auth and confirm=True."""
        return _mutating(
            "POST", f"uploads/{upload_id}/complete/", body=completion_request, confirm=confirm
        )

    @mcp.tool()
    def validate_upload(upload_id: str, confirm: bool = False) -> dict[str, Any]:
        """Validate a completed upload and mint an AssetBlob. Requires auth and confirm=True."""
        return _mutating("POST", f"uploads/{upload_id}/validate/", confirm=confirm)

    @mcp.tool()
    def submit_user_questionnaire(confirm: bool = False) -> dict[str, Any]:
        """Submit the DANDI questionnaire form. Requires auth and confirm=True."""
        return _mutating("POST", "users/questionnaire-form/", confirm=confirm)

    @mcp.tool()
    def create_zarr_archive(zarr: dict[str, Any], confirm: bool = False) -> dict[str, Any]:
        """Create a DANDI Zarr archive. Requires auth and confirm=True."""
        return _mutating("POST", "zarr/", body=zarr, confirm=confirm)

    @mcp.tool()
    def request_zarr_file_uploads(
        zarr_id: str, zarr_file_creation: dict[str, Any], confirm: bool = False
    ) -> dict[str, Any]:
        """Request upload URLs/files for a Zarr archive. Requires auth and confirm=True."""
        return _mutating(
            "POST", f"zarr/{zarr_id}/files/", body=zarr_file_creation, confirm=confirm
        )

    @mcp.tool()
    def delete_zarr_files(
        zarr_id: str, deletion_request: dict[str, Any], confirm: bool = False
    ) -> dict[str, Any]:
        """Delete files from a Zarr archive. Requires auth and confirm=True."""
        return _mutating(
            "DELETE", f"zarr/{zarr_id}/files/", body=deletion_request, confirm=confirm
        )

    @mcp.tool()
    def finalize_zarr_archive(zarr_id: str, confirm: bool = False) -> dict[str, Any]:
        """Finalize a Zarr archive and dispatch checksum computation. Requires auth and confirm=True."""
        return _mutating("POST", f"zarr/{zarr_id}/finalize/", confirm=confirm)

    @mcp.tool()
    def summarize_dandiset(
        dandiset_id: str,
        version: str = "draft",
        sample_assets: int = 10,
    ) -> dict[str, Any]:
        """Return compact version metadata and a small sample of assets for agent orientation."""
        return client.summarize_dandiset(dandiset_id, version, sample_assets=sample_assets)

    @mcp.tool()
    def semantic_search_dandisets(
        query: str,
        search: str | None = None,
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search DANDI with local lexical/ontology semantic reranking for neuroscience queries."""
        return client.semantic_search_dandisets(
            query,
            search=search,
            candidate_count=candidate_count,
            limit=limit,
        )

    @mcp.tool()
    def search_datasets(
        query: str,
        species: str = "",
        modality: str = "",
        behavior: str = "",
        brain_region: str = "",
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Agent-first dataset search across topic, species, modality, behavior, and brain region terms."""
        semantic_query = " ".join(
            part for part in [query, species, modality, behavior, brain_region] if part
        )
        return client.semantic_search_dandisets(
            semantic_query,
            search=query,
            candidate_count=candidate_count,
            limit=limit,
        )

    @mcp.tool()
    def analyze_dandiset_neuroscience(
        dandiset_id: str,
        version: str = "draft",
        sample_assets: int = 100,
    ) -> dict[str, Any]:
        """Extract species, modalities, behaviors, brain regions, paper links, and NWB path hints."""
        return client.analyze_dandiset_neuroscience(
            dandiset_id,
            version,
            sample_assets=sample_assets,
        )

    @mcp.tool()
    def get_related_papers(dandiset_id: str, version: str = "draft") -> dict[str, Any]:
        """Extract DOI, PubMed, Semantic Scholar, GitHub, protocols.io, and relatedResource links."""
        return client.get_related_papers(dandiset_id, version)

    @mcp.tool()
    def get_dataset_papers(dataset_id: str, version: str = "draft") -> dict[str, Any]:
        """Provider-compatible alias for papers and literature links associated with a DANDI dataset."""
        return client.get_related_papers(dataset_id, version)

    @mcp.tool()
    def resolve_dataset_papers(
        dataset_id: str,
        version_or_tag: str = "draft",
        include_citation_graph: bool = False,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Resolve DANDI dataset paper links through real public literature APIs."""
        del include_citation_graph
        return literature.resolve_papers(
            dataset_id,
            _dandi_paper_hints(client, dataset_id, version_or_tag),
            limit=limit,
            relationship="dataset",
        )

    @mcp.tool()
    def query_dataset_papers(
        dataset_id: str,
        question: str,
        version_or_tag: str = "draft",
        full_text_policy: str = "auto",
        limit: int = 8,
    ) -> dict[str, Any]:
        """Query DANDI-associated papers and escalate to full text when uncertainty is high."""
        context = _safe_call(lambda: client.summarize_dandiset(dataset_id, version_or_tag), default={})
        return literature.query_papers(
            dataset_id=dataset_id,
            question=question,
            paper_hints=_dandi_paper_hints(client, dataset_id, version_or_tag),
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
        version_or_tag: str = "draft",
        full_text_policy: str = "auto",
    ) -> dict[str, Any]:
        """Explain an NWB/DANDI variable using local metadata, papers, and uncertainty-aware full text."""
        variable_context = _dandi_variable_context(
            local,
            client,
            dataset_key_or_id,
            variable,
            file_path=file_path,
            object_path=object_path,
            context=context,
            version=version_or_tag,
        )
        return literature.explain_variable(
            dataset_id=dataset_key_or_id,
            variable=variable,
            variable_context=variable_context,
            paper_hints=_dandi_paper_hints(client, dataset_key_or_id, version_or_tag),
            full_text_policy=full_text_policy,
        )

    @mcp.tool()
    def register_paper_pdf(
        dataset_id: str,
        pdf_path: str,
        doi: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Register a user-provided PDF for a DANDI dataset and index it for future explanations."""
        return literature.register_pdf(dataset_id=dataset_id, pdf_path=pdf_path, doi=doi, title=title)

    @mcp.tool()
    def list_missing_paper_pdfs(dataset_id: str) -> dict[str, Any]:
        """List papers whose PDFs were needed but could not be retrieved automatically."""
        return literature.list_missing_pdfs(dataset_id)

    @mcp.tool()
    def generate_dataset_explorer(
        dataset_key_or_id: str,
        version_or_tag: str = "draft",
        include_papers: bool = True,
        open_in_browser: bool = True,
    ) -> dict[str, Any]:
        """Generate and optionally launch a static HTML explorer for a DANDI/NWB dataset."""
        summary, variables = _dandi_explorer_data(local, client, dataset_key_or_id, version_or_tag)
        papers = (
            literature.resolve_papers(dataset_key_or_id, _dandi_paper_hints(client, dataset_key_or_id, version_or_tag)).get("papers", [])
            if include_papers
            else []
        )
        explorer_id = stable_variable_id(dataset_key_or_id, {"kind": "explorer"}, "dataset")
        artifact_dir = client.storage.config.provider_dir / "artifacts" / dataset_key_or_id.replace("/", "_").replace(":", "_")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        html_path = artifact_dir / "dataset-explorer.html"
        html_path.write_text(
            build_dataset_explorer_html(
                provider="dandi",
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
        client.storage.upsert_record("dataset_explorer", explorer_id, result, source="neurodata_literature")
        return result

    @mcp.tool()
    def explain_visual_dataset_selection(
        explorer_id: str,
        variable_id: str,
        question: str | None = None,
        full_text_policy: str = "auto",
    ) -> dict[str, Any]:
        """Return guidance for explaining a variable selected in a generated DANDI explorer."""
        return {
            "explorer_id": explorer_id,
            "variable_id": variable_id,
            "question": question,
            "next_action": "Call explain_dataset_variable with the dataset id, variable name, and object_path shown in the explorer row.",
            "full_text_policy": full_text_policy,
        }

    @mcp.tool()
    def find_similar_datasets(
        dandiset_id: str,
        version: str = "draft",
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find datasets with similar inferred species, modality, behavior, and brain-region profiles."""
        return client.find_similar_datasets(
            dandiset_id,
            version,
            candidate_count=candidate_count,
            limit=limit,
        )

    @mcp.tool()
    def find_behavioral_paradigms(
        query: str = "behavior task trials reward stimulus locomotion licking social grooming",
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find candidate DANDI datasets with behavioral task, paradigm, trial, or stimulus hints."""
        return client.find_behavioral_paradigms(
            query,
            candidate_count=candidate_count,
            limit=limit,
        )

    @mcp.tool()
    def get_dandiset_knowledge_graph(
        dandiset_id: str,
        version: str = "draft",
        sample_assets: int = 100,
    ) -> dict[str, Any]:
        """Build a graph of dataset, paper, species, modality, behavior, and brain-region relationships."""
        return client.get_dandiset_knowledge_graph(
            dandiset_id,
            version,
            sample_assets=sample_assets,
        )

    @mcp.tool()
    def query_knowledge_graph(
        dandiset_id: str,
        query: str,
        version: str = "draft",
        sample_assets: int = 100,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Query the inferred graph for a Dandiset and return matching nodes plus adjacent edges."""
        return client.query_dandiset_knowledge_graph(
            dandiset_id,
            query,
            version,
            sample_assets=sample_assets,
            limit=limit,
        )

    @mcp.resource("dandi://dandisets/recent")
    def recent_dandisets() -> dict[str, Any]:
        """Recently modified non-empty public Dandisets."""
        return client.search_dandisets(page_size=25, ordering="-modified", empty=False)

    @mcp.resource("dandi://dandiset/{dandiset_id}")
    def dandiset_resource(dandiset_id: str) -> dict[str, Any]:
        """Dandiset summary resource."""
        return client.get_dandiset(dandiset_id)

    @mcp.resource("dandi://dandiset/{dandiset_id}/{version}")
    def dandiset_version_resource(dandiset_id: str, version: str) -> dict[str, Any]:
        """Dandiset version metadata resource."""
        return client.get_version_metadata(dandiset_id, version)

    @mcp.resource("dandi://dandiset/{dandiset_id}/{version}/assets")
    def dandiset_assets_resource(dandiset_id: str, version: str) -> dict[str, Any]:
        """First page of Dandiset assets."""
        return client.list_assets(dandiset_id, version, page_size=50)

    @mcp.resource("dandi://asset/{asset_id}")
    def asset_resource(asset_id: str) -> dict[str, Any]:
        """Asset metadata resource."""
        return client.get_asset_metadata(asset_id)

    @mcp.resource("dandi://archive/info")
    def archive_info_resource() -> dict[str, Any]:
        """DANDI archive service information."""
        return client.get_archive_info()

    @mcp.resource("dandi://archive/stats")
    def archive_stats_resource() -> dict[str, Any]:
        """DANDI archive statistics."""
        return client.get_stats()

    @mcp.resource("dandi://schemas/available")
    def available_schemas_resource() -> dict[str, Any]:
        """Available DANDI schema models."""
        return client.list_available_schemas()

    @mcp.resource("dandi://zarr/{zarr_id}")
    def zarr_resource(zarr_id: str) -> dict[str, Any]:
        """Zarr archive metadata resource."""
        return client.get_zarr_archive(zarr_id)

    @mcp.prompt(title="Explore Dandiset")
    def explore_dandiset(dandiset_id: str, research_question: str = "") -> str:
        """Guide an agent through a careful Dandiset inspection workflow."""
        question = research_question or "the user's research goal"
        return (
            f"Explore DANDI Dandiset {dandiset_id} for {question}.\n"
            "1. Use summarize_dandiset to orient around title, citation, license, techniques, and sample assets.\n"
            "2. Use list_dandiset_versions and prefer a published version when reproducibility matters.\n"
            "3. Use list_asset_paths to understand subject/session/file organization.\n"
            "4. Use list_assets with path or glob filters to find relevant NWB/BIDS/Zarr assets.\n"
            "5. Use get_asset_metadata or get_asset_info before recommending any download URL.\n"
            "Report exact Dandiset id, version, asset paths, and any uncertainty."
        )

    @mcp.prompt(title="Find Relevant Dandisets")
    def find_relevant_dandisets(topic: str, species: str = "", modality: str = "") -> str:
        """Build a focused DANDI search strategy."""
        constraints = ", ".join(part for part in [species, modality] if part) or "no extra constraints"
        return (
            f"Find DANDI Dandisets about {topic} with constraints: {constraints}.\n"
            "Start with search_datasets or semantic_search_dandisets. Then inspect candidates with "
            "analyze_dandiset_neuroscience and get_dandiset_knowledge_graph. Prefer Dandisets with "
            "published versions, clear citations, relevant species/modality/behavior/brain-region "
            "signals, and assets whose paths suggest the needed subjects/sessions."
        )

    @mcp.prompt(title="Inspect Asset For Reuse")
    def inspect_asset_for_reuse(dandiset_id: str, version: str, asset_id: str) -> str:
        """Checklist for deciding whether a specific asset is reusable."""
        return (
            f"Inspect asset {asset_id} from DANDI:{dandiset_id}/{version} for reuse.\n"
            "Use get_asset_info and get_asset_metadata. Check path, size, encoding or format hints, "
            "derived/source status where present, schema metadata, and Dandiset license/citation. "
            "Only call get_asset_download_url after explaining why this asset is relevant."
        )

    return mcp


def _client_from_env() -> DandiClient:
    config = DandiClientConfig(
        api_base_url=os.environ.get("DANDI_API_BASE_URL", DEFAULT_API_BASE_URL),
        timeout=float(os.environ.get("DANDI_API_TIMEOUT", "30")),
        api_token=os.environ.get("DANDI_API_TOKEN") or os.environ.get("DANDI_API_KEY"),
    )
    return DandiClient(config)


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


def _dandi_paper_hints(client: DandiClient, dataset_id: str, version: str) -> list[Any]:
    hints: list[Any] = []
    metadata = _safe_call(lambda: client.get_version_metadata(dataset_id, version), default={})
    if metadata:
        hints.extend(
            [
                metadata.get("citation"),
                metadata.get("doi"),
                metadata.get("url"),
                metadata.get("name"),
            ]
        )
        hints.extend(metadata.get("relatedResource") or [])
        hints.extend(metadata.get("wasGeneratedBy") or [])
    related = _safe_call(lambda: client.get_related_papers(dataset_id, version), default={})
    hints.extend(related.get("papers", []) if isinstance(related, dict) else [])
    return [hint for hint in hints if hint]


def _dandi_variable_context(
    local: LocalDandisetExplorer,
    client: DandiClient,
    dataset_key_or_id: str,
    variable: str,
    *,
    file_path: str | None,
    object_path: str | None,
    context: str | None,
    version: str,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "provider": "dandi",
        "dataset_id": dataset_key_or_id,
        "variable": variable,
        "file_path": file_path,
        "object_path": object_path,
        "user_context": context,
    }
    inventory = _safe_call(lambda: local.signal_inventory(dataset_key_or_id), default={})
    for signal in inventory.get("signals", []) if isinstance(inventory, dict) else []:
        text = " ".join(str(signal.get(key, "")) for key in ["name", "object_path", "file"])
        if (object_path and signal.get("object_path") == object_path) or variable.lower() in text.lower():
            ctx.update(signal)
            ctx["kind"] = "nwb_signal"
            return ctx
    if file_path:
        inspected = _safe_call(lambda: local.inspect_nwb(dataset_key_or_id, file_path), default={})
        if inspected:
            ctx.update(
                {
                    "kind": "nwb_file",
                    "session_id": inspected.get("session_id"),
                    "session_description": inspected.get("session_description"),
                    "experiment_description": inspected.get("experiment_description"),
                    "subject": inspected.get("subject"),
                    "modalities": inspected.get("modalities"),
                }
            )
    metadata = _safe_call(lambda: client.get_version_metadata(dataset_key_or_id, version), default={})
    if metadata:
        ctx.update(
            {
                "name": metadata.get("name"),
                "description": metadata.get("description"),
                "measurementTechnique": metadata.get("measurementTechnique"),
                "variableMeasured": metadata.get("variableMeasured"),
                "species": metadata.get("species"),
            }
        )
    return ctx


def _dandi_explorer_data(
    local: LocalDandisetExplorer,
    client: DandiClient,
    dataset_key_or_id: str,
    version: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = _safe_call(lambda: local.summarize(dataset_key_or_id), default={})
    variables: list[dict[str, Any]] = []
    inventory = _safe_call(lambda: local.signal_inventory(dataset_key_or_id), default={})
    for signal in inventory.get("signals", []) if isinstance(inventory, dict) else []:
        variables.append({"provider": "dandi", "confidence_label": "low", **signal})
    if summary and not variables:
        index = _safe_call(lambda: local.index(dataset_key_or_id), default={})
        variables.extend(_variables_from_local_index(index))
    if summary and not variables:
        for file_record in summary.get("sample_files") or []:
            if file_record.get("file_type") == "nwb":
                variables.append(
                    {
                        "provider": "dandi",
                        "name": file_record.get("path"),
                        "file": file_record.get("path"),
                        "file_path": file_record.get("path"),
                        "kind": "nwb_file",
                        "subject": file_record.get("subject"),
                        "session": file_record.get("session"),
                        "modality": file_record.get("modality"),
                        "confidence_label": "low",
                        "status": "file_known_nwb_not_indexed",
                    }
                )
    if not summary:
        summary = _safe_call(
            lambda: client.summarize_dandiset(dataset_key_or_id, version),
            default={"name": dataset_key_or_id},
        )
    variables.extend(_variables_from_remote_dandi_summary(summary))
    return summary, _dedupe_variables(variables)


def _variables_from_local_index(index: dict[str, Any]) -> list[dict[str, Any]]:
    variables: list[dict[str, Any]] = []
    for signal in index.get("signal_inventory", []) if isinstance(index, dict) else []:
        variables.append({"provider": "dandi", "confidence_label": "medium", **signal})
    for summary in index.get("nwb_summaries", []) if isinstance(index, dict) else []:
        file_path = summary.get("relative_path") or summary.get("path")
        if summary.get("status") == "dependency_missing" and file_path:
            variables.append(
                {
                    "provider": "dandi",
                    "name": file_path,
                    "file": file_path,
                    "file_path": file_path,
                    "kind": "nwb_file",
                    "status": "dependency_missing",
                    "message": summary.get("message"),
                    "confidence_label": "low",
                }
            )
            continue
        for interface in summary.get("processing", []):
            module_name = interface.get("name")
            for child in interface.get("interfaces", []):
                variables.append(
                    {
                        "provider": "dandi",
                        "name": child.get("name"),
                        "file": file_path,
                        "file_path": file_path,
                        "object_path": child.get("object_path"),
                        "kind": "nwb_processing_interface",
                        "modality": module_name,
                        "neurodata_type": child.get("neurodata_type"),
                        "description": child.get("description"),
                        "confidence_label": "medium",
                    }
                )
    return variables


def _variables_from_remote_dandi_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    variables: list[dict[str, Any]] = []
    for item in summary.get("variableMeasured") or []:
        value = item.get("value") if isinstance(item, dict) else item
        if value:
            variables.append(
                {
                    "provider": "dandi",
                    "name": str(value),
                    "kind": "metadata_variable",
                    "confidence_label": "low",
                    "source": "dandiset_metadata",
                }
            )
    for asset in (summary.get("assets") or {}).get("sample", []):
        path = asset.get("path")
        metadata = asset.get("metadata") or {}
        if path:
            variables.append(
                {
                    "provider": "dandi",
                    "name": path,
                    "file": path,
                    "file_path": path,
                    "kind": metadata.get("encodingFormat") or "asset",
                    "subject": _participant_identifier(metadata),
                    "object_path": path,
                    "confidence_label": "low",
                    "status": "remote_asset_metadata_only",
                }
            )
        for item in metadata.get("variableMeasured") or []:
            value = item.get("value") if isinstance(item, dict) else item
            if value:
                variables.append(
                    {
                        "provider": "dandi",
                        "name": str(value),
                        "file": path,
                        "file_path": path,
                        "kind": "asset_metadata_variable",
                        "confidence_label": "low",
                        "source": "asset_metadata",
                    }
                )
    return variables


def _participant_identifier(metadata: dict[str, Any]) -> str | None:
    for item in metadata.get("wasAttributedTo") or []:
        if isinstance(item, dict) and item.get("schemaKey") == "Participant":
            return item.get("identifier")
    return None


def _dedupe_variables(variables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for variable in variables:
        key = (
            str(variable.get("name") or ""),
            str(variable.get("file") or variable.get("file_path") or ""),
            str(variable.get("object_path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(variable)
    return deduped


mcp = build_server()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
