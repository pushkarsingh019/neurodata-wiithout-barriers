from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    llm_base_url: str
    llm_model: str | None
    llm_timeout: float
    dandi_api_base_url: str
    storage_dir: Path
    sample_download_max_bytes: int
    cors_origins: tuple[str, ...]


def load_config() -> AppConfig:
    repo_root = Path(__file__).resolve().parents[4]
    return AppConfig(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", os.environ.get("NEURODATA_WEB_PORT", "8787"))),
        llm_base_url=os.environ.get("NEURODATA_LLM_BASE_URL", "").rstrip("/"),
        llm_model=os.environ.get("NEURODATA_LLM_MODEL") or None,
        llm_timeout=float(os.environ.get("NEURODATA_LLM_TIMEOUT", "90")),
        dandi_api_base_url=os.environ.get("DANDI_API_BASE_URL", "https://api.dandiarchive.org/api"),
        storage_dir=Path(
            os.environ.get(
                "NEURODATA_MCP_STORAGE_DIR",
                str(repo_root / ".mcp-storage"),
            )
        ),
        sample_download_max_bytes=int(os.environ.get("NEURODATA_SAMPLE_DOWNLOAD_MAX_BYTES", "250000000")),
        cors_origins=tuple(
            origin.strip()
            for origin in os.environ.get("NEURODATA_CORS_ORIGINS", "*").split(",")
            if origin.strip()
        ),
    )
