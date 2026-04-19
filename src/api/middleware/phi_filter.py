"""
PHI Filter Processor — G-HARD-005.

Structlog processor that detects PHI field names in log entries and
raises CodingGuidelineViolationError before the log is written.

This is the data-layer enforcement of constitution Article II.4.
It runs BEFORE any log output — PHI never reaches the log sink.

The PHI_LOG_FIELD_NAMES blocklist is derived from HIPAA's 18 PHI
identifier categories (docs/skills/hipaa-compliance.md Section 1).

Constitution: Article II.4
Spec: specs/03-compliance-guardrail-architecture.md §1 G-HARD-005
Skill: docs/skills/hipaa-compliance.md Section 3
ADR: ADR-005 (HIPAA logging)
"""
from __future__ import annotations

import structlog

from src.core.exceptions import CodingGuidelineViolationError
from src.core.models.audit import PHI_FIELD_NAMES as _AUDIT_PHI_FIELDS

_GUARDRAIL_ID = "G-HARD-005"

# Union of audit model PHI fields + additional log-specific PHI fields
_LOG_PHI_FIELDS: frozenset[str] = _AUDIT_PHI_FIELDS | frozenset(
    {
        "patient_name",
        "mrn",
        "medical_record_number",
        "evidence_quote",
        "note_text",
        "clinical_text",
        "note_content",
    }
)


class PHIFilterProcessor:
    """
    Structlog processor that blocks PHI fields from log entries.

    Usage (in structlog configuration):
        structlog.configure(
            processors=[PHIFilterProcessor().process_log_entry, ...]
        )

    Or directly in tests:
        processor = PHIFilterProcessor()
        result = processor.process_log_entry(logger, method, event_dict)
        # Raises CodingGuidelineViolationError if PHI detected
        # Returns event_dict if clean
    """

    def process_log_entry(
        self,
        logger: object,
        method: str,
        event_dict: dict,
    ) -> dict:
        """
        Scan event_dict for PHI field names.
        Raises CodingGuidelineViolationError if any PHI field is detected.
        Returns event_dict unchanged if clean.

        Constitution: Article II.4 — PHI never in logs.
        """
        phi_violations = [
            key for key in event_dict
            if key.lower() in _LOG_PHI_FIELDS
        ]

        if phi_violations:
            raise CodingGuidelineViolationError(
                guardrail_id=_GUARDRAIL_ID,
                description=(
                    f"PHI field(s) detected in log entry: {phi_violations}. "
                    "These fields must never appear in logs. "
                    "Constitution Article II.4."
                ),
                constitution_article="II.4",
                suggested_remediation=(
                    f"Remove fields {phi_violations} from the log call. "
                    "Safe alternatives: encounter_id, code, confidence, "
                    "duration_ms, suggestion_count."
                ),
            )

        return event_dict
