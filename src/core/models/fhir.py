"""
FHIR R4 resource models and the DegradedResult contract.

FHIRPatient intentionally omits name, birthDate, and other PHI fields —
they are never needed by the coding or CDI logic and must never reach logs.

DegradedResult enforces constitution Article II.5: the system never
returns HTTP 500 or raises unhandled exceptions to the coder UI.

Constitution: Article II.4 (no PHI), II.5 (graceful degradation)
Spec: specs/05-fhir-integration.md
Skill: docs/skills/fhir-r4-integration.md
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.core.models.encounter import EncounterClass


class NoteContentType(str, Enum):
    PLAIN_TEXT = "plain_text"
    CDA_XML = "cda_xml"
    PDF_BASE64 = "pdf_base64"
    UNKNOWN = "unknown"


class FHIRPatient(BaseModel):
    """
    Minimal FHIR Patient fields for coding context.

    name and birthDate are intentionally absent — they are PHI and are
    never required by coding or CDI logic. Display masking (if any) is
    handled exclusively in the UI layer.
    """

    id: str  # FHIR Patient.id — system identifier, not PHI


class FHIRDocumentReference(BaseModel):
    """FHIR DocumentReference — clinical note with metadata."""

    id: str
    encounter_id: str
    note_type_loinc: str  # e.g. "34117-2" for H&P, "11488-4" for consult
    note_type_display: str
    authored_date: datetime
    content_type: NoteContentType
    note_text: str | None = None
    # note_text is None if extraction failed → triggers DegradedResult


class FHIREncounter(BaseModel):
    """FHIR Encounter — the admission or visit being coded."""

    id: str
    status: str  # "in-progress", "finished", "cancelled"
    class_code: str  # raw Epic class code before mapping
    encounter_class: EncounterClass  # mapped via EncounterClass enum
    period_start: datetime
    period_end: datetime | None = None
    attending_physician_id: str | None = None


class FHIRObservation(BaseModel):
    """
    Lab values and vitals — used by CDI agent for trigger detection.
    e.g. creatinine rise detection for AKI CDI opportunity (CDI-SEV-001).
    """

    id: str
    loinc_code: str
    display: str  # e.g. "Creatinine [Mass/volume] in Serum"
    value_quantity: float | None = None
    value_string: str | None = None
    unit: str | None = None
    effective_datetime: datetime
    interpretation: str | None = None  # "H" high, "L" low, "N" normal


class FHIRCondition(BaseModel):
    """Problem list entry — active diagnoses from the EHR."""

    id: str
    icd10_code: str | None = None
    snomed_code: str | None = None
    display: str
    clinical_status: str  # "active", "resolved", "inactive"
    recorded_date: datetime


class DegradedResult(BaseModel):
    """
    Returned by any agent or FHIR client on failure.

    Enforces constitution Article II.5: the API never returns HTTP 500.
    The UI receives this and enters manual mode — the coder continues
    working without AI suggestions until the system recovers.

    suggestions is always an empty list when is_degraded=True.
    error_message must never contain PHI — only system error descriptions.
    """

    is_degraded: bool = True
    suggestions: list[Any] = Field(default_factory=list)
    error_code: str = ""
    error_message: str = ""  # System error only — never PHI
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    partial_data: dict[str, Any] | None = None
