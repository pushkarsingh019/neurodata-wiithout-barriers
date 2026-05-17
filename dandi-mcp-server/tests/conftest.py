from __future__ import annotations

import os
import tempfile


os.environ.setdefault("NEURODATA_MCP_STORAGE_DIR", tempfile.mkdtemp(prefix="neurodata-storage-"))
