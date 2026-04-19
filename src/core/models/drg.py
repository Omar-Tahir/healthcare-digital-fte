"""
DRG (Diagnosis-Related Group) calculation models.

DRGImpact is the revenue impact calculation for adding one code to a claim.
Model validators automatically set G-SOFT-003 compliance review threshold
(revenue_difference > $5,000) at the data layer.

Constitution: Article II.6 (conservative defaults), IV.1 (revenue north star)
Spec: specs/01-coding-rules-engine.md §8 (DRG step)
Skill: docs/skills/drg-optimization.md
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class DRGWeight(BaseModel):
    """MS-DRG weight from CMS annual IPPS rule."""

    drg: str = Field(min_length=3, max_length=3)
    description: str
    weight: float = Field(gt=0)
    geometric_mean_los: float
    arithmetic_mean_los: float


class DRGResult(BaseModel):
    """Grouper output for a single code set."""

    drg: str
    description: str
    weight: float
    estimated_payment: float  # weight × hospital base rate


class DRGImpact(BaseModel):
    """
    Revenue impact of adding one code suggestion to a claim.

    is_significant auto-set for revenue_difference > $1,000.
    requires_compliance_review auto-set for revenue_difference > $5,000
    (G-SOFT-003 threshold — routes to compliance team before coder accepts).
    """

    current_drg: str
    current_drg_weight: float
    proposed_drg: str
    proposed_drg_weight: float
    revenue_difference: float  # positive = revenue gain
    is_significant: bool = False
    requires_compliance_review: bool = False

    @model_validator(mode="after")
    def set_impact_flags(self) -> "DRGImpact":
        """
        Data-layer enforcement of G-SOFT-003 thresholds.
        is_significant: revenue_difference > $1,000
        requires_compliance_review: revenue_difference > $5,000
        """
        if self.revenue_difference > 1000:
            self.is_significant = True
        if self.revenue_difference > 5000:
            self.requires_compliance_review = True
        return self


class DRGComplianceResult(BaseModel):
    """
    Return type of apply_drg_compliance_threshold (G-SOFT-003).

    compliance_review_required and compliance_review_reason are set
    by the guardrail function when revenue_difference > $5,000.
    """

    drg_impact: DRGImpact
    compliance_review_required: bool
    compliance_review_reason: str | None = None
