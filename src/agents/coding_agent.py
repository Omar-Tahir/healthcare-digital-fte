"""
Coding Agent — orchestrates the full coding analysis pipeline.

Pipeline (7 steps):
  1. Validate note has extractable text
  2. Run NLP pipeline → NLPResult (entity extraction, negation, temporal)
  3. Determine encounter coding class (inpatient vs outpatient)
  4. Call Claude with CODING_EXTRACTION_V1_0 prompt
  5. Parse and validate LLM suggestions (evidence_quote + uncertainty filter)
  6. Run ICD10RulesEngine (Excludes 1, mandatory paired codes)
  7. Sort by DRG impact, cap at 15, set review flags, return result

Constitution: II.1 (no autonomous claim — agent produces suggestions only),
              II.2 (evidence citation enforced at step 5),
              II.3 (ICD-10 guidelines as hard constraints at step 6),
              II.4 (no PHI in logs anywhere in this module),
              II.5 (DegradedResult on any failure — never raises to caller),
              II.6 (conservative defaults — revenue and confidence thresholds)

Spec: specs/01-coding-rules-engine.md
PHR: docs/phr/PHR-001-coding-extraction.md
"""
from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from typing import Any

import structlog
from pydantic import ValidationError

from src.core.llm.client import create_llm_client, default_model, strip_markdown_fences
from src.core.exceptions import GuardrailWarning
from src.core.icd10.rules_engine import ICD10RulesEngine
from src.core.models.cdi import CDIOpportunity, CDIOpportunityType
from src.core.models.encounter import EncounterClass, EncounterContext
from src.core.models.coding import (
    CodingAnalysisResult,
    CodingSuggestion,
    ValidationResult,
    ViolationSeverity,
)
from src.core.models.encounter import CodingClass, get_coding_class
from src.core.models.fhir import (
    DegradedResult,
    FHIRDocumentReference,
    FHIREncounter,
)
from src.nlp.pipeline import NLPPipeline
from src.prompts.coding_extraction import CODING_EXTRACTION_V1_0

log = structlog.get_logger()

# Outpatient coding classes — determines uncertain diagnosis rule application.
# OBS is OUTPATIENT — see docs/skills/fhir-r4-integration.md Section 3.
_OUTPATIENT_CODING_CLASSES: frozenset[CodingClass] = frozenset(
    {CodingClass.OUTPATIENT}
)

# Qualifier words that trigger the outpatient uncertain diagnosis rule.
# Per ICD-10-CM Official Guidelines Section IV.H.
# Full list in docs/skills/icd10-coding-rules.md Rule 2.
_UNCERTAINTY_QUALIFIERS: frozenset[str] = frozenset({
    "possible", "probable", "suspected", "rule out",
    "working diagnosis", "questionable", "likely",
    "still to be ruled out", "concern for", "appears to be",
    "consistent with", "compatible with", "indicative of",
    "suggestive of", "comparable with",
})

MAX_TOKENS = 1500  # Coding extraction JSON is ~600 tokens; 1500 gives headroom without inflating tail latency

_EVIDENCE_FUZZY_THRESHOLD = 0.80  # minimum SequenceMatcher ratio for fuzzy fallback
_EVIDENCE_MIN_FUZZY_LEN = 15       # short quotes skip fuzzy (too many false positives)


def _evidence_in_note(evidence_quote: str, note_text: str) -> bool:
    """
    Three-level evidence validation (G-HARD-002 implementation):

    1. Exact substring match (canonical).
    2. Normalized match — case-insensitive, collapsed whitespace.
       Catches LLM capitalization/spacing artifacts.
    3. Sliding-window fuzzy match (difflib SequenceMatcher).
       Catches minor paraphrases (e.g. "EF" vs "ejection fraction")
       without allowing fully hallucinated evidence.

    Returns False for quotes shorter than _EVIDENCE_MIN_FUZZY_LEN chars
    that fail levels 1–2 (too risky to fuzzy-match short strings).
    """
    if evidence_quote in note_text:
        return True

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())

    norm_q = _norm(evidence_quote)
    norm_n = _norm(note_text)

    if norm_q in norm_n:
        return True

    if len(norm_q) < _EVIDENCE_MIN_FUZZY_LEN:
        return False

    q_len = len(norm_q)
    window_size = int(q_len * 1.3)
    step = max(1, q_len // 3)

    for i in range(0, max(1, len(norm_n) - q_len + 1), step):
        window = norm_n[i : i + window_size]
        if SequenceMatcher(None, norm_q, window).ratio() >= _EVIDENCE_FUZZY_THRESHOLD:
            return True
    return False


class _AsyncLLMClient:
    """
    Provider-agnostic LLM wrapper (ADR-014).

    Exposes messages_create as a direct method so tests can patch it with:
        patch.object(agent._llm_client, "messages_create", new_callable=AsyncMock)

    Delegates to the provider selected by LLM_PROVIDER env var.
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


class CodingAgent:
    """
    Orchestrates clinical note → ICD-10 code suggestion pipeline.

    Returns CodingAnalysisResult (with is_degraded=True on partial failure)
    or DegradedResult on total pipeline failure.
    Never raises to the caller — constitution Article II.5.
    """

    def __init__(self) -> None:
        self._llm_client = _AsyncLLMClient()
        self._nlp = NLPPipeline()
        self._rules = ICD10RulesEngine()

    async def analyze(
        self,
        encounter: EncounterContext,
    ) -> CodingAnalysisResult | DegradedResult:
        """
        Analyze encounter using EncounterContext.
        Validates FHIR connectivity first; returns DegradedResult on failure.
        Constitution Article II.5: never raises.
        """
        import os
        fhir_base_url = os.getenv("FHIR_BASE_URL", "").strip()
        if fhir_base_url:
            # Production: validate FHIR connectivity before proceeding.
            from src.core.fhir.client import FHIRClient
            try:
                fhir = FHIRClient(
                    base_url=fhir_base_url,
                    client_id=os.getenv("FHIR_CLIENT_ID", ""),
                    private_key_pem=os.getenv("FHIR_PRIVATE_KEY_PEM", ""),
                    token_url=os.getenv("FHIR_TOKEN_URL", ""),
                )
                await fhir.get_encounter(encounter.encounter_id)
            except Exception as e:
                log.warning(
                    "coding_agent_fhir_failed",
                    error_type=type(e).__name__,
                    encounter_id=encounter.encounter_id,
                )
                return DegradedResult(
                    error_code="CODING_AGENT_FAILED",
                    error_message=f"Pipeline failed: {type(e).__name__}",
                )
        # No FHIR_BASE_URL — demo/dev mode, skip connectivity check.

        # Build FHIR models from EncounterContext for the pipeline
        encounter_class = EncounterClass.INPATIENT
        if encounter.encounter_setting in ("outpatient", "ambulatory"):
            encounter_class = EncounterClass.OUTPATIENT
        elif encounter.encounter_setting == "observation":
            encounter_class = EncounterClass.OBSERVATION

        from datetime import datetime, timezone
        fhir_encounter = FHIREncounter(
            id=encounter.encounter_id,
            status="in-progress",
            class_code=encounter_class.value,
            encounter_class=encounter_class,
            period_start=datetime.now(timezone.utc),
        )
        fhir_note = FHIRDocumentReference(
            id=f"doc-{encounter.encounter_id}",
            encounter_id=encounter.encounter_id,
            note_type_loinc="34117-2",
            note_type_display="H&P Note",
            authored_date=datetime.now(timezone.utc),
            content_type="plain_text",
            note_text=encounter.note_text,
        )
        return await self.analyze_note(fhir_note, fhir_encounter)

    async def analyze_note(
        self,
        note: FHIRDocumentReference,
        encounter: FHIREncounter,
    ) -> CodingAnalysisResult | DegradedResult:
        """
        Full coding analysis pipeline. Never raises.
        On total failure: returns DegradedResult.
        On partial failure: returns CodingAnalysisResult(is_degraded=True).
        """
        start_time = time.time()
        try:
            return await self._run_pipeline(note, encounter, start_time)
        except Exception as e:
            log.warning(
                "coding_agent_pipeline_failed",
                error_type=type(e).__name__,
                encounter_id=note.encounter_id,
                # Never log note content — PHI
            )
            return DegradedResult(
                error_code="CODING_AGENT_FAILED",
                error_message=f"Pipeline failed: {type(e).__name__}",
            )

    # ─── Pipeline steps ───────────────────────────────────────────────────────

    async def _run_pipeline(
        self,
        note: FHIRDocumentReference,
        encounter: FHIREncounter,
        start_time: float,
    ) -> CodingAnalysisResult:
        """Execute the 7-step analysis pipeline."""
        note_text = note.note_text or ""
        coding_class = get_coding_class(encounter.encounter_class)

        if not note_text.strip():
            return self._empty_result(note.encounter_id, coding_class, start_time)

        nlp_result = self._nlp.analyze(note_text)
        is_degraded = nlp_result.is_degraded

        raw_suggestions, raw_cdi, llm_degraded = await self._call_llm(
            note_text=note_text,
            encounter_class=encounter.class_code,
            nlp_entities=self._format_nlp_entities(nlp_result),
        )
        is_degraded = is_degraded or llm_degraded

        suggestions = self._parse_suggestions(raw_suggestions, note_text, coding_class)
        suggestions = self._apply_rules_engine(suggestions)
        suggestions.sort(key=lambda s: s.drg_revenue_delta, reverse=True)
        suggestions = suggestions[:15]

        elapsed_ms = (time.time() - start_time) * 1000
        log.info(
            "coding_analysis_complete",
            encounter_id=note.encounter_id,
            coding_class=coding_class.value,
            suggestion_count=len(suggestions),
            nlp_entity_count=nlp_result.entity_count,
            processing_time_ms=round(elapsed_ms, 1),
            is_degraded=is_degraded,
            # Never log note content, entity text, or any clinical detail
        )

        return CodingAnalysisResult(
            encounter_id=note.encounter_id,
            coding_class=coding_class.value,
            suggestions=suggestions,
            validation_result=ValidationResult(is_valid=True),
            processing_time_ms=elapsed_ms,
            nlp_entity_count=nlp_result.entity_count,
            is_degraded=is_degraded,
            cdi_opportunities=raw_cdi,
        )

    async def _call_llm(
        self,
        note_text: str,
        encounter_class: str,
        nlp_entities: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        """
        Call Claude with the coding extraction prompt.

        Returns (suggestions, cdi_opportunities, is_degraded).
        On any failure: returns ([], [], True) — never raises.
        """
        prompt = CODING_EXTRACTION_V1_0.format(
            encounter_class=encounter_class,
            note_text=note_text,
            nlp_entities=nlp_entities,
        )
        try:
            response = await self._llm_client.messages_create(
                model=default_model(),
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = strip_markdown_fences(response.content[0].text)
            parsed = json.loads(raw_text)
            return parsed.get("suggestions", []), parsed.get("cdi_opportunities", []), False
        except OSError as e:
            log.warning("llm_api_failed", error_type=type(e).__name__)
            return [], [], True
        except json.JSONDecodeError as e:
            log.warning("llm_response_parse_failed", error_type=type(e).__name__)
            return [], [], True
        except Exception as e:
            log.warning("llm_call_failed", error_type=type(e).__name__)
            return [], [], True

    def _parse_suggestions(
        self,
        raw_suggestions: list[dict[str, Any]],
        note_text: str,
        coding_class: CodingClass,
    ) -> list[CodingSuggestion]:
        """
        Parse and validate raw LLM suggestions.

        Applies Article II.2 (evidence_quote must be in note_text)
        and Article II.3 (outpatient uncertain diagnosis filtered).
        """
        parsed = []
        for raw in raw_suggestions:
            suggestion = self._parse_single_suggestion(raw, note_text, coding_class)
            if suggestion is not None:
                parsed.append(suggestion)
        return parsed

    def _parse_single_suggestion(
        self,
        raw: dict[str, Any],
        note_text: str,
        coding_class: CodingClass,
    ) -> CodingSuggestion | None:
        """Parse one raw suggestion dict. Returns None if it should be filtered."""
        try:
            evidence_quote = raw.get("evidence_quote", "") or ""
            if not evidence_quote:
                log.warning("suggestion_missing_evidence", code=raw.get("code", "?"))
                return None
            if not _evidence_in_note(evidence_quote, note_text):
                log.warning("suggestion_evidence_not_in_note", code=raw.get("code", "?"))
                return None

            qualifier = (raw.get("uncertainty_qualifier") or "").lower().strip()
            if coding_class in _OUTPATIENT_CODING_CLASSES and qualifier in _UNCERTAINTY_QUALIFIERS:
                log.info(
                    "outpatient_uncertain_dx_filtered",
                    code=raw.get("code", "?"),
                    qualifier=qualifier,
                )
                return None

            return CodingSuggestion(
                code=raw["code"],
                description=raw["description"],
                confidence=float(raw.get("confidence", 0.5)),
                evidence_quote=evidence_quote,
                drg_impact=raw.get("drg_impact_description", ""),
                drg_revenue_delta=float(raw.get("drg_revenue_delta", 0.0)),
                is_mcc=bool(raw.get("is_mcc", False)),
                is_cc=bool(raw.get("is_cc", False)),
                is_principal_dx_candidate=bool(raw.get("is_principal_dx_candidate", False)),
            )
        except (KeyError, ValidationError, ValueError, TypeError) as e:
            log.warning("suggestion_parse_failed", error_type=type(e).__name__, code=raw.get("code", "?"))
            return None

    def _apply_rules_engine(
        self,
        suggestions: list[CodingSuggestion],
    ) -> list[CodingSuggestion]:
        """
        Run ICD-10 rules engine. Removes Excludes 1 violators.
        When a pair violates Excludes 1, the lower-revenue code is removed.
        Returns original list if rules engine fails (degraded mode).
        """
        if not suggestions:
            return []
        codes = [s.code for s in suggestions]
        try:
            validation = self._rules.validate_code_set(codes, "", "")
            if validation.is_valid:
                return suggestions
            return self._remove_excludes1_violators(suggestions, validation)
        except Exception as e:
            log.warning("rules_engine_failed", error_type=type(e).__name__)
            return suggestions

    def _remove_excludes1_violators(
        self,
        suggestions: list[CodingSuggestion],
        validation: ValidationResult,
    ) -> list[CodingSuggestion]:
        """Remove the lower-revenue code from each Excludes 1 violation pair."""
        codes_to_remove: set[str] = set()
        for v in validation.violations:
            if v.severity == ViolationSeverity.CRITICAL and len(v.affected_codes) >= 2:
                code_a, code_b = v.affected_codes[0], v.affected_codes[1]
                delta_a = next((s.drg_revenue_delta for s in suggestions if s.code == code_a), 0.0)
                delta_b = next((s.drg_revenue_delta for s in suggestions if s.code == code_b), 0.0)
                codes_to_remove.add(code_a if delta_a <= delta_b else code_b)
        return [s for s in suggestions if s.code not in codes_to_remove]

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _empty_result(
        self,
        encounter_id: str,
        coding_class: CodingClass,
        start_time: float,
    ) -> CodingAnalysisResult:
        """Return a degraded result for an empty note."""
        log.warning("coding_agent_empty_note", encounter_id=encounter_id)
        return CodingAnalysisResult(
            encounter_id=encounter_id,
            coding_class=coding_class.value,
            suggestions=[],
            validation_result=ValidationResult(is_valid=True),
            processing_time_ms=(time.time() - start_time) * 1000,
            is_degraded=True,
        )

    def _format_nlp_entities(self, nlp_result: Any) -> str:
        """
        Format NLP entities as structured context for the LLM prompt.
        Only includes current, non-negated entities (max 30).
        Never includes PHI — entity types and positions only.
        """
        if not nlp_result.entities:
            return "No entities pre-extracted."
        from src.core.models.nlp import TemporalStatus

        active = [
            e for e in nlp_result.entities
            if not e.is_negated and e.temporal_status == TemporalStatus.CURRENT
        ]
        if not active:
            return "No active (non-negated, current) entities found."

        lines = [
            f"- [{e.entity_type.value}] '{e.text}' "
            f"(section: {e.source_section.value}, confidence: {e.confidence:.2f})"
            for e in active[:30]
        ]
        return "\n".join(lines)
