from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from ibl_mcp.client import IBLClient, IBLClientConfig


SESSION_ID = "ba892860-149e-4bff-9961-aa6583d96661"
DATASET_ID = "a5ad932b-b893-4522-b989-8f406d78e4e0"


def test_search_sessions_builds_common_one_query() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[])

    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
        transport=httpx.MockTransport(handler),
    )

    result = client.list_sessions(
        lab="cortexlab",
        datasets="spikes.times.npy",
        atlas_acronym="VISp",
        django="project__name__icontains,brainwide",
        page=2,
        page_size=2000,
    )

    assert result == []
    assert seen["url"].startswith("https://openalyx.example.test/sessions/")
    assert "lab=cortexlab" in seen["url"]
    assert "datasets=spikes.times.npy" in seen["url"]
    assert "atlas_acronym=VISp" in seen["url"]
    assert "django=project__name__icontains%2Cbrainwide" in seen["url"]
    assert "page=2" in seen["url"]
    assert "page_size=1000" in seen["url"]


def test_dataset_download_urls_collects_nested_file_urls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/datasets/{DATASET_ID}/":
            return httpx.Response(
                200,
                json={
                    "id": DATASET_ID,
                    "name": "spikes.times.npy",
                    "data_url": "https://ibl.flatironinstitute.org/file-a.npy",
                },
            )
        if request.url.path == "/files/":
            return httpx.Response(
                200,
                json=[
                    {"data_url": "https://ibl.flatironinstitute.org/file-a.npy"},
                    {"data_url": "https://ibl.flatironinstitute.org/file-b.npy"},
                ],
            )
        raise AssertionError(str(request.url))

    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
        transport=httpx.MockTransport(handler),
    )

    result = client.get_dataset_download_urls(DATASET_ID)

    assert result["download_urls"] == [
        "https://ibl.flatironinstitute.org/file-a.npy",
        "https://ibl.flatironinstitute.org/file-b.npy",
    ]
    assert result["count"] == 2


def test_call_alyx_api_blocks_mutation_without_explicit_allow() -> None:
    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(ValueError, match="allow_mutation"):
        client.call_alyx_api("PATCH", f"sessions/{SESSION_ID}/", body={"qc": "PASS"})


def test_token_sets_authorization_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json={"ok": True})

    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test", token="secret"),
        transport=httpx.MockTransport(handler),
    )

    assert client.list_endpoints() == {"ok": True}
    assert seen["authorization"] == "Token secret"


def test_list_task_protocols_derives_protocol_counts_from_sessions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sessions/"
        return httpx.Response(
            200,
            json=[
                {"id": SESSION_ID, "task_protocol": "biasedChoiceWorld"},
                {"id": "11111111-1111-4111-8111-111111111111", "task_protocol": "biasedChoiceWorld"},
                {"id": "22222222-2222-4222-8222-222222222222", "task_protocol": "ephys"},
            ],
        )

    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
        transport=httpx.MockTransport(handler),
    )

    result = client.list_task_protocols(search="choice")

    assert result["count"] == 2
    assert result["results"][0]["task_protocol"] == "biasedChoiceWorld"
    assert result["results"][0]["sample_count"] == 2


def test_download_url_writes_inside_configured_download_dir(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"hello", headers={"content-type": "application/octet-stream"})

    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test", download_dir=tmp_path),
        transport=httpx.MockTransport(handler),
    )

    result = client.download_url("https://ibl.example.test/data.npy", filename="data.npy")

    assert result["bytes"] == 5
    assert Path(result["path"]).read_bytes() == b"hello"
    assert Path(result["path"]).parent == tmp_path.resolve()


def test_download_url_rejects_path_traversal(tmp_path: Path) -> None:
    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test", download_dir=tmp_path),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"bad")),
    )

    with pytest.raises(ValueError, match="inside"):
        client.download_url("https://ibl.example.test/data.npy", filename="../escape.npy")


@pytest.mark.parametrize("bad_id", ["", "abc", "ba892860149e4bff9961aa6583d96661"])
def test_uuid_validation(bad_id: str) -> None:
    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )

    with pytest.raises(ValueError):
        client.get_session(bad_id)
