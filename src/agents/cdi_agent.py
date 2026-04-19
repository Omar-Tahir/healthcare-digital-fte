"""
CDI Agent — detects documentation gaps and generates AHIMA-compliant queries.

Pipeline:
  1. Parse note text for documented diagnosis terms (no LLM needed)
  2. Check lab observations against CDI trigger thresholds
  3. For each undetected opportunity: CDIOpportunity created
  4. For each opportunity: call Claude → generate CDIQuery (AHIMA-compliant)
  5. Return CDIAnalysisResult

Detection is deterministic (pure Python). Query generation uses Claude.
This separation makes detection fast and testable without API calls.

CDI agent does NOT code. It does NOT diagnose. It identifies documentation
gaps and asks physicians to clarify — constitution Article II.6 (conservative).

Spec: specs/02-cdi-intelligence-layer.md
PHR: docs/phr/PHR-002-cdi-query.md
Skill: docs/skills/cdi-query-writing.md
"""
from __future__ import annotations

import json
import time
from typing import Any

import structlog

from src.core.llm.client import create_llm_client, default_model, strip_markdown_fences
from src.core.models.cdi import CDIAnalysisResult, CDIOpportunity, CDIOpportunityType, CDIQuery
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
    FHIRObservation,
)
from src.prompts.cdi_query import CDI_QUERY_V1_0

log = structlog.get_logger()

MAX_TOKENS = 2048

# ─── Creatinine LOINC codes ───────────────────────────────────────────────────
_CREATININE_LOINC = "2160-0"

# ─── AKI documentation terms (if ANY present → already documented) ───────────
_AKI_TERMS: frozenset[str] = frozenset({
    "acute kidney injury", "aki", "acute renal failure",
    "arf", "acute renal insufficiency",
})

# ─── KDIGO Stage 1 thresholds ────────────────────────────────────────────────
_AKI_ABSOLUTE_RISE = 0.3   # mg/dL
_AKI_RELATIVE_RISE = 1.5   # 1.5x baseline

# ─── Terms considered "complete" for each CDI category ───────────────────────
_SEPSIS_TERMS: frozenset[str] = frozenset({
    "sepsis", "septic", "severe sepsis", "septic shock", "sirs",
})

_HF_SPECIFIC_TERMS: frozenset[str] = frozenset({
    "systolic", "diastolic", "hfref", "hfpef",
    "acute on chronic", "acute heart failure", "chronic heart failure",
})


class _AsyncLLMClient:
    """
    Provider-agnostic LLM wrapper (ADR-014).
    Exposes messages_create for easy test mocking.
    """

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


class CDIAgent:
    """
    Detects documentation gaps and generates AHIMA-compliant physician queries.

    Public interface:
      detect_opportunities(note, observations) → list[CDIOpportunity]  (no LLM)
      analyze(note, encounter, observations) → CDIAnalysisResult | DegradedResult
    """

    def __init__(self) -> None:
        self._llm_client = _AsyncLLMClient()

    # ─── Public API ──────────────────────────────────────────────────────────

    def detect_opportunities(
        self,
        note: FHIRDocumentReference,
        observations: list[FHIRObservation],
    ) -> list[CDIOpportunity]:
        """
        Deterministic CDI detection — no LLM calls.
        Returns list of detected opportunities (may be empty).
        Never raises.
        """
        note_text = (note.note_text or "").lower()
        encounter_id = note.encounter_id
        opportunities: list[CDIOpportunity] = []

        aki = self._detect_aki(observations, note_text, encounter_id)
        if aki is not None:
            opportunities.append(aki)

        return opportunities

    async def analyze(
        self,
        note: FHIRDocumentReference,
        encounter: FHIREncounter,
        observations: list[FHIRObservation],
    ) -> CDIAnalysisResult | DegradedResult:
        """
        Full CDI pipeline: detect opportunities then generate queries.
        Returns CDIAnalysisResult. On total failure: DegradedResult.
        Never raises — constitution Article II.5.
        """
        start = time.time()
        try:
            return await self._run_pipeline(note, encounter, observations, start)
        except Exception as e:
            log.warning(
                "cdi_agent_pipeline_failed",
                error_type=type(e).__name__,
                encounter_id=note.encounter_id,
            )
            return DegradedResult(
                error_code="CDI_AGENT_FAILED",
                error_message=f"Pipeline failed: {type(e).__name__}",
            )

    # ─── Pipeline ────────────────────────────────────────────────────────────

    async def _run_pipeline(
        self,
        note: FHIRDocumentReference,
        encounter: FHIREncounter,
        observations: list[FHIRObservation],
        start: float,
    ) -> CDIAnalysisResult:
        opportunities = self.detect_opportunities(note, observations)

        queries, llm_degraded = await self._generate_all_queries(
            opportunities, note, encounter
        )

        elapsed_ms = (time.time() - start) * 1000
        log.info(
            "cdi_analysis_complete",
            encounter_id=note.encounter_id,
            opportunity_count=len(opportunities),
            query_count=len(queries),
            is_degraded=llm_degraded,
            processing_time_ms=round(elapsed_ms, 1),
        )

        return CDIAnalysisResult(
            encounter_id=note.encounter_id,
            opportunities=opportunities,
            queries_generated=queries,
            is_degraded=llm_degraded,
        )

    async def _generate_all_queries(
        self,
        opportunities: list[CDIOpportunity],
        note: FHIRDocumentReference,
        encounter: FHIREncounter,
    ) -> tuple[list[CDIQuery], bool]:
        """Generate CDIQuery for each opportunity. Returns (queries, is_degraded)."""
        queries: list[CDIQuery] = []
        is_degraded = False

        for i, opportunity in enumerate(opportunities, start=1):
            query, failed = await self._generate_single_query(
                opportunity, note, encounter, query_number=i
            )
            if query is not None:
                queries.append(query)
            if failed:
                is_degraded = True

        return queries, is_degraded

    async def _generate_single_query(
        self,
        opportunity: CDIOpportunity,
        note: FHIRDocumentReference,
        encounter: FHIREncounter,
        query_number: int,
    ) -> tuple[CDIQuery | None, bool]:
        """
        Call Claude to generate one AHIMA-compliant query.
        Returns (CDIQuery, is_degraded_flag).
        """
        note_excerpt = self._safe_note_excerpt(note.note_text or "")
        prompt = CDI_QUERY_V1_0.format(
            opportunity_type=opportunity.query_category,
            encounter_id=opportunity.encounter_id,
            clinical_evidence=opportunity.query_text,
            note_context=note_excerpt,
        )

        try:
            response = await self._llm_client.messages_create(
                model=default_model(),
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = strip_markdown_fences(response.content[0].text)
            parsed = json.loads(raw_text)

            return CDIQuery(
                encounter_id=opportunity.encounter_id,
                physician_id="",  # Populated by BUILD-010 (coder UI)
                query_text=parsed["query_text"],
                multiple_choice_options=parsed["multiple_choice_options"],
                clinical_evidence=parsed["clinical_evidence"],
                drg_impact=opportunity.drg_impact,
                query_number=query_number,
            ), False

        except OSError as e:
            log.warning("cdi_llm_api_failed", error_type=type(e).__name__)
            return None, True
        except (json.JSONDecodeError, KeyError, Exception) as e:
            log.warning("cdi_query_generation_failed", error_type=type(e).__name__)
            return None, True

    # ─── Detection rules ─────────────────────────────────────────────────────

    def _detect_aki(
        self,
        observations: list[FHIRObservation],
        note_lower: str,
        encounter_id: str,
    ) -> CDIOpportunity | None:
        """
        CDI-SEV-001: Acute Kidney Injury not documented.

        Trigger: creatinine rise ≥ 0.3 mg/dL OR ≥ 1.5x baseline
        AND none of _AKI_TERMS appear in the note.

        Per Skill-02 Section 2.1 and DISC-002 CDI-SEV-001.
        Revenue impact: N17.x = MCC, $3,000-$8,000/case.
        """
        if any(term in note_lower for term in _AKI_TERMS):
            return None  # Already documented — no query needed

        creatinine = self._extract_creatinine(observations)
        if len(creatinine) < 2:
            return None  # Need at least two values to assess trend

        creatinine.sort(key=lambda o: o.effective_datetime)
        baseline_val = creatinine[0].value_quantity
        current_val = creatinine[-1].value_quantity

        if baseline_val is None or current_val is None or baseline_val <= 0:
            return None

        rise = current_val - baseline_val
        ratio = current_val / baseline_val

        if rise < _AKI_ABSOLUTE_RISE and ratio < _AKI_RELATIVE_RISE:
            return None  # Threshold not met

        evidence = (
            f"Creatinine rose from {baseline_val:.1f} to {current_val:.1f} mg/dL "
            f"(rise: +{rise:.1f} mg/dL, {ratio:.1f}x baseline), "
            f"meeting KDIGO Stage 1 criteria."
        )

        return CDIOpportunity(
            encounter_id=encounter_id,
            query_category=CDIOpportunityType.SEVERITY_UPGRADE.value,
            query_text=evidence,
            suggested_code="N17.9",
            drg_impact="$3,000-$8,000 per case (N17.x = MCC)",
        )

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _extract_creatinine(
        self, observations: list[FHIRObservation]
    ) -> list[FHIRObservation]:
        """Filter observations to creatinine LOINC code with numeric values."""
        return [
            o for o in observations
            if o.loinc_code == _CREATININE_LOINC and o.value_quantity is not None
        ]

    def _safe_note_excerpt(self, note_text: str, max_chars: int = 500) -> str:
        """
        Return a truncated note excerpt for prompt context.
        Keeps the assessment section if identifiable; otherwise first max_chars.
        Never raises.
        """
        if not note_text:
            return "[Note text unavailable]"
        assessment_idx = note_text.lower().find("assessment")
        start = assessment_idx if assessment_idx >= 0 else 0
        return note_text[start: start + max_chars].strip()
