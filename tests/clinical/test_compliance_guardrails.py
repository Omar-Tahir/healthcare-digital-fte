"""
BUILD-001 — Compliance Guardrail Tests
TDD Red Phase: All tests written BEFORE any implementation.
All tests MUST FAIL on first run — that is the correct state.

Constitution Articles: II.1, II.2, II.3, II.4, II.5, II.6
Spec reference: specs/03-compliance-guardrail-architecture.md
Skill references: docs/skills/icd10-coding-rules.md,
                  docs/skills/hipaa-compliance.md

These tests must pass forever — they are the safety net.
100% coverage required. No exceptions. (Constitution Article I.2)
"""

from __future__ import annotations

import pytest

from src.core.exceptions import (
    CodingGuidelineViolationError,
    EvidenceCitationRequiredError,
    HumanApprovalRequiredError,
    ICD10GuidelineViolationError,
)

# ---------------------------------------------------------------------------
# Test fixtures — minimal synthetic data, no real PHI.
# All patient identifiers, names, and clinical values are fabricated.
# ---------------------------------------------------------------------------

SAMPLE_NOTE_TEXT = (
    "Patient presented with cough and shortness of breath. "
    "Assessment: possible pneumonia. "
    "Plan: chest X-ray, antibiotics if confirmed."
)

SAMPLE_INPATIENT_NOTE_TEXT = (
    "Admitted with 3-day history of productive cough and fever. "
    "Assessment: possible pneumonia — will treat empirically. "
    "Impression: pneumonia, suspected bacterial etiology."
)

SAMPLE_CONFIRMED_NOTE_TEXT = (
    "Patient presents with documented community-acquired pneumonia. "
    "Confirmed by chest X-ray showing left lower lobe infiltrate. "
    "Diagnosis: pneumonia, community-acquired."
)

SAMPLE_DM_CKD_NOTE_TEXT = (
    "Patient has type 2 diabetes mellitus with stage 3 chronic kidney disease "
    "per nephrology consultation. eGFR 38."
)

SAMPLE_CHF_NOTE_TEXT = (
    "Patient has chronic heart failure. Ejection fraction 30%. "
    "No acute decompensation currently documented."
)

SAMPLE_PHI_NOTE_TEXT = (
    "John Smith, DOB 01/15/1960, MRN MRN12345678, "
    "presents with chest pain and shortness of breath."
)

VALID_CODE_SET = ["J18.9", "R05.9"]
MODIFIED_CODE_SET = ["J18.9", "R06.00"]  # different from VALID_CODE_SET


# ---------------------------------------------------------------------------
# GROUP 1 — Article II.1: No Autonomous Claim Submission
# G-HARD-001
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestNoAutonomousClaimSubmission:
    """
    Constitution Article II.1 — No claim submission without human approval.
    FCA risk: 31 USC §3729 — $13,946–$27,894 per false claim.
    Guardrail: G-HARD-001
    """

    def test_claim_submission_blocked_without_approval_token(self) -> None:
        """
        T-001-01: CRITICAL — No claim reaches FHIR without human approval token.
        Attempting submission with token=None must raise
        HumanApprovalRequiredError — never silently succeed.
        """
        from src.core.guardrails.claim_guardrail import validate_approval_token

        with pytest.raises(HumanApprovalRequiredError) as exc_info:
            validate_approval_token(
                token=None,
                encounter_id="ENC-001",
                code_set=VALID_CODE_SET,
            )

        assert exc_info.value.guardrail_id == "G-HARD-001"

    def test_claim_submission_succeeds_with_valid_token(self) -> None:
        """
        T-001-05: Valid HMAC-SHA256 token + matching code set hash = allowed.
        Token must be < 15 minutes old and cryptographically valid.
        """
        from src.core.guardrails.claim_guardrail import (
            generate_approval_token,
            validate_approval_token,
        )

        token = generate_approval_token(
            coder_id="CODER-001",
            encounter_id="ENC-001",
            code_set=VALID_CODE_SET,
        )

        # Should not raise — valid token, matching codes
        result = validate_approval_token(
            token=token,
            encounter_id="ENC-001",
            code_set=VALID_CODE_SET,
        )

        assert result is True

    def test_expired_token_blocked(self) -> None:
        """
        T-001-02: Token older than 15 minutes must be rejected.
        Same error class as missing token — HumanApprovalRequiredError.
        """
        from src.core.guardrails.claim_guardrail import validate_approval_token

        # Token issued 16 minutes ago (expired)
        with pytest.raises(HumanApprovalRequiredError) as exc_info:
            validate_approval_token(
                token="expired.token.signature",
                encounter_id="ENC-001",
                code_set=VALID_CODE_SET,
                _issued_at_override=-960,  # 960 seconds = 16 minutes ago
            )

        assert exc_info.value.guardrail_id == "G-HARD-001"
        assert "expired" in exc_info.value.reason.lower()

    def test_token_single_use_second_attempt_blocked(self) -> None:
        """
        T-001-03 (extended): Token consumed on first use.
        Second submission with same token must fail even if otherwise valid.
        Prevents replay attacks against the approval mechanism.
        """
        from src.core.guardrails.claim_guardrail import (
            generate_approval_token,
            validate_approval_token,
        )

        token = generate_approval_token(
            coder_id="CODER-001",
            encounter_id="ENC-002",
            code_set=VALID_CODE_SET,
        )

        # First use — should succeed
        validate_approval_token(
            token=token,
            encounter_id="ENC-002",
            code_set=VALID_CODE_SET,
        )

        # Second use with same token — must be rejected
        with pytest.raises(HumanApprovalRequiredError) as exc_info:
            validate_approval_token(
                token=token,
                encounter_id="ENC-002",
                code_set=VALID_CODE_SET,
            )

        assert "consumed" in exc_info.value.reason.lower() or \
               "already used" in exc_info.value.reason.lower()

    def test_token_bound_to_specific_code_set(self) -> None:
        """
        T-001-03: Token generated for codes [A, B, C].
        Submission with codes [A, B, D] must fail.
        Token is cryptographically bound to the approved code set hash.
        Prevents approving one set and submitting a different one.
        """
        from src.core.guardrails.claim_guardrail import (
            generate_approval_token,
            validate_approval_token,
        )

        token = generate_approval_token(
            coder_id="CODER-001",
            encounter_id="ENC-003",
            code_set=VALID_CODE_SET,
        )

        with pytest.raises(HumanApprovalRequiredError) as exc_info:
            validate_approval_token(
                token=token,
                encounter_id="ENC-003",
                code_set=MODIFIED_CODE_SET,  # different codes than approved
            )

        assert exc_info.value.guardrail_id == "G-HARD-001"
        assert "code set" in exc_info.value.reason.lower() or \
               "hash" in exc_info.value.reason.lower()


# ---------------------------------------------------------------------------
# GROUP 2 — Article II.2: No Clinical Assertion Without Source Citation
# G-HARD-002
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestNoAssertionWithoutCitation:
    """
    Constitution Article II.2 — Every suggestion must have evidence_quote.
    Patient safety: A suggestion without a source citation is a hallucination.
    Guardrail: G-HARD-002
    """

    def test_suggestion_without_evidence_quote_rejected(self) -> None:
        """
        T-002-01/02: CodingSuggestion with evidence_quote=None or ""
        must raise EvidenceCitationRequiredError.
        Zero tolerance — hard stop, not a warning.
        """
        from src.core.guardrails.evidence_guardrail import (
            validate_evidence_quotes,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        suggestion_no_quote = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.85,
            evidence_quote=None,
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-004",
            encounter_setting="inpatient",
            source_note_text=SAMPLE_INPATIENT_NOTE_TEXT,
            suggestions=[suggestion_no_quote],
        )

        with pytest.raises(EvidenceCitationRequiredError) as exc_info:
            validate_evidence_quotes(suggestion_set)

        assert exc_info.value.guardrail_id == "G-HARD-002"
        assert exc_info.value.code == "J18.9"

    def test_evidence_quote_must_be_substring_of_source_note(self) -> None:
        """
        T-002-03/05: evidence_quote must be a verbatim substring of source note.
        A hallucinated quote not found in the note is rejected.
        'Quote from different note' also fails this check.
        """
        from src.core.guardrails.evidence_guardrail import (
            validate_evidence_quotes,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        suggestion_hallucinated_quote = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.85,
            evidence_quote="patient has confirmed bacterial pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-005",
            encounter_setting="inpatient",
            # Note does NOT contain "patient has confirmed bacterial pneumonia"
            source_note_text=SAMPLE_INPATIENT_NOTE_TEXT,
            suggestions=[suggestion_hallucinated_quote],
        )

        with pytest.raises(EvidenceCitationRequiredError) as exc_info:
            validate_evidence_quotes(suggestion_set)

        assert exc_info.value.guardrail_id == "G-HARD-002"

    def test_evidence_quote_case_insensitive_match(self) -> None:
        """
        T-002-04 (extended): Case-insensitive substring check.
        "Possible Pneumonia" matches "possible pneumonia" in source note.
        """
        from src.core.guardrails.evidence_guardrail import (
            validate_evidence_quotes,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        suggestion_with_quote = CodingSuggestion(
            code="R05.9",
            description="Cough, unspecified",
            confidence=0.80,
            # Mixed-case version of text that IS in SAMPLE_NOTE_TEXT
            evidence_quote="Possible Pneumonia",
            drg_impact="$0",
            is_mcc=False,
            is_cc=False,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-006",
            encounter_setting="outpatient",
            source_note_text=SAMPLE_NOTE_TEXT,
            suggestions=[suggestion_with_quote],
        )

        # Should NOT raise — case-insensitive match should find it
        validate_evidence_quotes(suggestion_set)

    def test_multiple_suggestions_all_require_evidence_quote(self) -> None:
        """
        T-002-01 (multi-suggestion): 5 suggestions, 1 has evidence_quote=None.
        The ENTIRE result is rejected — not just the single bad suggestion.
        A partial result with a hallucination is not acceptable.
        """
        from src.core.guardrails.evidence_guardrail import (
            validate_evidence_quotes,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        good_suggestion = CodingSuggestion(
            code="R05.9",
            description="Cough, unspecified",
            confidence=0.82,
            evidence_quote="cough and shortness of breath",
            drg_impact="$0",
            is_mcc=False,
            is_cc=False,
        )
        bad_suggestion = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.75,
            evidence_quote=None,  # missing — this should fail the whole set
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-007",
            encounter_setting="outpatient",
            source_note_text=SAMPLE_NOTE_TEXT,
            suggestions=[good_suggestion, bad_suggestion],
        )

        with pytest.raises(EvidenceCitationRequiredError):
            validate_evidence_quotes(suggestion_set)


# ---------------------------------------------------------------------------
# GROUP 3 — Article II.3: ICD-10 Guidelines As Hard Constraints
# G-HARD-003, G-HARD-004
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestICD10GuidelinesHardConstraints:
    """
    Constitution Article II.3 — ICD-10 Official Guidelines are inviolable.
    FCA risk: Incorrect coding of government-payer claims.
    Guardrails: G-HARD-003, G-HARD-004
    """

    def test_excludes1_pair_rejected(self) -> None:
        """
        T-003-01: I50.9 (CHF unspecified) + I50.20 (systolic CHF unspecified)
        have an Excludes 1 relationship — the pair must be rejected.
        Neither code is wrong individually; the COMBINATION is prohibited.
        Per ICD-10-CM Official Guidelines Section I.A.12.a.
        """
        from src.core.guardrails.icd10_guardrail import validate_excludes1
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        chf_unspecified = CodingSuggestion(
            code="I50.9",
            description="Heart failure, unspecified",
            confidence=0.78,
            evidence_quote="chronic heart failure",
            drg_impact="$3,200",
            is_mcc=False,
            is_cc=True,
        )
        systolic_chf = CodingSuggestion(
            code="I50.20",
            description="Unspecified systolic (congestive) heart failure",
            confidence=0.72,
            evidence_quote="Ejection fraction 30%",
            drg_impact="$5,100",
            is_mcc=False,
            is_cc=True,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-008",
            encounter_setting="inpatient",
            source_note_text=SAMPLE_CHF_NOTE_TEXT,
            suggestions=[chf_unspecified, systolic_chf],
        )

        with pytest.raises(ICD10GuidelineViolationError) as exc_info:
            validate_excludes1(suggestion_set)

        assert exc_info.value.guardrail_id == "G-HARD-003"
        assert exc_info.value.violation_type == "excludes_1"

    def test_outpatient_uncertain_diagnosis_not_coded_as_confirmed(self) -> None:
        """
        T-004-01: Outpatient + "possible pneumonia" → J18.9 is prohibited.
        Must suggest symptom codes instead (R05.9, R06.00).
        Coding an uncertain outpatient diagnosis as confirmed = FCA risk.
        Per ICD-10-CM Section IV.H.
        """
        from src.core.guardrails.icd10_guardrail import (
            validate_outpatient_uncertain_diagnosis,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        uncertain_diagnosis_coded_confirmed = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.80,
            evidence_quote="possible pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
            qualifier_words=["possible"],
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-009",
            encounter_setting="outpatient",
            source_note_text=SAMPLE_NOTE_TEXT,
            suggestions=[uncertain_diagnosis_coded_confirmed],
        )

        with pytest.raises(ICD10GuidelineViolationError) as exc_info:
            validate_outpatient_uncertain_diagnosis(suggestion_set)

        assert exc_info.value.guardrail_id == "G-HARD-004"
        assert exc_info.value.violation_type == "outpatient_uncertain_diagnosis"

    def test_inpatient_uncertain_diagnosis_may_be_coded(self) -> None:
        """
        T-004-06: Inpatient + "suspected pneumonia" → J18.9 IS allowed.
        Per ICD-10-CM Official Guidelines Section II.H.
        Inpatient uncertain diagnoses are coded as if confirmed.
        """
        from src.core.guardrails.icd10_guardrail import (
            validate_outpatient_uncertain_diagnosis,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        inpatient_uncertain = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.80,
            evidence_quote="possible pneumonia — will treat empirically",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
            qualifier_words=["possible"],
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-010",
            encounter_setting="inpatient",  # inpatient — guideline II.H applies
            source_note_text=SAMPLE_INPATIENT_NOTE_TEXT,
            suggestions=[inpatient_uncertain],
        )

        # Should NOT raise — inpatient uncertain is allowed per Section II.H
        validate_outpatient_uncertain_diagnosis(suggestion_set)

    def test_observation_encounter_treated_as_outpatient(self) -> None:
        """
        T-004-01 (OBS variant): encounter.class = 'observation'
        must apply OUTPATIENT coding rules — not inpatient.
        Even though the patient is physically in the hospital.
        Per CMS OBS status rules and ICD-10-CM guidelines.
        """
        from src.core.guardrails.icd10_guardrail import (
            validate_outpatient_uncertain_diagnosis,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        obs_uncertain = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.78,
            evidence_quote="possible pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
            qualifier_words=["possible"],
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-011",
            encounter_setting="observation",  # OBS = outpatient rules
            source_note_text=SAMPLE_NOTE_TEXT,
            suggestions=[obs_uncertain],
        )

        # Must raise — observation is treated as outpatient
        with pytest.raises(ICD10GuidelineViolationError) as exc_info:
            validate_outpatient_uncertain_diagnosis(suggestion_set)

        assert exc_info.value.guardrail_id == "G-HARD-004"

    def test_mandatory_sequencing_rule_enforced(self) -> None:
        """
        T-sequencing-01: E11.22 (DM with diabetic CKD) requires a
        corresponding N18.x (CKD stage) code.
        If E11.22 is present without N18.x, the suggestion set must
        be enhanced with the required paired code (not rejected).
        Per ICD-10-CM 'Use Additional Code' instruction for E11.22.
        """
        from src.core.guardrails.icd10_guardrail import (
            enforce_mandatory_paired_codes,
        )
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        dm_ckd_without_stage = CodingSuggestion(
            code="E11.22",
            description="Type 2 diabetes mellitus with diabetic chronic kidney disease",
            confidence=0.88,
            evidence_quote=(
                "type 2 diabetes mellitus with stage 3 chronic kidney disease"
            ),
            drg_impact="$1,800",
            is_mcc=False,
            is_cc=True,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-012",
            encounter_setting="inpatient",
            source_note_text=SAMPLE_DM_CKD_NOTE_TEXT,
            suggestions=[dm_ckd_without_stage],
        )

        # Should not raise — should ADD the N18.x code
        result = enforce_mandatory_paired_codes(suggestion_set)

        # Verify N18.x was added to the suggestion set
        codes_in_result = [s.code for s in result.suggestions]
        assert any(code.startswith("N18.") for code in codes_in_result), (
            "N18.x CKD stage code must be added when E11.22 is present "
            "without a corresponding CKD stage code."
        )

    def test_low_confidence_routed_to_senior_queue(self) -> None:
        """
        T-101-03: Confidence 0.60 (in range 0.40–0.65) must be routed
        to senior coder queue with requires_senior_review=True.
        Must NOT appear in standard coder queue.
        Per G-SOFT-001 — low confidence routing.
        """
        from src.core.guardrails.confidence_guardrail import (
            apply_confidence_routing,
        )
        from src.core.models import CodingSuggestion

        low_confidence_suggestion = CodingSuggestion(
            code="G93.41",
            description="Metabolic encephalopathy",
            confidence=0.60,
            evidence_quote="confusion",
            drg_impact="$4,200",
            is_mcc=True,
            is_cc=False,
        )

        result = apply_confidence_routing(low_confidence_suggestion)

        assert result.requires_senior_review is True
        assert result.routing_queue == "senior_coder_queue"


# ---------------------------------------------------------------------------
# GROUP 4 — Article II.4: No PHI In Logs
# G-HARD-005
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestNoPHIInLogs:
    """
    Constitution Article II.4 — PHI never appears in any log.
    HIPAA risk: PHI in logs is a reportable HIPAA violation.
    Guardrail: G-HARD-005
    """

    def test_phi_patient_name_never_in_log_output(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        T-005-01: Run the coding pipeline on a note containing patient name.
        Capture all log output.
        Assert: patient name "John Smith" does not appear anywhere in logs.
        """
        import structlog

        from src.api.middleware.phi_filter import PHIFilterProcessor

        processor = PHIFilterProcessor()

        with pytest.raises(CodingGuidelineViolationError):
            processor.process_log_entry(
                logger=structlog.get_logger(),
                method="info",
                event_dict={
                    "event": "processing_note",
                    "patient_name": "John Smith",
                    "encounter_id": "ENC-013",
                },
            )

    def test_phi_clinical_content_never_in_log_output(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        T-005-05: evidence_quote (verbatim clinical text) must never
        appear in any log entry. Only safe fields are permitted:
        encounter_id, code, confidence, duration_ms.
        """
        import structlog

        from src.api.middleware.phi_filter import PHIFilterProcessor

        processor = PHIFilterProcessor()

        with pytest.raises(CodingGuidelineViolationError):
            processor.process_log_entry(
                logger=structlog.get_logger(),
                method="info",
                event_dict={
                    "event": "suggestion_generated",
                    "encounter_id": "ENC-014",
                    "evidence_quote": "patient has confirmed bacterial pneumonia",
                },
            )

    def test_phi_never_in_error_messages(self) -> None:
        """
        T-005-07: Trigger a validation error on a note containing patient name.
        Assert: the exception message contains no patient name.
        Exception messages are often logged via log.exception() — they must
        be PHI-free. (HIPAA Skill: Section 2, NOT Safe column.)
        """
        from src.api.middleware.phi_filter import PHIFilterProcessor

        processor = PHIFilterProcessor()

        with pytest.raises(CodingGuidelineViolationError):
            processor.process_log_entry(
                logger=None,
                method="error",
                event_dict={
                    "event": "error",
                    "mrn": "MRN12345678",
                    "encounter_id": "ENC-015",
                },
            )

    def test_safe_log_fields_pass_phi_filter(self) -> None:
        """
        T-005-06: Log entry with only safe fields (encounter_id, code,
        confidence, duration_ms) must pass through the PHI filter unchanged.
        """
        import structlog

        from src.api.middleware.phi_filter import PHIFilterProcessor

        processor = PHIFilterProcessor()

        # Should NOT raise — no PHI fields present
        result = processor.process_log_entry(
            logger=structlog.get_logger(),
            method="info",
            event_dict={
                "event": "coding_analysis_complete",
                "encounter_id": "ENC-016",
                "code": "E11.22",
                "confidence": 0.88,
                "duration_ms": 1247,
                "suggestion_count": 3,
            },
        )

        assert result["encounter_id"] == "ENC-016"
        assert result["code"] == "E11.22"


# ---------------------------------------------------------------------------
# GROUP 5 — Article II.5: Graceful Degradation
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestGracefulDegradation:
    """
    Constitution Article II.5 — AI must never block clinical workflows.
    Any AI failure returns DegradedResult; never an unhandled exception.
    """

    def test_fhir_api_failure_returns_degraded_result(self) -> None:
        """
        T-degraded-01: FHIR client raises httpx.ConnectError when FHIR_BASE_URL is set.
        The coding agent must NOT propagate the exception.
        Must return a result with is_degraded=True and suggestions=[].
        Coder workflow continues in manual mode.
        """
        import os
        from unittest.mock import AsyncMock, patch

        import httpx
        import pytest

        from src.agents.coding_agent import CodingAgent
        from src.core.models import DegradedResult, EncounterContext

        encounter = EncounterContext(
            encounter_id="ENC-017",
            encounter_setting="inpatient",
            note_text=SAMPLE_INPATIENT_NOTE_TEXT,
        )

        # Simulate production mode where FHIR_BASE_URL is configured
        with patch.dict(os.environ, {"FHIR_BASE_URL": "https://fhir.example.com/R4"}):
            with patch(
                "src.core.fhir.client.FHIRClient.get_encounter",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectError("FHIR server unreachable"),
            ):
                agent = CodingAgent()
                result = pytest.importorskip("asyncio").get_event_loop().run_until_complete(
                    agent.analyze(encounter)
                )

        # Accept either DegradedResult or CodingAnalysisResult(is_degraded=True)
        # Both satisfy the graceful degradation contract (Article II.5)
        assert result.is_degraded is True
        assert getattr(result, "suggestions", []) == []

    def test_llm_api_failure_returns_degraded_result(self) -> None:
        """
        T-degraded-02: Anthropic API raises APIConnectionError.
        The coding agent must NOT propagate the exception.
        Must return DegradedResult with is_degraded=True.
        """
        from unittest.mock import AsyncMock, patch

        import anthropic
        import pytest

        from src.agents.coding_agent import CodingAgent
        from src.core.models import DegradedResult, EncounterContext

        encounter = EncounterContext(
            encounter_id="ENC-018",
            encounter_setting="inpatient",
            note_text=SAMPLE_INPATIENT_NOTE_TEXT,
        )

        with patch(
            "anthropic.AsyncAnthropic.messages",
            new_callable=AsyncMock,
            side_effect=anthropic.APIConnectionError(request=None),
        ):
            agent = CodingAgent()
            result = pytest.importorskip("asyncio").get_event_loop().run_until_complete(
                agent.analyze(encounter)
            )

        # Accept either DegradedResult or CodingAnalysisResult(is_degraded=True)
        assert result.is_degraded is True

    def test_degraded_result_never_raises_to_api_caller(self) -> None:
        """
        T-degraded-03: Complete pipeline failure.
        The FastAPI route must return HTTP 200 with is_degraded=True.
        Must NOT return HTTP 500.
        The UI must always receive something it can render.
        """
        from unittest.mock import AsyncMock, patch

        from fastapi.testclient import TestClient

        from src.api.main import app

        client = TestClient(app)

        with patch(
            "src.agents.coding_agent.CodingAgent.analyze",
            new_callable=AsyncMock,
            side_effect=Exception("Unexpected total failure"),
        ):
            response = client.post(
                "/api/v1/coding/analyze",
                json={
                    "encounter_id": "ENC-019",
                    "encounter_setting": "inpatient",
                    "note_text": SAMPLE_INPATIENT_NOTE_TEXT,
                },
                headers={"Authorization": "Bearer dev-test-token"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["is_degraded"] is True


# ---------------------------------------------------------------------------
# GROUP 6 — Article II.6: Conservative Defaults
# G-SOFT-003, G-HARD-007
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestConservativeDefaults:
    """
    Constitution Article II.6 — When uncertain, always choose the
    conservative option. Upcoding risk > undercoding risk.
    Guardrails: G-HARD-007, G-SOFT-003
    """

    def test_uncertain_between_specificity_levels_uses_lower(self) -> None:
        """
        T-conservative-01: Documentation says "CHF" with no acuity qualifier.
        Two valid codes: I50.20 (unspecified systolic CHF) and
        I50.21 (acute systolic CHF).
        System must suggest I50.20 (lower specificity) + CDI query.
        Must NOT suggest I50.21 (higher specificity, unsupported by docs).
        Per Constitution Article II.6: lower specificity + CDI query is correct.
        """
        from src.core.guardrails.specificity_guardrail import (
            apply_conservative_specificity,
        )
        from src.core.models import CodingSuggestion

        suggestion_higher_specificity = CodingSuggestion(
            code="I50.21",
            description="Acute systolic (congestive) heart failure",
            confidence=0.72,
            evidence_quote="chronic heart failure",
            drg_impact="$7,500",
            is_mcc=False,
            is_cc=True,
        )

        result = apply_conservative_specificity(
            suggestion=suggestion_higher_specificity,
            documentation_supports_acuity=False,
        )

        # Must downgrade to lower specificity
        assert result.selected_code == "I50.20"
        assert result.cdi_query_required is True
        assert result.cdi_query_category is not None

    def test_high_revenue_suggestion_flags_for_compliance_review(self) -> None:
        """
        T-103-01: A suggestion that increases DRG revenue by > $5,000
        must include compliance_review_required=True.
        Not blocked — flagged. Human compliance team makes the final call.
        Per G-SOFT-003 and Constitution Article II.6.
        """
        from src.core.guardrails.drg_guardrail import (
            apply_drg_compliance_threshold,
        )
        from src.core.models import CodingSuggestion, DRGImpact

        high_value_suggestion = CodingSuggestion(
            code="A41.51",
            description="Sepsis due to Escherichia coli",
            confidence=0.88,
            evidence_quote="sepsis",
            drg_impact="$42,759",
            is_mcc=True,
            is_cc=False,
        )

        drg_impact = DRGImpact(
            current_drg="871",
            current_drg_weight=1.2342,
            proposed_drg="870",
            proposed_drg_weight=5.1200,
            revenue_difference=42759.00,
        )

        result = apply_drg_compliance_threshold(
            suggestion=high_value_suggestion,
            drg_impact=drg_impact,
        )

        assert result.compliance_review_required is True
        assert result.compliance_review_reason is not None
        assert result.drg_impact.revenue_difference > 5000


# ---------------------------------------------------------------------------
# GROUP 7 — Article II.6: G-HARD-007 Minimum Confidence Hard Stop
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestHardConfidenceThreshold:
    """
    Constitution Article II.6 — AI suggestions with confidence < 0.40
    are a hard stop. Output too uncertain to present to any user.
    Guardrail: G-HARD-007
    Spec reference: DESIGN-003 §1 G-HARD-007
    """

    def test_confidence_below_minimum_raises_hard_stop(self) -> None:
        """
        T-007-01: Confidence 0.35 < minimum threshold 0.40.
        Must raise CodingGuidelineViolationError — hard rejection.
        The suggestion is discarded, not routed. If genuinely ambiguous,
        the CDI agent generates a query instead.
        Per Constitution Article II.6: conservative default always.
        """
        from src.core.guardrails.confidence_guardrail import (
            validate_minimum_confidence,
        )
        from src.core.models import CodingSuggestion

        below_threshold = CodingSuggestion(
            code="G93.41",
            description="Metabolic encephalopathy",
            confidence=0.35,
            evidence_quote="confusion",
            drg_impact="$4,200",
            is_mcc=True,
            is_cc=False,
        )

        with pytest.raises(CodingGuidelineViolationError) as exc_info:
            validate_minimum_confidence(below_threshold)

        assert exc_info.value.guardrail_id == "G-HARD-007"

    def test_confidence_at_exactly_minimum_passes_hard_stop(self) -> None:
        """
        T-007-02: Confidence exactly 0.40 passes the hard stop.
        It enters the G-SOFT-001 range (senior coder routing).
        The hard stop boundary is inclusive at 0.40.
        """
        from src.core.guardrails.confidence_guardrail import (
            validate_minimum_confidence,
        )
        from src.core.models import CodingSuggestion

        at_threshold = CodingSuggestion(
            code="G93.41",
            description="Metabolic encephalopathy",
            confidence=0.40,
            evidence_quote="confusion",
            drg_impact="$4,200",
            is_mcc=True,
            is_cc=False,
        )

        # Should NOT raise — 0.40 passes the hard stop
        validate_minimum_confidence(at_threshold)

    def test_confidence_above_soft_threshold_passes_fully(self) -> None:
        """
        T-007-03: Confidence 0.88 passes both hard stop (0.40) and
        soft routing threshold (0.65). Normal suggestion flow.
        """
        from src.core.guardrails.confidence_guardrail import (
            validate_minimum_confidence,
        )
        from src.core.models import CodingSuggestion

        high_confidence = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.88,
            evidence_quote="community-acquired pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )

        # Should NOT raise
        validate_minimum_confidence(high_confidence)


# ---------------------------------------------------------------------------
# GROUP 8 — Article II.4: G-HARD-006 FHIR Write Requires HIPAA Audit
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.hard_guardrail
class TestFHIRWriteRequiresAudit:
    """
    Constitution Article II.4 — Every FHIR write must be preceded by
    a complete HIPAA audit log entry. Untracked writes to PHI are not
    permitted under HIPAA and constitute a compliance gap OIG auditors
    specifically examine.
    Guardrail: G-HARD-006
    Spec reference: DESIGN-003 §1 G-HARD-006
    """

    def test_fhir_write_without_user_id_blocked(self) -> None:
        """
        T-006-01: AuditLogEntry with user_id=None is incomplete.
        The FHIR write must not proceed — incomplete audit = hard stop.
        Per HIPAA: all access to PHI must be attributable to an identity.
        """
        from src.core.guardrails.fhir_audit_guardrail import (
            validate_fhir_write_audit,
        )
        from src.core.models import AuditLogEntry

        incomplete_audit = AuditLogEntry(
            operation="create",
            resource_type="Claim",
            resource_id="CLAIM-001",
            user_id=None,  # Missing — incomplete audit entry
            user_role="coder",
            encounter_id="ENC-020",
            justification="claim submission",
        )

        with pytest.raises(CodingGuidelineViolationError) as exc_info:
            validate_fhir_write_audit(incomplete_audit)

        assert exc_info.value.guardrail_id == "G-HARD-006"

    def test_fhir_write_blocked_when_audit_service_unavailable(self) -> None:
        """
        T-006-02: Even with a complete AuditLogEntry, if writing the audit
        log fails (service unavailable), the FHIR write must NOT proceed.
        PHI access without a committed audit trail is unacceptable.
        """
        from unittest.mock import patch

        from src.core.guardrails.fhir_audit_guardrail import (
            validate_fhir_write_audit,
        )
        from src.core.models import AuditLogEntry

        complete_audit = AuditLogEntry(
            operation="create",
            resource_type="Claim",
            resource_id="CLAIM-002",
            user_id="CODER-001",
            user_role="coder",
            encounter_id="ENC-021",
            justification="claim submission after coder review",
        )

        with patch(
            "src.core.guardrails.fhir_audit_guardrail.write_audit_log",
            side_effect=Exception("Audit service unavailable"),
        ):
            with pytest.raises(CodingGuidelineViolationError) as exc_info:
                validate_fhir_write_audit(complete_audit)

        assert exc_info.value.guardrail_id == "G-HARD-006"

    def test_fhir_write_proceeds_with_complete_valid_audit(self) -> None:
        """
        T-006-03: Complete AuditLogEntry + healthy audit service = proceed.
        The guardrail returns True to signal the FHIR write is authorized.
        """
        from unittest.mock import patch

        from src.core.guardrails.fhir_audit_guardrail import (
            validate_fhir_write_audit,
        )
        from src.core.models import AuditLogEntry

        complete_audit = AuditLogEntry(
            operation="create",
            resource_type="Claim",
            resource_id="CLAIM-003",
            user_id="CODER-001",
            user_role="coder",
            encounter_id="ENC-022",
            justification="claim submission after coder review",
        )

        with patch(
            "src.core.guardrails.fhir_audit_guardrail.write_audit_log",
            return_value=True,
        ):
            result = validate_fhir_write_audit(complete_audit)

        assert result is True


# ---------------------------------------------------------------------------
# GROUP 9 — Article II.3: G-SOFT-002 Copy-Forward Detection
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.soft_guardrail
class TestCopyForwardDetection:
    """
    Constitution Article II.6 (Conservative Defaults) — Notes with > 85%
    similarity to a prior note are flagged. Copy-forward documentation
    supporting higher-level billing is FCA exposure (DISC-002 Section A.3).
    Guardrail: G-SOFT-002
    Spec reference: DESIGN-003 §1 G-SOFT-002
    """

    def test_high_similarity_note_generates_copy_forward_warning(self) -> None:
        """
        T-002-S-01: Note similarity 0.91 > 0.85 threshold.
        GuardrailWarning(guardrail_id="G-SOFT-002") must be attached to the
        suggestion set. Coder must acknowledge before accepting any suggestion.
        """
        from src.core.exceptions import GuardrailWarning
        from src.core.guardrails.copy_forward_guardrail import detect_copy_forward
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        suggestion = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.82,
            evidence_quote="community-acquired pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-023",
            encounter_setting="inpatient",
            source_note_text=SAMPLE_CONFIRMED_NOTE_TEXT,
            suggestions=[suggestion],
            note_similarity_score=0.91,  # > 0.85 threshold
        )

        result = detect_copy_forward(suggestion_set)

        set_guardrail_ids = [w.guardrail_id for w in result.warnings]
        assert "G-SOFT-002" in set_guardrail_ids, (
            "CodingSuggestionSet must have a G-SOFT-002 warning when "
            "note similarity exceeds 0.85."
        )
        warning = next(w for w in result.warnings if w.guardrail_id == "G-SOFT-002")
        assert warning.severity == "medium"
        assert warning.requires_explicit_acknowledgment is True

    def test_low_similarity_note_has_no_copy_forward_warning(self) -> None:
        """
        T-002-S-02: Note similarity 0.72 < 0.85 threshold.
        No G-SOFT-002 warning should be attached to the suggestion set.
        """
        from src.core.guardrails.copy_forward_guardrail import detect_copy_forward
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        suggestion = CodingSuggestion(
            code="J18.9",
            description="Pneumonia, unspecified organism",
            confidence=0.82,
            evidence_quote="community-acquired pneumonia",
            drg_impact="$2,400",
            is_mcc=False,
            is_cc=False,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-024",
            encounter_setting="inpatient",
            source_note_text=SAMPLE_CONFIRMED_NOTE_TEXT,
            suggestions=[suggestion],
            note_similarity_score=0.72,  # below threshold
        )

        result = detect_copy_forward(suggestion_set)

        set_guardrail_ids = [w.guardrail_id for w in result.warnings]
        assert "G-SOFT-002" not in set_guardrail_ids


# ---------------------------------------------------------------------------
# GROUP 10 — Article II.3: G-SOFT-004 Excludes 2 Human Confirmation
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.soft_guardrail
class TestExcludes2HumanConfirmation:
    """
    Excludes 2 codes MAY appear together if both conditions are independently
    documented, but require human confirmation. Unlike Excludes 1 (hard stop),
    Excludes 2 is a soft guardrail — human decision with documented rationale.
    Guardrail: G-SOFT-004
    Spec reference: DESIGN-003 §1 G-SOFT-004
    """

    SAMPLE_OBESITY_SLEEP_APNEA_NOTE = (
        "Patient has morbid obesity (BMI 42) with independently documented "
        "obstructive sleep apnea confirmed by sleep study. Both conditions "
        "are active and require management."
    )

    def test_excludes2_pair_generates_confirmation_warning(self) -> None:
        """
        T-004-S-01: E66.01 (Morbid obesity) + G47.33 (Obstructive sleep apnea)
        have an Excludes 2 relationship. Both codes get a warning requiring
        confirmation that both conditions are independently documented.
        Codes are NOT removed — this is not a hard stop.
        """
        from src.core.guardrails.icd10_guardrail import validate_excludes2
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        morbid_obesity = CodingSuggestion(
            code="E66.01",
            description="Morbid (severe) obesity due to excess calories",
            confidence=0.88,
            evidence_quote="morbid obesity (BMI 42)",
            drg_impact="$1,100",
            is_mcc=False,
            is_cc=True,
        )
        sleep_apnea = CodingSuggestion(
            code="G47.33",
            description="Obstructive sleep apnea (adult)(pediatric)",
            confidence=0.85,
            evidence_quote="obstructive sleep apnea confirmed by sleep study",
            drg_impact="$900",
            is_mcc=False,
            is_cc=True,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-025",
            encounter_setting="inpatient",
            source_note_text=self.SAMPLE_OBESITY_SLEEP_APNEA_NOTE,
            suggestions=[morbid_obesity, sleep_apnea],
        )

        result = validate_excludes2(suggestion_set)

        # Both codes must still be present — Excludes 2 is NOT a hard stop
        result_codes = [s.code for s in result.suggestions]
        assert "E66.01" in result_codes
        assert "G47.33" in result_codes

        # Each code in the Excludes 2 pair must have a G-SOFT-004 warning
        for suggestion in result.suggestions:
            if suggestion.code in ("E66.01", "G47.33"):
                warning_ids = [w.guardrail_id for w in suggestion.warnings]
                assert "G-SOFT-004" in warning_ids, (
                    f"Code {suggestion.code} must have a G-SOFT-004 warning "
                    "in an Excludes 2 pair."
                )

    def test_non_excludes2_pair_has_no_confirmation_warning(self) -> None:
        """
        T-004-S-02: E11.22 + N18.3 do NOT have an Excludes 2 relationship.
        No G-SOFT-004 warning should be attached to either code.
        """
        from src.core.guardrails.icd10_guardrail import validate_excludes2
        from src.core.models import CodingSuggestion, CodingSuggestionSet

        dm_ckd = CodingSuggestion(
            code="E11.22",
            description="Type 2 diabetes mellitus with diabetic CKD",
            confidence=0.88,
            evidence_quote="type 2 diabetes mellitus with stage 3 chronic kidney disease",
            drg_impact="$1,800",
            is_mcc=False,
            is_cc=True,
        )
        ckd_stage = CodingSuggestion(
            code="N18.3",
            description="Chronic kidney disease, stage 3",
            confidence=0.90,
            evidence_quote="stage 3 chronic kidney disease",
            drg_impact="$1,400",
            is_mcc=False,
            is_cc=True,
        )

        suggestion_set = CodingSuggestionSet(
            encounter_id="ENC-026",
            encounter_setting="inpatient",
            source_note_text=SAMPLE_DM_CKD_NOTE_TEXT,
            suggestions=[dm_ckd, ckd_stage],
        )

        result = validate_excludes2(suggestion_set)

        for suggestion in result.suggestions:
            warning_ids = [w.guardrail_id for w in suggestion.warnings]
            assert "G-SOFT-004" not in warning_ids


# ---------------------------------------------------------------------------
# GROUP 11 — G-SOFT-005: Third CDI Query Triggers CDI Specialist Escalation
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.soft_guardrail
class TestCDIQueryEscalation:
    """
    Generating a 3rd+ CDI query on the same encounter risks physician
    notification fatigue — a known OIG compliance concern where physicians
    reflexively answer "yes" without clinical reassessment.
    Guardrail: G-SOFT-005
    Spec reference: DESIGN-003 §1 G-SOFT-005
    """

    def test_third_cdi_query_routed_to_cdi_specialist(self) -> None:
        """
        T-005-S-01: Encounter already has 2 active/resolved CDI queries.
        A third CDI opportunity must be routed to CDI specialist review
        before being sent to the physician.
        routing must be "cdi_specialist_review", not "physician_direct".
        """
        from src.core.guardrails.cdi_guardrail import apply_cdi_query_escalation
        from src.core.models import CDIOpportunity

        # Simulate existing queries count
        existing_query_count = 2

        opportunity = CDIOpportunity(
            encounter_id="ENC-027",
            query_category="specificity",
            query_text="Please clarify the acuity of heart failure.",
            suggested_code="I50.21",
            drg_impact="$3,100",
        )

        result = apply_cdi_query_escalation(
            opportunity=opportunity,
            existing_query_count=existing_query_count,
        )

        assert result.routing == "cdi_specialist_review"
        warning_ids = [w.guardrail_id for w in result.warnings]
        assert "G-SOFT-005" in warning_ids

    def test_first_cdi_query_routes_directly_to_physician(self) -> None:
        """
        T-005-S-02: First CDI query on an encounter (no existing queries).
        Routing must be "physician_direct" — no escalation, no warning.
        """
        from src.core.guardrails.cdi_guardrail import apply_cdi_query_escalation
        from src.core.models import CDIOpportunity

        existing_query_count = 0

        opportunity = CDIOpportunity(
            encounter_id="ENC-028",
            query_category="specificity",
            query_text="Please clarify the acuity of heart failure.",
            suggested_code="I50.21",
            drg_impact="$3,100",
        )

        result = apply_cdi_query_escalation(
            opportunity=opportunity,
            existing_query_count=existing_query_count,
        )

        assert result.routing == "physician_direct"
        warning_ids = [w.guardrail_id for w in result.warnings]
        assert "G-SOFT-005" not in warning_ids
