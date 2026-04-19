"""
NLP pipeline output models.

ClinicalEntity is the atomic output unit of the NER pipeline.
Negation and temporal status are required fields — the rules engine
depends on is_negated and temporal_status to avoid coding
historically-mentioned or family-history conditions.

Constitution: Article II.2 (source citation — entity.text is the source)
Spec: specs/01-coding-rules-engine.md §4 (NLP step)
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NoteSection(str, Enum):
    """Section of the clinical note where an entity was found."""

    SUBJECTIVE = "subjective"
    OBJECTIVE = "objective"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    HISTORY = "history"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    DISEASE = "DISEASE"
    FINDING = "FINDING"
    CHEMICAL = "CHEMICAL"
    PROCEDURE = "PROCEDURE"
    ANATOMY = "ANATOMY"
    LAB_VALUE = "LAB_VALUE"


class TemporalStatus(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FAMILY = "family"


class ClinicalEntity(BaseModel):
    """
    A clinical entity extracted from a note by the NER pipeline.

    is_negated=True means the condition was documented as absent.
    temporal_status=HISTORICAL means it is past, not current.
    Both must be checked before suggesting an ICD-10 code.
    """

    text: str  # verbatim text from note — this IS the evidence_quote source
    entity_type: EntityType
    start_char: int
    end_char: int
    source_section: NoteSection
    is_negated: bool
    negation_cue: str | None = None  # e.g. "no", "denies", "without"
    temporal_status: TemporalStatus
    temporal_cue: str | None = None  # e.g. "history of", "prior"
    confidence: float = Field(ge=0.0, le=1.0)


class NLPResult(BaseModel):
    """Complete output of the NLP pipeline for one clinical note."""

    entities: list[ClinicalEntity] = Field(default_factory=list)
    sections: dict[str, str] = Field(default_factory=dict)
    processing_time_ms: float = 0.0
    entity_count: int = 0
    negated_count: int = 0
    historical_count: int = 0
    is_degraded: bool = False
