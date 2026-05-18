#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import time
from urllib import request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warm a dataset skill cache.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--provider", default="dandi", choices=["dandi", "openneuro", "ibl"])
    parser.add_argument("--dataset-id", default="001097")
    return parser.parse_args()


def get_json(base_url: str, path: str) -> dict:
    with request.urlopen(f"{base_url}{path}", timeout=60) as response:
        return json.loads(response.read())


def post_json(base_url: str, path: str, payload: dict, timeout: int = 240) -> dict:
    req = request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def main() -> None:
    args = parse_args()
    dataset_path = f"/api/{args.provider}/{args.dataset_id}"
    status = get_json(args.base_url, f"{dataset_path}/skill-status")
    print(json.dumps(status, indent=2), flush=True)
    if status.get("ready"):
        print("CACHE_READY", flush=True)
        return

    missing = status.get("missing_variables", [])
    total = len(missing)
    for index, variable in enumerate(missing, start=1):
        payload = {
            "variable": variable.get("name") or variable.get("object_path") or "variable",
            "file_path": variable.get("file"),
            "object_path": variable.get("object_path"),
        }
        label = f"{payload['variable']} | {payload['file_path']}"
        start = time.time()
        try:
            result = post_json(
                args.base_url,
                f"{dataset_path}/variables/explain",
                payload,
                timeout=300,
            )
            print(
                f"[{index:02d}/{total:02d}] {time.time() - start:6.1f}s "
                f"{result.get('ai_status')} {result.get('confidence_label')} :: {label}",
                flush=True,
            )
        except Exception as exc:
            print(f"[{index:02d}/{total:02d}] FAIL :: {label} :: {exc}", flush=True)

    final_status = get_json(args.base_url, f"{dataset_path}/skill-status")
    print(json.dumps(final_status, indent=2), flush=True)
    print("CACHE_READY" if final_status.get("ready") else "CACHE_INCOMPLETE", flush=True)


if __name__ == "__main__":
    main()
