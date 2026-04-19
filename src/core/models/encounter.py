"""
Encounter and patient context models.

Defines the encounter classification logic that determines which
ICD-10 coding rules apply. OBS (observation) maps to OUTPATIENT —
the most commonly confused mapping in hospital coding.

Constitution: Article II.3 (ICD-10 hard constraints), II.4 (no PHI)
Spec: specs/01-coding-rules-engine.md §1
Skill: docs/skills/icd10-coding-rules.md Rule 2 (outpatient uncertain dx)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EncounterClass(str, Enum):
    """
    Epic FHIR encounter class codes.
    OBS maps to OUTPATIENT for ICD-10 coding purposes.
    Per CMS OBS status rules + ICD-10-CM Official Guidelines.
    """

    INPATIENT = "IMP"
    OUTPATIENT = "AMB"
    EMERGENCY = "EMER"
    OBSERVATION = "OBS"


# The classes that trigger outpatient coding rules.
# OBS is here — this is the most commonly confused mapping.
OUTPATIENT_ENCOUNTER_CLASSES: frozenset[EncounterClass] = frozenset(
    {EncounterClass.OUTPATIENT, EncounterClass.EMERGENCY, EncounterClass.OBSERVATION}
)

INPATIENT_ENCOUNTER_CLASSES: frozenset[EncounterClass] = frozenset(
    {EncounterClass.INPATIENT}
)


class CodingClass(str, Enum):
    """
    Simplified two-way classification for coding rule application.
    OBS collapses to OUTPATIENT here — always.
    """

    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"


# Full uncertainty qualifier word list per ICD-10-CM Section IV.H.
# Outpatient + any of these = cannot code as confirmed diagnosis.
# Inpatient + any of these = may code as confirmed (Section II.H).
# Skill reference: docs/skills/icd10-coding-rules.md Rule 2
UNCERTAINTY_QUALIFIERS: frozenset[str] = frozenset(
    {
        "possible",
        "probable",
        "suspected",
        "rule out",
        "working diagnosis",
        "questionable",
        "likely",
        "still to be ruled out",
        "concern for",
        "appears to be",
        "consistent with",
        "compatible with",
        "indicative of",
        "suggestive of",
        "comparable with",
    }
)


def get_coding_class(encounter_class: EncounterClass) -> CodingClass:
    """
    The single authoritative function for encounter → coding rule mapping.

    Called by: rules engine, coding agent, CDI agent.
    Never duplicated inline — always call this function.
    """
    if encounter_class in OUTPATIENT_ENCOUNTER_CLASSES:
        return CodingClass.OUTPATIENT
    return CodingClass.INPATIENT


class EncounterContext(BaseModel):
    """
    Minimal encounter context for coding analysis requests.

    Simple model used by the coding agent input — does not carry
    PHI content fields. encounter_setting is a plain string matching
    the test interface ("inpatient", "outpatient", "observation").
    """

    encounter_id: str
    encounter_setting: str  # "inpatient", "outpatient", "observation"
    note_text: str


class PatientContext(BaseModel):
    """
    Full patient context for FHIR-integrated analysis.

    Only system identifiers — no PHI content fields.
    Per constitution Article II.4 + docs/skills/hipaa-compliance.md.
    NEVER ADD: patient_name, dob, mrn, address, phone, ssn.
    """

    patient_id: str = Field(description="FHIR Patient.id — system identifier, not PHI")
    encounter_id: str = Field(description="FHIR Encounter.id — system identifier")
    encounter_class: EncounterClass
    coding_class: CodingClass
    encounter_date: datetime
