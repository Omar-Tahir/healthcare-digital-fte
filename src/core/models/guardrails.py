"""
Guardrail result and token models.

GuardrailWarning is imported from exceptions.py (defined there so
BUILD-001 compliance tests can import it from src.core.exceptions).
Re-exported here for consumers who import from src.core.models.

Constitution: Article II.1 (approval token), II.6 (soft guardrail warnings)
Spec: specs/03-compliance-guardrail-architecture.md §1
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# GuardrailWarning defined in exceptions.py — imported here for re-export.
# Compliance tests import it from src.core.exceptions.
# All other consumers can import from src.core.models.
from src.core.exceptions import GuardrailWarning

__all__ = ["GuardrailWarning", "GuardrailType", "GuardrailResult", "ApprovalToken"]


class GuardrailType(str, Enum):
    HARD = "HARD"  # G-HARD: raises exception, execution halts
    SOFT = "SOFT"  # G-SOFT: returns warning, human decides
    MON = "MON"  # G-MON: background alert, does not block


class GuardrailResult(BaseModel):
    """
    Returned by every guardrail check function.

    HARD violations raise an exception before this is returned.
    SOFT violations are returned here with warning for human review.
    MON violations are logged without blocking the request.
    """

    passed: bool
    guardrail_id: str  # e.g. "G-HARD-001", "G-SOFT-002"
    guardrail_type: GuardrailType
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ApprovalToken(BaseModel):
    """
    The human approval token that satisfies constitution Article II.1.

    Required before any FHIR Claim write (status → active).
    Cryptographically bound to a specific coder, encounter, and code set.
    Single-use: consumed on first successful validation (replay prevention).
    Token expires after 15 minutes (per spec — test uses 15 min window).

    Spec: specs/06-coder-review-ui.md §4
    Guardrail: G-HARD-001
    """

    token_value: str
    encounter_id: str
    coder_id: str
    approved_codes_hash: str  # SHA-256 of sorted, JSON-serialized approved code list
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_consumed: bool = False
    # Single-use: set True after first successful validation.
    # Second use with same token raises HumanApprovalRequiredError.
