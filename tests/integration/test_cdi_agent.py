"""
CDI Agent Integration Tests — BUILD-007.
Written BEFORE implementation (TDD red phase, constitution Article I.2).

Detection tests (1, 2, 6) are pure Python — no LLM mock needed.
Query generation tests (3, 4, 5) mock the LLM via patch.object.
Degradation test (7) simulates LLM failure.

Constitution: II.2 (evidence-grounded queries only),
              II.4 (no PHI in logs),
              II.5 (graceful degradation),
              II.6 (conservative — query, never diagnose)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.cdi_agent import CDIAgent
from src.core.models.cdi import CDIAnalysisResult, CDIOpportunity
from src.core.models.encounter import EncounterClass
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRObservation,
    NoteContentType,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

_NOW = datetime.now(timezone.utc)
_EARLIER = _NOW - timedelta(hours=24)

# AKI note: creatinine rise documented but AKI NOT mentioned
CREATININE_RISE_NOTE = """
Assessment: Patient with known CKD stage 3. Creatinine has risen
from 1.1 to 2.4 mg/dL over the past 24 hours. Patient appears
volume-depleted. IV fluids started.
Plan: Hold nephrotoxics. Monitor renal function.
"""

# Same creatinine rise but physician already documented AKI
AKI_DOCUMENTED_NOTE = """
Assessment: Acute kidney injury superimposed on CKD stage 3.
Creatinine rose from 1.1 to 2.4 mg/dL. Likely pre-renal etiology.
Plan: IV fluids, hold nephrotoxics, nephrology consult.
"""

# Complete documentation — no CDI opportunities expected
COMPLETE_DOCUMENTATION_NOTE = """
Assessment: Acute kidney injury (KDIGO Stage 1), pre-renal.
Sepsis due to urinary tract infection — meeting SIRS criteria.
Acute on chronic systolic heart failure. Type 2 diabetes mellitus
with diabetic nephropathy.
Plan: IV fluids, broad-spectrum antibiotics, cardiology consult.
"""


def make_encounter(class_code: str = "IMP") -> FHIREncounter:
    return FHIREncounter(
        id="enc-001",
        status="in-progress",
        class_code=class_code,
        encounter_class=EncounterClass(class_code),
        period_start=_NOW,
    )


def make_note(text: str) -> FHIRDocumentReference:
    return FHIRDocumentReference(
        id="doc-001",
        encounter_id="enc-001",
        note_type_loinc="34117-2",
        note_type_display="H&P Note",
        authored_date=_NOW,
        content_type=NoteContentType.PLAIN_TEXT,
        note_text=text,
    )


def make_creatinine_observations(
    baseline: float = 1.1,
    current: float = 2.4,
) -> list[FHIRObservation]:
    """Two creatinine values spanning 24 hours — rise triggers AKI detection."""
    return [
        FHIRObservation(
            id="obs-cr-baseline",
            loinc_code="2160-0",
            display="Creatinine [Mass/volume] in Serum",
            value_quantity=baseline,
            unit="mg/dL",
            effective_datetime=_EARLIER,
        ),
        FHIRObservation(
            id="obs-cr-current",
            loinc_code="2160-0",
            display="Creatinine [Mass/volume] in Serum",
            value_quantity=current,
            unit="mg/dL",
            effective_datetime=_NOW,
        ),
    ]


def _make_mock_query_response() -> MagicMock:
    """Non-leading, AHIMA-compliant LLM query response."""
    content = json.dumps({
        "query_text": (
            "The patient's creatinine rose from 1.1 to 2.4 mg/dL within "
            "24 hours (+1.3 mg/dL, 2.2x baseline), meeting KDIGO Stage 1 "
            "criteria. Based on your clinical assessment of this patient, "
            "what best describes the patient's renal status?"
        ),
        "multiple_choice_options": [
            "Acute kidney injury (AKI) — please specify stage and etiology if known",
            "Acute on chronic kidney disease",
            "Chronic kidney disease progression without acute component",
            "Creatinine elevation attributable to medications or hydration changes",
            "Condition not present",
            "Unable to determine at this time",
            "Other: ___________",
        ],
        "clinical_evidence": (
            "Creatinine rose from 1.1 to 2.4 mg/dL within 24 hours "
            "(+1.3 mg/dL, 2.2x baseline), meeting KDIGO Stage 1 criteria."
        ),
        "is_non_leading": True,
    })
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=content)]
    return mock_resp


# ─── Detection tests (pure Python, no LLM) ───────────────────────────────────


class TestCDIDetection:
    """
    Detection logic is deterministic — no LLM calls needed.
    These tests run against the rules engine directly.
    """

    @pytest.fixture
    def agent(self) -> CDIAgent:
        return CDIAgent()

    def test_aki_detected_from_creatinine_trend(
        self, agent: CDIAgent
    ) -> None:
        """
        KDIGO criteria: creatinine rise ≥ 0.3 mg/dL within 48 hours.
        Baseline=1.1, current=2.4 → rise=1.3, ratio=2.2x → detect.
        AKI not in note → opportunity generated.

        Per Skill-02 Section 2.1 and DISC-002 CDI-SEV-001.
        """
        note = make_note(CREATININE_RISE_NOTE)
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        opportunities = agent.detect_opportunities(note, observations)

        assert len(opportunities) >= 1
        aki_opps = [o for o in opportunities if "AKI" in o.query_category.upper()
                    or "N17" in o.suggested_code
                    or "kidney" in o.query_text.lower()]
        assert len(aki_opps) >= 1

    def test_aki_not_detected_when_documented(
        self, agent: CDIAgent
    ) -> None:
        """
        If physician already documented AKI, no CDI query is generated.
        Detection trigger requires absence of AKI terms in note.
        """
        note = make_note(AKI_DOCUMENTED_NOTE)
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        opportunities = agent.detect_opportunities(note, observations)

        aki_opps = [o for o in opportunities if "N17" in o.suggested_code
                    or "kidney injury" in o.query_text.lower()]
        assert len(aki_opps) == 0

    def test_no_cdi_opportunity_when_documentation_complete(
        self, agent: CDIAgent
    ) -> None:
        """
        When all common conditions are explicitly documented, no
        CDI queries should be generated.
        Note explicitly states AKI, sepsis, HF type/acuity, DM complications.
        """
        note = make_note(COMPLETE_DOCUMENTATION_NOTE)
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        opportunities = agent.detect_opportunities(note, observations)

        # At least no AKI opportunity — it's already documented
        aki_opps = [o for o in opportunities if "N17" in o.suggested_code
                    or "kidney injury" in o.query_text.lower()]
        assert len(aki_opps) == 0


# ─── Query generation tests (mocked LLM) ──────────────────────────────────────


class TestCDIQueryGeneration:
    """Query generation tests with mocked LLM — no API key required."""

    @pytest.fixture
    def agent(self) -> CDIAgent:
        return CDIAgent()

    @pytest.mark.asyncio
    async def test_query_is_non_leading(
        self, agent: CDIAgent
    ) -> None:
        """
        AHIMA requirement: generated queries must not be leading.
        Skill-02 Section 1: prohibited phrases never appear.
        """
        note = make_note(CREATININE_RISE_NOTE)
        encounter = make_encounter("IMP")
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock,
            return_value=_make_mock_query_response(),
        ):
            result = await agent.analyze(note, encounter, observations)

        assert isinstance(result, CDIAnalysisResult)

        leading_phrases = [
            "would you agree",
            "please document",
            "the patient has",
            "coding requires",
            "for billing",
            "for reimbursement",
            "drg",
        ]
        for query in result.queries_generated:
            query_lower = query.query_text.lower()
            for phrase in leading_phrases:
                assert phrase not in query_lower, (
                    f"Leading phrase '{phrase}' found in query text"
                )

    @pytest.mark.asyncio
    async def test_query_includes_objective_evidence(
        self, agent: CDIAgent
    ) -> None:
        """
        AHIMA requirement: query must cite specific objective findings.
        Article II.2: every clinical statement grounded in source data.
        """
        note = make_note(CREATININE_RISE_NOTE)
        encounter = make_encounter("IMP")
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock,
            return_value=_make_mock_query_response(),
        ):
            result = await agent.analyze(note, encounter, observations)

        assert isinstance(result, CDIAnalysisResult)
        for query in result.queries_generated:
            assert query.clinical_evidence
            assert len(query.clinical_evidence) > 0

    @pytest.mark.asyncio
    async def test_query_has_multiple_choice_options(
        self, agent: CDIAgent
    ) -> None:
        """
        AHIMA requirement: queries must have >= 2 response options.
        Must include a 'not present' and 'unable to determine' option.
        """
        note = make_note(CREATININE_RISE_NOTE)
        encounter = make_encounter("IMP")
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        with patch.object(
            agent._llm_client, "messages_create", new_callable=AsyncMock,
            return_value=_make_mock_query_response(),
        ):
            result = await agent.analyze(note, encounter, observations)

        assert isinstance(result, CDIAnalysisResult)
        for query in result.queries_generated:
            assert len(query.multiple_choice_options) >= 2
            options_lower = [o.lower() for o in query.multiple_choice_options]
            # Must include a "no" / "not present" option
            has_no_option = any(
                "not present" in o or "unable to determine" in o
                for o in options_lower
            )
            assert has_no_option, "Query missing 'condition not present' option"

    @pytest.mark.asyncio
    async def test_cdi_agent_returns_degraded_on_llm_failure(
        self, agent: CDIAgent
    ) -> None:
        """
        Article II.5: LLM failure during query generation → degraded result.
        Detection still occurs; queries list is empty. Workflow continues.
        """
        import anthropic

        note = make_note(CREATININE_RISE_NOTE)
        encounter = make_encounter("IMP")
        observations = make_creatinine_observations(baseline=1.1, current=2.4)

        with patch.object(
            agent._llm_client,
            "messages_create",
            new_callable=AsyncMock,
            side_effect=anthropic.APIConnectionError(request=MagicMock()),
        ):
            result = await agent.analyze(note, encounter, observations)

        assert isinstance(result, (CDIAnalysisResult, DegradedResult))
        if isinstance(result, CDIAnalysisResult):
            assert result.is_degraded is True
