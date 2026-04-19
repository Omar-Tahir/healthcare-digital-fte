"""
HIPAA audit log models.

Two distinct audit models:
  AuditLogEntry    — FHIR write pre-authorization audit (G-HARD-006).
                     Records who is writing what to a PHI system.
  UserActionAuditEntry — Coder UI action audit (HIPAA access log).
                         The 'details' dict is PHI-checked at model creation.

PHI_FIELD_NAMES enforces constitution Article II.4 at the data layer:
PHI field names in audit details raise ValidationError before any write.

Constitution: Article II.4 (no PHI in logs)
Spec: specs/01-coding-rules-engine.md §7 (audit), specs/06 §5
Skill: docs/skills/hipaa-compliance.md Section 1 & 2
ADR: ADR-005 (HIPAA logging)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

# PHI field names that can never appear in audit log details.
# Source: docs/skills/hipaa-compliance.md Section 1 (18 PHI identifiers).
PHI_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "patient_name",
        "name",
        "first_name",
        "last_name",
        "date_of_birth",
        "dob",
        "birth_date",
        "address",
        "street",
        "city",
        "zip",
        "postal_code",
        "phone",
        "telephone",
        "fax",
        "email",
        "email_address",
        "ssn",
        "social_security",
        "mrn",
        "medical_record_number",
        "insurance_id",
        "member_id",
        "subscriber_id",
        "note_text",
        "clinical_content",
        "note_content",
        "evidence_quote",
        "clinical_note",
        "diagnosis_text",
        "assessment",
    }
)


class AuditAction(str, Enum):
    """Actions performed by coders — logged for HIPAA access audit trail."""

    VIEWED = "VIEWED"
    ACCEPTED_CODE = "ACCEPTED_CODE"
    REJECTED_CODE = "REJECTED_CODE"
    MODIFIED_CODE = "MODIFIED_CODE"
    SENT_CDI_QUERY = "SENT_CDI_QUERY"
    DISMISSED_CDI = "DISMISSED_CDI"
    SUBMITTED_CLAIM = "SUBMITTED_CLAIM"
    TOKEN_GENERATED = "TOKEN_GENERATED"
    TOKEN_VALIDATED = "TOKEN_VALIDATED"
    TOKEN_REJECTED = "TOKEN_REJECTED"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    GUARDRAIL_TRIGGERED = "GUARDRAIL_TRIGGERED"
    DEGRADED_MODE = "DEGRADED_MODE"


class AuditLogEntry(BaseModel):
    """
    FHIR write pre-authorization audit entry (G-HARD-006).

    Written BEFORE the FHIR write operation. If the write_audit_log()
    call fails, the FHIR write does not proceed — per constitution II.4.

    user_id is Optional to allow the model to be constructed with user_id=None
    (the fhir_audit_guardrail then rejects the incomplete entry).
    """

    operation: str  # "create", "update", "delete"
    resource_type: str  # "Claim", "DocumentReference", etc.
    resource_id: str
    user_id: str | None = None  # None = incomplete, guardrail rejects
    user_role: str
    encounter_id: str
    justification: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UserActionAuditEntry(BaseModel):
    """
    Coder UI action audit entry — HIPAA access log for PHI data.

    The 'details' dict is validated at model creation: PHI field names
    raise ValidationError before the entry is written anywhere.
    Retained for HIPAA-required 2,190 days (6 years).

    Safe fields for details: code, confidence, guardrail_id, duration_ms,
    suggestion_count, drg_delta, session_id, model_version.
    See docs/skills/hipaa-compliance.md Section 2 for full safe list.
    """

    coder_id: str  # internal user identifier — not PHI
    encounter_id: str  # FHIR Encounter.id — not PHI
    action: AuditAction
    code: str | None = None  # ICD-10 code if action involves one
    session_id: str
    details: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_no_phi_in_details(self) -> "UserActionAuditEntry":
        """
        Hard enforcement of constitution Article II.4 at data layer.
        PHI field names in details raise ValueError (wrapped as ValidationError).
        """
        for key in self.details:
            if key.lower() in PHI_FIELD_NAMES:
                raise ValueError(
                    f"PHI field '{key}' detected in audit log details. "
                    f"Audit logs must never contain PHI. "
                    f"Constitution Article II.4. "
                    f"Remove '{key}' or replace value with a safe identifier."
                )
        return self
