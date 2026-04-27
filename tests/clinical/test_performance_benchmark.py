"""
VALIDATE-005 — End-to-End Performance Benchmark

Validates the <30 second per-chart SLA required before hospital pilot.
Uses 10 synthetic charts from the known-cases fixture (no PHI).

Spec: specs/08-performance-benchmark.md
Constitution: Article II.4 (synthetic notes only, no PHI in logs),
              Article IV.4 (Phase 1 exit criteria)

Run:
    python -m pytest tests/clinical/test_performance_benchmark.py -m performance -v -s
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest
import pytest_asyncio

# Load env before importing src modules that read env at import time
from dotenv import load_dotenv

load_dotenv()

from tests.fixtures.known_cases.cases import ALL_CASES
from src.agents.coding_agent import CodingAgent
from src.core.models.fhir import FHIRDocumentReference, FHIREncounter
from src.core.models.fhir import DegradedResult
from src.core.models.encounter import EncounterClass
from src.nlp.pipeline import NLPPipeline

# ─── Constants ──────────────────────────────────────────────────────────────

# Spec §3: use first 10 cases — representative of real inpatient charts.
BENCHMARK_CASES = ALL_CASES[:10]

# Spec §4: latency targets
PER_CHART_MAX_S = 30.0
MEDIAN_MAX_S = 20.0
NLP_MAX_MS = 500.0


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_fhir_objects(
    case_id: str,
    note_text: str,
) -> tuple[FHIRDocumentReference, FHIREncounter]:
    """Build minimal FHIR objects from a KnownCase for direct analyze_note() calls."""
    enc_id = f"perf-{case_id}"
    note = FHIRDocumentReference(
        id=f"doc-{enc_id}",
        encounter_id=enc_id,
        note_type_loinc="18842-5",  # Discharge summary — primary coding doc
        note_type_display="Discharge Summary",
        authored_date=datetime.now(timezone.utc),
        content_type="plain_text",
        note_text=note_text,
    )
    encounter = FHIREncounter(
        id=enc_id,
        status="finished",
        class_code=EncounterClass.INPATIENT.value,
        encounter_class=EncounterClass.INPATIENT,
        period_start=datetime.now(timezone.utc),
    )
    return note, encounter


def _llm_configured() -> bool:
    """True when at least one LLM provider env var is set."""
    return bool(
        os.getenv("GROQ_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def agent() -> CodingAgent:
    if not _llm_configured():
        pytest.skip("No LLM API key configured — set GROQ_API_KEY to run performance tests")
    return CodingAgent()


# ─── Tests ───────────────────────────────────────────────────────────────────

@pytest.mark.performance
@pytest.mark.asyncio
async def test_per_chart_latency(agent: CodingAgent) -> None:
    """Each of the 10 benchmark charts must complete in < 30 seconds (spec §4)."""
    failures: list[str] = []

    for case in BENCHMARK_CASES:
        note, encounter = _make_fhir_objects(case.case_id, case.note_text)

        start = time.perf_counter()
        result = await agent.analyze_note(note, encounter)
        elapsed_s = time.perf_counter() - start

        # Constitution Article II.4: never log note content or PHI
        status = "PASS" if elapsed_s < PER_CHART_MAX_S else "FAIL"
        degraded = isinstance(result, DegradedResult)
        print(
            f"  {case.case_id:<14} | "
            f"{'degraded' if degraded else 'ok':8} | "
            f"{elapsed_s:5.2f}s | {status}"
        )

        if elapsed_s >= PER_CHART_MAX_S:
            failures.append(
                f"{case.case_id} took {elapsed_s:.1f}s (limit {PER_CHART_MAX_S}s)"
            )

    assert not failures, (
        f"Performance SLA breached on {len(failures)} chart(s):\n"
        + "\n".join(failures)
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_median_latency(agent: CodingAgent) -> None:
    """Median chart time must be < 20s — 30s headroom for production variance (spec §4)."""
    times: list[float] = []

    for case in BENCHMARK_CASES:
        note, encounter = _make_fhir_objects(case.case_id, case.note_text)
        start = time.perf_counter()
        await agent.analyze_note(note, encounter)
        times.append(time.perf_counter() - start)

    times_sorted = sorted(times)
    n = len(times_sorted)
    if n % 2 == 1:
        median_s = times_sorted[n // 2]
    else:
        median_s = (times_sorted[n // 2 - 1] + times_sorted[n // 2]) / 2

    print(
        f"\n  Median: {median_s:.2f}s | "
        f"p95: {times_sorted[int(n * 0.95)]:.2f}s | "
        f"Max: {max(times_sorted):.2f}s"
    )

    assert median_s < MEDIAN_MAX_S, (
        f"Median chart time {median_s:.1f}s exceeds {MEDIAN_MAX_S}s target"
    )


@pytest.mark.performance
def test_nlp_pipeline_latency() -> None:
    """NLP pipeline alone (no LLM call) must run in < 500ms per chart (spec §4)."""
    nlp = NLPPipeline()
    failures: list[str] = []

    for case in BENCHMARK_CASES:
        start = time.perf_counter()
        nlp.analyze(case.note_text)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"  {case.case_id:<14} | NLP: {elapsed_ms:.1f}ms")
        if elapsed_ms >= NLP_MAX_MS:
            failures.append(
                f"{case.case_id} NLP took {elapsed_ms:.0f}ms (limit {NLP_MAX_MS:.0f}ms)"
            )

    assert not failures, (
        f"NLP pipeline too slow on {len(failures)} chart(s):\n"
        + "\n".join(failures)
    )
