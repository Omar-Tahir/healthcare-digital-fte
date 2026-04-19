# ADR-013: MIMIC-IV Benchmark Design

**Status:** ACCEPTED
**Date:** 2026-04-08
**Decision makers:** Engineering team
**Constitution references:** Article I.1 (spec first),
Article II.4 (no PHI), Article IV.1 (revenue impact)
**Spec:** specs/07-mimic-benchmark.md

---

## Context

Phase 1 exit criteria (DESIGN-000 §4) include demonstrating coding
accuracy on real clinical data before the first hospital pilot.
MIMIC-IV is the only publicly available de-identified EHR dataset
at sufficient scale with gold-standard ICD codes.

Three decisions required architectural choices.

---

## Decision 1: MIMIC-IV over MIMIC-III

**MIMIC-III** (2001–2012) uses ICD-9-CM codes. Our system targets
ICD-10-CM. Cross-version benchmarking requires unreliable code
mapping (GEMs tables have 1-to-many and many-to-1 issues).

**MIMIC-IV** (2008–2019) includes ICD-10-CM admissions (post-2015
transition). These can be compared directly without mapping.

**Decision:** Use MIMIC-IV v2.2, filter `icd_version=10` only.

---

## Decision 2: Precision (Acceptance Rate) as Primary Metric

Three candidate primary metrics:

| Metric | Definition | Problem |
|--------|-----------|---------|
| F1 score | Harmonic mean of precision and recall | Weights recall and precision equally; recall is harder to optimize without overcoding |
| Recall | % of gold codes found | Rewards overcoding — penalized by FCA (Article II.6) |
| Precision | % of suggestions that match gold | Measures coder trust: "when AI suggests a code, is it right?" |

**Decision:** Precision (acceptance rate) is primary.

**Rationale:** A coder who sees our suggestions and accepts 70% of them
is getting real value. A system with high recall but low precision
forces coders to evaluate many wrong codes — reducing throughput
and trust, which is the opposite of the product goal.

Secondary target for recall at 55% — ensures we are not suggesting
only the obvious codes while missing meaningful secondary diagnoses.

---

## Decision 3: pytest skipif vs Separate Test Suite

Two options for MIMIC-dependent tests:

| Option | Pros | Cons |
|--------|------|------|
| Separate test suite outside pytest | No pytest skip noise | Not integrated with CI; separate tooling |
| pytest.mark.skipif(not MIMIC_AVAILABLE) | Integrated; run anywhere with data | Skip messages in CI |

**Decision:** pytest.mark.skipif within `tests/clinical/`.

**Rationale:**
- Infrastructure tests (scoring math, CSV parsing, report models)
  always run and validate benchmark logic without data
- MIMIC-dependent tests skip cleanly in CI with a clear reason message
- When a hospital pilot provides MIMIC-equivalent data, the same
  test class can be reused with a different data path
- ADR-011 (Phase Gate Verification) established `tests/clinical/`
  as the home for clinical accuracy tests

---

## Decision 4: Benchmark Runner as CLI Module

The benchmark runner (`python -m src.benchmarks.mimic_benchmark`)
is separate from the pytest test suite.

**Rationale:**
- Full 100-run benchmark costs ~$1.50 and takes 45–90 minutes
- pytest runs should be free and fast (CI constraint)
- The runner writes JSON results to `data/mimic/benchmark_results/`
  which are gitignored
- `pytest -m mimic` runs only the MIMIC integration tests (skip
  the runner; validate only that the infrastructure works)

---

## Consequences

- `data/mimic/` must be gitignored (contains de-identified patient data)
- `benchmark_results/` is also gitignored
- PhysioNet credentials required to download data — see
  `scripts/download_mimic4.sh` for instructions
- Coverage for `src/benchmarks/` is measured but does not count
  toward the 80% project-wide coverage target (MIMIC tests are
  skipped in CI)
