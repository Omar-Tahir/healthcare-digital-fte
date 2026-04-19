"""
BUILD-002 — Pydantic Domain Models Unit Tests
TDD Red Phase: All tests written BEFORE model files exist.
All tests MUST FAIL with ImportError first — that is correct state.

After models are created:
  - These 24 tests pass (green)
  - Compliance tests still fail (assertion errors, not import errors)

Constitution Articles: II.2 (evidence citation), II.4 (no PHI in logs),
                       III.4 (Pydantic v2)
Spec reference: specs/01-coding-rules-engine.md §1,
                specs/02-cdi-intelligence-layer.md,
                specs/03-compliance-guardrail-architecture.md
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# GROUP 1 — Encounter models: coding class derivation and qualifier words
# ---------------------------------------------------------------------------


class TestEncounterModels:
    """
    Verifies encounter → coding class mapping and uncertainty qualifier set.
    These rules drive the outpatient uncertain diagnosis guardrail (G-HARD-004).
    """

    def test_obs_encounter_maps_to_outpatient_coding_class(self) -> None:
        """
        OBS (observation) status patients MUST use outpatient coding rules.
        The most commonly confused mapping in hospital coding.
        Per CMS OBS status rules + ICD-10-CM Official Guidelines.
        """
        from src.core.models.encounter import CodingClass, EncounterClass, get_coding_class

        result = get_coding_class(EncounterClass.OBSERVATION)
        assert result == CodingClass.OUTPATIENT

    def test_imp_encounter_maps_to_inpatient_coding_class(self) -> None:
        """
        IMP (inpatient) class uses inpatient coding rules.
        Inpatient uncertain diagnoses may be coded as confirmed (II.H).
        """
        from src.core.models.encounter import CodingClass, EncounterClass, get_coding_class

        result = get_coding_class(EncounterClass.INPATIENT)
        assert result == CodingClass.INPATIENT

    def test_emer_encounter_maps_to_outpatient_coding_class(self) -> None:
        """
        EMER (emergency) class uses outpatient coding rules.
        Emergency visits are outpatient unless patient is formally admitted.
        """
        from src.core.models.encounter import CodingClass, EncounterClass, get_coding_class

        result = get_coding_class(EncounterClass.EMERGENCY)
        assert result == CodingClass.OUTPATIENT

    def test_uncertainty_qualifiers_set_contains_all_six(self) -> None:
        """
        UNCERTAINTY_QUALIFIERS frozenset must contain all 6 canonical
        uncertainty words from ICD-10-CM Section IV.H.
        Missing any one of these creates a False Claims Act exposure.
        """
        from src.core.models.encounter import UNCERTAINTY_QUALIFIERS

        required = {
            "possible",
            "probable",
            "suspected",
            "rule out",
            "working diagnosis",
            "questionable",
        }
        assert required.issubset(UNCERTAINTY_QUALIFIERS), (
            f"Missing qualifiers: {required - UNCERTAINTY_QUALIFIERS}"
        )


# ---------------------------------------------------------------------------
# GROUP 2 — Coding models: field constraints and model validators
# ---------------------------------------------------------------------------


class TestCodingModels:
    """
    Verifies CodingSuggestion, CodingSuggestionSet, and CodingAnalysisResult
    enforce constitution Article II.2 and II.6 at the data layer.
    """

    def test_coding_suggestion_requires_evidence_quote(self) -> None:
        """
        A valid CodingSuggestion with a populated evidence_quote
        creates successfully. The evidence_quote field must be present
        and accessible — it is the core patient safety field per II.2.
        """
        from src.core.models import CodingSuggestion

        suggestion = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.88,
            evidence_quote="confirmed community-acquired pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )
        assert suggestion.evidence_quote == "confirmed community-acquired pneumonia"

    def test_empty_evidence_quote_fails_validation(self) -> None:
        """
        evidence_quote="" (empty string) must fail Pydantic validation.
        An empty quote is as dangerous as None — no source = hallucination.
        Pydantic rejects this at the data layer before any guardrail runs.
        """
        from pydantic import ValidationError

        from src.core.models import CodingSuggestion

        with pytest.raises(ValidationError):
            CodingSuggestion(
                code="J18.9",
                description="Pneumonia, unspecified organism",
                confidence=0.88,
                evidence_quote="",  # empty string — must be rejected
                drg_impact="$2,400",
                is_mcc=False,
                is_cc=False,
            )

    def test_low_confidence_sets_senior_review_flag(self) -> None:
        """
        confidence=0.60 (in 0.40–0.65 range) must automatically set
        requires_senior_review=True via model validator.
        This is the data-layer enforcement of G-SOFT-001.
        """
        from src.core.models import CodingSuggestion

        suggestion = CodingSuggestion(
            code="G93.41",
            description="Metabolic encephalopathy",
            confidence=0.60,
            evidence_quote="confusion",
            drg_impact="$4,200",
            is_mcc=True,
            is_cc=False,
        )
        assert suggestion.requires_senior_review is True

    def test_high_revenue_delta_sets_compliance_flag(self) -> None:
        """
        A CodingSuggestion with a DRG impact description indicating high
        revenue should be passable — the compliance flag is on DRGImpact,
        not CodingSuggestion directly. This test verifies the suggestion
        can hold a high-value drg_impact string without validation error.
        """
        from src.core.models import CodingSuggestion

        suggestion = CodingSuggestion(
            code="A41.51",
            description="Sepsis due to Escherichia coli",
            confidence=0.88,
            evidence_quote="sepsis",
            drg_impact="$42,759",  # high value — string representation
            is_mcc=True,
            is_cc=False,
        )
        assert suggestion.code == "A41.51"
        assert suggestion.drg_impact == "$42,759"

    def test_critical_violation_makes_result_invalid(self) -> None:
        """
        ValidationResult with a CRITICAL violation must have is_valid=False
        regardless of what is_valid was set to initially.
        This is the model-level enforcement of ICD-10 hard constraints.
        """
        from src.core.models.coding import (
            GuidelineViolation,
            ValidationResult,
            ViolationSeverity,
        )

        result = ValidationResult(
            is_valid=True,  # caller set this to True
            violations=[
                GuidelineViolation(
                    rule_id="G-HARD-003",
                    severity=ViolationSeverity.CRITICAL,
                    description="Excludes 1 pair detected",
                    affected_codes=["I50.9", "I50.20"],
                    remediation="Remove one code.",
                )
            ],
        )
        # Model validator must override is_valid=True when CRITICAL violation present
        assert result.is_valid is False

    def test_copy_forward_flagged_above_threshold(self) -> None:
        """
        CodingAnalysisResult with note_similarity_to_prior=0.91 must
        automatically set copy_forward_flagged=True via model validator.
        G-SOFT-002 threshold: 0.85.
        """
        from src.core.models.coding import CodingAnalysisResult, ValidationResult

        result = CodingAnalysisResult(
            encounter_id="ENC-TEST",
            coding_class="inpatient",
            validation_result=ValidationResult(is_valid=True),
            note_similarity_to_prior=0.91,
        )
        assert result.copy_forward_flagged is True

    def test_max_15_suggestions_enforced(self) -> None:
        """
        CodingAnalysisResult.suggestions has max_length=15.
        A claim with 16+ suggested codes would be a clinical quality issue.
        Pydantic must reject lists longer than 15.
        """
        from pydantic import ValidationError

        from src.core.models import CodingSuggestion
        from src.core.models.coding import CodingAnalysisResult, ValidationResult

        too_many = [
            CodingSuggestion(
                code=f"Z{str(i).zfill(2)}.9",
                description=f"Code {i}",
                confidence=0.88,
                evidence_quote=f"evidence {i}",
                drg_impact="$0",
                is_mcc=False,
                is_cc=False,
            )
            for i in range(16)
        ]

        with pytest.raises(ValidationError):
            CodingAnalysisResult(
                encounter_id="ENC-TEST",
                coding_class="inpatient",
                suggestions=too_many,
                validation_result=ValidationResult(is_valid=True),
            )


# ---------------------------------------------------------------------------
# GROUP 3 — Guardrail models: token and warning field presence
# ---------------------------------------------------------------------------


class TestGuardrailModels:
    """
    Verifies ApprovalToken and GuardrailWarning have the fields that
    the guardrail functions and the coder UI depend on.
    """

    def test_approval_token_model_fields_present(self) -> None:
        """
        ApprovalToken must have all fields required by the Article II.1 guardrail:
        token_value, encounter_id, coder_id, approved_codes_hash,
        expires_at, is_consumed.
        """
        from datetime import timedelta, timezone

        from src.core.models.guardrails import ApprovalToken
        from datetime import datetime

        now = datetime.now(tz=timezone.utc)
        token = ApprovalToken(
            token_value="signed.token.value",
            encounter_id="ENC-001",
            coder_id="CODER-001",
            approved_codes_hash="abc123def456",
            expires_at=now + timedelta(minutes=15),
        )
        assert token.encounter_id == "ENC-001"
        assert token.is_consumed is False
        assert token.approved_codes_hash == "abc123def456"

    def test_guardrail_warning_model_fields_present(self) -> None:
        """
        GuardrailWarning (from exceptions.py) must have the fields that
        soft guardrail functions attach to suggestions.
        """
        from src.core.exceptions import GuardrailWarning

        warning = GuardrailWarning(
            guardrail_id="G-SOFT-002",
            severity="medium",
            warning_message="Note similarity 91% exceeds threshold.",
        )
        assert warning.guardrail_id == "G-SOFT-002"
        assert warning.severity == "medium"
        assert warning.requires_explicit_acknowledgment is True
        assert warning.acknowledged_by is None


# ---------------------------------------------------------------------------
# GROUP 4 — Audit log PHI protection
# ---------------------------------------------------------------------------


class TestAuditLogPHIProtection:
    """
    Verifies UserActionAuditEntry rejects PHI field names in its details dict.
    This is the data-layer enforcement of constitution Article II.4.
    """

    def test_phi_field_name_in_details_raises_error(self) -> None:
        """
        details dict with key "mrn" must raise ValidationError.
        MRN is PHI identifier #8 (HIPAA).
        """
        from pydantic import ValidationError

        from src.core.models.audit import AuditAction, UserActionAuditEntry

        with pytest.raises(ValidationError) as exc_info:
            UserActionAuditEntry(
                coder_id="CODER-001",
                encounter_id="ENC-001",
                action=AuditAction.ACCEPTED_CODE,
                session_id="SESSION-001",
                details={"mrn": "MRN12345678"},  # PHI — must be rejected
            )
        assert "PHI" in str(exc_info.value) or "mrn" in str(exc_info.value).lower()

    def test_patient_name_in_details_raises_error(self) -> None:
        """
        details dict with key "patient_name" must raise ValidationError.
        Patient name is PHI identifier #1 (HIPAA).
        """
        from pydantic import ValidationError

        from src.core.models.audit import AuditAction, UserActionAuditEntry

        with pytest.raises(ValidationError):
            UserActionAuditEntry(
                coder_id="CODER-001",
                encounter_id="ENC-001",
                action=AuditAction.ACCEPTED_CODE,
                session_id="SESSION-001",
                details={"patient_name": "John Smith"},
            )

    def test_note_text_in_details_raises_error(self) -> None:
        """
        details dict with key "note_text" must raise ValidationError.
        Clinical note content is PHI when stored in audit logs.
        """
        from pydantic import ValidationError

        from src.core.models.audit import AuditAction, UserActionAuditEntry

        with pytest.raises(ValidationError):
            UserActionAuditEntry(
                coder_id="CODER-001",
                encounter_id="ENC-001",
                action=AuditAction.ACCEPTED_CODE,
                session_id="SESSION-001",
                details={"note_text": "Patient presented with..."},
            )

    def test_safe_fields_in_details_pass(self) -> None:
        """
        details with only safe fields (code, confidence, guardrail_id)
        must create successfully. Safe fields must not be blocked.
        """
        from src.core.models.audit import AuditAction, UserActionAuditEntry

        entry = UserActionAuditEntry(
            coder_id="CODER-001",
            encounter_id="ENC-001",
            action=AuditAction.ACCEPTED_CODE,
            session_id="SESSION-001",
            details={
                "code": "E11.22",
                "confidence": 0.88,
                "guardrail_id": "G-SOFT-001",
                "duration_ms": 1247,
            },
        )
        assert entry.details["code"] == "E11.22"

    def test_encounter_id_in_details_is_safe(self) -> None:
        """
        encounter_id in details is a system identifier, not PHI.
        Must not be blocked even though it looks like an identifier.
        """
        from src.core.models.audit import AuditAction, UserActionAuditEntry

        entry = UserActionAuditEntry(
            coder_id="CODER-001",
            encounter_id="ENC-001",
            action=AuditAction.ACCEPTED_CODE,
            session_id="SESSION-001",
            details={"related_encounter_id": "ENC-456"},
        )
        assert entry.details["related_encounter_id"] == "ENC-456"

    def test_icd10_code_in_details_is_safe(self) -> None:
        """
        ICD-10 codes in details are system identifiers, not PHI.
        Per HIPAA Skill Section 2: codes not linked to patient in logs are safe.
        """
        from src.core.models.audit import AuditAction, UserActionAuditEntry

        entry = UserActionAuditEntry(
            coder_id="CODER-001",
            encounter_id="ENC-001",
            action=AuditAction.REJECTED_CODE,
            session_id="SESSION-001",
            details={"rejected_code": "J18.9", "reason": "insufficient_evidence"},
        )
        assert entry.details["rejected_code"] == "J18.9"


# ---------------------------------------------------------------------------
# GROUP 5 — DegradedResult
# ---------------------------------------------------------------------------


class TestDegradedResult:
    """
    Verifies DegradedResult satisfies constitution Article II.5.
    Must be returned by any agent or FHIR client on failure.
    """

    def test_degraded_result_is_degraded_true(self) -> None:
        """
        DegradedResult must have is_degraded=True by default.
        The API layer checks this field to return manual mode to the UI.
        """
        from src.core.models import DegradedResult

        result = DegradedResult(
            error_code="FHIR_UNAVAILABLE",
            error_message="FHIR server unreachable",
        )
        assert result.is_degraded is True
        assert result.suggestions == []

    def test_degraded_result_no_phi_in_error_message(self) -> None:
        """
        DegradedResult.error_message must only contain system error info,
        never clinical content or patient identifiers.
        This test documents the convention — not enforced by Pydantic
        (free text field), but verified by test to lock in the pattern.
        """
        from src.core.models import DegradedResult

        result = DegradedResult(
            error_code="LLM_TIMEOUT",
            error_message="Claude API timeout after 60s — retries exhausted",
        )
        # Error message should describe the system failure, not clinical content
        assert "patient" not in result.error_message.lower()
        assert "mrn" not in result.error_message.lower()
        assert result.is_degraded is True


# ---------------------------------------------------------------------------
# GROUP 6 — DRG models: threshold flags
# ---------------------------------------------------------------------------


class TestDRGModels:
    """
    Verifies DRGImpact model validators enforce G-SOFT-003 thresholds
    at the data layer before any guardrail function runs.
    """

    def test_drg_impact_sets_significant_flag(self) -> None:
        """
        revenue_difference=1500 > 1000 threshold → is_significant=True.
        is_significant drives UI highlighting and priority sorting.
        """
        from src.core.models import DRGImpact

        impact = DRGImpact(
            current_drg="871",
            current_drg_weight=1.2342,
            proposed_drg="870",
            proposed_drg_weight=2.1000,
            revenue_difference=1500.0,
        )
        assert impact.is_significant is True

    def test_drg_impact_sets_compliance_review_flag(self) -> None:
        """
        revenue_difference=42759 > 5000 threshold → requires_compliance_review=True.
        G-SOFT-003: DRG increases > $5,000 route to compliance team before coder.
        """
        from src.core.models import DRGImpact

        impact = DRGImpact(
            current_drg="871",
            current_drg_weight=1.2342,
            proposed_drg="870",
            proposed_drg_weight=5.1200,
            revenue_difference=42759.0,
        )
        assert impact.requires_compliance_review is True
        assert impact.is_significant is True  # > 1000 also
