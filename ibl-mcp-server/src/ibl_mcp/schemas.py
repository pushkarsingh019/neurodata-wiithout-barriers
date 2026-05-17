from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


QCRisk = Literal["ok", "warning", "critical", "unknown"]


class Provenance(BaseModel):
    """Machine-readable provenance included in high-level tool outputs."""

    source: str = "International Brain Laboratory OpenAlyx"
    alyx_base_url: str
    endpoint: str | None = None
    session_id: str | None = None
    dataset_ids: list[str] = Field(default_factory=list)
    dataset_names: list[str] = Field(default_factory=list)
    generated_by: str = "ibl-mcp-server"


class QCWarning(BaseModel):
    """Quality or availability warning surfaced to agents."""

    risk: QCRisk
    code: str
    message: str
    affected: list[str] = Field(default_factory=list)


class ToolEnvelope(BaseModel):
    """Common response envelope for AI-native tools."""

    ok: bool = True
    data: Any
    qc: list[QCWarning] = Field(default_factory=list)
    provenance: Provenance
    next_actions: list[str] = Field(default_factory=list)

    def model_dump_plain(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class DatasetNeed(BaseModel):
    """Named dataset pattern expected for an IBL modality."""

    name: str
    required: bool = False
    description: str


class KnowledgeGraphQuery(BaseModel):
    """Tiny graph query contract for the current in-process graph scaffold."""

    entity_type: str | None = None
    predicate: str | None = None
    value: str | None = None
    limit: int = 25
