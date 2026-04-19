"""
BUILD-003 — ICD-10 Rules Engine Unit Tests
TDD Red Phase: Written BEFORE implementation files exist.

Constitution Articles:
  II.3 — ICD-10 Official Guidelines as hard constraints
  I.2  — Tests before implementation

Skill reference: docs/skills/icd10-coding-rules.md
Spec reference:  specs/01-coding-rules-engine.md §2
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# GROUP 1 — Excludes 1 detection
# G-HARD-003: Excludes 1 pair is a hard stop (Constitution Article II.3)
# ---------------------------------------------------------------------------


class TestExcludes1Detection:
    """
    Validates that the rules engine correctly detects Excludes 1 pairs.
    A pair detected → GuidelineViolation(severity=CRITICAL).
    No pair detected → empty violation list.
    Spec: RULE-EX1 per Section I.A.12.a
    """

    def test_excludes1_violation_detected(self) -> None:
        """
        I50.9 (CHF unspecified) + I50.20 (unspecified systolic CHF)
        have an Excludes 1 relationship — 'unspecified' form and
        'specific type' form of the same condition cannot coexist.
        Rules engine must return a CRITICAL violation.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine
        from src.core.models.coding import ViolationSeverity

        engine = ICD10RulesEngine()
        violations = engine.validate_excludes1_pairs(["I50.9", "I50.20"])

        assert len(violations) >= 1
        critical = [v for v in violations if v.severity == ViolationSeverity.CRITICAL]
        assert len(critical) >= 1
        assert "I50.9" in critical[0].affected_codes or "I50.20" in critical[0].affected_codes

    def test_excludes1_violation_is_bidirectional(self) -> None:
        """
        Excludes 1 relationships are bidirectional.
        [I50.20, I50.9] must produce the same violation as [I50.9, I50.20].
        The order the codes are submitted must not affect detection.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        violations_ab = engine.validate_excludes1_pairs(["I50.9", "I50.20"])
        violations_ba = engine.validate_excludes1_pairs(["I50.20", "I50.9"])

        assert len(violations_ab) == len(violations_ba)
        assert len(violations_ab) >= 1

    def test_valid_codes_pass_excludes1_check(self) -> None:
        """
        E11.22 (T2DM with diabetic CKD) + N18.3 (CKD stage 3) do NOT
        have an Excludes 1 relationship — they are a mandatory pair.
        Rules engine must return zero violations for this valid combination.
        Skill: icd10-coding-rules.md Rule 3 (mandatory sequencing).
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        violations = engine.validate_excludes1_pairs(["E11.22", "N18.3"])

        assert violations == []

    def test_multiple_violations_all_returned(self) -> None:
        """
        Code set with TWO Excludes 1 violations must return both.
        The rules engine never short-circuits on the first violation —
        coders need the complete picture to fix all issues in one pass.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        # I50.9 + I50.20 = first Excludes 1 pair
        # E10.9 + E11.9 = second Excludes 1 pair (Type 1 DM + Type 2 DM)
        violations = engine.validate_excludes1_pairs(
            ["I50.9", "I50.20", "E10.9", "E11.9"]
        )

        assert len(violations) >= 2


# ---------------------------------------------------------------------------
# GROUP 2 — Outpatient uncertain diagnosis rules
# G-HARD-004: Outpatient uncertain dx prohibition (Article II.3, Section IV.H)
# ---------------------------------------------------------------------------


class TestUncertainDiagnosisRules:
    """
    The most important encounter-setting rule in the rules engine.
    Outpatient + uncertain qualifier = cannot code as confirmed.
    Inpatient + uncertain qualifier = may code as confirmed (Section II.H).
    OBS (observation) uses outpatient rules — this is commonly confused.
    """

    def test_outpatient_uncertain_diagnosis_blocked(self) -> None:
        """
        "possible" qualifier + outpatient setting → cannot code as confirmed.
        Returns (False, reason_string).
        Skill: icd10-coding-rules.md Rule 2.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        can_code, reason = engine.can_code_uncertain_diagnosis(
            encounter_setting="outpatient",
            qualifier_words=["possible"],
        )

        assert can_code is False
        assert len(reason) > 0  # must explain why

    def test_inpatient_uncertain_diagnosis_allowed(self) -> None:
        """
        "possible" qualifier + inpatient setting → may code as confirmed.
        Returns (True, reason_string).
        Per ICD-10-CM Official Guidelines Section II.H.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        can_code, reason = engine.can_code_uncertain_diagnosis(
            encounter_setting="inpatient",
            qualifier_words=["possible"],
        )

        assert can_code is True
        assert "II.H" in reason or "inpatient" in reason.lower()

    def test_observation_class_uses_outpatient_rules(self) -> None:
        """
        Observation status encounter + uncertain qualifier → outpatient rules apply.
        OBS patients are physically in the hospital but coded as outpatient.
        Per CMS OBS status rules — this is the most commonly confused mapping.
        Skill: icd10-coding-rules.md Section 3.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        can_code, reason = engine.can_code_uncertain_diagnosis(
            encounter_setting="observation",
            qualifier_words=["suspected"],
        )

        assert can_code is False
        assert len(reason) > 0

    def test_no_qualifier_words_not_blocked(self) -> None:
        """
        Confirmed diagnosis with no uncertainty qualifiers → always allowed.
        Tests that the engine does not block confirmed outpatient diagnoses.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        can_code, reason = engine.can_code_uncertain_diagnosis(
            encounter_setting="outpatient",
            qualifier_words=[],  # no uncertainty qualifiers
        )

        assert can_code is True


# ---------------------------------------------------------------------------
# GROUP 3 — Mandatory paired codes
# RULE-SEQ-003 per Section I.A.13 (Use Additional Code)
# ---------------------------------------------------------------------------


class TestMandatoryPairedCodes:
    """
    Certain codes have "Use Additional Code" or "Code First" instructions.
    The rules engine must detect these and surface the missing paired codes.
    """

    def test_mandatory_paired_code_detected(self) -> None:
        """
        E11.22 (T2DM with diabetic CKD) has a "Use Additional Code"
        instruction for N18.x (CKD stage). When E11.22 is present
        without any N18.x code, the engine must return the N18. prefix
        as a required addition.
        Spec: RULE-SEQ-003, Skill Section 1 Rule 3.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        required = engine.get_mandatory_paired_codes("E11.22")

        assert len(required) >= 1
        assert any(r.startswith("N18") for r in required)

    def test_code_without_pairing_requirement_returns_empty(self) -> None:
        """
        J18.9 (Pneumonia) has no mandatory paired code requirements.
        Engine must return an empty list — not every code needs a pair.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        required = engine.get_mandatory_paired_codes("J18.9")

        assert required == []


# ---------------------------------------------------------------------------
# GROUP 4 — DRG impact calculation
# Article IV.1: Revenue impact is the north star metric
# ---------------------------------------------------------------------------


class TestDRGImpactCalculation:
    """
    Simplified DRG grouper for Phase 1.
    Full CMS grouper logic is BUILD-008.
    Tests that adding an MCC code to a CHF claim improves the DRG tier.
    """

    def test_drg_impact_calculation_heart_failure_family(self) -> None:
        """
        Heart failure DRG family (DRG 291-293):
        - DRG 293: HF without CC/MCC → weight ~1.08
        - DRG 292: HF with CC  → weight ~2.54
        - DRG 291: HF with MCC → weight ~4.22

        I50.9 (CHF unspecified) has CC status.
        Adding I50.21 (acute systolic CHF, MCC) improves DRG tier.
        Revenue delta must be positive.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        result = engine.calculate_drg_impact(
            current_codes=["I50.9"],
            proposed_addition="I50.21",
        )

        assert result["current_drg"] is not None
        assert result["proposed_drg"] is not None
        assert result["revenue_delta"] > 0
        assert float(result["proposed_weight"]) > float(result["current_weight"])
        assert result["proposed_drg"] != result["current_drg"]


# ---------------------------------------------------------------------------
# GROUP 5 — Full validation pipeline
# ---------------------------------------------------------------------------


class TestFullValidationPipeline:
    """
    Tests the validate_code_set() orchestration method that runs
    all sub-checks and returns a complete ValidationResult.
    """

    def test_validation_result_is_valid_when_no_violations(self) -> None:
        """
        A clean code set with no violations produces ValidationResult.is_valid=True.
        E11.22 + N18.3 — valid mandatory pair, no Excludes 1, confirmed inpatient.
        """
        from src.core.icd10.rules_engine import ICD10RulesEngine

        engine = ICD10RulesEngine()
        result = engine.validate_code_set(
            codes=["E11.22", "N18.3"],
            encounter_setting="inpatient",
            note_text=(
                "Patient has type 2 diabetes mellitus with stage 3 "
                "chronic kidney disease. eGFR 38."
            ),
        )

        assert result.is_valid is True
        critical = [
            v for v in result.violations
            if v.severity.value == "CRITICAL"
        ]
        assert critical == []
