from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from ibl_mcp.storage import MCPStorage


DEFAULT_ALYX_BASE_URL = "https://openalyx.internationalbrainlab.org"
DEFAULT_PUBLIC_USERNAME = "intbrainlab"
DEFAULT_PUBLIC_PASSWORD = "international"
DEFAULT_DOWNLOAD_DIR = Path.home() / ".cache" / "ibl-mcp" / "downloads"
MAX_PAGE_SIZE = 1000
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AlyxAPIError(RuntimeError):
    """Raised when OpenAlyx/Alyx returns an unsuccessful response."""


@dataclass(frozen=True)
class IBLClientConfig:
    alyx_base_url: str = DEFAULT_ALYX_BASE_URL
    timeout: float = 45.0
    username: str | None = None
    password: str | None = None
    token: str | None = None
    download_dir: Path | None = None
    storage: MCPStorage | None = None


class IBLClient:
    """Small REST client for International Brain Laboratory OpenAlyx/Alyx data."""

    def __init__(
        self,
        config: IBLClientConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or IBLClientConfig()
        self.storage = self.config.storage or MCPStorage.from_env("ibl")
        if self.config.download_dir is None:
            object.__setattr__(self.config, "download_dir", self.storage.config.downloads_dir)
        self._transport = transport
        headers = {"User-Agent": "ibl-mcp-server/0.1.0"}
        if self.config.token:
            headers["Authorization"] = f"Token {self.config.token}"
        auth = None
        if self.config.username and self.config.password and not self.config.token:
            auth = None
        self._client = httpx.Client(
            base_url=self.config.alyx_base_url.rstrip("/") + "/",
            timeout=self.config.timeout,
            follow_redirects=False,
            transport=transport,
            headers=headers,
            auth=auth,
        )
        self._token_initialized = bool(self.config.token)

    def close(self) -> None:
        self._client.close()

    def list_endpoints(self) -> dict[str, Any]:
        """Return all endpoints advertised by this Alyx instance."""
        return self._get("api/schema", params={"format": "json"})

    def describe_endpoint(self, endpoint: str) -> dict[str, Any]:
        """Return OPTIONS metadata for an endpoint where the server exposes it."""
        response = self._client.options(_endpoint_path(endpoint))
        return self._response_payload(response)

    def list_sessions(
        self,
        *,
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
        """List sessions using common ONE/Alyx public search filters."""
        return self._get("sessions", params=_clean_params(locals()))

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._get(f"sessions/{_uuid_like(session_id)}")

    def list_datasets(
        self,
        *,
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
        return self._get("datasets", params=_clean_params(locals()))

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._get(f"datasets/{_uuid_like(dataset_id)}")

    def list_files(
        self,
        *,
        dataset: str | None = None,
        session: str | None = None,
        exists: bool | None = True,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("files", params=_clean_params(locals()))

    def list_insertions(
        self,
        *,
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
        return self._get("insertions", params=_clean_params(locals()))

    def get_insertion(self, insertion_id: str) -> dict[str, Any]:
        return self._get(f"insertions/{_uuid_like(insertion_id)}")

    def list_trajectories(
        self,
        *,
        probe_insertion: str | None = None,
        provenance: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("trajectories", params=_clean_params(locals()))

    def list_channels(
        self,
        *,
        probe_insertion: str | None = None,
        session: str | None = None,
        atlas_acronym: str | None = None,
        atlas_id: str | int | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("channels", params=_clean_params(locals()))

    def list_subjects(
        self,
        *,
        nickname: str | None = None,
        lab: str | None = None,
        project: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("subjects", params=_clean_params(locals()))

    def list_brain_regions(
        self,
        *,
        acronym: str | None = None,
        name: str | None = None,
        id: str | int | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("brain-regions", params=_clean_params(locals()))

    def list_dataset_types(
        self,
        *,
        name: str | None = None,
        filename: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("dataset-types", params=_clean_params(locals()))

    def list_data_formats(
        self,
        *,
        name: str | None = None,
        file_extension: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("data-formats", params=_clean_params(locals()))

    def list_tags(self, *, name: str | None = None) -> dict[str, Any] | list[Any]:
        return self._get("tags", params=_clean_params(locals()))

    def list_labs(self, *, name: str | None = None) -> dict[str, Any] | list[Any]:
        return self._get("labs", params=_clean_params(locals()))

    def list_projects(self, *, name: str | None = None) -> dict[str, Any] | list[Any]:
        return self._get("projects", params=_clean_params(locals()))

    def list_task_protocols(
        self,
        *,
        search: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """Derive task protocol names from sessions because Alyx does not expose them as a first-class endpoint."""
        django = f"task_protocol__icontains,{search}" if search else None
        sessions = self.list_sessions(django=django, page=page, page_size=page_size or 250)
        rows = _compact_page(sessions)["results"]
        counts: dict[str, int] = {}
        examples: dict[str, list[str]] = {}
        for session in rows:
            if not isinstance(session, dict):
                continue
            protocol = session.get("task_protocol") or "unknown"
            counts[protocol] = counts.get(protocol, 0) + 1
            if len(examples.setdefault(protocol, [])) < 5 and session.get("id"):
                examples[protocol].append(session["id"])
        return {
            "count": len(counts),
            "results": [
                {"task_protocol": protocol, "sample_count": count, "example_session_ids": examples.get(protocol, [])}
                for protocol, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
            ],
            "source_session_count": len(rows),
        }

    def list_revisions(
        self,
        *,
        dataset: str | None = None,
        session: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("revisions", params=_clean_params(locals()))

    def list_downloads(
        self,
        *,
        dataset: str | None = None,
        session: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("downloads", params=_clean_params(locals()))

    def list_tasks(
        self,
        *,
        session: str | None = None,
        lab: str | None = None,
        name: str | None = None,
        status: str | None = None,
        django: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self._get("tasks", params=_clean_params(locals()))

    def get_cache_info(self) -> dict[str, Any]:
        return self._get("cache")

    def get_cache_zip_url(self) -> dict[str, Any]:
        return self._redirect_url("cache.zip")

    def get_dataset_download_urls(self, dataset_id: str) -> dict[str, Any]:
        """Collect direct download URLs embedded in dataset and file records."""
        dataset = self.get_dataset(dataset_id)
        urls = _extract_urls(dataset)
        try:
            files = self.list_files(dataset=dataset_id, exists=True)
            urls.extend(_extract_urls(files))
        except AlyxAPIError:
            files = {"error": "Unable to list file records for dataset."}
        deduped = sorted(set(urls))
        return {
            "dataset_id": dataset_id,
            "download_urls": deduped,
            "count": len(deduped),
            "dataset": dataset,
            "files": files,
            "note": "IBL file records usually expose object-store URLs in data_url fields. If empty, query files or use the ONE Python client for authenticated/cache-aware download resolution.",
        }

    def download_url(
        self,
        url: str,
        *,
        filename: str | None = None,
        max_bytes: int = 2_000_000_000,
    ) -> dict[str, Any]:
        """Download a URL to the configured download directory."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        name = filename or Path(parsed.path).name or "ibl-download.bin"
        destination = _safe_download_path(self.config.download_dir, name)
        response = self._download_client_get(url)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                raise AlyxAPIError("Redirect response did not include a location header")
            response = self._download_client_get(location)
        if not response.is_success:
            self._raise_for_response(response)
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError(f"download is larger than max_bytes ({max_bytes})")
        self.config.download_dir.mkdir(parents=True, exist_ok=True)
        total = 0
        with destination.open("wb") as stream:
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise ValueError(f"download exceeded max_bytes ({max_bytes})")
                stream.write(chunk)
        result = {
            "path": str(destination),
            "bytes": total,
            "source_url": url,
            "content_type": response.headers.get("content-type"),
        }
        self.storage.upsert_record("download", str(destination), result, source="IBL explicit URL download")
        return result

    def get_url_bytes(self, url: str, *, max_bytes: int = 200_000_000) -> tuple[bytes, dict[str, str | None]]:
        """Fetch an explicit URL into memory for small analysis arrays."""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        response = self._download_client_get(url)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                raise AlyxAPIError("Redirect response did not include a location header")
            response = self._download_client_get(location)
        if not response.is_success:
            self._raise_for_response(response)
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError(f"payload is larger than max_bytes ({max_bytes})")
        content = response.content
        if len(content) > max_bytes:
            raise ValueError(f"payload exceeded max_bytes ({max_bytes})")
        return content, {
            "content_type": response.headers.get("content-type"),
            "source_url": str(response.url),
            "content_length": response.headers.get("content-length"),
        }

    def summarize_session(self, session_id: str, *, dataset_limit: int = 25) -> dict[str, Any]:
        session = self.get_session(session_id)
        datasets = self.list_datasets(session=session_id, exists=True, page_size=dataset_limit)
        insertions = self.list_insertions(session=session_id)
        return {
            "session_id": session_id,
            "session": session,
            "datasets": _compact_page(datasets),
            "insertions": _compact_page(insertions),
            "next_steps": [
                "Use list_datasets with collection/name/dataset_type filters to narrow files.",
                "Use get_dataset_download_urls once a dataset id is selected.",
                "Use list_insertions, list_channels, and list_trajectories for ephys anatomy context.",
            ],
        }

    def call_alyx_api(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: Any | None = None,
        allow_mutation: bool = False,
    ) -> dict[str, Any] | list[Any]:
        method = method.upper()
        if method not in {"GET", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("method must be GET, OPTIONS, POST, PUT, PATCH, or DELETE")
        if method in MUTATING_METHODS and not allow_mutation:
            raise ValueError("mutating Alyx API calls require allow_mutation=True")
        clean_path = path.lstrip("/")
        self._ensure_token()
        response = self._client.request(method, clean_path, params=query, json=body)
        return self._response_payload(response)

    def _get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        self._ensure_token()
        response = self._client.get(path, params=params)
        return self._response_payload(response)

    def _create_auth_token(self, username: str, password: str) -> str:
        response = self._client.post("auth-token", json={"username": username, "password": password})
        payload = self._response_payload(response)
        if not isinstance(payload, dict) or not payload.get("token"):
            raise AlyxAPIError("Alyx auth-token response did not include a token")
        return str(payload["token"])

    def _ensure_token(self) -> None:
        if self._token_initialized or not (self.config.username and self.config.password):
            return
        token = self._create_auth_token(self.config.username, self.config.password)
        self._client.headers["Authorization"] = f"Token {token}"
        self._token_initialized = True

    def _download_client_get(self, url: str) -> httpx.Response:
        """Fetch data URLs without leaking Alyx Authorization headers to object storage."""
        with httpx.Client(
            timeout=self.config.timeout,
            follow_redirects=False,
            headers={"User-Agent": "ibl-mcp-server/0.1.0"},
            transport=self._transport,
        ) as client:
            return client.get(url)

    def _redirect_url(self, path: str) -> dict[str, Any]:
        self._ensure_token()
        response = self._client.get(path)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                raise AlyxAPIError("Redirect response did not include a location header")
            return {"download_url": location, "host": urlparse(location).netloc}
        if response.is_success:
            return {
                "download_url": str(response.url),
                "host": response.url.host,
                "note": "The cache endpoint returned a body rather than a redirect.",
            }
        self._raise_for_response(response)

    def _response_payload(self, response: httpx.Response) -> dict[str, Any] | list[Any]:
        if response.is_success:
            if response.content:
                try:
                    return response.json()
                except ValueError:
                    return {"text": response.text}
            return {"status_code": response.status_code}
        if response.status_code in {301, 302, 303, 307, 308}:
            return {"status_code": response.status_code, "location": response.headers.get("location")}
        self._raise_for_response(response)

    def _raise_for_response(self, response: httpx.Response) -> None:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        raise AlyxAPIError(f"Alyx API request failed with HTTP {response.status_code}: {detail}")


def _clean_params(values: dict[str, Any]) -> dict[str, Any]:
    values.pop("self", None)
    page = values.pop("page", None)
    page_size = values.pop("page_size", None)
    params: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, bool):
            params[key] = "true" if value else "false"
        else:
            params[key] = value
    if page_size is not None:
        limit = min(_positive_int(int(page_size), "page_size"), MAX_PAGE_SIZE)
        params["limit"] = limit
        if page is not None:
            params["offset"] = (_positive_int(int(page), "page") - 1) * limit
    elif page is not None:
        page_value = _positive_int(int(page), "page")
        params["offset"] = (page_value - 1) * 250
    return params


def _compact_page(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"count": len(payload), "results": payload}
    return {
        "count": payload.get("count", len(payload.get("results", []))),
        "next": payload.get("next"),
        "previous": payload.get("previous"),
        "results": payload.get("results", payload),
    }


def _extract_urls(payload: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"data_url", "download_url", "url"} and isinstance(value, str):
                parsed = urlparse(value)
                if parsed.scheme in {"http", "https"}:
                    urls.append(value)
            else:
                urls.extend(_extract_urls(value))
    elif isinstance(payload, list):
        for item in payload:
            urls.extend(_extract_urls(item))
    return urls


def _safe_download_path(root: Path, filename: str) -> Path:
    root = root.expanduser().resolve()
    candidate = (root / filename).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("filename must stay inside the configured download directory")
    return candidate


def _endpoint_path(value: str) -> str:
    value = value.strip().strip("/")
    if not value:
        raise ValueError("endpoint must not be empty")
    return quote(value, safe="-_")


def _uuid_like(value: str) -> str:
    value = value.strip()
    if len(value) != 36 or value.count("-") != 4:
        raise ValueError("id must be a UUID")
    return value


def _positive_int(value: int, name: str) -> int:
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value
