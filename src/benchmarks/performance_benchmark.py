"""
VALIDATE-005 — Performance Benchmark Script

Prints a timing table for 10 benchmark charts.
Exit code 0 = PASS, 1 = FAIL.

Run:
    python -m src.benchmarks.performance_benchmark

Spec: specs/08-performance-benchmark.md
Constitution: Article II.4 (synthetic notes only, no PHI)
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


PER_CHART_MAX_S = 30.0
MEDIAN_MAX_S = 20.0
NLP_MAX_MS = 500.0


async def run() -> bool:
    from tests.fixtures.known_cases.cases import ALL_CASES
    from src.agents.coding_agent import CodingAgent
    from src.core.models.fhir import FHIRDocumentReference, FHIREncounter, DegradedResult
    from src.core.models.encounter import EncounterClass
    from src.nlp.pipeline import NLPPipeline

    cases = ALL_CASES[:10]
    agent = CodingAgent()
    nlp = NLPPipeline()

    print("\nHealthcare Digital FTE — Performance Benchmark (VALIDATE-005)")
    print("=" * 65)
    print(f"{'Case':<16} │ {'NLP':>7} │ {'Total':>7} │ {'Status'}")
    print("─" * 65)

    times: list[float] = []
    nlp_times: list[float] = []
    all_passed = True

    for case in cases:
        enc_id = f"bench-{case.case_id}"
        note = FHIRDocumentReference(
            id=f"doc-{enc_id}",
            encounter_id=enc_id,
            note_type_loinc="18842-5",
            note_type_display="Discharge Summary",
            authored_date=datetime.now(timezone.utc),
            content_type="plain_text",
            note_text=case.note_text,
        )
        encounter = FHIREncounter(
            id=enc_id,
            status="finished",
            class_code=EncounterClass.INPATIENT.value,
            encounter_class=EncounterClass.INPATIENT,
            period_start=datetime.now(timezone.utc),
        )

        # NLP-only timing
        t0 = time.perf_counter()
        nlp.analyze(case.note_text)
        nlp_ms = (time.perf_counter() - t0) * 1000
        nlp_times.append(nlp_ms)

        # Full pipeline timing
        t1 = time.perf_counter()
        result = await agent.analyze_note(note, encounter)
        total_s = time.perf_counter() - t1
        times.append(total_s)

        passed = total_s < PER_CHART_MAX_S
        if not passed:
            all_passed = False
        degraded = isinstance(result, DegradedResult)
        label = "FAIL" if not passed else ("DEGRADED" if degraded else "PASS")

        print(
            f"{case.case_id:<16} │ {nlp_ms:>6.1f}ms │ {total_s:>6.2f}s │ {label}"
        )

    print("─" * 65)
    times_s = sorted(times)
    n = len(times_s)
    median = times_s[n // 2] if n % 2 == 1 else (times_s[n // 2 - 1] + times_s[n // 2]) / 2
    p95 = times_s[int(n * 0.95)]

    print(f"{'Median':<16} │ {sum(nlp_times)/len(nlp_times):>6.1f}ms │ {median:>6.2f}s │")
    print(f"{'p95':<16} │ {'':>7} │ {p95:>6.2f}s │")
    print(f"{'Max':<16} │ {max(nlp_times):>6.1f}ms │ {max(times_s):>6.2f}s │")
    print("=" * 65)

    median_ok = median < MEDIAN_MAX_S
    if all_passed and median_ok:
        print(f"VALIDATE-005: PASS — all 10 charts under {PER_CHART_MAX_S:.0f}s, median {median:.1f}s")
    else:
        if not all_passed:
            print(f"VALIDATE-005: FAIL — one or more charts exceeded {PER_CHART_MAX_S:.0f}s")
        if not median_ok:
            print(f"VALIDATE-005: FAIL — median {median:.1f}s exceeds {MEDIAN_MAX_S:.0f}s target")

    return all_passed and median_ok


if __name__ == "__main__":
    passed = asyncio.run(run())
    sys.exit(0 if passed else 1)
