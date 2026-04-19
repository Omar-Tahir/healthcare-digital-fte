#!/usr/bin/env python3
"""
Healthcare Digital FTE — Live Known-Cases Benchmark

Runs the 20 DISC-002 hand-labeled specificity upgrade cases through the
real coding agent (using the configured LLM provider from LLM_PROVIDER env var).

Usage:
    LLM_PROVIDER=groq GROQ_API_KEY=<key> uv run python scripts/run_live_benchmark.py

Output: precision table + summary score
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.coding_agent import CodingAgent
from src.core.models.encounter import EncounterContext
from tests.fixtures.known_cases.cases import ALL_CASES, CDI_QUERY_CASES, DIRECT_CODE_CASES, KnownCase

_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 15.0  # seconds — Groq rate limit window


async def _analyze_with_retry(agent: CodingAgent, encounter: EncounterContext):
    """
    Run analysis with exponential backoff on rate limit errors.
    Groq free tier hits token-per-minute caps on rapid sequential requests.
    """
    for attempt in range(_MAX_RETRIES):
        result = await agent.analyze(encounter)
        # If degraded due to LLM failure and we have retries left, pause and retry
        is_degraded = getattr(result, "is_degraded", True)
        has_suggestions = bool(getattr(result, "suggestions", []))
        has_cdi = bool(getattr(result, "cdi_opportunities", []))
        if is_degraded and not has_suggestions and not has_cdi and attempt < _MAX_RETRIES - 1:
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            print(f"      [rate limit — retry {attempt + 1}/{_MAX_RETRIES - 1} in {delay:.0f}s]")
            await asyncio.sleep(delay)
            continue
        return result
    return result


def _encounter_setting(case: KnownCase) -> str:
    """All known cases are inpatient admissions (discharge summaries)."""
    return "inpatient"


def _code_found(result_suggestions: list, target_code: str) -> tuple[bool, float]:
    """Check if the specific code appears in suggestions. Return (found, confidence)."""
    target = target_code.upper().replace(".", "")
    for s in result_suggestions:
        candidate = s.code.upper().replace(".", "")
        if candidate == target or candidate.startswith(target[:5]):
            return True, s.confidence
    return False, 0.0


def _cdi_triggered(result) -> bool:
    """Check if any CDI opportunity was detected."""
    return len(getattr(result, "cdi_opportunities", [])) > 0


async def run_benchmark() -> None:
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    model = os.getenv("LLM_MODEL", "")
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print()
    print("=" * 70)
    print("  Healthcare Digital FTE — Live Known-Cases Benchmark")
    print(f"  Date:     {run_date}")
    print(f"  Provider: {provider}", end="")
    if model:
        print(f" / {model}", end="")
    print()
    print(f"  Cases:    {len(ALL_CASES)} (DISC-002 specificity upgrades)")
    print("=" * 70)
    print()

    agent = CodingAgent()

    header = f"  {'#':>2}  {'Case':<32}  {'Expected':<10}  {'Result':<10}  {'Conf':>5}"
    print(header)
    print("  " + "-" * 65)

    direct_correct = 0
    direct_total = 0
    cdi_correct = 0
    cdi_total = 0
    degraded_count = 0

    for i, case in enumerate(ALL_CASES, 1):
        encounter = EncounterContext(
            encounter_id=f"bench-{case.case_id}",
            encounter_setting=_encounter_setting(case),
            note_text=case.note_text,
        )

        result = await _analyze_with_retry(agent, encounter)

        if getattr(result, "is_degraded", True) and not getattr(result, "suggestions", []):
            degraded_count += 1
            print(f"  {i:>2}  {case.title[:32]:<32}  {case.specific_code:<10}  {'DEGRADED':<10}  {'—':>5}")
            continue

        suggestions = getattr(result, "suggestions", [])

        if case.expect_cdi_query:
            cdi_total += 1
            triggered = _cdi_triggered(result)
            if triggered:
                cdi_correct += 1
            label = "CDI ✓" if triggered else "CDI ✗"
            print(f"  {i:>2}  {case.title[:32]:<32}  {case.specific_code:<10}  {label:<10}  {'—':>5}")
        else:
            direct_total += 1
            found, conf = _code_found(suggestions, case.specific_code)
            if found:
                direct_correct += 1
            label = "FOUND ✓" if found else "MISSED ✗"
            conf_str = f"{conf:.2f}" if found else "—"
            print(f"  {i:>2}  {case.title[:32]:<32}  {case.specific_code:<10}  {label:<10}  {conf_str:>5}")

        # Pause between cases — Groq free tier: ~6k TPM, ~1.5k tokens/case → 15s minimum.
        await asyncio.sleep(15.0)

    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)

    if direct_total > 0:
        direct_pct = direct_correct / direct_total * 100
        print(f"  Specific-code precision:  {direct_correct}/{direct_total}  ({direct_pct:.0f}%)")
    if cdi_total > 0:
        cdi_pct = cdi_correct / cdi_total * 100
        print(f"  CDI opportunity recall:   {cdi_correct}/{cdi_total}  ({cdi_pct:.0f}%)")
    if degraded_count > 0:
        print(f"  Degraded (LLM failures):  {degraded_count}")

    total_correct = direct_correct + cdi_correct
    total_cases = direct_total + cdi_total
    if total_cases > 0:
        overall_pct = total_correct / total_cases * 100
        print()
        print(f"  Overall:  {total_correct}/{total_cases}  ({overall_pct:.0f}%)")

    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
