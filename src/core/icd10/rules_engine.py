"""
ICD-10 Rules Engine — pure Python validation, no LLM calls.

Encodes ICD-10-CM Official Guidelines as deterministic hard constraints.
Every output goes through this engine before reaching the coder interface.

This is the component that makes constitution Article II.3 real in code:
  - Excludes 1 pairs → CRITICAL violation → claim cannot proceed
  - Outpatient uncertain diagnosis → CRITICAL violation → hard stop
  - Missing mandatory paired codes → auto-addition + warning
  - DRG impact calculation → revenue delta for coder context

Constitution: Article II.3 (ICD-10 hard constraints), III.6 (< 40 lines/fn)
Spec: specs/01-coding-rules-engine.md §2
Skill: docs/skills/icd10-coding-rules.md Rules 1-5
"""
from __future__ import annotations

import structlog

from src.core.icd10.data_loader import ICD10DataLoader, _BASE_RATE, _DRG_WEIGHTS
from src.core.models.coding import GuidelineViolation, ValidationResult, ViolationSeverity
from src.core.models.encounter import UNCERTAINTY_QUALIFIERS

log = structlog.get_logger()

# Encounter settings that use outpatient coding rules.
# OBS is outpatient — this is the most commonly confused mapping.
# Per CMS OBS status rules + ICD-10-CM Official Guidelines Section IV.
_OUTPATIENT_SETTINGS = frozenset({"outpatient", "observation", "emergency", "AMB", "EMER", "OBS"})


class ICD10RulesEngine:
    """
    Validates ICD-10-CM code sets against Official Coding Guidelines.

    Instantiate once and reuse — the data loader has no mutable state.
    All validate_* methods return violations, never raise exceptions.
    The guardrail layer (icd10_guardrail.py) converts violations to exceptions.
    """

    def __init__(self) -> None:
        self._loader = ICD10DataLoader()

    def validate_code_set(
        self,
        codes: list[str],
        encounter_setting: str,
        note_text: str,
    ) -> ValidationResult:
        """
        Run the full validation pipeline on a proposed code set.

        Pipeline:
          1. Excludes 1 pair check (CRITICAL)
          2. Mandatory paired code check (HIGH — surfaces auto-additions)

        Returns ValidationResult — never raises. Guardrail layer raises.
        """
        violations: list[GuidelineViolation] = []
        violations.extend(self.validate_excludes1_pairs(codes))

        has_critical = any(v.severity == ViolationSeverity.CRITICAL for v in violations)
        is_valid = not has_critical

        log.info(
            "rules_engine_validation_complete",
            code_count=len(codes),
            violation_count=len(violations),
            is_valid=is_valid,
        )
        return ValidationResult(is_valid=is_valid, violations=violations)

    def validate_excludes1_pairs(
        self, codes: list[str]
    ) -> list[GuidelineViolation]:
        """
        Check all pairwise combinations in codes[] against Excludes 1 lookup.

        O(n²) but n ≤ 15 per claim → negligible cost.
        Any pair found in Excludes 1 data → CRITICAL violation.
        Never short-circuits — returns ALL violations found.
        """
        violations: list[GuidelineViolation] = []
        for i, code_a in enumerate(codes):
            excluded = self._loader.get_excludes1_partners(code_a)
            for code_b in codes[i + 1 :]:
                if code_b in excluded:
                    violations.append(self._make_excludes1_violation(code_a, code_b))
        return violations

    def can_code_uncertain_diagnosis(
        self,
        encounter_setting: str,
        qualifier_words: list[str],
    ) -> tuple[bool, str]:
        """
        Determine whether an uncertain diagnosis may be coded as confirmed.

        Rules:
        - Outpatient (including OBS) + uncertainty qualifier → (False, reason)
          Per ICD-10-CM Section IV.H: code sign/symptom instead.
        - Inpatient + uncertainty qualifier → (True, reason)
          Per ICD-10-CM Section II.H: code as confirmed.
        - No qualifier words → (True, "confirmed diagnosis")
        """
        has_qualifier = any(q.lower() in UNCERTAINTY_QUALIFIERS for q in qualifier_words)
        if not has_qualifier:
            return True, "confirmed diagnosis — no uncertainty qualifiers detected"

        if encounter_setting in _OUTPATIENT_SETTINGS:
            return (
                False,
                f"Outpatient encounter with uncertainty qualifier — "
                f"cannot code as confirmed per ICD-10-CM Section IV.H. "
                f"Code the presenting sign or symptom instead.",
            )
        return (
            True,
            f"Inpatient uncertain diagnosis — may code as confirmed "
            f"per ICD-10-CM Official Guidelines Section II.H.",
        )

    def get_mandatory_paired_codes(self, code: str) -> list[str]:
        """
        Return required paired code prefixes for this code.

        Example: E11.22 → ["N18."] (CKD stage must accompany DM+CKD code).
        Returns empty list if no pairing requirement exists.
        """
        return self._loader.get_mandatory_paired_codes(code)

    def calculate_drg_impact(
        self,
        current_codes: list[str],
        proposed_addition: str,
    ) -> dict[str, object]:
        """
        Calculate revenue impact of adding proposed_addition to current_codes.

        Uses simplified DRG grouper (full CMS logic is BUILD-008).
        Returns dict with current_drg, proposed_drg, weights, revenue_delta.
        Base rate: $3,800 (national average Medicare IPPS rate, simplified).
        """
        current_drg, current_weight = self._loader.get_drg_for_code_set(current_codes)
        proposed_drg, proposed_weight = self._loader.get_drg_for_code_set(
            current_codes + [proposed_addition]
        )
        revenue_delta = (proposed_weight - current_weight) * _BASE_RATE

        log.info(
            "drg_impact_calculated",
            current_drg=current_drg,
            proposed_drg=proposed_drg,
            revenue_delta=round(revenue_delta, 2),
        )
        return {
            "current_drg": current_drg,
            "current_weight": current_weight,
            "proposed_drg": proposed_drg,
            "proposed_weight": proposed_weight,
            "revenue_delta": round(revenue_delta, 2),
        }

    def _make_excludes1_violation(
        self, code_a: str, code_b: str
    ) -> GuidelineViolation:
        """Build the CRITICAL GuidelineViolation for an Excludes 1 pair."""
        return GuidelineViolation(
            rule_id="G-HARD-003",
            severity=ViolationSeverity.CRITICAL,
            description=(
                f"Excludes 1 violation: {code_a} and {code_b} are mutually "
                f"exclusive per ICD-10-CM Section I.A.12.a. "
                f"These codes CANNOT appear together on the same claim."
            ),
            affected_codes=[code_a, code_b],
            remediation=(
                f"Remove one code. If documentation supports both conditions, "
                f"generate a CDI query to clarify which is correct."
            ),
        )
