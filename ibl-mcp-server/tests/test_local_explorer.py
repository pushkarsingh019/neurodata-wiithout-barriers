from __future__ import annotations

from pathlib import Path

from ibl_mcp.local_explorer import LocalIBLExplorer
from ibl_mcp.storage import MCPStorage, StorageConfig


def test_local_ibl_explorer_indexes_alf_dataset(tmp_path: Path) -> None:
    dataset_root = tmp_path / "ibl-session"
    alf_dir = dataset_root / "sub-mouse1" / "ses-2020-01-01" / "alf"
    probe_dir = dataset_root / "sub-mouse1" / "ses-2020-01-01" / "alf" / "probe00"
    alf_dir.mkdir(parents=True)
    probe_dir.mkdir(parents=True)
    (alf_dir / "_ibl_trials.intervals.npy").write_bytes(b"fake")
    (alf_dir / "_ibl_wheel.position.npy").write_bytes(b"fake")
    (probe_dir / "spikes.times.npy").write_bytes(b"fake")
    explorer = LocalIBLExplorer(MCPStorage(StorageConfig(provider="ibl", root_dir=tmp_path / "storage")))

    registered = explorer.register(path=str(dataset_root), session_id="session-test")
    indexed = explorer.index(registered["dataset_key"])
    inventory = explorer.signal_inventory(registered["dataset_key"])
    report = explorer.report(registered["dataset_key"])

    assert indexed["subjects"] == ["mouse1"]
    assert indexed["sessions"] == ["2020-01-01"]
    assert {"behavior", "ecephys"} <= set(indexed["modalities"])
    assert inventory["count"] == 3
    assert Path(report["report_path"]).exists()
