from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StorageConfig:
    provider: str
    root_dir: Path

    @property
    def provider_dir(self) -> Path:
        return self.root_dir / self.provider

    @property
    def db_path(self) -> Path:
        return self.provider_dir / "metadata.sqlite3"

    @property
    def downloads_dir(self) -> Path:
        return self.provider_dir / "downloads"


class MCPStorage:
    """Shared local storage contract used by every neurodata MCP server."""

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self.config.provider_dir.mkdir(parents=True, exist_ok=True)
        self.config.downloads_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @classmethod
    def from_env(cls, provider: str) -> "MCPStorage":
        env_prefix = provider.upper().replace("-", "_")
        root = Path(
            os.environ.get(
                f"{env_prefix}_MCP_STORAGE_DIR",
                os.environ.get("NEURODATA_MCP_STORAGE_DIR", str(Path.home() / ".cache" / "neurodata-without-barriers")),
            )
        )
        return cls(StorageConfig(provider=provider, root_dir=root))

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.config.provider,
            "schema_version": SCHEMA_VERSION,
            "root_dir": str(self.config.root_dir),
            "provider_dir": str(self.config.provider_dir),
            "database": str(self.config.db_path),
            "downloads_dir": str(self.config.downloads_dir),
        }

    def upsert_record(
        self,
        record_type: str,
        record_id: str,
        payload: dict[str, Any],
        *,
        source: str,
        version: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO records(provider, record_type, record_id, version, source, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, json(?), CURRENT_TIMESTAMP)
                ON CONFLICT(provider, record_type, record_id, version) DO UPDATE SET
                    source = excluded.source,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (self.config.provider, record_type, record_id, version or "", source, _json(payload)),
            )

    def upsert_embedding(
        self,
        object_type: str,
        object_id: str,
        vector: Iterable[float],
        *,
        model: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        vector_values = list(vector)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO embeddings(provider, object_type, object_id, model, dimensions, vector_json, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, json(?), json(?), CURRENT_TIMESTAMP)
                ON CONFLICT(provider, object_type, object_id, model) DO UPDATE SET
                    dimensions = excluded.dimensions,
                    vector_json = excluded.vector_json,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    self.config.provider,
                    object_type,
                    object_id,
                    model,
                    len(vector_values),
                    _json(vector_values),
                    _json(payload or {}),
                ),
            )

    def replace_graph(self, graph_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO graphs(provider, graph_id, nodes_json, edges_json, updated_at)
                VALUES (?, ?, json(?), json(?), CURRENT_TIMESTAMP)
                ON CONFLICT(provider, graph_id) DO UPDATE SET
                    nodes_json = excluded.nodes_json,
                    edges_json = excluded.edges_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (self.config.provider, graph_id, _json(nodes), _json(edges)),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    provider TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, record_type, record_id, version)
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    provider TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, object_type, object_id, model)
                );
                CREATE TABLE IF NOT EXISTS graphs (
                    provider TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    nodes_json TEXT NOT NULL,
                    edges_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (provider, graph_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.config.db_path)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
