"""
Coding suggestion and result models.

CodingSuggestion is the core output unit of the coding agent.
The evidence_quote field is the implementation of constitution Article II.2:
every clinical assertion must trace to a verbatim physician quote.

Constitution: Article II.2 (evidence citation), II.6 (conservative defaults)
Spec: specs/01-coding-rules-engine.md §1.2, §1.3
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.exceptions import GuardrailWarning


class ViolationSeverity(str, Enum):
    CRITICAL = "CRITICAL"  # Hard stop — raises exception, blocks output
    HIGH = "HIGH"  # Significant DRG or audit risk
    MEDIUM = "MEDIUM"  # Guideline deviation — requires review
    LOW = "LOW"  # Best practice suggestion


class GuidelineViolation(BaseModel):
    """A single ICD-10 guideline violation found by the rules engine."""

    rule_id: str  # e.g. "G-HARD-003", "RULE-EX1-001"
    severity: ViolationSeverity
    description: str
    affected_codes: list[str]
    remediation: str


class ValidationResult(BaseModel):
    """
    Output of the ICD-10 rules engine for a suggestion set.
    A CRITICAL violation forces is_valid=False regardless of the caller's intent.
    """

    is_valid: bool
    violations: list[GuidelineViolation] = Field(default_factory=list)
    auto_additions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def critical_violation_makes_invalid(self) -> "ValidationResult":
        """Any CRITICAL violation overrides is_valid to False."""
        has_critical = any(
            v.severity == ViolationSeverity.CRITICAL for v in self.violations
        )
        if has_critical:
            self.is_valid = False
        return self


class CodingSuggestion(BaseModel):
    """
    A single ICD-10-CM code suggestion from the coding agent.

    evidence_quote is the implementation of constitution Article II.2.
    It is Optional at the Pydantic level (None allowed) because the LLM
    may fail to provide one — the guardrail (validate_evidence_quotes)
    catches and rejects None at runtime with EvidenceCitationRequiredError.

    Empty string "" is rejected at model creation time by field_validator.
    """

    code: str = Field(min_length=3, max_length=8)
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quote: str | None = None
    drg_impact: str  # human-readable: "$2,400", "+$42,759 if accepted"
    drg_revenue_delta: float = 0.0  # numeric delta for guardrail thresholds
    is_mcc: bool = False
    is_cc: bool = False
    is_principal_dx_candidate: bool = False
    qualifier_words: list[str] = Field(default_factory=list)
    warnings: list[GuardrailWarning] = Field(default_factory=list)
    requires_senior_review: bool = False
    compliance_review_required: bool = False
    routing_queue: str = "standard_queue"

    @field_validator("evidence_quote")
    @classmethod
    def evidence_quote_not_empty_string(cls, v: str | None) -> str | None:
        """
        Empty string is rejected — it provides no evidence and is as
        dangerous as None. The guardrail catches None; Pydantic catches "".
        """
        if v is not None and len(v.strip()) == 0:
            raise ValueError(
                "evidence_quote cannot be an empty string. "
                "Use None if no quote is available; the guardrail will reject it."
            )
        return v

    @model_validator(mode="after")
    def set_review_flags(self) -> "CodingSuggestion":
        """
        Automatically set routing flags based on confidence and revenue thresholds.
        G-SOFT-001: confidence 0.40–0.65 → senior coder queue.
        G-SOFT-003: revenue_delta > $5,000 → compliance review required.
        """
        if self.confidence < 0.65:
            self.requires_senior_review = True
            self.routing_queue = "senior_coder_queue"
        if self.drg_revenue_delta > 5000:
            self.compliance_review_required = True
        return self


class CodingSuggestionSet(BaseModel):
    """
    A complete set of suggestions for one encounter.

    This is the input to the rules engine and all guardrail validators.
    source_note_text is used by validate_evidence_quotes to verify that
    every evidence_quote is a verbatim substring of the note.
    """

    encounter_id: str
    encounter_setting: str  # "inpatient", "outpatient", "observation"
    source_note_text: str
    suggestions: list[CodingSuggestion] = Field(default_factory=list)
    warnings: list[GuardrailWarning] = Field(default_factory=list)
    note_similarity_score: float | None = None  # for G-SOFT-002 copy-forward


class CodingAnalysisResult(BaseModel):
    """
    Complete output of the coding agent for one encounter.

    suggestions is capped at 15 — more than 15 suggested codes indicates
    a clinical quality issue and is rejected at the data layer.
    """

    encounter_id: str
    coding_class: str  # "inpatient" or "outpatient"
    suggestions: Annotated[list[CodingSuggestion], Field(max_length=15)] = Field(
        default_factory=list
    )
    validation_result: ValidationResult
    note_similarity_to_prior: float = 0.0
    copy_forward_flagged: bool = False
    processing_time_ms: float = 0.0
    nlp_entity_count: int = 0
    is_degraded: bool = False
    cdi_opportunities: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def flag_copy_forward(self) -> "CodingAnalysisResult":
        """G-SOFT-002 threshold: 0.85."""
        if self.note_similarity_to_prior > 0.85:
            self.copy_forward_flagged = True
        return self


class ConfidenceRoutingResult(BaseModel):
    """Return type of apply_confidence_routing (G-SOFT-001)."""

    code: str
    confidence: float
    requires_senior_review: bool
    routing_queue: str  # "standard_queue" or "senior_coder_queue"


class SpecificityResult(BaseModel):
    """
    Return type of apply_conservative_specificity (Article II.6).
    When documentation does not support a higher-specificity code,
    the system downgrades and generates a CDI query.
    """

    selected_code: str
    original_code: str
    cdi_query_required: bool
    cdi_query_category: str | None = None
