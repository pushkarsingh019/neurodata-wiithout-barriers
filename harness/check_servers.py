#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


SERVERS = {
    "dandi": {
        "directory": "dandi-mcp-server",
        "module": "dandi_mcp.server",
    },
    "ibl": {
        "directory": "ibl-mcp-server",
        "module": "ibl_mcp.server",
    },
    "openneuro": {
        "directory": "openneuro-mcp-server",
        "module": "openneuro_mcp.server",
    },
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def check_server(root: Path, name: str, directory: str, module: str) -> bool:
    project_dir = root / directory
    code = (
        f"from {module} import build_server; "
        "server = build_server(); "
        "print(type(server).__name__)"
    )
    command = [
        "uv",
        "--directory",
        str(project_dir),
        "run",
        "python",
        "-c",
        code,
    ]
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(project_dir / ".uv-cache")
    env.setdefault("NEURODATA_MCP_STORAGE_DIR", str(root / ".mcp-storage"))
    result = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
    if result.returncode == 0:
        print(f"ok\t{name}\t{result.stdout.strip()}")
        return True

    print(f"fail\t{name}", file=sys.stderr)
    if result.stdout:
        print(result.stdout.strip(), file=sys.stderr)
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return False


def main() -> None:
    root = repo_root()
    ok = True
    for name, server in SERVERS.items():
        ok = check_server(root, name, server["directory"], server["module"]) and ok
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
