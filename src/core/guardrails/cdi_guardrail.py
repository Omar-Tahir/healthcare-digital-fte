"""
CDI Query Escalation Guardrail — G-SOFT-005.

Enforces constitution Article II.6 (conservative defaults): Generating
a 3rd+ CDI query on the same encounter risks physician notification fatigue.
A known OIG compliance concern where physicians reflexively answer "yes"
without clinical reassessment.

When query_count >= 2, the 3rd CDI opportunity is routed to CDI specialist
review before being sent to the physician.

The guardrail is SOFT — the CDI specialist makes the final judgment about
whether to proceed, modify, or suppress the query.

Constitution: Article II.6
Spec: specs/03-compliance-guardrail-architecture.md §1 G-SOFT-005
Research: docs/research/DISC-002-documentation-failure-patterns.md
"""
from __future__ import annotations

import structlog

from src.core.exceptions import GuardrailWarning
from src.core.models.cdi import CDIOpportunity

log = structlog.get_logger()

_GUARDRAIL_ID = "G-SOFT-005"
_ESCALATION_THRESHOLD = 2  # escalate when existing_query_count >= 2


def apply_cdi_query_escalation(
    opportunity: CDIOpportunity,
    existing_query_count: int,
) -> CDIOpportunity:
    """
    Apply CDI query escalation rule (G-SOFT-005).

    If existing_query_count >= 2 (this would be the 3rd+ query):
    → routing = "cdi_specialist_review"
    → Add G-SOFT-005 warning

    If existing_query_count < 2 (first or second query):
    → routing = "physician_direct"
    → No warning added
    """
    if existing_query_count >= _ESCALATION_THRESHOLD:
        warning = GuardrailWarning(
            guardrail_id=_GUARDRAIL_ID,
            severity="medium",
            warning_message=(
                f"This encounter already has {existing_query_count} CDI queries. "
                "A 3rd+ query risks physician notification fatigue — an OIG "
                "compliance concern where physicians reflexively agree without "
                "clinical reassessment. CDI specialist review required before "
                "sending to the physician."
            ),
            requires_explicit_acknowledgment=True,
        )

        log.info(
            "cdi_query_escalated",
            guardrail_id=_GUARDRAIL_ID,
            encounter_id=opportunity.encounter_id,
            existing_query_count=existing_query_count,
        )

        updated_warnings = list(opportunity.warnings) + [warning]
        return opportunity.model_copy(update={
            "routing": "cdi_specialist_review",
            "warnings": updated_warnings,
        })

    return opportunity.model_copy(update={"routing": "physician_direct"})
