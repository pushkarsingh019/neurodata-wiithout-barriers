from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Provider = Literal["dandi", "openneuro", "ibl"]


class DatasetResolveRequest(BaseModel):
    value: str = Field(..., min_length=1)


class DatasetResolveResponse(BaseModel):
    provider: Provider
    dataset_id: str
    route: str
    source: str


class DatasetPage(BaseModel):
    provider: Provider = "dandi"
    dataset_id: str
    version: str = "draft"
    route: str
    summary: dict[str, Any]
    neuroscience: dict[str, Any]
    papers: list[dict[str, Any]]
    assets: dict[str, Any]
    ai_overview: str | None = None
    ai_status: Literal["ready", "unavailable", "error"] = "ready"
    ai_error: str | None = None


class VariableInventory(BaseModel):
    provider: Provider = "dandi"
    dataset_id: str
    source: Literal["local_index", "metadata", "archive"]
    local_index_status: Literal["indexed", "not_indexed", "missing_dependency", "error"]
    variables: list[dict[str, Any]]
    message: str | None = None


class VariableExplainRequest(BaseModel):
    variable: str = Field(..., min_length=1)
    file_path: str | None = None
    object_path: str | None = None
    context: str | None = None
    version: str = "draft"


class VariableExplainResponse(BaseModel):
    provider: Provider = "dandi"
    dataset_id: str
    variable: str
    loading_code: str
    explanation: str | None
    evidence: list[dict[str, Any]]
    context: dict[str, Any]
    preview: dict[str, Any] | None = None
    confidence_label: str = "unknown"
    ai_status: Literal["ready", "unavailable", "error"] = "ready"
    ai_error: str | None = None


class IndexLocalRequest(BaseModel):
    path: str
    dandiset_id: str | None = None
    version: str | None = None
    inspect_limit: int = Field(25, ge=1, le=500)


class IndexLocalResponse(BaseModel):
    status: Literal["indexed", "dependency_missing", "error"]
    dataset_key: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class DownloadSampleRequest(BaseModel):
    version: str = "draft"
    max_assets: int = Field(1, ge=1, le=5)
    max_bytes: int | None = Field(default=None, ge=1)


class DownloadSampleResponse(BaseModel):
    status: Literal["downloaded", "skipped", "error"]
    downloads: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None


class SkillStatusResponse(BaseModel):
    provider: Provider = "dandi"
    dataset_id: str
    ready: bool
    total_variables: int
    cached_variables: int
    missing_variables: list[dict[str, Any]] = Field(default_factory=list)
    message: str


class SkillPrepareResponse(SkillStatusResponse):
    generated_variables: int = 0
    failed_variables: list[dict[str, Any]] = Field(default_factory=list)
