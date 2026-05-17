from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class Modality(str, Enum):
    MRI = "mri"
    FMRI = "fmri"
    DIFFUSION_MRI = "diffusion_mri"
    EEG = "eeg"
    MEG = "meg"
    IEEG = "ieeg"
    PET = "pet"
    BEHAVIOR = "behavior"
    PHYSIOLOGY = "physiology"
    VIDEO = "video"
    MOTION = "motion"
    DERIVATIVE = "derivative"
    UNKNOWN = "unknown"


class Species(str, Enum):
    HUMAN = "Homo sapiens"
    MOUSE = "Mus musculus"
    RAT = "Rattus norvegicus"
    MACAQUE = "Macaca"
    UNKNOWN = "unknown"


class Confidence(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    doi: str | None = None
    pubmed_id: str | None = None
    semantic_scholar_id: str | None = None
    arxiv_id: str | None = None
    title: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None
    relationship: Literal["primary", "methods", "reused_by", "related", "unknown"] = "unknown"
    provenance: list[str] = Field(default_factory=list)


class BehavioralParadigm(BaseModel):
    name: str
    normalized_name: str
    category: str | None = None
    stimuli: list[str] = Field(default_factory=list)
    responses: list[str] = Field(default_factory=list)
    reinforcement: list[str] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=lambda: Confidence(value=0.0))


class TaskStructure(BaseModel):
    task_name: str
    event_columns: list[str] = Field(default_factory=list)
    trial_type_values: list[str] = Field(default_factory=list)
    onset_range_seconds: tuple[float, float] | None = None
    duration_range_seconds: tuple[float, float] | None = None
    inferred_paradigms: list[BehavioralParadigm] = Field(default_factory=list)


class SubjectSummary(BaseModel):
    participant_count: int | None = None
    species: Species = Species.UNKNOWN
    species_confidence: Confidence = Field(default_factory=lambda: Confidence(value=0.0))
    columns: list[str] = Field(default_factory=list)
    categorical_fields: dict[str, list[str]] = Field(default_factory=dict)


class DatasetFile(BaseModel):
    id: str | None = None
    path: str
    filename: str
    size: int | None = None
    directory: bool = False
    annexed: bool | None = None
    modality: Modality = Modality.UNKNOWN
    bids_entity: dict[str, str] = Field(default_factory=dict)


class DatasetMetadata(BaseModel):
    id: str
    name: str | None = None
    version: str | None = None
    description: dict[str, Any] = Field(default_factory=dict)
    doi: str | None = None
    authors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    modalities: list[Modality] = Field(default_factory=list)
    species: Species = Species.UNKNOWN
    behavioral_paradigms: list[BehavioralParadigm] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    provenance: list[str] = Field(default_factory=list)


class DatasetSearchFilters(BaseModel):
    query: str | None = None
    modalities: list[Modality] = Field(default_factory=list)
    species: list[Species] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    paradigms: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    institutions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class SearchResult(BaseModel):
    dataset: DatasetMetadata
    score: float = Field(ge=0.0)
    matched_fields: list[str] = Field(default_factory=list)
    explanation: str | None = None
