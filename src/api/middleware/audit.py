"""
HIPAA audit logging middleware.

Every user action is written to the audit trail.
Audit records contain only identifiers + actions — never PHI.
Retention: 2,190 days (6 years) per HIPAA requirements.

Constitution: II.4 (no PHI in audit log)
Spec: specs/06-coder-review-ui.md §5
Skill: docs/skills/hipaa-compliance.md Section 4
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone

from src.core.models.audit import AuditAction, UserActionAuditEntry

log = structlog.get_logger()


def write_audit_log(entry: UserActionAuditEntry) -> None:
    """
    Write audit log entry.
    In production: write to PostgreSQL audit_log table.
    In development: write to structlog (captured in tests).

    UserActionAuditEntry model_validator already enforces
    that no PHI field names appear in details.
    """
    log.info(
        "audit_event",
        timestamp=entry.timestamp.isoformat(),
        coder_id=entry.coder_id,
        encounter_id=entry.encounter_id,
        action=entry.action.value,
        code=entry.code,
        session_id=entry.session_id,
        **({"details": entry.details} if entry.details else {}),
    )


def create_audit_entry(
    coder_id: str,
    encounter_id: str,
    action: AuditAction,
    session_id: str = "dev-session",
    code: str | None = None,
    details: dict | None = None,
) -> UserActionAuditEntry:
    """Helper to create audit entries without boilerplate."""
    return UserActionAuditEntry(
        coder_id=coder_id,
        encounter_id=encounter_id,
        action=action,
        session_id=session_id,
        code=code,
        details=details or {},
        timestamp=datetime.now(timezone.utc),
    )
