"""
Copy-Forward Detection Guardrail — G-SOFT-002.

Enforces constitution Article II.6 (conservative defaults): Notes with
> 85% token similarity to a prior note are flagged. Copy-forward
documentation supporting higher-level billing is FCA exposure.

Reference: DISC-002 Section A.3 — "Documentation copy-forward is
the most common OIG audit finding in hospital coding."

The guardrail is SOFT (not a hard stop). The coder must explicitly
acknowledge the warning before accepting any suggestion. The suggestion
set is NOT rejected — the coder makes the final judgment.

Constitution: Article II.6
Spec: specs/03-compliance-guardrail-architecture.md §1 G-SOFT-002
Research: docs/research/DISC-002-documentation-failure-patterns.md
"""
from __future__ import annotations

import structlog

from src.core.exceptions import GuardrailWarning
from src.core.models.coding import CodingSuggestionSet

log = structlog.get_logger()

_GUARDRAIL_ID = "G-SOFT-002"
_SIMILARITY_THRESHOLD = 0.85


def detect_copy_forward(
    suggestion_set: CodingSuggestionSet,
) -> CodingSuggestionSet:
    """
    Detect copy-forward documentation pattern.

    If note_similarity_score > 0.85, adds a G-SOFT-002 warning to
    the suggestion set's warnings list. The coder must acknowledge
    this warning before accepting any suggestion.

    If note_similarity_score is None or <= 0.85, returns unchanged.
    """
    similarity = suggestion_set.note_similarity_score

    if similarity is not None and similarity > _SIMILARITY_THRESHOLD:
        warning = GuardrailWarning(
            guardrail_id=_GUARDRAIL_ID,
            severity="medium",
            warning_message=(
                f"Note similarity score {similarity:.0%} exceeds the "
                f"{_SIMILARITY_THRESHOLD:.0%} copy-forward threshold. "
                "This note may be copy-forwarded from a prior encounter. "
                "Verify that the documentation reflects the current "
                "clinical situation before accepting any suggestion."
            ),
            requires_explicit_acknowledgment=True,
        )

        log.info(
            "copy_forward_detected",
            guardrail_id=_GUARDRAIL_ID,
            similarity_score=similarity,
            threshold=_SIMILARITY_THRESHOLD,
            encounter_id=suggestion_set.encounter_id,
        )

        # Return new set with warning appended — do NOT mutate in place
        updated_warnings = list(suggestion_set.warnings) + [warning]
        return suggestion_set.model_copy(update={"warnings": updated_warnings})

    return suggestion_set
