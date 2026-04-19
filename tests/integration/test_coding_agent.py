"""
Coding Agent Integration Tests — BUILD-006.
Written BEFORE implementation (TDD red phase per constitution Article I.2).

These tests use mocked LLM responses — no real Anthropic API key required.
Run with: uv run pytest tests/integration/test_coding_agent.py -v

Constitution: II.1 (no claim without approval token),
              II.2 (evidence citation required on every suggestion),
              II.3 (ICD-10 guidelines enforced — Excludes 1, uncertain dx),
              II.4 (no PHI in logs),
              II.5 (graceful degradation — DegradedResult on failure),
              II.6 (conservative defaults — revenue thresholds, confidence flags)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.coding_agent import CodingAgent
from src.core.models.coding import CodingAnalysisResult, CodingSuggestion
from src.core.models.encounter import CodingClass, EncounterClass
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
    NoteContentType,
)

# ─── Clinical note fixtures ───────────────────────────────────────────────────

HEART_FAILURE_NOTE = """
Assessment: Patient presents with acute exacerbation of
congestive heart failure, systolic type. Creatinine has
risen from 1.1 to 2.4 mg/dL over the past 48 hours.
Patient also has type 2 diabetes mellitus with stage 3
chronic kidney disease. Blood pressure 158/96.

Plan: Admit for IV diuresis. Furosemide 40mg IV BID.
Cardiology consult requested.
"""

UNCERTAIN_OUTPATIENT_NOTE = """
Assessment: Possible community-acquired pneumonia versus
viral upper respiratory infection. Chest X-ray shows
possible right lower lobe infiltrate — will follow up.
Plan: Empiric azithromycin. Return if worsening.
"""

INPATIENT_UNCERTAIN_NOTE = """
Assessment: Probable sepsis secondary to urinary tract
infection. Patient meets SIRS criteria. Lactate 2.8.
Will treat empirically pending blood culture results.
"""


def make_document_reference(note_text: str) -> FHIRDocumentReference:
    return FHIRDocumentReference(
        id="doc-001",
        encounter_id="enc-001",
        note_type_loinc="34117-2",
        note_type_display="History and physical note",
        authored_date=datetime.now(timezone.utc),
        content_type=NoteContentType.PLAIN_TEXT,
        note_text=note_text,
    )


def make_encounter(class_code: str) -> FHIREncounter:
    return FHIREncounter(
        id="enc-001",
        status="in-progress",
        class_code=class_code,
        encounter_class=EncounterClass(class_code),
        period_start=datetime.now(timezone.utc),
    )


def _make_mock_llm_response(suggestions: list[dict]) -> MagicMock:
    """Create a mock Anthropic API response containing suggestions JSON."""
    content = json.dumps({
        "suggestions": suggestions,
        "cdi_opportunities": [],
    })
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=content)]
    return mock_response


# ─── Core behavior ────────────────────────────────────────────────────────────


class TestCodingAgentCore:
    """Core orchestration tests — mocked LLM, no API key needed."""

    @pytest.fixture
    def agent(self) -> CodingAgent:
        return CodingAgent()

    @pytest.mark.asyncio
    async def test_returns_coding_analysis_result(
        self, agent: CodingAgent
    ) -> None:
        """
        Agent always returns CodingAnalysisResult, never raises.
        Article II.5: graceful degradation.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "I50.21",
                    "description": "Systolic heart failure, acute",
                    "confidence": 0.92,
                    "evidence_quote": "congestive heart failure, systolic type",
                    "drg_impact_description": "+$7,500 vs unspecified CHF",
                    "drg_revenue_delta": 7500.0,
                    "is_mcc": False,
                    "is_cc": True,
                    "is_principal_dx_candidate": True,
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        assert isinstance(result, CodingAnalysisResult)
        assert not result.is_degraded

    @pytest.mark.asyncio
    async def test_every_suggestion_has_evidence_quote(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.2: evidence_quote required and must be in source note.
        Every suggestion from the agent is traceable to verbatim text.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "I50.21",
                    "description": "Systolic heart failure, acute",
                    "confidence": 0.92,
                    "evidence_quote": "congestive heart failure, systolic type",
                    "drg_impact_description": "significant",
                    "drg_revenue_delta": 7500.0,
                    "is_mcc": False,
                    "is_cc": True,
                    "is_principal_dx_candidate": True,
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        for suggestion in result.suggestions:
            assert suggestion.evidence_quote is not None
            assert len(suggestion.evidence_quote) > 0
            assert suggestion.evidence_quote in (doc.note_text or "")

    @pytest.mark.asyncio
    async def test_evidence_quote_not_in_note_filters_suggestion(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.2: suggestion with hallucinated evidence_quote is removed.
        A quote not present in source note = hallucination → filter out.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "I50.21",
                    "description": "Systolic CHF",
                    "confidence": 0.90,
                    "evidence_quote": "this text does not exist in the note",
                    "drg_impact_description": "significant",
                    "drg_revenue_delta": 7500.0,
                    "is_mcc": False,
                    "is_cc": True,
                    "is_principal_dx_candidate": True,
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        codes = [s.code for s in result.suggestions]
        assert "I50.21" not in codes

    @pytest.mark.asyncio
    async def test_outpatient_uncertain_diagnosis_filtered(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.3: uncertain diagnosis NOT coded in outpatient.
        'Possible pneumonia' → J18.9 must be filtered out.
        AMB encounter + 'possible' qualifier = outpatient rule violation.
        """
        doc = make_document_reference(UNCERTAIN_OUTPATIENT_NOTE)
        encounter = make_encounter("AMB")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "J18.9",
                    "description": "Pneumonia, unspecified",
                    "confidence": 0.75,
                    "evidence_quote": "Possible community-acquired pneumonia",
                    "drg_impact_description": "moderate",
                    "drg_revenue_delta": 1500.0,
                    "is_mcc": False,
                    "is_cc": False,
                    "is_principal_dx_candidate": True,
                    "uncertainty_qualifier": "possible",
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        codes = [s.code for s in result.suggestions]
        assert "J18.9" not in codes

    @pytest.mark.asyncio
    async def test_inpatient_uncertain_diagnosis_allowed(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.3: uncertain diagnosis MAY be coded for inpatient.
        'Probable sepsis' → A41.9 IS allowed for IMP encounter.
        Per ICD-10-CM Official Guidelines Section II.H.
        """
        doc = make_document_reference(INPATIENT_UNCERTAIN_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "A41.9",
                    "description": "Sepsis, unspecified",
                    "confidence": 0.82,
                    "evidence_quote": "Probable sepsis secondary to urinary tract",
                    "drg_impact_description": "significant — MCC",
                    "drg_revenue_delta": 12000.0,
                    "is_mcc": True,
                    "is_cc": False,
                    "is_principal_dx_candidate": True,
                    "uncertainty_qualifier": "probable",
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        codes = [s.code for s in result.suggestions]
        assert "A41.9" in codes

    @pytest.mark.asyncio
    async def test_excludes1_violation_filtered(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.3: Excludes 1 pair never appears together.
        I50.9 (HF unspecified) + I50.21 (acute systolic HF) → Excludes 1.
        Rules engine removes the lower-revenue code.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "I50.9",
                    "description": "Heart failure, unspecified",
                    "confidence": 0.88,
                    "evidence_quote": "congestive heart failure",
                    "drg_impact_description": "low",
                    "drg_revenue_delta": 0.0,
                    "is_mcc": False,
                    "is_cc": False,
                    "is_principal_dx_candidate": False,
                },
                {
                    "code": "I50.21",
                    "description": "Systolic heart failure, acute",
                    "confidence": 0.91,
                    "evidence_quote": "congestive heart failure, systolic type",
                    "drg_impact_description": "significant",
                    "drg_revenue_delta": 7500.0,
                    "is_mcc": False,
                    "is_cc": True,
                    "is_principal_dx_candidate": True,
                },
            ])
            result = await agent.analyze_note(doc, encounter)

        codes = [s.code for s in result.suggestions]
        assert not ("I50.9" in codes and "I50.21" in codes)

    @pytest.mark.asyncio
    async def test_low_confidence_flagged_for_senior_review(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.6: confidence < 0.65 → requires_senior_review=True.
        G-SOFT-001 conservative default — uncertain suggestions flagged.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "E11.22",
                    "description": "DM2 with diabetic CKD",
                    "confidence": 0.55,
                    "evidence_quote": "type 2 diabetes mellitus with stage 3 chronic kidney disease",
                    "drg_impact_description": "moderate",
                    "drg_revenue_delta": 2400.0,
                    "is_mcc": False,
                    "is_cc": True,
                    "is_principal_dx_candidate": False,
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        low_conf = [s for s in result.suggestions if s.confidence < 0.65]
        for s in low_conf:
            assert s.requires_senior_review is True

    @pytest.mark.asyncio
    async def test_high_revenue_delta_flagged_for_compliance(
        self, agent: CodingAgent
    ) -> None:
        """
        G-SOFT-003: drg_revenue_delta > $5,000 → compliance_review_required.
        Article II.6: conservative defaults — high-impact suggestions reviewed.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "A41.9",
                    "description": "Sepsis, unspecified",
                    "confidence": 0.88,
                    "evidence_quote": "sepsis secondary to",
                    "drg_impact_description": "+$12,000",
                    "drg_revenue_delta": 12000.0,
                    "is_mcc": True,
                    "is_cc": False,
                    "is_principal_dx_candidate": True,
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        high_revenue = [s for s in result.suggestions if s.drg_revenue_delta > 5000]
        for s in high_revenue:
            assert s.compliance_review_required is True

    @pytest.mark.asyncio
    async def test_max_15_suggestions_enforced(
        self, agent: CodingAgent
    ) -> None:
        """Result never contains more than 15 suggestions."""
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        suggestions = [
            {
                "code": f"Z{i:02d}.0",
                "description": f"Code {i}",
                "confidence": 0.80,
                "evidence_quote": "type 2 diabetes mellitus",
                "drg_impact_description": "moderate",
                "drg_revenue_delta": float(i * 100),
                "is_mcc": False,
                "is_cc": False,
                "is_principal_dx_candidate": False,
            }
            for i in range(1, 21)  # 20 suggestions
        ]

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response(suggestions)
            result = await agent.analyze_note(doc, encounter)

        assert len(result.suggestions) <= 15

    @pytest.mark.asyncio
    async def test_returns_degraded_on_llm_failure(
        self, agent: CodingAgent
    ) -> None:
        """
        Article II.5: LLM API failure → is_degraded=True result.
        Workflow continues — never raises to caller.
        """
        import anthropic

        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with patch.object(
            agent._llm_client,
            "messages_create",
            new_callable=AsyncMock,
            side_effect=anthropic.APIConnectionError(request=MagicMock()),
        ):
            result = await agent.analyze_note(doc, encounter)

        assert isinstance(result, (CodingAnalysisResult, DegradedResult))
        if isinstance(result, CodingAnalysisResult):
            assert result.is_degraded is True

    @pytest.mark.asyncio
    async def test_phi_never_in_logs(
        self, agent: CodingAgent, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        Article II.4: clinical note content never appears in logs.
        Note text is PHI — must not reach any log record.
        """
        doc = make_document_reference(HEART_FAILURE_NOTE)
        encounter = make_encounter("IMP")

        with caplog.at_level(logging.DEBUG):
            with patch.object(
                agent._llm_client, "messages_create", new_callable=AsyncMock
            ) as mock_llm:
                mock_llm.return_value = _make_mock_llm_response([])
                await agent.analyze_note(doc, encounter)

        for record in caplog.records:
            assert "heart failure" not in record.message.lower()
            assert "furosemide" not in record.message.lower()
            assert "creatinine" not in record.message.lower()

    @pytest.mark.asyncio
    async def test_observation_encounter_uses_outpatient_rules(
        self, agent: CodingAgent
    ) -> None:
        """
        OBS (observation status) uses outpatient coding rules.
        Uncertain diagnosis filtered same as AMB.
        Per CMS OBS status billing rules.
        """
        doc = make_document_reference(UNCERTAIN_OUTPATIENT_NOTE)
        encounter = make_encounter("OBS")

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _make_mock_llm_response([
                {
                    "code": "J18.9",
                    "description": "Pneumonia, unspecified",
                    "confidence": 0.75,
                    "evidence_quote": "Possible community-acquired pneumonia",
                    "drg_impact_description": "moderate",
                    "drg_revenue_delta": 1500.0,
                    "is_mcc": False,
                    "is_cc": False,
                    "is_principal_dx_candidate": True,
                    "uncertainty_qualifier": "possible",
                }
            ])
            result = await agent.analyze_note(doc, encounter)

        codes = [s.code for s in result.suggestions]
        assert "J18.9" not in codes
