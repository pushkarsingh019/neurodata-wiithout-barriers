from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_GRAPHQL_URL = "https://openneuro.org/crn/graphql"
DEFAULT_RAW_DATASET_URL = "https://raw.githubusercontent.com/OpenNeuroDatasets"
MAX_PAGE_SIZE = 100


class OpenNeuroAPIError(RuntimeError):
    """Raised when the OpenNeuro GraphQL API returns an unsuccessful response."""


@dataclass(frozen=True)
class OpenNeuroClientConfig:
    graphql_url: str = DEFAULT_GRAPHQL_URL
    raw_dataset_url: str = DEFAULT_RAW_DATASET_URL
    timeout: float = 30.0
    api_token: str | None = None


class OpenNeuroClient:
    """Read-only OpenNeuro GraphQL client."""

    def __init__(
        self,
        config: OpenNeuroClientConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or OpenNeuroClientConfig()
        headers = {"User-Agent": "openneuro-mcp-server/0.1.0"}
        if self.config.api_token:
            headers["Authorization"] = f"Bearer {self.config.api_token}"
        self._client = httpx.Client(
            timeout=self.config.timeout,
            follow_redirects=True,
            transport=transport,
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._client.post(self.config.graphql_url, json={"query": query, "variables": variables or {}})
        if response.status_code >= 400:
            raise OpenNeuroAPIError(f"OpenNeuro returned HTTP {response.status_code}: {response.text[:500]}")
        payload = response.json()
        if payload.get("errors"):
            raise OpenNeuroAPIError(f"OpenNeuro GraphQL errors: {payload['errors']}")
        return payload.get("data", {})

    def search_datasets(self, query: str | None = None, *, first: int = 25, after: str | None = None) -> dict[str, Any]:
        if query:
            if query.startswith("ds") and query[2:].isdigit():
                dataset = self.get_dataset(query)
                return {
                    "edges": [{"cursor": query, "node": dataset}],
                    "pageInfo": {"count": 1, "hasNextPage": False, "endCursor": query},
                }
            gql = """
            query SearchDatasets($query: DatasetSearchInput!, $first: Int, $after: String) {
              advancedSearch(query: $query, first: $first, after: $after) {
                edges {
                  node {
                    id
                    name
                    created
                    public
                    uploader { name email institution }
                    latestSnapshot { tag created }
                  }
                }
                pageInfo { count hasNextPage endCursor }
              }
            }
            """
            variables = {
                "query": {"keywords": [query], "publicOnly": True},
                "first": _page_size(first),
                "after": after,
            }
            return self.graphql(gql, variables).get("advancedSearch", {})
        gql = """
        query ListDatasets($first: Int, $after: String) {
          datasets(first: $first, after: $after) {
            edges {
              cursor
              node {
                id
                name
                created
                public
                uploader { name email institution }
                latestSnapshot { tag created }
              }
            }
            pageInfo { count hasNextPage endCursor }
          }
        }
        """
        return self.graphql(gql, {"first": _page_size(first), "after": after}).get("datasets", {})

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        gql = """
        query Dataset($id: ID!) {
          dataset(id: $id) {
            id
            name
            created
            public
            uploader { name email }
            latestSnapshot { tag created }
          }
        }
        """
        return self.graphql(gql, {"id": _dataset_id(dataset_id)}).get("dataset", {})

    def get_snapshot(self, dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        dataset_id = _dataset_id(dataset_id)
        tag = self._snapshot_tag(dataset_id, tag)
        gql = """
        query Snapshot($datasetId: ID!, $tag: String!) {
          snapshot(datasetId: $datasetId, tag: $tag) {
            id
            tag
            created
            description {
              Acknowledgements
              Authors
              BIDSVersion
              DatasetDOI
              DatasetType
              EthicsApprovals
              Funding
              HowToAcknowledge
              License
              Name
              ReferencesAndLinks
              SeniorAuthor
              id
            }
            summary {
              dataProcessed
              modalities
              primaryModality
              secondaryModalities
              sessions
              size
              subjects
              tasks
              totalFiles
            }
            readme
          }
        }
        """
        return self.graphql(gql, {"datasetId": dataset_id, "tag": tag}).get("snapshot", {})

    def list_files(
        self,
        dataset_id: str,
        *,
        tag: str = "latest",
        tree: str | None = None,
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        dataset_id = _dataset_id(dataset_id)
        tag = self._snapshot_tag(dataset_id, tag)
        gql = """
        query SnapshotFiles($datasetId: ID!, $tag: String!, $tree: String, $recursive: Boolean) {
          snapshot(datasetId: $datasetId, tag: $tag) {
            files(tree: $tree, recursive: $recursive) {
              id
              filename
              size
              directory
              annexed
            }
          }
        }
        """
        snapshot = self.graphql(
            gql,
            {
                "datasetId": _dataset_id(dataset_id),
                "tag": tag,
                "tree": tree,
                "recursive": recursive,
            },
        ).get("snapshot", {})
        return list(snapshot.get("files") or [])

    def get_file_text(self, dataset_id: str, path: str, *, tag: str = "latest") -> dict[str, Any]:
        dataset_id = _dataset_id(dataset_id)
        safe_path = path.lstrip("/")
        branch_or_tag = self._snapshot_tag(dataset_id, tag)
        url = f"{self.config.raw_dataset_url.rstrip('/')}/{dataset_id}/{branch_or_tag}/{safe_path}"
        response = self._client.get(url)
        if response.status_code >= 400:
            raise OpenNeuroAPIError(f"Could not fetch {safe_path} for {dataset_id}: HTTP {response.status_code}")
        return {"filename": safe_path, "size": len(response.content), "text": response.text, "source_url": url}

    def _snapshot_tag(self, dataset_id: str, tag: str) -> str:
        if tag != "latest":
            return tag
        latest = self.get_dataset(dataset_id).get("latestSnapshot", {}).get("tag")
        if not latest:
            raise OpenNeuroAPIError(f"Dataset {dataset_id} does not expose a latest snapshot tag")
        return latest


def _dataset_id(value: str) -> str:
    if not value.startswith("ds") or not value[2:].isdigit():
        raise ValueError("OpenNeuro dataset_id must look like ds000001")
    return value


def _page_size(value: int) -> int:
    if value < 1:
        raise ValueError("page_size must be positive")
    return min(value, MAX_PAGE_SIZE)
