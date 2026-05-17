from __future__ import annotations

from io import BytesIO
from typing import Any

import httpx
import numpy as np

from ibl_mcp.client import IBLClient, IBLClientConfig
from ibl_mcp.services import IBLDomainService


SESSION_ID = "ba892860-149e-4bff-9961-aa6583d96661"


def npy_bytes(values: Any) -> bytes:
    stream = BytesIO()
    np.save(stream, np.asarray(values), allow_pickle=False)
    return stream.getvalue()


def test_behavior_summary_loads_trial_arrays_and_surfaces_qc() -> None:
    dataset_names = {
        "choice": "_ibl_trials.choice.npy",
        "feedback": "_ibl_trials.feedbackType.npy",
        "stim": "_ibl_trials.stimOn_times.npy",
        "move": "_ibl_trials.firstMovement_times.npy",
        "response": "_ibl_trials.response_times.npy",
        "prob_left": "_ibl_trials.probabilityLeft.npy",
    }
    dataset_ids = {name: f"00000000-0000-4000-8000-{idx:012d}" for idx, name in enumerate(dataset_names.values(), start=1)}
    arrays = {
        dataset_ids[dataset_names["choice"]]: [1, -1, 1, 1],
        dataset_ids[dataset_names["feedback"]]: [1, -1, 1, 1],
        dataset_ids[dataset_names["stim"]]: [0.1, 1.0, 2.0, 3.0],
        dataset_ids[dataset_names["move"]]: [0.3, 1.4, 2.2, 3.3],
        dataset_ids[dataset_names["response"]]: [0.4, 1.6, 2.4, 3.5],
        dataset_ids[dataset_names["prob_left"]]: [0.2, 0.5, 0.5, 0.8],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/datasets":
            return httpx.Response(
                200,
                json=[
                    {"id": dataset_id, "name": name, "collection": "alf"}
                    for name, dataset_id in dataset_ids.items()
                ],
            )
        if path.startswith("/datasets/"):
            dataset_id = path.strip("/").split("/")[1]
            return httpx.Response(200, json={"id": dataset_id, "data_url": f"https://objects.example.test/{dataset_id}.npy"})
        if path == "/files":
            dataset_id = request.url.params.get("dataset")
            return httpx.Response(200, json=[{"data_url": f"https://objects.example.test/{dataset_id}.npy"}])
        if request.url.host == "objects.example.test":
            dataset_id = path.rsplit("/", 1)[-1].removesuffix(".npy")
            return httpx.Response(200, content=npy_bytes(arrays[dataset_id]))
        raise AssertionError(str(request.url))

    client = IBLClient(
        IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
        transport=httpx.MockTransport(handler),
    )
    service = IBLDomainService(client)

    result = service.get_behavior_summary(SESSION_ID)

    assert result["data"]["n_trials"] == 4
    assert result["data"]["performance_correct"] == 0.75
    assert result["data"]["fraction_right_choices"] == 0.75
    assert result["data"]["median_reaction_time"] == 0.25
    assert any(warning["code"] == "few_trials" for warning in result["qc"])
    assert result["provenance"]["session_id"] == SESSION_ID


def test_semantic_search_returns_publication_and_modality_matches() -> None:
    service = IBLDomainService(
        IBLClient(
            IBLClientConfig(alyx_base_url="https://openalyx.example.test"),
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        )
    )

    result = service.semantic_search("brainwide spikes visual cortex", limit=5)

    assert result["data"]["results"]
    assert result["data"]["mode"] == "lexical-semantic-fallback"
