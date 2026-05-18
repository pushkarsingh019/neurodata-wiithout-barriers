from __future__ import annotations

import sys
from pathlib import Path


def ensure_repo_imports() -> Path:
    backend_src = Path(__file__).resolve()
    repo_root = backend_src.parents[4]
    paths = [
        repo_root / "dandi-mcp-server" / "src",
        repo_root / "openneuro-mcp-server" / "src",
        repo_root / "ibl-mcp-server" / "src",
    ]
    for path in paths:
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    return repo_root
