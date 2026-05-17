from __future__ import annotations

import httpx
import pytest

from dandi_mcp.client import DandiClient, DandiClientConfig


def test_search_dandisets_builds_expected_query() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"count": 0, "results": []})

    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api"),
        transport=httpx.MockTransport(handler),
    )

    result = client.search_dandisets(search="motor cortex", page=2, page_size=2000)

    assert result["count"] == 0
    assert "search=motor+cortex" in seen["url"]
    assert "page=2" in seen["url"]
    assert "page_size=1000" in seen["url"]
    assert "ordering=-modified" in seen["url"]


def test_get_asset_download_url_returns_redirect_location() -> None:
    asset_id = "a5ad932b-b893-4522-b989-8f406d78e4e0"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/assets/{asset_id}/download/"
        return httpx.Response(302, headers={"location": "https://objects.example.test/file.nwb"})

    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api"),
        transport=httpx.MockTransport(handler),
    )

    result = client.get_asset_download_url(asset_id, content_disposition="inline")

    assert result["asset_id"] == asset_id
    assert result["download_url"] == "https://objects.example.test/file.nwb"
    assert result["host"] == "objects.example.test"


def test_call_api_blocks_mutation_without_explicit_allow() -> None:
    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(ValueError, match="allow_mutation"):
        client.call_api("POST", "dandisets/000006/star/")


def test_call_api_can_reach_arbitrary_get_path() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["query"] = request.url.query.decode()
        return httpx.Response(200, json={"ok": True})

    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api"),
        transport=httpx.MockTransport(handler),
    )

    result = client.call_api("GET", "/api/schemas/", query={"model": "Dandiset"})

    assert result == {"ok": True}
    assert seen["path"] == "/api/schemas/"
    assert seen["query"] == "model=Dandiset"


@pytest.mark.parametrize("bad_path", ["https://evil.example/api", "../users/me/", "dandisets/../users/me/"])
def test_call_api_rejects_external_or_traversal_paths(bad_path: str) -> None:
    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api", api_token="secret"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(ValueError):
        client.call_api("GET", bad_path)


def test_api_token_sets_authorization_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json={"ok": True})

    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api", api_token="secret"),
        transport=httpx.MockTransport(handler),
    )

    assert client.get_archive_info() == {"ok": True}
    assert seen["authorization"] == "token secret"


@pytest.mark.parametrize("bad_id", ["6", "00006", "abc006", "000006/draft"])
def test_dandiset_id_validation(bad_id: str) -> None:
    client = DandiClient(
        DandiClientConfig(api_base_url="https://example.test/api"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(ValueError):
        client.get_dandiset(bad_id)
