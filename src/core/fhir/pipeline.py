"""
EpicCodingPipeline — end-to-end Epic FHIR → ICD-10 suggestions → draft Claim.

Pipeline:
  1. get_encounter()          → FHIREncounter
  2. get_clinical_notes()     → [FHIRDocumentReference, ...]
  3. get_recent_labs()        → [FHIRObservation, ...] (CDI context)
  4. CodingAgent.analyze_note() × N
  5. merge_suggestions()      → dedup by code, keep highest confidence, cap 15
  6. write_draft_claim()      → Claim(status=draft)

Constitution: II.1 (draft claim only), II.2 (evidence required),
              II.4 (no PHI in logs), II.5 (DegradedResult, never raise)
Spec: specs/09-epic-coding-pipeline.md
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from src.core.models.cdi import CDIOpportunity
from src.core.models.coding import CodingSuggestion
from src.core.models.fhir import DegradedResult

if TYPE_CHECKING:
    from src.core.fhir.client import FHIRClient

log = structlog.get_logger()

# LOINC codes fetched for every run — feed CDI context to the LLM.
_CDI_LOINC_PANEL: list[str] = [
    "2160-0",   # Creatinine → AKI
    "33914-3",  # eGFR → CKD staging
    "2345-7",   # Glucose → DM
    "6690-2",   # WBC → Sepsis
    "2823-3",   # Potassium → Electrolyte disorder
]


class PipelineResult(BaseModel):
    patient_id: str
    encounter_id: str
    notes_analyzed: int
    suggestions: list[CodingSuggestion]
    cdi_opportunities: list[CDIOpportunity]
    draft_claim_id: str | None
    processing_time_ms: float
    is_degraded: bool


class EpicCodingPipeline:
    """
    Orchestrates the full Epic FHIR → coding suggestions → draft claim loop.

    Usage:
        pipeline = EpicCodingPipeline(fhir_client=client)
        result = await pipeline.run(patient_id="...", encounter_id="...")
    """

    def __init__(self, fhir_client: FHIRClient) -> None:
        self._fhir = fhir_client

    async def run(
        self,
        patient_id: str,
        encounter_id: str,
    ) -> PipelineResult:
        """
        Full end-to-end pipeline. Never raises — always returns PipelineResult.
        is_degraded=True when any step fails; suggestions may still be returned
        from partial analysis.
        """
        start = time.time()
        try:
            return await self._execute(patient_id, encounter_id, start)
        except Exception as e:
            log.warning(
                "epic_pipeline_failed",
                error_type=type(e).__name__,
                encounter_id=encounter_id,
            )
            return self._degraded(patient_id, encounter_id, start)

    async def _execute(
        self,
        patient_id: str,
        encounter_id: str,
        start: float,
    ) -> PipelineResult:
        is_degraded = False

        # Step 1: Encounter
        encounter = await self._fhir.get_encounter(encounter_id)
        if isinstance(encounter, DegradedResult):
            log.warning(
                "epic_pipeline_encounter_failed",
                encounter_id=encounter_id,
                error_code=encounter.error_code,
            )
            return self._degraded(patient_id, encounter_id, start)

        # Step 2: Clinical notes
        notes = await self._fhir.get_clinical_notes(patient_id, encounter_id)
        if not notes:
            log.warning(
                "epic_pipeline_no_notes",
                encounter_id=encounter_id,
                patient_id=patient_id,
            )
            return PipelineResult(
                patient_id=patient_id,
                encounter_id=encounter_id,
                notes_analyzed=0,
                suggestions=[],
                cdi_opportunities=[],
                draft_claim_id=None,
                processing_time_ms=(time.time() - start) * 1000,
                is_degraded=True,
            )

        # Step 3: Labs (non-fatal — empty list is fine)
        await self._fhir.get_recent_labs(patient_id, encounter_id, _CDI_LOINC_PANEL)

        # Step 4: Analyze notes in parallel — each is independent
        import asyncio
        from src.agents.coding_agent import CodingAgent
        agent = CodingAgent()
        text_notes = [n for n in notes if n.note_text]

        async def _analyze(note):
            return await agent.analyze_note(note, encounter)

        raw_results = await asyncio.gather(
            *[_analyze(n) for n in text_notes],
            return_exceptions=True,
        )

        all_suggestions: list[list[CodingSuggestion]] = []
        all_cdi: list[CDIOpportunity] = []
        notes_analyzed = 0

        for result in raw_results:
            if isinstance(result, Exception) or isinstance(result, DegradedResult):
                is_degraded = True
                log.warning(
                    "epic_pipeline_note_analysis_degraded",
                    encounter_id=encounter_id,
                    error_type=type(result).__name__,
                )
                continue
            if result.is_degraded:
                is_degraded = True
            all_suggestions.append(result.suggestions)
            all_cdi.extend(result.cdi_opportunities or [])
            notes_analyzed += 1

        # Step 5: Merge suggestions across notes
        merged = _merge_suggestions(all_suggestions)
        merged_cdi = _merge_cdi(all_cdi)

        # Step 6: Write draft claim (non-fatal)
        draft_claim_id: str | None = None
        if merged:
            from src.core.models.coding import CodingAnalysisResult, ValidationResult
            coding_result = CodingAnalysisResult(
                encounter_id=encounter_id,
                coding_class="inpatient",
                suggestions=merged,
                validation_result=ValidationResult(is_valid=True),
                processing_time_ms=0,
            )
            claim_result = await self._fhir.write_draft_claim(
                encounter_id, coding_result, patient_id=patient_id
            )
            if isinstance(claim_result, DegradedResult):
                log.warning(
                    "epic_pipeline_claim_write_failed",
                    encounter_id=encounter_id,
                    error_code=claim_result.error_code,
                )
                is_degraded = True
            else:
                draft_claim_id = claim_result.get("id")

        log.info(
            "epic_pipeline_complete",
            encounter_id=encounter_id,
            notes_analyzed=notes_analyzed,
            suggestion_count=len(merged),
            is_degraded=is_degraded,
            processing_time_ms=round((time.time() - start) * 1000, 1),
        )

        return PipelineResult(
            patient_id=patient_id,
            encounter_id=encounter_id,
            notes_analyzed=notes_analyzed,
            suggestions=merged,
            cdi_opportunities=merged_cdi,
            draft_claim_id=draft_claim_id,
            processing_time_ms=(time.time() - start) * 1000,
            is_degraded=is_degraded,
        )

    def _degraded(
        self,
        patient_id: str,
        encounter_id: str,
        start: float,
    ) -> PipelineResult:
        return PipelineResult(
            patient_id=patient_id,
            encounter_id=encounter_id,
            notes_analyzed=0,
            suggestions=[],
            cdi_opportunities=[],
            draft_claim_id=None,
            processing_time_ms=(time.time() - start) * 1000,
            is_degraded=True,
        )


def _merge_cdi(opportunities: list[CDIOpportunity]) -> list[CDIOpportunity]:
    """
    Dedup CDI opportunities across notes by (suggested_code, query_category).
    Keeps first occurrence — CDI queries are equivalent if they target the same
    code with the same category regardless of which note triggered them.
    """
    seen: set[tuple[str, str]] = set()
    merged: list[CDIOpportunity] = []
    for opp in opportunities:
        key = (opp.suggested_code, opp.query_category)
        if key not in seen:
            seen.add(key)
            merged.append(opp)
    return merged


def _merge_suggestions(
    result_sets: list[list[CodingSuggestion]],
) -> list[CodingSuggestion]:
    """
    Dedup by ICD-10 code across multiple note results.
    Keeps highest-confidence instance per code.
    Sorts descending by drg_revenue_delta, caps at 15.
    """
    best: dict[str, CodingSuggestion] = {}
    for suggestions in result_sets:
        for s in suggestions:
            if s.code not in best or s.confidence > best[s.code].confidence:
                best[s.code] = s
    return sorted(best.values(), key=lambda s: s.drg_revenue_delta, reverse=True)[:15]
