from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from dandi_mcp.intelligence import (
    build_knowledge_graph,
    extract_literature_links,
    query_graph,
    semantic_rank,
    summarize_neuroscience_metadata,
)
from dandi_mcp.storage import MCPStorage


DEFAULT_API_BASE_URL = "https://api.dandiarchive.org/api"
MAX_PAGE_SIZE = 1000


class DandiAPIError(RuntimeError):
    """Raised when the DANDI API returns an unsuccessful response."""


@dataclass(frozen=True)
class DandiClientConfig:
    api_base_url: str = DEFAULT_API_BASE_URL
    timeout: float = 30.0
    api_token: str | None = None
    storage: MCPStorage | None = None


class DandiClient:
    """Small read-only client for the public DANDI REST API."""

    def __init__(
        self,
        config: DandiClientConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or DandiClientConfig()
        self.storage = self.config.storage or MCPStorage.from_env("dandi")
        headers = {"User-Agent": "dandi-mcp-server/0.1.0"}
        if self.config.api_token:
            headers["Authorization"] = f"token {self.config.api_token}"
        self._client = httpx.Client(
            base_url=self.config.api_base_url.rstrip("/") + "/",
            timeout=self.config.timeout,
            follow_redirects=False,
            transport=transport,
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    def search_dandisets(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
        ordering: str = "-modified",
        draft: bool = True,
        empty: bool = False,
        embargoed: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": _positive_int(page, "page"),
            "page_size": _page_size(page_size),
            "ordering": ordering,
            "draft": _bool_string(draft),
            "empty": _bool_string(empty),
            "embargoed": _bool_string(embargoed),
        }
        if search:
            params["search"] = search
        return self._get("dandisets/", params=params)

    def get_dandiset(self, dandiset_id: str) -> dict[str, Any]:
        return self._get(f"dandisets/{_dandiset_id(dandiset_id)}/")

    def list_versions(
        self,
        dandiset_id: str,
        *,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/",
            params={"page": _positive_int(page, "page"), "page_size": _page_size(page_size)},
        )

    def get_version_metadata(self, dandiset_id: str, version: str = "draft") -> dict[str, Any]:
        return self._get(f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/")

    def list_assets(
        self,
        dandiset_id: str,
        version: str = "draft",
        *,
        path: str | None = None,
        glob: str | None = None,
        metadata: bool = False,
        zarr: bool = False,
        page: int = 1,
        page_size: int = 50,
        order: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": _positive_int(page, "page"),
            "page_size": _page_size(page_size),
            "metadata": _bool_string(metadata),
            "zarr": _bool_string(zarr),
        }
        if path:
            params["path"] = path
        if glob:
            params["glob"] = glob
        if order:
            params["order"] = order
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/assets/",
            params=params,
        )

    def list_asset_paths(
        self,
        dandiset_id: str,
        version: str = "draft",
        *,
        path_prefix: str = "",
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        params = {
            "path_prefix": path_prefix,
            "page": _positive_int(page, "page"),
            "page_size": _page_size(page_size),
        }
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/assets/paths/",
            params=params,
        )

    def get_asset_metadata(self, asset_id: str) -> dict[str, Any]:
        return self._get(f"assets/{_uuid_like(asset_id)}/")

    def get_asset_info_by_id(self, asset_id: str) -> dict[str, Any]:
        return self._get(f"assets/{_uuid_like(asset_id)}/info/")

    def get_asset_info(self, dandiset_id: str, version: str, asset_id: str) -> dict[str, Any]:
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/assets/{_uuid_like(asset_id)}/info/"
        )

    def get_version_asset_metadata(
        self, dandiset_id: str, version: str, asset_id: str
    ) -> dict[str, Any]:
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/assets/{_uuid_like(asset_id)}/"
        )

    def get_asset_validation(self, dandiset_id: str, version: str, asset_id: str) -> dict[str, Any]:
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/assets/{_uuid_like(asset_id)}/validation/"
        )

    def get_asset_download_url(
        self,
        asset_id: str,
        *,
        content_disposition: str = "attachment",
    ) -> dict[str, Any]:
        if content_disposition not in {"attachment", "inline"}:
            raise ValueError("content_disposition must be 'attachment' or 'inline'")
        response = self._client.get(
            f"assets/{_uuid_like(asset_id)}/download/",
            params={"content_disposition": content_disposition},
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            self._raise_for_response(response)
        location = response.headers.get("location")
        if not location:
            raise DandiAPIError("DANDI did not return a download redirect location")
        result = {
            "asset_id": asset_id,
            "download_url": location,
            "content_disposition": content_disposition,
            "host": urlparse(location).netloc,
            "note": "DANDI download URLs are redirects to object storage and may expire.",
        }
        self.storage.upsert_record("download_url", asset_id, result, source="DANDI asset download redirect")
        return result

    def get_version_asset_download_url(
        self,
        dandiset_id: str,
        version: str,
        asset_id: str,
    ) -> dict[str, Any]:
        response = self._client.get(
            f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/assets/{_uuid_like(asset_id)}/download/"
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            self._raise_for_response(response)
        location = response.headers.get("location")
        if not location:
            raise DandiAPIError("DANDI did not return a download redirect location")
        result = {
            "dandiset_id": dandiset_id,
            "version": version,
            "asset_id": asset_id,
            "download_url": location,
            "host": urlparse(location).netloc,
            "note": "DANDI download URLs are redirects to object storage and may expire.",
        }
        self.storage.upsert_record(
            "download_url",
            asset_id,
            result,
            source="DANDI asset download redirect",
            version=version,
        )
        return result

    def get_version_info(self, dandiset_id: str, version: str = "draft") -> dict[str, Any]:
        return self._get(f"dandisets/{_dandiset_id(dandiset_id)}/versions/{_version(version)}/info/")

    def list_uploads(
        self,
        dandiset_id: str,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        return self._get(
            f"dandisets/{_dandiset_id(dandiset_id)}/uploads/",
            params={"page": _positive_int(page, "page"), "page_size": _page_size(page_size)},
        )

    def list_dandiset_users(self, dandiset_id: str) -> dict[str, Any]:
        return self._get(f"dandisets/{_dandiset_id(dandiset_id)}/users/")

    def get_archive_info(self) -> dict[str, Any]:
        return self._get("info/")

    def list_schemas(self, model: str) -> dict[str, Any]:
        if model not in {"Dandiset", "Asset", "PublishedDandiset", "PublishedAsset"}:
            raise ValueError(
                "model must be one of: Dandiset, Asset, PublishedDandiset, PublishedAsset"
            )
        return self._get("schemas/", params={"model": model})

    def list_available_schemas(self) -> dict[str, Any]:
        return self._get("schemas/available/")

    def get_stats(self) -> dict[str, Any]:
        return self._get("stats/")

    def list_users(self, *, approved_only: bool = False) -> dict[str, Any]:
        return self._get("users/", params={"approved_only": _bool_string(approved_only)})

    def get_current_user(self) -> dict[str, Any]:
        return self._get("users/me/")

    def get_user_questionnaire_form(self) -> dict[str, Any]:
        return self._get("users/questionnaire-form/")

    def search_users(self, username: str) -> dict[str, Any]:
        if not username:
            raise ValueError("username is required")
        return self._get("users/search/", params={"username": username})

    def list_zarr_archives(
        self,
        *,
        page: int = 1,
        page_size: int = 25,
        dandiset: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "page": _positive_int(page, "page"),
            "page_size": _page_size(page_size),
        }
        if dandiset:
            params["dandiset"] = _dandiset_id(dandiset)
        if name:
            params["name"] = name
        return self._get("zarr/", params=params)

    def get_zarr_archive(self, zarr_id: str) -> dict[str, Any]:
        return self._get(f"zarr/{_path_part(zarr_id)}/")

    def list_zarr_files(
        self,
        zarr_id: str,
        *,
        after: str = "",
        prefix: str = "",
        limit: int = 1000,
        download: bool = False,
    ) -> dict[str, Any]:
        return self._get(
            f"zarr/{_path_part(zarr_id)}/files/",
            params={
                "after": after,
                "prefix": prefix,
                "limit": _positive_int(limit, "limit"),
                "download": _bool_string(download),
            },
        )

    def get_auth_token(self) -> dict[str, Any]:
        return self._get("auth/token/")

    def call_api(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        allow_mutation: bool = False,
    ) -> dict[str, Any]:
        """Call any DANDI API endpoint with guardrails for non-GET methods."""
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("method must be GET, POST, PUT, PATCH, or DELETE")
        if method != "GET" and not allow_mutation:
            raise ValueError("non-GET DANDI API calls require allow_mutation=True")
        clean_path = path.lstrip("/")
        if clean_path.startswith("api/"):
            clean_path = clean_path[4:]
        clean_path = _relative_api_path(clean_path)
        response = self._client.request(method, clean_path, params=query, json=body)
        return self._response_payload(response)

    def summarize_dandiset(
        self,
        dandiset_id: str,
        version: str = "draft",
        *,
        sample_assets: int = 10,
    ) -> dict[str, Any]:
        metadata = self.get_version_metadata(dandiset_id, version)
        assets = self.list_assets(dandiset_id, version, page_size=min(sample_assets, 100))
        result = {
            "dandiset_id": dandiset_id,
            "version": version,
            "url": metadata.get("url"),
            "name": metadata.get("name"),
            "description": metadata.get("description"),
            "citation": metadata.get("citation"),
            "license": metadata.get("license"),
            "keywords": metadata.get("keywords"),
            "about": metadata.get("about"),
            "measurementTechnique": metadata.get("measurementTechnique"),
            "variableMeasured": metadata.get("variableMeasured"),
            "assets": {
                "count": assets.get("count"),
                "sample": assets.get("results", []),
                "next": assets.get("next"),
            },
        }
        self.storage.upsert_record(
            "dataset_summary",
            _dandiset_id(dandiset_id),
            result,
            source="DANDI REST API",
            version=version,
        )
        return result

    def analyze_dandiset_neuroscience(
        self,
        dandiset_id: str,
        version: str = "draft",
        *,
        sample_assets: int = 100,
    ) -> dict[str, Any]:
        metadata = self.get_version_metadata(dandiset_id, version)
        assets = self.list_assets(
            dandiset_id,
            version,
            page_size=min(sample_assets, MAX_PAGE_SIZE),
            metadata=True,
        )
        result = summarize_neuroscience_metadata(metadata, assets.get("results", []))
        self.storage.upsert_record(
            "neuroscience_summary",
            _dandiset_id(dandiset_id),
            result,
            source="DANDI metadata intelligence",
            version=version,
        )
        return result

    def get_related_papers(self, dandiset_id: str, version: str = "draft") -> dict[str, Any]:
        metadata = self.get_version_metadata(dandiset_id, version)
        result = {
            "dandiset_id": dandiset_id,
            "version": version,
            "papers": extract_literature_links(metadata),
            "provenance": {
                "source": "DANDI version metadata",
                "note": (
                    "This extracts DOI, PubMed, Semantic Scholar, GitHub, protocols.io, and "
                    "relatedResource links already present in metadata. It does not yet call "
                    "external literature APIs."
                ),
            },
        }
        self.storage.upsert_record(
            "papers",
            _dandiset_id(dandiset_id),
            result,
            source="DANDI version metadata",
            version=version,
        )
        return result

    def semantic_search_dandisets(
        self,
        query: str,
        *,
        search: str | None = None,
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        candidates = self.search_dandisets(
            search=search or query,
            page_size=min(candidate_count, MAX_PAGE_SIZE),
        ).get("results", [])
        records = [self._candidate_record(candidate) for candidate in candidates]
        for record in records:
            record_id = str(record.get("identifier") or record.get("id") or "")
            if record_id:
                self.storage.upsert_record(
                    "dataset_candidate",
                    record_id,
                    record,
                    source="DANDI keyword search",
                )
        matches = semantic_rank(query, records, limit=limit)
        return {
            "query": query,
            "candidate_count": len(records),
            "results": [
                {
                    "score": match.score,
                    "matched_terms": match.matched_terms,
                    "explanation": match.explanation,
                    "dandiset": match.record,
                }
                for match in matches
            ],
            "provenance": {
                "retrieval": "DANDI keyword search followed by local lexical/ontology reranking",
                "embedding_model": None,
                "limitations": (
                    "This is a deterministic lexical semantic baseline. A production vector "
                    "index should replace candidate generation and scoring for corpus-scale search."
                ),
            },
        }

    def find_similar_datasets(
        self,
        dandiset_id: str,
        version: str = "draft",
        *,
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        metadata = self.get_version_metadata(dandiset_id, version)
        intelligence = summarize_neuroscience_metadata(metadata)
        query_terms = [
            *(intelligence["species"] or []),
            *(intelligence["modalities"] or []),
            *(intelligence["behaviors"] or []),
            *(intelligence["brain_regions"] or []),
            str(metadata.get("name") or ""),
        ]
        query = " ".join(term for term in query_terms if term).strip() or str(metadata.get("name") or dandiset_id)
        results = self.semantic_search_dandisets(
            query,
            candidate_count=candidate_count,
            limit=limit + 1,
        )
        filtered = [
            result
            for result in results["results"]
            if str(result["dandiset"].get("identifier", "")).removeprefix("DANDI:") != dandiset_id
        ][:limit]
        results["source_dandiset"] = {
            "dandiset_id": dandiset_id,
            "version": version,
            "query_profile": intelligence,
        }
        results["results"] = filtered
        return results

    def find_behavioral_paradigms(
        self,
        query: str = "behavior task trials reward stimulus locomotion licking social grooming",
        *,
        candidate_count: int = 25,
        limit: int = 10,
    ) -> dict[str, Any]:
        return self.semantic_search_dandisets(
            query,
            candidate_count=candidate_count,
            limit=limit,
        )

    def get_dandiset_knowledge_graph(
        self,
        dandiset_id: str,
        version: str = "draft",
        *,
        sample_assets: int = 100,
    ) -> dict[str, Any]:
        metadata = self.get_version_metadata(dandiset_id, version)
        assets = self.list_assets(
            dandiset_id,
            version,
            page_size=min(sample_assets, MAX_PAGE_SIZE),
            metadata=True,
        )
        graph = build_knowledge_graph(metadata, assets.get("results", []))
        self.storage.replace_graph(
            f"dandiset:{_dandiset_id(dandiset_id)}:{version}",
            graph.get("nodes", []),
            graph.get("edges", []),
        )
        return graph

    def query_dandiset_knowledge_graph(
        self,
        dandiset_id: str,
        query: str,
        version: str = "draft",
        *,
        sample_assets: int = 100,
        limit: int = 20,
    ) -> dict[str, Any]:
        graph = self.get_dandiset_knowledge_graph(
            dandiset_id,
            version,
            sample_assets=sample_assets,
        )
        result = query_graph(graph, query, limit=limit)
        result["dandiset_id"] = dandiset_id
        result["version"] = version
        return result

    def _candidate_record(self, candidate: dict[str, Any]) -> dict[str, Any]:
        record = dict(candidate)
        dandiset_id = str(record.get("identifier") or record.get("id") or "").removeprefix("DANDI:")
        draft = record.get("draft_version") if isinstance(record.get("draft_version"), dict) else {}
        most_recent = (
            record.get("most_recent_published_version")
            if isinstance(record.get("most_recent_published_version"), dict)
            else {}
        )
        record["semantic_text"] = {
            "name": record.get("name") or draft.get("name") or most_recent.get("name"),
            "description": draft.get("description") or most_recent.get("description"),
            "created": record.get("created"),
            "modified": record.get("modified"),
        }
        if dandiset_id:
            record["identifier"] = dandiset_id
        return record

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._client.get(path, params=params)
        return self._response_payload(response)

    def _response_payload(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_success:
            if response.content:
                try:
                    return response.json()
                except ValueError:
                    return {"text": response.text}
            return {"status_code": response.status_code}
        if response.status_code in {301, 302, 303, 307, 308}:
            return {
                "status_code": response.status_code,
                "location": response.headers.get("location"),
            }
        self._raise_for_response(response)

    def _raise_for_response(self, response: httpx.Response) -> None:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        raise DandiAPIError(f"DANDI API request failed with HTTP {response.status_code}: {detail}")


def _bool_string(value: bool) -> str:
    return "true" if value else "false"


def _page_size(value: int) -> int:
    value = _positive_int(value, "page_size")
    return min(value, MAX_PAGE_SIZE)


def _positive_int(value: int, name: str) -> int:
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _dandiset_id(value: str) -> str:
    value = value.removeprefix("DANDI:").strip("/")
    if not value.isdigit() or len(value) != 6:
        raise ValueError("dandiset_id must look like '000006' or 'DANDI:000006'")
    return value


def _version(value: str) -> str:
    value = value.strip()
    if value == "draft":
        return value
    parts = value.split(".")
    if len(parts) == 3 and parts[0] == "0" and len(parts[1]) == 6 and len(parts[2]) == 4:
        return value
    raise ValueError("version must be 'draft' or a DANDI version like '0.220126.1855'")


def _uuid_like(value: str) -> str:
    value = value.strip()
    if len(value) != 36 or value.count("-") != 4:
        raise ValueError("asset_id must be a UUID")
    return value


def _path_part(value: str) -> str:
    value = value.strip().strip("/")
    if not value:
        raise ValueError("path value must not be empty")
    return quote(value, safe="")


def _relative_api_path(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value:
        raise ValueError("path must be a relative DANDI API path")
    if "\\" in value:
        raise ValueError("path must not contain backslashes")
    parts = [part for part in value.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise ValueError("path must not contain dot-directory segments")
    return value
