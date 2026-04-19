"""
CDI (Clinical Documentation Improvement) opportunity and query models.

The CDI layer identifies documentation gaps and generates compliant
physician queries. It does NOT code and does NOT suggest diagnoses.
It asks physicians to clarify — using non-leading, AHIMA-compliant queries.

Constitution: Article II.2 (source citation), II.6 (conservative defaults)
Spec: specs/02-cdi-intelligence-layer.md
Skill: docs/skills/cdi-query-writing.md
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.core.exceptions import GuardrailWarning


class CDIOpportunityType(str, Enum):
    """
    CDI opportunity categories.
    Maps to the detection patterns in docs/skills/cdi-query-writing.md.
    """

    SEVERITY_UPGRADE = "severity_upgrade"
    SPECIFICITY_UPGRADE = "specificity_upgrade"
    CAUSALITY_LINK = "causality_link"
    POA_CLARIFICATION = "poa_clarification"


class CDIOpportunity(BaseModel):
    """
    A detected CDI opportunity ready for physician query generation.

    Fields match the compliance test interface — encounter_id,
    query_category, query_text, suggested_code, drg_impact.
    The routing and warnings fields support G-SOFT-005 (3rd query escalation).
    """

    encounter_id: str
    query_category: str  # "severity_upgrade", "specificity_upgrade", etc.
    query_text: str  # AHIMA-compliant draft query text
    suggested_code: str  # ICD-10 code this query targets
    drg_impact: str  # human-readable revenue impact string
    warnings: list[GuardrailWarning] = Field(default_factory=list)
    routing: str = "physician_direct"  # "physician_direct" or "cdi_specialist_review"


class CDIQuery(BaseModel):
    """
    A finalized CDI query ready to send to a physician.
    AHIMA-compliant format per docs/skills/cdi-query-writing.md.

    Multiple-choice options are required — AHIMA prohibits open-ended
    queries without structured response options (prevents leading queries).
    """

    encounter_id: str
    physician_id: str
    query_text: str
    multiple_choice_options: list[str] = Field(min_length=2)
    clinical_evidence: str  # objective data cited in the query
    drg_impact: str
    query_number: int  # G-SOFT-005: escalate on 3rd+ query
    is_escalated: bool = False


class CDIAnalysisResult(BaseModel):
    """Complete CDI analysis output for one encounter."""

    encounter_id: str
    opportunities: list[CDIOpportunity] = Field(default_factory=list)
    queries_generated: list[CDIQuery] = Field(default_factory=list)
    is_degraded: bool = False
