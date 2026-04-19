"""
ICD-10 Guardrail Functions — thin wrappers over ICD10RulesEngine.

These are the functions imported by the compliance tests.
They take CodingSuggestionSet (Pydantic models) as input,
call the rules engine (which works on plain code strings),
and raise/return the appropriate exception or modified model.

Hard guardrails (G-HARD-003, G-HARD-004):
  - Raise ICD10GuidelineViolationError on violation
  - Never return silently when a violation exists

Soft guardrails (G-SOFT-004):
  - Attach GuardrailWarning to affected suggestions
  - Return the modified CodingSuggestionSet

Constitution: Article II.3 (ICD-10 hard constraints)
Spec: DESIGN-003 §1 G-HARD-003, G-HARD-004, G-SOFT-004
"""
from __future__ import annotations

import structlog

from src.core.exceptions import GuardrailWarning, ICD10GuidelineViolationError
from src.core.icd10.rules_engine import ICD10RulesEngine
from src.core.models import CodingSuggestion, CodingSuggestionSet

log = structlog.get_logger()

# Module-level engine instance — stateless, safe to share
_engine = ICD10RulesEngine()


def validate_excludes1(suggestion_set: CodingSuggestionSet) -> None:
    """
    G-HARD-003: Raise ICD10GuidelineViolationError if any Excludes 1 pair
    is present in the suggestion set.

    Never returns silently on a violation — this is a hard stop.
    Constitution Article II.3: Excludes 1 pair = CRITICAL violation.
    """
    codes = [s.code for s in suggestion_set.suggestions]
    violations = _engine.validate_excludes1_pairs(codes)
    critical = [v for v in violations if v.severity.value == "CRITICAL"]

    if critical:
        pair = critical[0].affected_codes
        log.critical(
            "hard_guardrail_violation",
            guardrail_id="G-HARD-003",
            encounter_id=suggestion_set.encounter_id,
            code_a=pair[0] if len(pair) > 0 else "",
            code_b=pair[1] if len(pair) > 1 else "",
        )
        raise ICD10GuidelineViolationError(
            guardrail_id="G-HARD-003",
            violation_type="excludes_1",
            description=critical[0].description,
            suggested_remediation=critical[0].remediation,
        )


def validate_excludes2(
    suggestion_set: CodingSuggestionSet,
) -> CodingSuggestionSet:
    """
    G-SOFT-004: Attach GuardrailWarning to any suggestion that is part of
    an Excludes 2 pair with another suggestion in the same set.

    Does NOT raise — returns modified suggestion_set with warnings attached.
    Human coder must acknowledge before accepting the pair.
    """
    codes = [s.code for s in suggestion_set.suggestions]
    for suggestion in suggestion_set.suggestions:
        partners = _engine._loader.get_excludes2_partners(suggestion.code)
        if any(c in partners for c in codes if c != suggestion.code):
            _attach_excludes2_warning(suggestion, suggestion_set.encounter_id)
    return suggestion_set


def validate_outpatient_uncertain_diagnosis(
    suggestion_set: CodingSuggestionSet,
) -> None:
    """
    G-HARD-004: Raise ICD10GuidelineViolationError if this is an outpatient
    encounter and any suggestion has uncertainty qualifier words.

    Inpatient encounters pass through — Section II.H allows this.
    OBS (observation) uses outpatient rules — always.
    Constitution Article II.3 + ICD-10-CM Section IV.H.
    """
    for suggestion in suggestion_set.suggestions:
        if not suggestion.qualifier_words:
            continue
        can_code, reason = _engine.can_code_uncertain_diagnosis(
            encounter_setting=suggestion_set.encounter_setting,
            qualifier_words=suggestion.qualifier_words,
        )
        if not can_code:
            log.critical(
                "hard_guardrail_violation",
                guardrail_id="G-HARD-004",
                encounter_id=suggestion_set.encounter_id,
                code=suggestion.code,
                setting=suggestion_set.encounter_setting,
            )
            raise ICD10GuidelineViolationError(
                guardrail_id="G-HARD-004",
                violation_type="outpatient_uncertain_diagnosis",
                description=reason,
                suggested_remediation=(
                    "Replace with the presenting sign or symptom code "
                    "(Chapter 18, R00-R99). Generate a CDI query if the "
                    "physician subsequently confirms the diagnosis."
                ),
            )


def enforce_mandatory_paired_codes(
    suggestion_set: CodingSuggestionSet,
) -> CodingSuggestionSet:
    """
    RULE-SEQ-003: For each suggestion with a mandatory paired code requirement,
    check whether the required code prefix is already in the set.
    If missing, add a placeholder suggestion for the required paired code.

    Does NOT raise — adds missing paired codes and returns the modified set.
    The added suggestion has confidence=0.70 (routes to senior coder review).
    """
    existing_codes = [s.code for s in suggestion_set.suggestions]
    to_add: list[CodingSuggestion] = []

    for suggestion in suggestion_set.suggestions:
        required_prefixes = _engine.get_mandatory_paired_codes(suggestion.code)
        for prefix in required_prefixes:
            if not any(c.startswith(prefix) for c in existing_codes):
                to_add.append(_build_paired_code_suggestion(suggestion.code, prefix))

    if to_add:
        suggestion_set.suggestions.extend(to_add)
        log.info(
            "mandatory_paired_codes_added",
            encounter_id=suggestion_set.encounter_id,
            added_count=len(to_add),
        )
    return suggestion_set


def _attach_excludes2_warning(
    suggestion: CodingSuggestion, encounter_id: str
) -> None:
    """Attach G-SOFT-004 GuardrailWarning to a suggestion in an Excludes 2 pair."""
    warning = GuardrailWarning(
        guardrail_id="G-SOFT-004",
        severity="medium",
        warning_message=(
            f"Code {suggestion.code} has an Excludes 2 relationship with "
            f"another code in this set. Both codes MAY be reported together "
            f"if both conditions are independently documented. Please confirm "
            f"documentation supports both conditions before accepting."
        ),
    )
    suggestion.warnings.append(warning)
    log.info(
        "soft_guardrail_warning_attached",
        guardrail_id="G-SOFT-004",
        encounter_id=encounter_id,
        code=suggestion.code,
    )


def _build_paired_code_suggestion(
    trigger_code: str, required_prefix: str
) -> CodingSuggestion:
    """
    Build a placeholder CodingSuggestion for a mandatory paired code.

    Uses confidence=0.70 (below 0.65 threshold → routes to senior review).
    evidence_quote=None because this is a coding rule requirement, not
    an LLM-extracted suggestion — the coder must verify the specific code.
    """
    default_codes = {"N18.": "N18.9", "R65.": "R65.20"}
    suggested_code = default_codes.get(required_prefix, f"{required_prefix}9")
    return CodingSuggestion(
        code=suggested_code,
        description=f"Mandatory paired code for {trigger_code} (see Use Additional Code instruction)",
        confidence=0.70,
        evidence_quote=None,
        drg_impact="See coder review — depends on stage/specificity",
        is_mcc=False,
        is_cc=False,
    )
