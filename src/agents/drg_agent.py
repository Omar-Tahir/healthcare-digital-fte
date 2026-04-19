"""
DRG Agent — generates CFO-readable revenue impact narratives.

Takes DRGImpact data (pre-calculated by DRGGrouper) and calls Claude
with PROMPT-003 to produce a plain-English executive summary.

The LLM FORMATS revenue data — it does NOT calculate it. Dollar amounts
come from the DRGGrouper. This prevents arithmetic hallucination.

Constitution: II.1 (narrative is a suggestion, not a claim),
              II.4 (no PHI in logs — only codes and DRG numbers),
              II.5 (DegradedResult on any failure — never raises),
              II.6 (compliance framing — never upcoding language),
              IV.1 (revenue north star — narrative serves CFO)
Spec: specs/04-prompt-engineering-architecture.md §2.3
PHR:  docs/phr/PHR-003-drg-analysis.md
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic import BaseModel

from src.core.llm.client import create_llm_client, default_model, strip_markdown_fences
from src.core.models.drg import DRGImpact
from src.core.models.fhir import DegradedResult
from src.prompts.drg_analysis import DRG_ANALYSIS_V1_0

log = structlog.get_logger()

MAX_TOKENS = 1024


class DRGNarrative(BaseModel):
    """Plain-English DRG impact narrative for CFO/HIM Director."""

    executive_summary: str
    current_drg: str
    proposed_drg: str
    revenue_impact: str        # formatted: "$5,987.00"
    compliance_note: str
    requires_compliance_review: bool = False


class _AsyncLLMClient:
    """Provider-agnostic LLM wrapper (ADR-014). Thin wrapper for testable LLM calls."""

    def __init__(self) -> None:
        self._provider = create_llm_client()

    async def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
    ) -> Any:
        return await self._provider.messages_create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )


class DRGAgent:
    """
    Generates revenue impact narratives from DRG data.

    Never raises to caller — returns DegradedResult on any failure.
    """

    def __init__(self) -> None:
        self._llm_client = _AsyncLLMClient()

    async def generate_narrative(
        self,
        drg_impact: DRGImpact,
        principal_dx: str,
        proposed_code: str,
        proposed_code_description: str,
    ) -> DRGNarrative | DegradedResult:
        """
        Generate a CFO-readable narrative from DRG impact data.

        Returns DRGNarrative on success, DegradedResult on any failure.
        """
        try:
            return await self._call_llm(
                drg_impact, principal_dx,
                proposed_code, proposed_code_description,
            )
        except Exception as e:
            log.warning(
                "drg_agent_failed",
                error_type=type(e).__name__,
                current_drg=drg_impact.current_drg,
                proposed_drg=drg_impact.proposed_drg,
            )
            return DegradedResult(
                error_code="DRG_AGENT_FAILED",
                error_message=f"Narrative generation failed: {type(e).__name__}",
            )

    async def _call_llm(
        self,
        impact: DRGImpact,
        principal_dx: str,
        proposed_code: str,
        proposed_code_description: str,
    ) -> DRGNarrative:
        """Format prompt, call Claude, parse response."""
        prompt = DRG_ANALYSIS_V1_0.format(
            principal_dx=principal_dx,
            proposed_code=proposed_code,
            proposed_code_description=proposed_code_description,
            current_drg=impact.current_drg,
            current_drg_weight=impact.current_drg_weight,
            proposed_drg=impact.proposed_drg,
            proposed_drg_weight=impact.proposed_drg_weight,
            revenue_difference=impact.revenue_difference,
        )

        response = await self._llm_client.messages_create(
            model=default_model(),
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = strip_markdown_fences(response.content[0].text)
        parsed = json.loads(raw_text)

        log.info(
            "drg_narrative_generated",
            current_drg=impact.current_drg,
            proposed_drg=impact.proposed_drg,
            revenue_difference=round(impact.revenue_difference, 2),
        )

        return DRGNarrative(
            executive_summary=parsed["executive_summary"],
            current_drg=parsed["current_drg"],
            proposed_drg=parsed["proposed_drg"],
            revenue_impact=parsed["revenue_impact"],
            compliance_note=parsed["compliance_note"],
            requires_compliance_review=impact.requires_compliance_review,
        )
