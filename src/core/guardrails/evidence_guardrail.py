"""
Evidence Citation Guardrail — G-HARD-002.

Enforces constitution Article II.2: Every clinical assertion must have
a verbatim evidence_quote from the source note.

A suggestion without a source citation is a hallucination.
A hallucinated diagnosis in a signed medical record is a patient
safety event and a legal liability.

Constitution: Article II.2
Spec: specs/03-compliance-guardrail-architecture.md §1 G-HARD-002
"""
from __future__ import annotations

import structlog

from src.core.exceptions import EvidenceCitationRequiredError
from src.core.models.coding import CodingSuggestionSet

log = structlog.get_logger()

_GUARDRAIL_ID = "G-HARD-002"


def validate_evidence_quotes(suggestion_set: CodingSuggestionSet) -> None:
    """
    Validate that every suggestion in the set has an evidence_quote
    that is a verbatim (case-insensitive) substring of the source note.

    Raises EvidenceCitationRequiredError on first violation found.
    The error identifies the specific failing code.

    Constitution: Article II.2
    """
    note_lower = suggestion_set.source_note_text.lower()

    for suggestion in suggestion_set.suggestions:
        # Check 1: evidence_quote must exist
        if suggestion.evidence_quote is None:
            log.warning(
                "evidence_quote_missing",
                guardrail_id=_GUARDRAIL_ID,
                code=suggestion.code,
            )
            raise EvidenceCitationRequiredError(
                guardrail_id=_GUARDRAIL_ID,
                code=suggestion.code,
                reason=(
                    f"Code {suggestion.code} has no evidence_quote. "
                    "Every suggestion must cite verbatim source text."
                ),
            )

        # Check 2: evidence_quote must be substring of source note (case-insensitive)
        if suggestion.evidence_quote.lower() not in note_lower:
            log.warning(
                "evidence_quote_not_in_note",
                guardrail_id=_GUARDRAIL_ID,
                code=suggestion.code,
            )
            raise EvidenceCitationRequiredError(
                guardrail_id=_GUARDRAIL_ID,
                code=suggestion.code,
                reason=(
                    f"evidence_quote for {suggestion.code} is not found in the "
                    "source note. Quote may be hallucinated or from a different note."
                ),
            )
