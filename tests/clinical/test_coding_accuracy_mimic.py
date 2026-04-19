"""
MIMIC-IV Accuracy Benchmark Tests

Three test classes:
  TestBenchmarkScoring  — always runs; validates precision/recall math
  TestCodeNormalization — always runs; validates ICD code normalizer
  TestMimicDataLoader   — always runs; validates CSV loader with fixtures
  TestMimicAccuracy     — SKIPPED unless MIMIC-IV data is downloaded

Constitution: Article II.4 (no PHI in any test output or log)
Spec:         specs/07-mimic-benchmark.md
ADR:          docs/adr/ADR-013-mimic-benchmark-design.md
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import pytest

from src.benchmarks.mimic_loader import MimicAdmission, MimicLoader
from src.benchmarks.mimic_benchmark import (
    BenchmarkReport,
    BenchmarkResult,
    MimicBenchmark,
)

# ─── Data availability check ─────────────────────────────────────────────────

MIMIC_DATA_DIR = Path("data/mimic")
_DISCHARGE_CSV = MIMIC_DATA_DIR / "raw" / "discharge.csv"
_DIAGNOSES_CSV = MIMIC_DATA_DIR / "raw" / "diagnoses_icd.csv"
MIMIC_AVAILABLE = _DISCHARGE_CSV.exists() and _DIAGNOSES_CSV.exists()


# ─── Fixtures ─────────────────────────────────────────────────────────────────

HEART_FAILURE_NOTE = """
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Acute-on-chronic systolic heart failure, decompensated

HISTORY OF PRESENT ILLNESS:
Patient is a 68-year-old male with a history of chronic systolic heart failure
(EF 30%) who presents with worsening dyspnea and lower extremity edema.
Creatinine on admission was 2.4, up from baseline of 1.1, consistent with
acute kidney injury in the setting of decreased cardiac output.

ASSESSMENT AND PLAN:
1. Acute-on-chronic systolic heart failure, decompensated (I50.23)
   - IV diuresis with Lasix
   - Daily weights, strict I/O
2. Acute kidney injury (N17.9) — creatinine 2.4 (baseline 1.1)
   - Hold ACE inhibitor
   - Monitor renal function
3. Type 2 diabetes mellitus without complications (E11.9)
   - Continue home insulin regimen

DISCHARGE CONDITION: Stable, improved
""".strip()

HEART_FAILURE_GOLD_CODES = ["I50.23", "N17.9", "E11.9"]

SIMPLE_NOTE = """
DISCHARGE SUMMARY

DIAGNOSIS: Essential hypertension

HISTORY: 55-year-old female admitted for blood pressure management.
Blood pressure was 180/110 on admission.

PLAN: Essential hypertension (I10) — start amlodipine 5mg daily.
""".strip()

SIMPLE_GOLD_CODES = ["I10"]


def _write_fixture_csvs(tmp_path: Path) -> tuple[Path, Path]:
    """
    Write minimal MIMIC-style CSV files to tmp_path.
    Returns (discharge_path, diagnoses_path).
    """
    discharge_path = tmp_path / "discharge.csv"
    diagnoses_path = tmp_path / "diagnoses_icd.csv"

    with open(discharge_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["note_id", "subject_id", "hadm_id", "note_type",
                    "note_seq", "charttime", "storetime", "text"])
        w.writerow(["n1", "100", "10001", "Discharge summary",
                    "1", "2018-01-01", "2018-01-01", HEART_FAILURE_NOTE])
        w.writerow(["n2", "101", "10002", "Discharge summary",
                    "1", "2019-03-15", "2019-03-15", SIMPLE_NOTE])

    with open(diagnoses_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["subject_id", "hadm_id", "seq_num", "icd_code", "icd_version"])
        # Admission 10001 — heart failure codes (ICD-10, no dots)
        w.writerow(["100", "10001", "1", "I5023", "10"])
        w.writerow(["100", "10001", "2", "N179", "10"])
        w.writerow(["100", "10001", "3", "E119", "10"])
        # Admission 10002 — hypertension
        w.writerow(["101", "10002", "1", "I10", "10"])
        # ICD-9 admission — should be excluded
        w.writerow(["102", "10003", "1", "4280", "9"])

    return discharge_path, diagnoses_path


# ─── TestCodeNormalization ────────────────────────────────────────────────────

class TestCodeNormalization:
    """Validate the ICD-10 code normalizer (dot removal)."""

    def test_removes_dot(self) -> None:
        from src.benchmarks.mimic_benchmark import normalize_code
        assert normalize_code("I50.9") == "I509"

    def test_removes_dot_7char_code(self) -> None:
        from src.benchmarks.mimic_benchmark import normalize_code
        assert normalize_code("S72.001A") == "S72001A"

    def test_no_change_if_no_dot(self) -> None:
        from src.benchmarks.mimic_benchmark import normalize_code
        assert normalize_code("I509") == "I509"

    def test_uppercases(self) -> None:
        from src.benchmarks.mimic_benchmark import normalize_code
        assert normalize_code("i50.9") == "I509"

    def test_strips_whitespace(self) -> None:
        from src.benchmarks.mimic_benchmark import normalize_code
        assert normalize_code(" I50.9 ") == "I509"

    def test_empty_string_returns_empty(self) -> None:
        from src.benchmarks.mimic_benchmark import normalize_code
        assert normalize_code("") == ""


# ─── TestBenchmarkScoring ─────────────────────────────────────────────────────

class TestBenchmarkScoring:
    """Validate precision/recall/F1 calculations — no MIMIC data needed."""

    def setup_method(self) -> None:
        self.bm = MimicBenchmark(data_dir=MIMIC_DATA_DIR)

    def test_perfect_precision_all_suggestions_correct(self) -> None:
        p = self.bm.calculate_precision(["I50.9", "N17.9"], ["I50.9", "N17.9"])
        assert p == 1.0

    def test_partial_precision(self) -> None:
        # 1 of 2 suggestions correct
        p = self.bm.calculate_precision(["I50.9", "E11.9"], ["I50.9", "N17.9"])
        assert p == pytest.approx(0.5)

    def test_zero_precision_no_overlap(self) -> None:
        p = self.bm.calculate_precision(["I50.9"], ["N17.9"])
        assert p == 0.0

    def test_precision_is_zero_when_no_suggestions(self) -> None:
        p = self.bm.calculate_precision([], ["I50.9"])
        assert p == 0.0

    def test_perfect_recall_all_gold_found(self) -> None:
        r = self.bm.calculate_recall(["I50.9", "N17.9"], ["I50.9", "N17.9"])
        assert r == 1.0

    def test_partial_recall_misses_one_code(self) -> None:
        # Found 1 of 3 gold codes
        r = self.bm.calculate_recall(["I50.9"], ["I50.9", "N17.9", "E11.9"])
        assert r == pytest.approx(1 / 3)

    def test_recall_is_zero_when_no_gold(self) -> None:
        r = self.bm.calculate_recall(["I50.9"], [])
        assert r == 0.0

    def test_f1_is_harmonic_mean(self) -> None:
        # precision=0.5, recall=1.0 → F1 = 2*(0.5*1.0)/(0.5+1.0) ≈ 0.667
        f1 = self.bm.calculate_f1(precision=0.5, recall=1.0)
        assert f1 == pytest.approx(2 / 3, rel=1e-3)

    def test_f1_is_zero_when_precision_and_recall_both_zero(self) -> None:
        f1 = self.bm.calculate_f1(precision=0.0, recall=0.0)
        assert f1 == 0.0

    def test_normalization_enables_dot_insensitive_matching(self) -> None:
        # Coding agent returns "I50.23"; MIMIC stores "I5023"
        p = self.bm.calculate_precision(["I50.23"], ["I5023"])
        assert p == 1.0

    def test_parent_match_first_3_chars(self) -> None:
        # I50.23 and I50.9 share prefix "I50"
        matches = self.bm.parent_matches(["I50.23"], ["I50.9"])
        assert len(matches) == 1

    def test_no_parent_match_different_prefix(self) -> None:
        matches = self.bm.parent_matches(["N17.9"], ["I50.9"])
        assert len(matches) == 0


# ─── TestBenchmarkResult ──────────────────────────────────────────────────────

class TestBenchmarkResult:
    """Validate BenchmarkResult model."""

    def test_result_fields_populated(self) -> None:
        result = BenchmarkResult(
            hadm_id="10001",
            suggested_codes=["I50.23", "N17.9"],
            gold_codes=["I50.23", "N17.9", "E11.9"],
            exact_matches=["I50.23", "N17.9"],
            parent_matches=["I50.23", "N17.9"],
            precision=1.0,
            recall=2 / 3,
            is_degraded=False,
        )
        assert result.hadm_id == "10001"
        assert result.precision == 1.0
        assert not result.is_degraded

    def test_degraded_result_has_zero_precision(self) -> None:
        result = BenchmarkResult(
            hadm_id="10002",
            suggested_codes=[],
            gold_codes=["I10"],
            exact_matches=[],
            parent_matches=[],
            precision=0.0,
            recall=0.0,
            is_degraded=True,
        )
        assert result.is_degraded
        assert result.precision == 0.0


# ─── TestBenchmarkReport ──────────────────────────────────────────────────────

class TestBenchmarkReport:
    """Validate BenchmarkReport model and meets_target logic."""

    def test_meets_target_true_when_precision_above_70(self) -> None:
        report = BenchmarkReport(
            run_date="2026-04-08",
            sample_size=2,
            valid_runs=2,
            mean_precision=0.75,
            mean_recall=0.60,
            mean_f1=0.67,
            meets_target=True,
            degraded_count=0,
            results=[],
        )
        assert report.meets_target

    def test_meets_target_false_when_precision_below_70(self) -> None:
        report = BenchmarkReport(
            run_date="2026-04-08",
            sample_size=2,
            valid_runs=2,
            mean_precision=0.65,
            mean_recall=0.55,
            mean_f1=0.60,
            meets_target=False,
            degraded_count=0,
            results=[],
        )
        assert not report.meets_target

    def test_report_serializes_to_json(self) -> None:
        report = BenchmarkReport(
            run_date="2026-04-08",
            sample_size=1,
            valid_runs=1,
            mean_precision=0.80,
            mean_recall=0.60,
            mean_f1=0.69,
            meets_target=True,
            degraded_count=0,
            results=[],
        )
        data = json.loads(report.model_dump_json())
        assert data["mean_precision"] == pytest.approx(0.80)
        assert "results" in data

    def test_report_contains_no_phi_fields(self) -> None:
        """PHI fields must not exist in BenchmarkReport."""
        report = BenchmarkReport(
            run_date="2026-04-08",
            sample_size=1,
            valid_runs=1,
            mean_precision=0.80,
            mean_recall=0.60,
            mean_f1=0.69,
            meets_target=True,
            degraded_count=0,
            results=[],
        )
        data = report.model_dump()
        phi_field_names = {
            "patient_name", "name", "dob", "date_of_birth",
            "mrn", "ssn", "address", "phone", "note_text",
            "discharge_note", "subject_id",
        }
        for field in phi_field_names:
            assert field not in data, f"PHI field '{field}' found in BenchmarkReport"


# ─── TestMimicDataLoader ──────────────────────────────────────────────────────

class TestMimicDataLoader:
    """CSV loading logic — uses synthetic fixture data, no real MIMIC needed."""

    def test_loader_raises_on_missing_data_dir(self) -> None:
        loader = MimicLoader(Path("/nonexistent/mimic"))
        with pytest.raises(FileNotFoundError):
            loader.load_admissions(sample_size=1)

    def test_loads_fixture_admissions(self, tmp_path: Path) -> None:
        discharge_path, diagnoses_path = _write_fixture_csvs(tmp_path)
        loader = MimicLoader(tmp_path, discharge_filename="discharge.csv",
                             diagnoses_filename="diagnoses_icd.csv")
        admissions = loader.load_admissions(sample_size=10)
        assert len(admissions) == 2  # Only ICD-10 admissions (not the ICD-9 one)

    def test_excludes_icd9_admissions(self, tmp_path: Path) -> None:
        _write_fixture_csvs(tmp_path)
        loader = MimicLoader(tmp_path, discharge_filename="discharge.csv",
                             diagnoses_filename="diagnoses_icd.csv")
        admissions = loader.load_admissions(sample_size=10)
        hadm_ids = {a.hadm_id for a in admissions}
        assert "10003" not in hadm_ids  # ICD-9 admission excluded

    def test_gold_codes_formatted_with_dots(self, tmp_path: Path) -> None:
        _write_fixture_csvs(tmp_path)
        loader = MimicLoader(tmp_path, discharge_filename="discharge.csv",
                             diagnoses_filename="diagnoses_icd.csv")
        admissions = loader.load_admissions(sample_size=10)
        hf_admission = next(a for a in admissions if a.hadm_id == "10001")
        # Codes stored as "I5023" in CSV — loader adds dots: "I50.23"
        assert "I50.23" in hf_admission.gold_codes

    def test_principal_dx_is_seq_num_1(self, tmp_path: Path) -> None:
        _write_fixture_csvs(tmp_path)
        loader = MimicLoader(tmp_path, discharge_filename="discharge.csv",
                             diagnoses_filename="diagnoses_icd.csv")
        admissions = loader.load_admissions(sample_size=10)
        hf_admission = next(a for a in admissions if a.hadm_id == "10001")
        assert hf_admission.principal_dx == "I50.23"

    def test_sample_size_limits_results(self, tmp_path: Path) -> None:
        _write_fixture_csvs(tmp_path)
        loader = MimicLoader(tmp_path, discharge_filename="discharge.csv",
                             diagnoses_filename="diagnoses_icd.csv")
        admissions = loader.load_admissions(sample_size=1)
        assert len(admissions) == 1

    def test_mimic_admission_model_fields(self, tmp_path: Path) -> None:
        _write_fixture_csvs(tmp_path)
        loader = MimicLoader(tmp_path, discharge_filename="discharge.csv",
                             diagnoses_filename="diagnoses_icd.csv")
        admissions = loader.load_admissions(sample_size=10)
        for a in admissions:
            assert a.hadm_id
            assert a.discharge_note
            assert a.gold_codes
            assert a.principal_dx
            assert a.total_code_count == len(a.gold_codes)


# ─── TestMimicAccuracy — requires downloaded data ────────────────────────────

@pytest.mark.skipif(not MIMIC_AVAILABLE,
                    reason="MIMIC-IV data not downloaded — run scripts/download_mimic4.sh")
@pytest.mark.mimic
class TestMimicAccuracy:
    """
    Clinical accuracy tests against real MIMIC-IV data.
    Skipped unless data/mimic/raw/{discharge,diagnoses_icd}.csv are present.

    These are the Phase 1 exit criteria for clinical accuracy
    (DESIGN-000 §4, specs/07-mimic-benchmark.md §6.2).
    """

    @pytest.fixture(autouse=True)
    def benchmark(self) -> MimicBenchmark:
        return MimicBenchmark(data_dir=MIMIC_DATA_DIR)

    @pytest.mark.asyncio
    async def test_acceptance_rate_exceeds_70_percent(
        self, benchmark: MimicBenchmark
    ) -> None:
        """Primary Phase 1 exit criterion: precision ≥ 0.70."""
        report = await benchmark.run(sample_size=100)
        assert report.mean_precision >= 0.70, (
            f"Acceptance rate {report.mean_precision:.1%} < 70% target. "
            f"Valid runs: {report.valid_runs}/{report.sample_size}. "
            f"Mean recall: {report.mean_recall:.1%}"
        )

    @pytest.mark.asyncio
    async def test_recall_rate_exceeds_55_percent(
        self, benchmark: MimicBenchmark
    ) -> None:
        """Secondary target: recall ≥ 0.55."""
        report = await benchmark.run(sample_size=100)
        assert report.mean_recall >= 0.55, (
            f"Recall {report.mean_recall:.1%} < 55% target."
        )

    @pytest.mark.asyncio
    async def test_principal_dx_found_in_majority(
        self, benchmark: MimicBenchmark
    ) -> None:
        """Principal diagnosis in suggestions for ≥ 80% of cases."""
        report = await benchmark.run(sample_size=100)
        principal_found = sum(
            1 for r in report.results
            if not r.is_degraded and any(
                benchmark.normalize_code(s) == benchmark.normalize_code(
                    next(a.principal_dx for a in benchmark._last_admissions
                         if a.hadm_id == r.hadm_id)
                )
                for s in r.suggested_codes
            )
        )
        valid = report.valid_runs
        rate = principal_found / valid if valid > 0 else 0.0
        assert rate >= 0.80, (
            f"Principal DX found in {rate:.1%} of cases; target ≥ 80%"
        )

    @pytest.mark.asyncio
    async def test_no_phi_in_benchmark_report(
        self, benchmark: MimicBenchmark
    ) -> None:
        """BenchmarkReport must not expose PHI fields — Article II.4."""
        report = await benchmark.run(sample_size=10)
        report_json = report.model_dump_json()
        phi_tokens = ["patient_name", "date_of_birth", "ssn", "address",
                      "discharge_note", "note_text", "subject_id"]
        for token in phi_tokens:
            assert token not in report_json, (
                f"PHI field '{token}' found in benchmark report"
            )

    @pytest.mark.asyncio
    async def test_degraded_rate_below_10_percent(
        self, benchmark: MimicBenchmark
    ) -> None:
        """Agent degraded in fewer than 10% of cases — Article II.5."""
        report = await benchmark.run(sample_size=100)
        degraded_rate = report.degraded_count / report.sample_size
        assert degraded_rate < 0.10, (
            f"Degraded rate {degraded_rate:.1%} ≥ 10%"
        )
