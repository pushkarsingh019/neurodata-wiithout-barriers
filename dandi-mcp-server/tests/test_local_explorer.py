from __future__ import annotations

from pathlib import Path

import pytest

from dandi_mcp.local_explorer import LocalDandisetExplorer
from dandi_mcp.storage import MCPStorage, StorageConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DANDISET = REPO_ROOT / "001097"


def _explorer(tmp_path: Path) -> LocalDandisetExplorer:
    storage = MCPStorage(StorageConfig(provider="dandi", root_dir=tmp_path / "storage"))
    return LocalDandisetExplorer(storage)


def test_register_and_browse_local_dandiset(tmp_path: Path) -> None:
    explorer = _explorer(tmp_path)

    registered = explorer.register(path=str(SAMPLE_DANDISET))
    summary = explorer.summarize(registered["dataset_key"])
    files = explorer.list_files(registered["dataset_key"], file_type="nwb")
    browse = explorer.browse(registered["dataset_key"])

    assert registered["dandiset_id"] == "001097"
    assert registered["nwb_file_count"] == 2
    assert summary["file_type_counts"]["nwb"] == 2
    assert files["count"] == 2
    assert {item["path"] for item in browse["children"]} >= {"dandiset.yaml", "sub-m541", "sub-m542"}


@pytest.mark.skipif(not SAMPLE_DANDISET.exists(), reason="sample Dandiset is not available")
def test_inspect_index_and_report_sample_nwb(tmp_path: Path) -> None:
    explorer = _explorer(tmp_path)
    registered = explorer.register(path=str(SAMPLE_DANDISET))
    key = registered["dataset_key"]

    inspected = explorer.inspect_nwb(key, "sub-m541/sub-m541_behavior.nwb")
    indexed = explorer.index(key)
    inventory = explorer.signal_inventory(key)
    report = explorer.report(key)

    assert inspected["status"] == "ok"
    assert inspected["subject"]["subject_id"] == "m541"
    assert "ophys" in {module["name"] for module in inspected["processing"]}
    assert indexed["nwb_file_count"] == 2
    assert set(indexed["subjects"]) == {"m541", "m542"}
    assert inventory["count"] >= 1
    assert Path(report["report_path"]).exists()


def test_extract_trials_reports_not_found_for_sample_without_trials(tmp_path: Path) -> None:
    explorer = _explorer(tmp_path)
    registered = explorer.register(path=str(SAMPLE_DANDISET))

    result = explorer.extract_trials(
        registered["dataset_key"],
        "sub-m541/sub-m541_behavior.nwb",
        limit=5,
    )

    assert result["status"] == "not_found"
    assert result["trials"]["present"] is False
