"""
MIMIC-IV Accuracy Benchmark Runner

Runs the coding agent against MIMIC-IV discharge summaries and
calculates precision (acceptance rate), recall, and F1.

Primary target: precision ≥ 0.70 (Phase 1 exit criterion)
Secondary target: recall ≥ 0.55

Constitution: Article II.4 (no PHI in logs or report)
              Article II.5 (DegradedResult counted, not crashed)
Spec: specs/07-mimic-benchmark.md
ADR:  docs/adr/ADR-013-mimic-benchmark-design.md

CLI usage:
    uv run python -m src.benchmarks.mimic_benchmark --sample 100
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog
from pydantic import BaseModel

from src.benchmarks.mimic_loader import MimicAdmission, MimicLoader
from src.core.models.encounter import EncounterContext

log = structlog.get_logger()

# Default delay between LLM calls — stays within API rate limits
_DEFAULT_DELAY_S = float(os.getenv("BENCHMARK_DELAY_S", "1.0"))


class BenchmarkResult(BaseModel):
    """Scoring outcome for a single admission."""

    hadm_id: str
    suggested_codes: list[str]
    gold_codes: list[str]
    exact_matches: list[str]
    parent_matches: list[str]
    precision: float
    recall: float
    is_degraded: bool


class BenchmarkReport(BaseModel):
    """Aggregate report across all scored admissions."""

    run_date: str
    sample_size: int
    valid_runs: int
    mean_precision: float
    mean_recall: float
    mean_f1: float
    meets_target: bool
    degraded_count: int
    results: list[BenchmarkResult]


def normalize_code(raw: str) -> str:
    """Remove dots, uppercase, strip whitespace. 'I50.9' → 'I509'."""
    return raw.replace(".", "").upper().strip()


class MimicBenchmark:
    """
    Benchmark the coding agent against MIMIC-IV ground truth.

    Parameters
    ----------
    data_dir:
        Root MIMIC data directory (typically Path("data/mimic")).
    delay_s:
        Seconds to sleep between LLM calls. Defaults to BENCHMARK_DELAY_S
        env var or 1.0.
    """

    def __init__(
        self,
        data_dir: Path,
        delay_s: float = _DEFAULT_DELAY_S,
    ) -> None:
        self._data_dir = data_dir
        self._delay_s = delay_s
        self._last_admissions: list[MimicAdmission] = []

    async def run(self, sample_size: int = 100) -> BenchmarkReport:
        """
        Load admissions, run coding agent on each, return BenchmarkReport.
        Never raises — DegradedResult counted as degraded_count.
        """
        from src.agents.coding_agent import CodingAgent

        loader = MimicLoader(self._data_dir)
        admissions = loader.load_admissions(sample_size=sample_size)
        self._last_admissions = admissions

        log.info(
            "mimic_benchmark_start",
            sample_size=len(admissions),
        )

        agent = CodingAgent()
        results: list[BenchmarkResult] = []

        for i, admission in enumerate(admissions):
            result = await self._score_admission(agent, admission)
            results.append(result)
            if i > 0 and self._delay_s > 0:
                await asyncio.sleep(self._delay_s)

        return self._build_report(results, sample_size)

    async def _score_admission(
        self,
        agent: "CodingAgent",
        admission: MimicAdmission,
    ) -> BenchmarkResult:
        """Run agent on one admission; return scored BenchmarkResult."""
        from src.core.models.fhir import DegradedResult

        encounter = EncounterContext(
            encounter_id=f"mimic-{admission.hadm_id}",
            encounter_setting="inpatient",
            note_text=admission.discharge_note,
        )

        result = await agent.analyze_note(
            note=self._build_fhir_note(encounter),
            encounter=self._build_fhir_encounter(encounter),
        )

        if isinstance(result, DegradedResult):
            log.warning(
                "mimic_benchmark_degraded",
                hadm_id=admission.hadm_id,
                # note content intentionally omitted
            )
            return BenchmarkResult(
                hadm_id=admission.hadm_id,
                suggested_codes=[],
                gold_codes=admission.gold_codes,
                exact_matches=[],
                parent_matches=[],
                precision=0.0,
                recall=0.0,
                is_degraded=True,
            )

        suggested = [s.code for s in result.suggestions]
        exact = self._exact_matches(suggested, admission.gold_codes)
        parent = self.parent_matches(suggested, admission.gold_codes)
        p = self.calculate_precision(suggested, admission.gold_codes)
        r = self.calculate_recall(suggested, admission.gold_codes)

        log.info(
            "mimic_benchmark_scored",
            hadm_id=admission.hadm_id,
            suggestion_count=len(suggested),
            exact_match_count=len(exact),
            precision=round(p, 3),
            recall=round(r, 3),
        )
        return BenchmarkResult(
            hadm_id=admission.hadm_id,
            suggested_codes=suggested,
            gold_codes=admission.gold_codes,
            exact_matches=exact,
            parent_matches=parent,
            precision=p,
            recall=r,
            is_degraded=False,
        )

    def _build_report(
        self,
        results: list[BenchmarkResult],
        sample_size: int,
    ) -> BenchmarkReport:
        """Aggregate individual results into a BenchmarkReport."""
        valid = [r for r in results if not r.is_degraded]
        degraded = len(results) - len(valid)

        if not valid:
            mean_p = mean_r = mean_f1 = 0.0
        else:
            mean_p = sum(r.precision for r in valid) / len(valid)
            mean_r = sum(r.recall for r in valid) / len(valid)
            mean_f1 = self.calculate_f1(mean_p, mean_r)

        report = BenchmarkReport(
            run_date=datetime.now(timezone.utc).isoformat(),
            sample_size=sample_size,
            valid_runs=len(valid),
            mean_precision=round(mean_p, 4),
            mean_recall=round(mean_r, 4),
            mean_f1=round(mean_f1, 4),
            meets_target=mean_p >= 0.70,
            degraded_count=degraded,
            results=results,
        )
        log.info(
            "mimic_benchmark_complete",
            sample_size=sample_size,
            valid_runs=len(valid),
            degraded_count=degraded,
            mean_precision=report.mean_precision,
            mean_recall=report.mean_recall,
            mean_f1=report.mean_f1,
            meets_target=report.meets_target,
        )
        return report

    # ─── Scoring primitives ───────────────────────────────────────────────────

    def calculate_precision(
        self,
        suggested: list[str],
        gold: list[str],
    ) -> float:
        """Fraction of suggestions that match a gold code (acceptance rate)."""
        if not suggested:
            return 0.0
        return len(self._exact_matches(suggested, gold)) / len(suggested)

    def calculate_recall(
        self,
        suggested: list[str],
        gold: list[str],
    ) -> float:
        """Fraction of gold codes found in suggestions."""
        if not gold:
            return 0.0
        return len(self._exact_matches(suggested, gold)) / len(gold)

    def calculate_f1(self, precision: float, recall: float) -> float:
        """Harmonic mean of precision and recall."""
        denom = precision + recall
        if denom == 0.0:
            return 0.0
        return 2 * precision * recall / denom

    def parent_matches(
        self,
        suggested: list[str],
        gold: list[str],
    ) -> list[str]:
        """Return suggestions matching a gold code at the 3-char prefix level."""
        gold_prefixes = {normalize_code(c)[:3] for c in gold}
        return [s for s in suggested if normalize_code(s)[:3] in gold_prefixes]

    def normalize_code(self, code: str) -> str:
        """Public alias for module-level normalize_code."""
        return normalize_code(code)

    def _exact_matches(
        self,
        suggested: list[str],
        gold: list[str],
    ) -> list[str]:
        """Suggestions that match a gold code after normalization."""
        norm_gold = {normalize_code(c) for c in gold}
        return [s for s in suggested if normalize_code(s) in norm_gold]

    # ─── FHIR model builders ──────────────────────────────────────────────────

    def _build_fhir_note(
        self,
        encounter: "EncounterContext",
    ) -> "FHIRDocumentReference":
        from datetime import datetime, timezone
        from src.core.models.fhir import FHIRDocumentReference
        return FHIRDocumentReference(
            id=f"doc-{encounter.encounter_id}",
            encounter_id=encounter.encounter_id,
            note_type_loinc="18842-5",   # Discharge summary LOINC
            note_type_display="Discharge Summary",
            authored_date=datetime.now(timezone.utc),
            content_type="plain_text",
            note_text=encounter.note_text,
        )

    def _build_fhir_encounter(
        self,
        encounter: "EncounterContext",
    ) -> "FHIREncounter":
        from datetime import datetime, timezone
        from src.core.models.fhir import FHIREncounter
        from src.core.models.encounter import EncounterClass
        return FHIREncounter(
            id=encounter.encounter_id,
            status="finished",
            class_code="IMP",
            encounter_class=EncounterClass.INPATIENT,
            period_start=datetime.now(timezone.utc),
        )


# ─── CLI entry point ──────────────────────────────────────────────────────────

def _parse_args() -> dict[str, int | Path]:
    import argparse
    parser = argparse.ArgumentParser(
        description="MIMIC-IV Accuracy Benchmark — runs coding agent on MIMIC data"
    )
    parser.add_argument(
        "--sample", type=int, default=100,
        help="Number of admissions to score (default: 100)",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/mimic"),
        help="MIMIC data root directory (default: data/mimic)",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/mimic/benchmark_results"),
        help="Directory to write results JSON",
    )
    args = parser.parse_args()
    return {"sample": args.sample, "data_dir": args.data_dir, "output": args.output}


async def _main() -> None:
    args = _parse_args()
    benchmark = MimicBenchmark(data_dir=args["data_dir"])
    report = await benchmark.run(sample_size=args["sample"])

    output_dir: Path = args["output"]
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    out_file = output_dir / f"{ts}_benchmark_n{args['sample']}.json"
    out_file.write_text(report.model_dump_json(indent=2))

    print(f"\n=== MIMIC-IV Benchmark Results ===")
    print(f"Sample size:      {report.valid_runs}/{report.sample_size} valid")
    print(f"Acceptance rate:  {report.mean_precision:.1%}  (target ≥ 70%)")
    print(f"Recall rate:      {report.mean_recall:.1%}     (target ≥ 55%)")
    print(f"F1 score:         {report.mean_f1:.1%}")
    print(f"Degraded:         {report.degraded_count}")
    print(f"MEETS TARGET:     {'YES ✓' if report.meets_target else 'NO ✗'}")
    print(f"\nResults written to: {out_file}")


if __name__ == "__main__":
    asyncio.run(_main())
