# Validate Phase — Healthcare Digital FTE
# Read when: working on validation, benchmarking, or pilot planning

## Current Suite State
- 271 passed, 5 skipped (MIMIC data not downloaded)
- All 12 Article II guardrails enforced and tested

## Remaining Validate Tasks

### VALIDATE-003 — MIMIC-IV Accuracy Run
- Status: BLOCKED — PhysioNet credentials required
- Command: `bash scripts/download_mimic4.sh <username>`
- Then: `uv run python -m src.benchmarks.mimic_benchmark --sample 100`
- Targets: acceptance rate ≥ 70%, recall ≥ 55%
- Files: src/benchmarks/mimic_benchmark.py, tests/clinical/test_coding_accuracy_mimic.py
- ADR: docs/adr/ADR-013-mimic-benchmark-design.md

### VALIDATE-004 — Epic Sandbox Integration
- Status: NOT STARTED
- Purpose: Test against real FHIR API (not mocked)
- Requires: Epic sandbox credentials + SMART on FHIR app registration
- Focus: FHIRClient, FHIRAuthenticator, all mcp_fhir_* tools

### VALIDATE-005 — Performance Benchmark
- Status: NOT STARTED
- Target: <30 seconds end-to-end per chart
- Measure: NLP pipeline + LLM call + rules engine + DRG calculation
- Method: time the full CodingAgent.analyze() on 10 test charts

### VALIDATE-006 — First Hospital Pilot
- Status: NOT STARTED
- Target: 1 mid-market hospital
- Requirements before pilot:
  - MIMIC accuracy ≥ 70% acceptance rate
  - Epic sandbox integration passing
  - Performance <30s/chart
  - HIPAA BAA signed
  - Compliance review of all 12 guardrails by legal

## Benchmark Infrastructure (already built)

### Known-Cases Benchmark
- 20 hand-labeled cases in tests/fixtures/known_cases/cases.py
- Source: DISC-002 §B.1 documentation failure patterns
- 15 direct-code cases + 5 CDI-query cases
- Run: `uv run pytest tests/clinical/test_known_cases_benchmark.py -v`

### MIMIC-IV Benchmark
- Infrastructure: src/benchmarks/mimic_loader.py + mimic_benchmark.py
- Data location: data/mimic/raw/ (gitignored)
- 5 tests skip until data downloaded (pytest.mark.mimic)
- Run: `uv run pytest tests/clinical/test_coding_accuracy_mimic.py -v`
