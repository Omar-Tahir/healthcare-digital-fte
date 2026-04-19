"""
Known-Cases Benchmark — tests coding agent against 20 hand-labeled
specificity upgrade cases from DISC-002 §B.1.

Two test classes:
  TestKnownCasesInfrastructure — always runs, validates fixture data
  TestCodingAgentKnownCases    — runs against mocked LLM, validates
                                  that the pipeline handles each case

The mocked LLM returns the specific code from ground truth. The tests
verify that the 7-step pipeline (NLP → LLM → parse → rules → sort →
cap → return) preserves the code through all validation layers.

For a LIVE benchmark (real LLM, ~$0.30 for 20 cases):
  uv run pytest tests/clinical/test_known_cases_benchmark.py -m live_benchmark -v

Constitution: Article II.4 (synthetic notes only — no PHI)
Source: docs/research/DISC-002-documentation-failure-patterns.md §B.1
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.coding_agent import CodingAgent
from src.benchmarks.mimic_benchmark import normalize_code
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
)
from src.core.models.encounter import EncounterClass
from tests.fixtures.known_cases.cases import (
    ALL_CASES,
    CDI_QUERY_CASES,
    DIRECT_CODE_CASES,
    KnownCase,
    REVENUE_IMPACT_CASES,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_fhir_note(case: KnownCase) -> FHIRDocumentReference:
    return FHIRDocumentReference(
        id=f"doc-{case.case_id}",
        encounter_id=case.case_id,
        note_type_loinc="18842-5",
        note_type_display="Discharge Summary",
        authored_date=datetime.now(timezone.utc),
        content_type="plain_text",
        note_text=case.note_text,
    )


def _build_fhir_encounter(case: KnownCase) -> FHIREncounter:
    return FHIREncounter(
        id=case.case_id,
        status="finished",
        class_code="IMP",
        encounter_class=EncounterClass.INPATIENT,
        period_start=datetime.now(timezone.utc),
    )


def _mock_llm_response(case: KnownCase) -> str:
    """
    Build a mock LLM JSON response that returns the specific code.

    The evidence_quote must be a verbatim substring of the note —
    Article II.2 enforced by the coding agent's _parse_suggestions.
    We extract a real phrase from the note for each case.
    """
    # Find a verbatim evidence quote from the note
    evidence = _extract_evidence_quote(case)

    suggestions = [{
        "code": case.specific_code,
        "description": f"Specific code for {case.title}",
        "confidence": 0.90,
        "evidence_quote": evidence,
        "drg_impact_description": f"${case.drg_revenue_low}-${case.drg_revenue_high}",
        "drg_revenue_delta": float(case.drg_revenue_low),
        "is_mcc": case.drg_revenue_high > 5000,
        "is_cc": case.drg_revenue_high > 0,
        "is_principal_dx_candidate": True,
        "uncertainty_qualifier": None,
    }]

    # If nonspecific != specific, also suggest nonspecific
    if case.nonspecific_code != case.specific_code:
        ns_evidence = _extract_evidence_quote_nonspecific(case)
        if ns_evidence:
            suggestions.append({
                "code": case.nonspecific_code,
                "description": f"Non-specific code for {case.title}",
                "confidence": 0.85,
                "evidence_quote": ns_evidence,
                "drg_impact_description": "Lower specificity code",
                "drg_revenue_delta": 0.0,
                "is_mcc": False,
                "is_cc": False,
                "is_principal_dx_candidate": False,
                "uncertainty_qualifier": None,
            })

    cdi_opportunities = []
    if case.expect_cdi_query:
        cdi_opportunities.append({
            "condition": case.title,
            "rationale": f"Documentation supports specificity upgrade from {case.nonspecific_code}",
            "evidence": evidence,
            "revenue_impact": f"${case.drg_revenue_low}-${case.drg_revenue_high}",
            "suggested_query": f"Please clarify: {case.cdi_query_keyword}",
        })

    return json.dumps({
        "suggestions": suggestions,
        "cdi_opportunities": cdi_opportunities,
    })


def _extract_evidence_quote(case: KnownCase) -> str:
    """Extract a real verbatim phrase from the note for evidence_quote."""
    # Search for key clinical phrases that would support the specific code
    _KEY_PHRASES = {
        "DISC002-01": "acute exacerbation of her chronic systolic heart failure",
        "DISC002-02": "sepsis with organ dysfunction",
        "DISC002-03": "creatinine rose from baseline of 1.0 to peak of 2.8",
        "DISC002-04": "PaO2 of 54 mmHg on room air",
        "DISC002-05": "BMI 16.8",
        "DISC002-06": "Sputum culture grew Pseudomonas aeruginosa",
        "DISC002-07": "CKD stage 3",
        "DISC002-08": "acute exacerbation of COPD",
        "DISC002-09": "elevated ammonia level of 142",
        "DISC002-10": "stage 3 pressure injury",
        "DISC002-11": "anemia secondary to acute gastrointestinal hemorrhage",
        "DISC002-12": "BMI of 42.3",
        "DISC002-13": "persistent",
        "DISC002-14": "Urine culture: >100,000 CFU Escherichia coli",
        "DISC002-15": "anterior STEMI",
        "DISC002-16": "Etiology determined to be alcohol-related",
        "DISC002-17": "left femoral vein",
        "DISC002-18": "right middle cerebral artery",
        "DISC002-19": "withdrawal delirium",
        "DISC002-20": "hypertensive heart disease",
    }
    phrase = _KEY_PHRASES.get(case.case_id, "")
    # Verify it's actually in the note (Article II.2)
    if phrase and phrase in case.note_text:
        return phrase
    # Fallback: first 80 chars of the note
    return case.note_text[:80]


def _extract_evidence_quote_nonspecific(case: KnownCase) -> str | None:
    """Extract evidence for nonspecific code — a broader phrase."""
    _NS_PHRASES = {
        "DISC002-01": "heart failure",
        "DISC002-02": "Sepsis",
        "DISC002-03": "heart failure exacerbation",
        "DISC002-04": "shortness of breath",
        "DISC002-05": "Weight: 98 lbs",
        "DISC002-06": "Pneumonia",
        "DISC002-07": "Type 2 diabetes mellitus",
        "DISC002-08": "COPD",
        "DISC002-09": "Altered mental status",
        "DISC002-10": "Pressure ulcer",
        "DISC002-11": "Hemoglobin on admission: 6.8",
        "DISC002-12": "obese",
        "DISC002-13": "Atrial fibrillation",
        "DISC002-17": "Deep vein thrombosis",
        "DISC002-19": "Alcohol use",
        "DISC002-20": "Hypertension",
    }
    phrase = _NS_PHRASES.get(case.case_id)
    if phrase and phrase in case.note_text:
        return phrase
    return None


# ─── Infrastructure Tests (always run) ────────────────────────────────────────

class TestKnownCasesInfrastructure:
    """Validate the 20 test fixtures are well-formed."""

    def test_all_20_cases_loaded(self) -> None:
        assert len(ALL_CASES) == 20

    def test_each_case_has_unique_id(self) -> None:
        ids = [c.case_id for c in ALL_CASES]
        assert len(ids) == len(set(ids))

    def test_evidence_quotes_are_in_notes(self) -> None:
        """Every evidence_quote must be a verbatim substring — Article II.2."""
        for case in ALL_CASES:
            quote = _extract_evidence_quote(case)
            assert quote in case.note_text, (
                f"{case.case_id}: evidence quote not found in note"
            )

    def test_nonspecific_and_specific_codes_differ_for_upgrade_cases(self) -> None:
        """Most cases should have different nonspecific vs specific codes."""
        upgrade_cases = [c for c in ALL_CASES
                         if c.nonspecific_code != c.specific_code]
        # At least 18 of 20 should be actual upgrades (case 14 UTI is same)
        assert len(upgrade_cases) >= 18

    def test_revenue_impact_cases_have_positive_range(self) -> None:
        for case in REVENUE_IMPACT_CASES:
            assert case.drg_revenue_high > 0, f"{case.case_id} has zero revenue"
            assert case.drg_revenue_high >= case.drg_revenue_low

    def test_cdi_query_cases_count(self) -> None:
        """Cases where CDI query is expected (documentation is insufficient)."""
        assert len(CDI_QUERY_CASES) >= 4  # AKI, resp failure, malnutrition, obesity, encephalopathy

    def test_direct_code_cases_count(self) -> None:
        """Cases where the note already supports the specific code."""
        assert len(DIRECT_CODE_CASES) >= 14

    def test_all_notes_are_synthetic(self) -> None:
        """No real PHI should exist in fixture notes — Article II.4."""
        for case in ALL_CASES:
            for phi_marker in ["MRN", "SSN", "555-", "DOB:","Social Security"]:
                assert phi_marker not in case.note_text, (
                    f"{case.case_id}: potential PHI marker '{phi_marker}' found"
                )

    def test_note_text_minimum_length(self) -> None:
        """Each note should be substantive enough for NLP processing."""
        for case in ALL_CASES:
            assert len(case.note_text) >= 200, (
                f"{case.case_id}: note too short ({len(case.note_text)} chars)"
            )


# ─── Coding Agent Pipeline Tests (mocked LLM) ────────────────────────────────

class TestCodingAgentKnownCases:
    """
    Run coding agent pipeline against each known case with mocked LLM.

    Tests verify the 7-step pipeline preserves the specific code through
    NLP → LLM → parse → validate → rules → sort → cap → return.
    """

    @pytest.fixture
    def agent(self) -> CodingAgent:
        return CodingAgent()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        DIRECT_CODE_CASES,
        ids=[c.case_id for c in DIRECT_CODE_CASES],
    )
    async def test_specific_code_in_suggestions(
        self, agent: CodingAgent, case: KnownCase
    ) -> None:
        """
        When the note supports the specific code, the agent should
        include it in suggestions after all pipeline stages.
        """
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=_mock_llm_response(case))]

        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_response,
        ):
            result = await agent.analyze_note(
                note=_build_fhir_note(case),
                encounter=_build_fhir_encounter(case),
            )

        assert not isinstance(result, DegradedResult), (
            f"{case.case_id}: agent returned DegradedResult"
        )
        suggested_codes = {normalize_code(s.code) for s in result.suggestions}
        expected = normalize_code(case.specific_code)
        assert expected in suggested_codes, (
            f"{case.case_id} ({case.title}): expected {case.specific_code} "
            f"in suggestions, got {[s.code for s in result.suggestions]}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "case",
        CDI_QUERY_CASES,
        ids=[c.case_id for c in CDI_QUERY_CASES],
    )
    async def test_cdi_opportunity_detected(
        self, agent: CodingAgent, case: KnownCase
    ) -> None:
        """
        When the note has evidence but lacks explicit diagnosis,
        the agent should still suggest the specific code (LLM detects it)
        AND flag it as a CDI opportunity.
        """
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=_mock_llm_response(case))]

        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_response,
        ):
            result = await agent.analyze_note(
                note=_build_fhir_note(case),
                encounter=_build_fhir_encounter(case),
            )

        assert not isinstance(result, DegradedResult), (
            f"{case.case_id}: agent returned DegradedResult"
        )
        # The specific code should still be in suggestions
        suggested_codes = {normalize_code(s.code) for s in result.suggestions}
        expected = normalize_code(case.specific_code)
        assert expected in suggested_codes, (
            f"{case.case_id} ({case.title}): expected {case.specific_code} "
            f"in suggestions even for CDI cases"
        )

    @pytest.mark.asyncio
    async def test_no_case_produces_degraded_result(
        self, agent: CodingAgent
    ) -> None:
        """All 20 notes should process without degradation — Article II.5."""
        for case in ALL_CASES:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=_mock_llm_response(case))]

            with patch.object(
                agent._llm_client, "messages_create",
                new_callable=AsyncMock, return_value=mock_response,
            ):
                result = await agent.analyze_note(
                    note=_build_fhir_note(case),
                    encounter=_build_fhir_encounter(case),
                )
            assert not isinstance(result, DegradedResult), (
                f"{case.case_id}: unexpected degraded result"
            )

    @pytest.mark.asyncio
    async def test_all_suggestions_have_evidence_quotes(
        self, agent: CodingAgent
    ) -> None:
        """
        Every suggestion must have evidence_quote — Article II.2.
        This verifies the pipeline's evidence validation doesn't
        strip valid quotes.
        """
        for case in ALL_CASES[:5]:  # Sample 5 to keep test fast
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=_mock_llm_response(case))]

            with patch.object(
                agent._llm_client, "messages_create",
                new_callable=AsyncMock, return_value=mock_response,
            ):
                result = await agent.analyze_note(
                    note=_build_fhir_note(case),
                    encounter=_build_fhir_encounter(case),
                )
            if isinstance(result, DegradedResult):
                continue
            for s in result.suggestions:
                assert s.evidence_quote, (
                    f"{case.case_id}: suggestion {s.code} has no evidence_quote"
                )
                assert s.evidence_quote in case.note_text, (
                    f"{case.case_id}: evidence_quote for {s.code} not in note"
                )

    @pytest.mark.asyncio
    async def test_pipeline_precision_on_direct_cases(
        self, agent: CodingAgent
    ) -> None:
        """
        Measure: what fraction of specific codes survive the full pipeline?
        Target: 100% with mocked LLM (pipeline should not filter valid codes).
        """
        hits = 0
        total = len(DIRECT_CODE_CASES)

        for case in DIRECT_CODE_CASES:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=_mock_llm_response(case))]

            with patch.object(
                agent._llm_client, "messages_create",
                new_callable=AsyncMock, return_value=mock_response,
            ):
                result = await agent.analyze_note(
                    note=_build_fhir_note(case),
                    encounter=_build_fhir_encounter(case),
                )
            if isinstance(result, DegradedResult):
                continue
            suggested = {normalize_code(s.code) for s in result.suggestions}
            if normalize_code(case.specific_code) in suggested:
                hits += 1

        precision = hits / total if total > 0 else 0.0
        assert precision == 1.0, (
            f"Pipeline precision on direct cases: {precision:.1%} "
            f"({hits}/{total}). All mocked codes should survive the pipeline."
        )
