# DESIGN-008: End-to-End Performance Benchmark

**Status:** COMPLETE
**Date:** 2026-04-27
**Author:** Claude (AI Engineering Partner)
**Constitution references:** Article I.1 (spec before code),
Article I.2 (TDD), Article II.4 (no PHI in results),
Article IV.4 (Phase 1 exit criteria — must pass before Phase 2)
**Scope:** Measure wall-clock latency of the full CodingAgent pipeline
against the <30 second per-chart SLA required for hospital pilot.

---

## 1. Purpose

The performance benchmark answers one question:

> Can the system analyze a clinical chart and return ICD-10
> suggestions within 30 seconds under normal operating conditions?

This is the latency SLA agreed in VALIDATE-006 (hospital pilot
requirements). If the system cannot meet it, clinicians will abandon
the tool mid-workflow — killing adoption before revenue.

**VALIDATE-005 exit criteria (all must pass):**
- Each of 10 benchmark charts completes in **< 30 seconds**
- Median chart time **< 20 seconds** (30s headroom for production variance)
- NLP pipeline alone (no LLM) **< 500 ms** per chart
- Zero `DegradedResult` returns (system must be functional, not just fast)

---

## 2. Pipeline Under Measurement

```
FHIRDocumentReference + FHIREncounter
        │
        ▼
CodingAgent.analyze_note()     ← wall clock starts here
        │
        ├─ NLPPipeline.analyze()           ← component timer A
        │  (section_parser→ner→negation→temporal)
        │
        ├─ LLM call (Groq / Anthropic)     ← component timer B
        │  CODING_EXTRACTION_V1_0 prompt
        │
        ├─ _parse_suggestions()            ← component timer C
        │  (evidence validation, uncertain dx filter)
        │
        └─ _apply_rules_engine()           ← component timer D
           (Excludes1, mandatory paired codes)
        │
        ▼
CodingAnalysisResult.processing_time_ms   ← wall clock ends
```

The LLM call dominates (typically 1–10s on Groq free tier).
NLP + rules together are expected to take < 200ms.

---

## 3. Test Dataset

10 synthetic charts from `tests/fixtures/known_cases/cases.py`.
These are hand-labeled clinical notes (DISC-002 §B.1) — no PHI.

| Case ID | Condition | Expected Complexity |
|---------|-----------|---------------------|
| DISC002-01 | Heart failure | High (multiple codes) |
| DISC002-02 | Sepsis | High (MCC present) |
| DISC002-03 | AKI | Medium |
| DISC002-04 | Respiratory failure | High |
| DISC002-05 | Malnutrition | Medium |
| DISC002-06 | Pneumonia | Medium |
| DISC002-07 | Type 2 Diabetes | Low |
| DISC002-08 | COPD exacerbation | Medium |
| DISC002-09 | Encephalopathy | High |
| DISC002-10 | Pressure ulcer | Medium |

All charts are inpatient class (`IMP`) — longest notes, most
computationally representative of real hospital use.

---

## 4. Pass/Fail Criteria

| Metric | Target | Fail Condition |
|--------|--------|----------------|
| Per-chart max | < 30s | Any chart ≥ 30s |
| Median | < 20s | Median ≥ 20s |
| NLP-only (no LLM) | < 500ms | Any NLP run ≥ 500ms |
| Degraded rate | 0% | Any DegradedResult |

---

## 5. Output Format

The benchmark script prints a timing table:

```
Healthcare Digital FTE — Performance Benchmark (VALIDATE-005)
==============================================================
Case               │ NLP (ms) │ Total (s) │ Status
─────────────────────────────────────────────────────────
DISC002-01 HF      │       82 │      4.2  │  PASS
DISC002-02 Sepsis  │       91 │      5.1  │  PASS
...
─────────────────────────────────────────────────────────
Median             │       88 │      4.7  │
p95                │      120 │      8.3  │
Max                │      150 │      9.1  │  PASS (<30s)
==============================================================
VALIDATE-005: PASS — all 10 charts under 30s, median 4.7s
```

---

## 6. Testing Strategy

**pytest marker:** `@pytest.mark.performance`

**Test file:** `tests/clinical/test_performance_benchmark.py`

Three test functions:
1. `test_per_chart_latency` — each chart < 30s; asserts all pass
2. `test_median_latency` — median < 20s
3. `test_nlp_pipeline_latency` — NLP alone < 500ms (no LLM, sync only)

Tests skip automatically if `LLM_PROVIDER` env var is not set,
so CI pipelines without API keys don't fail.

**Benchmark script:** `src/benchmarks/performance_benchmark.py`
- Run with: `python -m src.benchmarks.performance_benchmark`
- Prints full timing table to stdout
- Exits 0 on PASS, 1 on FAIL

---

## 7. Relation to Other Benchmarks

| Benchmark | File | Measures |
|-----------|------|---------|
| Known-cases (VALIDATE-002) | test_known_cases_benchmark.py | Coding accuracy |
| MIMIC-IV (VALIDATE-003) | test_coding_accuracy_mimic.py | Real-world precision/recall |
| **Performance (VALIDATE-005)** | **test_performance_benchmark.py** | **Latency SLA** |

Accuracy and latency are independent. A system can be fast and wrong,
or slow and right. We require both: ≥70% acceptance rate AND <30s/chart.
