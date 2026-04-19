"""
Confidence-based routing and hard-stop guardrails.

G-SOFT-001: Confidence in range [0.40, 0.65) → route to senior coder queue.
G-HARD-007: Confidence < 0.40 → hard stop, raise CodingGuidelineViolationError.

Constitution reference: Article II.6 (Conservative Defaults)
Spec reference: DESIGN-003 §1 G-SOFT-001, G-HARD-007
"""
from __future__ import annotations

from src.core.exceptions import CodingGuidelineViolationError
from src.core.models.coding import CodingSuggestion

_MINIMUM_CONFIDENCE: float = 0.40
_SENIOR_REVIEW_THRESHOLD: float = 0.65


def validate_minimum_confidence(suggestion: CodingSuggestion) -> None:
    """
    G-HARD-007: Reject any suggestion with confidence < 0.40.

    A suggestion this uncertain provides no clinical value and increases
    the risk of a hallucinated diagnosis reaching a coder.
    The CDI agent should generate a query instead.

    Raises:
        CodingGuidelineViolationError: if confidence < 0.40
    """
    if suggestion.confidence < _MINIMUM_CONFIDENCE:
        raise CodingGuidelineViolationError(
            guardrail_id="G-HARD-007",
            description=(
                f"Suggestion for {suggestion.code} has confidence "
                f"{suggestion.confidence:.2f}, below minimum threshold "
                f"{_MINIMUM_CONFIDENCE}. Suggestion discarded."
            ),
            constitution_article="II.6",
            suggested_remediation=(
                "Route to CDI agent to generate a physician query "
                "requesting clarification before re-attempting coding."
            ),
        )


def apply_confidence_routing(suggestion: CodingSuggestion) -> CodingSuggestion:
    """
    G-SOFT-001: Route suggestions with confidence in [0.40, 0.65) to
    senior coder queue with requires_senior_review=True.

    The CodingSuggestion model validator already applies this logic on
    construction; this function provides the explicit guardrail interface
    for use in the agent pipeline.

    Returns the suggestion (modified in-place if routing update needed).
    """
    if suggestion.confidence < _SENIOR_REVIEW_THRESHOLD:
        suggestion.requires_senior_review = True
        suggestion.routing_queue = "senior_coder_queue"
    return suggestion
