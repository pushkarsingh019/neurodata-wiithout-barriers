from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from openneuro_mcp.bids import parse_dataset_description, parse_participants_tsv
from openneuro_mcp.client import OpenNeuroClient
from openneuro_mcp.service import OpenNeuroSemanticService


def main() -> int:
    parser = argparse.ArgumentParser(description="Live OpenNeuro MCP smoke test.")
    parser.add_argument("--dataset-id", default="ds000001")
    parser.add_argument("--workdir", default="/private/tmp/openneuro-mcp-smoke")
    args = parser.parse_args()

    dataset_id = args.dataset_id
    workdir = Path(args.workdir)
    clone_dir = workdir / dataset_id

    client = OpenNeuroClient()
    service = OpenNeuroSemanticService(client)

    print(f"1. Querying OpenNeuro dataset {dataset_id}")
    dataset = client.get_dataset(dataset_id)
    snapshot = client.get_snapshot(dataset_id)
    print(json.dumps({"id": dataset["id"], "name": dataset["name"], "latest": snapshot["tag"]}, indent=2))

    print("2. Fetching and classifying top-level files")
    files = service.get_dataset_files(dataset_id, recursive=False)
    top_level = [item["filename"] for item in files["files"]]
    print(json.dumps({"top_level_count": len(top_level), "sample": top_level[:10]}, indent=2))
    assert "dataset_description.json" in top_level

    print("3. Enriching dataset metadata through the service layer")
    metadata = service.get_dataset_metadata(dataset_id, include_files=True)
    print(
        json.dumps(
            {
                "name": metadata["name"],
                "modalities": metadata["modalities"],
                "species": metadata["species"],
                "quality": metadata["quality"],
                "bids_summary": {
                    "file_count": metadata["bids_summary"]["file_count"],
                    "tasks": metadata["bids_summary"]["tasks"][:10],
                    "has_derivatives": metadata["bids_summary"]["has_derivatives"],
                },
            },
            indent=2,
        )
    )

    print("4. Downloading public Git mirror")
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    workdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            f"https://github.com/OpenNeuroDatasets/{dataset_id}.git",
            str(clone_dir),
        ],
        check=True,
    )

    print("5. Validating downloaded BIDS metadata")
    description_path = clone_dir / "dataset_description.json"
    participants_path = clone_dir / "participants.tsv"
    assert description_path.exists(), "dataset_description.json missing from downloaded dataset"
    description = parse_dataset_description(description_path.read_text())
    participants = parse_participants_tsv(participants_path.read_text() if participants_path.exists() else None)
    print(
        json.dumps(
            {
                "downloaded_path": str(clone_dir),
                "description_name": description.get("Name"),
                "bids_version": description.get("BIDSVersion"),
                "participant_count": participants.participant_count,
                "participant_columns": participants.columns,
            },
            indent=2,
        )
    )

    print("SMOKE_TEST_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
