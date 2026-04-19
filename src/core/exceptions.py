"""
Core exception hierarchy and guardrail models for the Healthcare Digital FTE system.

Exceptions are the contract between hard guardrails and callers.
GuardrailWarning is the contract between soft guardrails and the review UI.

Exceptions are NEVER caught silently — they propagate to the API layer
and are logged (without PHI) to the audit trail.

Constitution reference: Article II (all clauses)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class GuardrailWarning(BaseModel):
    """
    Warning attached to a suggestion or suggestion set that requires
    explicit human acknowledgment before the coder can accept the output.

    Soft guardrails produce GuardrailWarning — they do not block execution
    but require a human decision to proceed. The coder UI displays warnings
    prominently; each must be acknowledged before the suggestion is accepted.

    Constitution reference: Article II.6 (Conservative Defaults)
    Spec reference: DESIGN-003 §1 Type B
    """

    guardrail_id: str
    severity: Literal["high", "medium"]
    warning_message: str
    requires_explicit_acknowledgment: bool = True
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    acknowledgment_reason: str | None = None


class HumanApprovalRequiredError(Exception):
    """
    Raised when claim submission is attempted without a valid
    human approval token from a credentialed coder.

    Constitution reference: Article II.1
    FCA relevance: 31 USC §3729 — autonomous claim submission
    without human review is the highest legal risk in healthcare AI.
    """

    def __init__(self, guardrail_id: str, reason: str) -> None:
        self.guardrail_id = guardrail_id
        self.reason = reason
        super().__init__(f"[{guardrail_id}] Human approval required: {reason}")


class EvidenceCitationRequiredError(Exception):
    """
    Raised when a code suggestion lacks a required evidence_quote,
    or when the evidence_quote is not a substring of the source note.

    Constitution reference: Article II.2
    Patient safety relevance: A suggestion without a source citation
    is a hallucination. Hallucinated diagnoses are patient safety events.
    """

    def __init__(self, guardrail_id: str, code: str, reason: str) -> None:
        self.guardrail_id = guardrail_id
        self.code = code
        self.reason = reason
        super().__init__(
            f"[{guardrail_id}] Evidence citation required for {code}: {reason}"
        )


class ICD10GuidelineViolationError(Exception):
    """
    Raised when a suggestion or suggestion set violates the
    ICD-10-CM Official Coding Guidelines published by CMS.

    This includes:
    - Excludes 1 code pairs in the same suggestion set
    - Uncertain outpatient diagnoses coded as confirmed
    - Mandatory sequencing violations
    - Invalid 7th character assignments

    Constitution reference: Article II.3
    FCA relevance: Incorrect coding of government-payer claims
    constitutes a False Claims Act violation.
    """

    def __init__(
        self,
        guardrail_id: str,
        violation_type: str,
        description: str,
        suggested_remediation: str,
    ) -> None:
        self.guardrail_id = guardrail_id
        self.violation_type = violation_type
        self.description = description
        self.suggested_remediation = suggested_remediation
        super().__init__(
            f"[{guardrail_id}] ICD-10 guideline violation ({violation_type}): "
            f"{description}"
        )


class CodingGuidelineViolationError(Exception):
    """
    General coding rules engine violation. Raised when the rules
    engine detects any structural violation in a suggestion set
    that does not map to a more specific exception type.

    Constitution reference: Article II.3
    """

    def __init__(
        self,
        guardrail_id: str,
        description: str,
        constitution_article: str,
        suggested_remediation: str,
    ) -> None:
        self.guardrail_id = guardrail_id
        self.description = description
        self.constitution_article = constitution_article
        self.suggested_remediation = suggested_remediation
        super().__init__(
            f"[{guardrail_id}] Coding guideline violation "
            f"(Article {constitution_article}): {description}"
        )
