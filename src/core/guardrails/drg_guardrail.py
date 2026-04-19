"""
DRG Compliance Threshold Guardrail — G-SOFT-003.

Enforces constitution Article II.6: Revenue delta > $5,000 requires
compliance team review before the coder can accept the suggestion.

Not a hard stop — the coder can still accept with compliance team approval.
But autonomous acceptance of high-value suggestions without compliance
review is an FCA exposure vector.

Constitution: Article II.6
Spec: specs/03-compliance-guardrail-architecture.md §1 G-SOFT-003
Skill: docs/skills/drg-optimization.md
"""
from __future__ import annotations

import structlog

from src.core.models.coding import CodingSuggestion
from src.core.models.drg import DRGComplianceResult, DRGImpact

log = structlog.get_logger()

_COMPLIANCE_THRESHOLD = 5000.0  # dollars


def apply_drg_compliance_threshold(
    suggestion: CodingSuggestion,
    drg_impact: DRGImpact,
) -> DRGComplianceResult:
    """
    Apply G-SOFT-003: flag suggestions where DRG revenue delta > $5,000
    for compliance team review.

    Returns DRGComplianceResult with compliance_review_required=True
    and a compliance_review_reason if threshold is exceeded.
    The DRGImpact model also auto-sets requires_compliance_review via
    its own model_validator for delta > $5,000.
    """
    if drg_impact.revenue_difference > _COMPLIANCE_THRESHOLD:
        reason = (
            f"Code {suggestion.code} would increase DRG revenue by "
            f"${drg_impact.revenue_difference:,.2f} (threshold: "
            f"${_COMPLIANCE_THRESHOLD:,.0f}). "
            "Compliance team review required before acceptance."
        )

        log.info(
            "drg_compliance_threshold_exceeded",
            code=suggestion.code,
            revenue_difference=drg_impact.revenue_difference,
            threshold=_COMPLIANCE_THRESHOLD,
        )

        return DRGComplianceResult(
            drg_impact=drg_impact,
            compliance_review_required=True,
            compliance_review_reason=reason,
        )

    return DRGComplianceResult(
        drg_impact=drg_impact,
        compliance_review_required=False,
        compliance_review_reason=None,
    )
