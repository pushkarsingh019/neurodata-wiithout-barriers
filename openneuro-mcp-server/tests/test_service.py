from __future__ import annotations

from typing import Any

from openneuro_mcp.service import OpenNeuroSemanticService


class FakeClient:
    def search_datasets(self, query: str | None = None, *, first: int = 25, after: str | None = None) -> dict[str, Any]:
        return {"edges": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return {"id": dataset_id, "name": "Human reward learning fMRI"}

    def get_snapshot(self, dataset_id: str, tag: str = "latest") -> dict[str, Any]:
        return {
            "id": f"{dataset_id}:1.0.0",
            "tag": "1.0.0",
            "description": {
                "Name": "Human reward learning fMRI",
                "BIDSVersion": "1.10.0",
                "DatasetType": "raw",
                "Authors": ["Ada Lovelace"],
                "DatasetDOI": "10.18112/openneuro.ds000001.v1.0.0",
                "Keywords": ["reward", "fMRI"],
                "ReferencesAndLinks": ["https://github.com/example/analysis"],
            },
        }

    def list_files(
        self,
        dataset_id: str,
        *,
        tag: str = "latest",
        tree: str | None = None,
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            {"id": "1", "filename": "dataset_description.json", "size": 100, "directory": False},
            {"id": "2", "filename": "participants.tsv", "size": 50, "directory": False},
            {"id": "3", "filename": "sub-01/func/sub-01_task-reward_bold.nii.gz", "size": 1000, "directory": False},
            {"id": "4", "filename": "sub-01/func/sub-01_task-reward_events.tsv", "size": 100, "directory": False},
            {"id": "5", "filename": "derivatives/fmriprep/sub-01/func/file.nii.gz", "size": 100, "directory": False},
        ]

    def get_file_text(self, dataset_id: str, path: str, *, tag: str = "latest") -> dict[str, Any]:
        if path == "participants.tsv":
            return {"text": "participant_id\tage\tspecies\nsub-01\t22\thuman\n"}
        return {"text": "onset\tduration\ttrial_type\n0\t1\treward\n"}


def test_service_enriches_metadata_and_indexes() -> None:
    service = OpenNeuroSemanticService(FakeClient())  # type: ignore[arg-type]
    metadata = service.get_dataset_metadata("ds000001", include_files=True)
    assert metadata["doi"] == "10.18112/openneuro.ds000001.v1.0.0"
    assert "fmri" in metadata["modalities"]
    assert metadata["quality"]["score"] == 1.0
    results = service.semantic_search("reward fMRI")
    assert results["results"][0]["id"] == "ds000001"


def test_service_subject_events_pipelines_and_code() -> None:
    service = OpenNeuroSemanticService(FakeClient())  # type: ignore[arg-type]
    assert service.get_subject_info("ds000001")["subject_info"]["participant_count"] == 1
    events = service.get_events("ds000001", "reward", path="sub-01/func/sub-01_task-reward_events.tsv")
    assert events["task_structure"]["trial_type_values"] == ["reward"]
    assert service.get_analysis_pipelines("ds000001")["pipelines"] == ["fmriprep"]
    assert service.get_associated_code("ds000001")["github_repositories"] == ["https://github.com/example/analysis"]
