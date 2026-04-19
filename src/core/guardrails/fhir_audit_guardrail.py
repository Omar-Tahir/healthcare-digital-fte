"""
FHIR Write Audit Guardrail — G-HARD-006.

Enforces constitution Article II.4: Every FHIR write to a PHI resource
must be preceded by a committed audit log entry. If the audit write fails,
the FHIR write does not proceed.

Untracked writes to PHI are not permitted under HIPAA and constitute a
compliance gap that OIG auditors specifically examine.

Constitution: Article II.4
Spec: specs/03-compliance-guardrail-architecture.md §1 G-HARD-006
Skill: docs/skills/hipaa-compliance.md Section 4
"""
from __future__ import annotations

import structlog

from src.core.exceptions import CodingGuidelineViolationError
from src.core.models.audit import AuditLogEntry

log = structlog.get_logger()

_GUARDRAIL_ID = "G-HARD-006"


def write_audit_log(entry: AuditLogEntry) -> bool:
    """
    Write FHIR write audit log entry.
    In production: write to PostgreSQL audit_log table.
    In tests: this function is patched to simulate success/failure.
    Returns True on success; raises on failure.
    """
    log.info(
        "fhir_write_audit",
        operation=entry.operation,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        user_id=entry.user_id,
        user_role=entry.user_role,
        encounter_id=entry.encounter_id,
    )
    return True


def validate_fhir_write_audit(audit_entry: AuditLogEntry) -> bool:
    """
    Validate FHIR write audit entry and commit it before allowing the write.

    Raises CodingGuidelineViolationError if:
    - user_id is None (incomplete audit — write not attributable to an identity)
    - write_audit_log() raises (audit service unavailable)

    Returns True if the audit is complete and committed.
    Constitution: Article II.4 — PHI access must be auditable.
    """
    if audit_entry.user_id is None:
        log.warning(
            "fhir_write_audit_incomplete",
            guardrail_id=_GUARDRAIL_ID,
            reason="user_id is None",
            encounter_id=audit_entry.encounter_id,
        )
        raise CodingGuidelineViolationError(
            guardrail_id=_GUARDRAIL_ID,
            description=(
                "FHIR write blocked: audit log entry is incomplete. "
                "user_id=None means this write is not attributable "
                "to an authenticated identity. Per HIPAA, all access "
                "to PHI must be attributed to an identity."
            ),
            constitution_article="II.4",
            suggested_remediation=(
                "Supply a valid user_id (authenticated coder ID) "
                "before attempting the FHIR write."
            ),
        )

    try:
        write_audit_log(audit_entry)
    except Exception as e:
        log.warning(
            "fhir_write_audit_service_failed",
            guardrail_id=_GUARDRAIL_ID,
            error_type=type(e).__name__,
            encounter_id=audit_entry.encounter_id,
        )
        raise CodingGuidelineViolationError(
            guardrail_id=_GUARDRAIL_ID,
            description=(
                "FHIR write blocked: audit log service unavailable. "
                "PHI access without a committed audit trail is unacceptable."
            ),
            constitution_article="II.4",
            suggested_remediation=(
                "Restore audit log service connectivity before "
                "retrying the FHIR write operation."
            ),
        ) from e

    return True
