from __future__ import annotations

from pathlib import Path

from openneuro_mcp.local_explorer import LocalOpenNeuroExplorer
from openneuro_mcp.storage import MCPStorage, StorageConfig


def _write_sample_bids(root: Path) -> None:
    (root / "sub-01" / "func").mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        '{"Name": "Tiny BIDS", "BIDSVersion": "1.9.0", "DatasetType": "raw"}\n',
        encoding="utf-8",
    )
    (root / "participants.tsv").write_text("participant_id\tsex\nsub-01\tF\n", encoding="utf-8")
    (root / "sub-01" / "func" / "sub-01_task-rest_bold.nii.gz").write_text("fake", encoding="utf-8")
    (root / "sub-01" / "func" / "sub-01_task-rest_events.tsv").write_text(
        "onset\tduration\ttrial_type\n0\t1\tstart\n2\t1\tstop\n",
        encoding="utf-8",
    )


def test_local_openneuro_explorer_indexes_bids_dataset(tmp_path: Path) -> None:
    dataset_root = tmp_path / "ds-test"
    dataset_root.mkdir()
    _write_sample_bids(dataset_root)
    explorer = LocalOpenNeuroExplorer(MCPStorage(StorageConfig(provider="openneuro", root_dir=tmp_path / "storage")))

    registered = explorer.register(path=str(dataset_root), dataset_id="ds-test")
    indexed = explorer.index(registered["dataset_key"])
    events = explorer.extract_events(registered["dataset_key"], task="rest")
    report = explorer.report(registered["dataset_key"])

    assert indexed["subjects"] == ["01"]
    assert indexed["tasks"] == ["rest"]
    assert "fmri" in indexed["modalities"]
    assert events["row_count"] == 2
    assert Path(report["report_path"]).exists()
