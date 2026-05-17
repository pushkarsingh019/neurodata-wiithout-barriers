from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (
    ROOT / "web-app" / "backend" / "src",
    ROOT / "dandi-mcp-server" / "src",
):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

os.environ.setdefault("NEURODATA_MCP_STORAGE_DIR", "/tmp/neurodata-mcp-storage")

from neurodata_web.main import app  # noqa: E402
