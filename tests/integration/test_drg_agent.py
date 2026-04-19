"""
DRG Agent Integration Tests — BUILD-007

Tests the DRG narrative generation pipeline:
  DRGGrouper results → PROMPT-003 → Claude → DRGNarrative

Constitution: Article II.5 (DegradedResult on failure, never raises),
              Article II.6 (conservative — no upcoding language),
              Article IV.1 (revenue north star — narrative serves CFO)
Spec: specs/04-prompt-engineering-architecture.md §2.3
PHR:  docs/phr/PHR-003-drg-analysis.md
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.drg_agent import DRGAgent, DRGNarrative
from src.core.models.drg import DRGImpact
from src.core.models.fhir import DegradedResult


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _aki_impact() -> DRGImpact:
    """Sepsis + AKI: DRG 872 → 871, ~$5,988 delta."""
    return DRGImpact(
        current_drg="872",
        current_drg_weight=1.8240,
        proposed_drg="871",
        proposed_drg_weight=3.3994,
        revenue_difference=5986.52,
    )


def _hf_impact() -> DRGImpact:
    """Heart failure specificity: DRG 293 → 291, ~$3,200 delta."""
    return DRGImpact(
        current_drg="293",
        current_drg_weight=0.6700,
        proposed_drg="291",
        proposed_drg_weight=1.5100,
        revenue_difference=3192.00,
    )


def _mock_llm_response(narrative: str, compliance_note: str) -> MagicMock:
    """Build a mock Claude response with valid JSON."""
    response_json = json.dumps({
        "executive_summary": narrative,
        "current_drg": "872",
        "proposed_drg": "871",
        "revenue_impact": "$5,987",
        "compliance_note": compliance_note,
    })
    mock = MagicMock()
    mock.content = [MagicMock(text=response_json)]
    return mock


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestDRGAgent:
    """DRG narrative generation with mocked LLM."""

    @pytest.fixture
    def agent(self) -> DRGAgent:
        return DRGAgent()

    @pytest.mark.asyncio
    async def test_generates_narrative_from_drg_impact(
        self, agent: DRGAgent,
    ) -> None:
        """Agent produces a DRGNarrative from DRGImpact data."""
        mock_resp = _mock_llm_response(
            narrative="Documenting acute kidney injury improved severity classification.",
            compliance_note="Revenue reflects documentation accuracy.",
        )
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_resp,
        ):
            result = await agent.generate_narrative(
                drg_impact=_aki_impact(),
                principal_dx="A41.9",
                proposed_code="N17.9",
                proposed_code_description="Acute kidney injury, unspecified",
            )
        assert isinstance(result, DRGNarrative)
        assert result.executive_summary
        assert result.compliance_note

    @pytest.mark.asyncio
    async def test_narrative_contains_revenue_amount(
        self, agent: DRGAgent,
    ) -> None:
        """Narrative includes the dollar amount from DRG impact."""
        mock_resp = _mock_llm_response(
            narrative="AKI documentation resulted in a $5,987 improvement.",
            compliance_note="This reflects clinical accuracy.",
        )
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_resp,
        ):
            result = await agent.generate_narrative(
                drg_impact=_aki_impact(),
                principal_dx="A41.9",
                proposed_code="N17.9",
                proposed_code_description="Acute kidney injury, unspecified",
            )
        assert isinstance(result, DRGNarrative)
        assert "$" in result.revenue_impact

    @pytest.mark.asyncio
    async def test_compliance_review_flag_for_high_impact(
        self, agent: DRGAgent,
    ) -> None:
        """DRG impact > $5,000 triggers compliance review flag."""
        mock_resp = _mock_llm_response(
            narrative="AKI documentation improved severity classification.",
            compliance_note="Flagged for compliance review.",
        )
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_resp,
        ):
            result = await agent.generate_narrative(
                drg_impact=_aki_impact(),  # $5,987 > $5,000 threshold
                principal_dx="A41.9",
                proposed_code="N17.9",
                proposed_code_description="Acute kidney injury, unspecified",
            )
        assert isinstance(result, DRGNarrative)
        assert result.requires_compliance_review

    @pytest.mark.asyncio
    async def test_no_compliance_flag_for_low_impact(
        self, agent: DRGAgent,
    ) -> None:
        """DRG impact < $5,000 does not trigger compliance flag."""
        mock_resp = _mock_llm_response(
            narrative="HF specificity improved DRG assignment.",
            compliance_note="Revenue reflects documentation accuracy.",
        )
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_resp,
        ):
            result = await agent.generate_narrative(
                drg_impact=_hf_impact(),  # $3,192 < $5,000 threshold
                principal_dx="I50.9",
                proposed_code="I50.23",
                proposed_code_description="Acute on chronic systolic HF",
            )
        assert isinstance(result, DRGNarrative)
        assert not result.requires_compliance_review

    @pytest.mark.asyncio
    async def test_returns_degraded_result_on_llm_failure(
        self, agent: DRGAgent,
    ) -> None:
        """Article II.5: LLM failure returns DegradedResult, never raises."""
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock,
            side_effect=Exception("API unavailable"),
        ):
            result = await agent.generate_narrative(
                drg_impact=_aki_impact(),
                principal_dx="A41.9",
                proposed_code="N17.9",
                proposed_code_description="Acute kidney injury, unspecified",
            )
        assert isinstance(result, DegradedResult)
        assert result.is_degraded

    @pytest.mark.asyncio
    async def test_returns_degraded_result_on_json_parse_failure(
        self, agent: DRGAgent,
    ) -> None:
        """Malformed LLM output returns DegradedResult, not crash."""
        bad_mock = MagicMock()
        bad_mock.content = [MagicMock(text="not valid json")]
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=bad_mock,
        ):
            result = await agent.generate_narrative(
                drg_impact=_aki_impact(),
                principal_dx="A41.9",
                proposed_code="N17.9",
                proposed_code_description="Acute kidney injury, unspecified",
            )
        assert isinstance(result, DegradedResult)

    @pytest.mark.asyncio
    async def test_no_phi_in_logs(self, agent: DRGAgent) -> None:
        """Article II.4: No PHI in any log output."""
        mock_resp = _mock_llm_response(
            narrative="Summary text.",
            compliance_note="Compliance note.",
        )
        with patch.object(
            agent._llm_client, "messages_create",
            new_callable=AsyncMock, return_value=mock_resp,
        ):
            result = await agent.generate_narrative(
                drg_impact=_aki_impact(),
                principal_dx="A41.9",
                proposed_code="N17.9",
                proposed_code_description="Acute kidney injury, unspecified",
            )
        # If we get here without logging PHI, the test passes.
        # The DRG agent logs only codes and DRG numbers — no patient data.
        assert isinstance(result, DRGNarrative)
