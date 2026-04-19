# Build Status — Healthcare Digital FTE
# Read when: continuing BUILD work or diagnosing test failures

## Phase 1 — Coding AI + CDI Intelligence

### DISCOVER (complete)
- [x] DISC-001: ICD-10 official guidelines
- [x] DISC-002: Documentation failure patterns
- [x] DISC-003: FHIR implementation edge cases
- [x] DISC-004: Payer denial patterns
- [x] DISC-005: Competitor technical analysis

### DESIGN (complete)
- [x] DESIGN-001: Coding rules engine spec (specs/01-coding-rules-engine.md)
- [x] DESIGN-002: CDI intelligence layer spec (specs/02-cdi-intelligence-layer.md)
- [x] DESIGN-003: Compliance guardrail architecture (specs/03-compliance-guardrail-architecture.md)
- [x] DESIGN-004: Prompt engineering architecture (specs/04-prompt-engineering-architecture.md)
- [x] DESIGN-007: MIMIC benchmark spec (specs/07-mimic-benchmark.md)

### BUILD (complete — 271 passed, 5 skipped)

**BUILD-001** — Compliance guardrail tests (2026-04-02) — 36 tests written (TDD red)
- tests/clinical/test_compliance_guardrails.py
- src/core/exceptions.py: HumanApprovalRequiredError, EvidenceCitationRequiredError, ICD10GuidelineViolationError, CodingGuidelineViolationError, GuardrailWarning
- Covers G-HARD-001..007, G-SOFT-001..005

**BUILD-002** — Pydantic domain models (2026-04-02) — 23 tests
- src/core/models/ — 8 files, all domain models
- Unit tests: 23 PASSED

**BUILD-003** — ICD-10 rules engine (2026-04-03) — 12 tests
- src/core/icd10/data_loader.py — embedded Excludes1/2, mandatory paired, CC/MCC, DRG data
- src/core/icd10/rules_engine.py — ICD10RulesEngine (validate_excludes1, uncertain dx, DRG impact)
- src/core/guardrails/icd10_guardrail.py — G-HARD-003, G-HARD-004, G-SOFT-004
- src/core/guardrails/confidence_guardrail.py — G-SOFT-001, G-HARD-007
- tests/unit/test_icd10_rules_engine.py: 12 PASSED

**BUILD-004** — NLP pipeline (2026-04-03) — 54 tests
- src/nlp/pipeline.py — NLPPipeline.analyze() (section parse→NER→negation→temporal)
- src/nlp/section_parser.py, ner.py, negation.py, temporal.py
- tests/unit/test_nlp_pipeline.py: 54 PASSED

**BUILD-005** — Coding agent + PROMPT-001 (2026-04-05) — 12 tests
- src/agents/coding_agent.py — CodingAgent (7-step: NLP→LLM→parse→rules→sort→cap→return)
- src/prompts/coding_extraction.py — CODING_EXTRACTION_V1_0 (PHR-001)
- src/core/models/coding.py — drg_revenue_delta + G-SOFT-003 compliance_review_required validator
- Guardrails: II.2 (evidence_quote), II.3 (uncertain dx), II.4 (no PHI), II.5 (DegradedResult), II.6 (routing)
- tests/integration/test_coding_agent.py: 12 PASSED

**BUILD-006** — CDI agent + PROMPT-002 (2026-04-05) — 7 tests
- src/agents/cdi_agent.py — CDIAgent (detect_opportunities + analyze)
  - detect_opportunities: deterministic KDIGO threshold (creatinine ≥0.3 mg/dL OR ≥1.5x baseline)
  - analyze: detect → LLM query generation → CDIAnalysisResult
- src/prompts/cdi_query.py — CDI_QUERY_V1_0 (PHR-002, AHIMA-compliant, non-leading)
- tests/integration/test_cdi_agent.py: 7 PASSED

**BUILD-007** — DRG agent + PROMPT-003 (2026-04-13) — 7 tests
- src/prompts/drg_analysis.py — DRG_ANALYSIS_V1_0 (PHR-003, plain-English CFO narrative)
- src/agents/drg_agent.py — DRGAgent (generate_narrative)
  - Input: DRGImpact + principal_dx + proposed_code
  - Output: DRGNarrative (executive_summary, compliance_note)
  - requires_compliance_review auto-set for delta >$5,000
- tests/integration/test_drg_agent.py: 7 PASSED

**BUILD-008** — DRG calculator + MCP tools (2026-04-05) — 10 tests
- src/core/drg/grouper.py — DRGGrouper (calculate_drg, calculate_impact)
- src/mcp/icd10_tools.py — mcp_icd10_lookup, mcp_excludes1_check
- src/mcp/drg_tools.py — mcp_drg_calculate, mcp_drg_impact
- src/mcp/fhir_tools.py — mcp_fhir_get_encounter, mcp_fhir_get_clinical_notes, mcp_fhir_get_recent_labs
- Key: I50.9 (CC) → DRG 292; +N17.9 (MCC) → DRG 291 (+$6,384)
- tests/unit/test_drg_grouper.py: 10 PASSED

**BUILD-009** — FHIR client (2026-04-05) — 20 tests
- src/core/fhir/auth.py — FHIRAuthenticator (SMART on FHIR JWT assertion)
- src/core/fhir/resources.py — parse_patient/encounter/document/observation, extract_note_text
- src/core/fhir/client.py — FHIRClient (get_patient, get_encounter, get_clinical_notes, get_recent_labs, write_draft_claim)
- OBS→OUTPATIENT mapping verified
- tests/unit/test_fhir_client.py: 20 PASSED

**BUILD-010** — Coder review UI (2026-04-06) — 17 tests
- src/api/security/approval_token.py — ApprovalTokenService (HMAC-SHA256, 15-min expiry, single-use)
- src/api/middleware/auth.py — verify_session
- src/api/middleware/audit.py — write_audit_log, create_audit_entry (UserActionAuditEntry)
- src/api/routes/health.py — GET /health → 200
- src/api/routes/coding.py — GET /queue, GET /review/{id}, POST /review/{id}/approve (token required)
- src/api/main.py — FastAPI app
- tests/unit/test_approval_token.py: 10 PASSED
- tests/integration/test_coder_workflow.py: 7 PASSED

**BUILD-011** — End-to-end integration (2026-04-05) — 17 tests
- tests/integration/test_full_pipeline.py
- All 12 Article II compliance guardrails enforced and tested end-to-end
- Compliance guardrails completed (was 25 failing):
  - src/core/guardrails/claim_guardrail.py — G-HARD-001
  - src/core/guardrails/evidence_guardrail.py — G-HARD-002
  - src/api/middleware/phi_filter.py — G-HARD-005
  - src/core/guardrails/specificity_guardrail.py — G-SOFT-003
  - src/core/guardrails/drg_guardrail.py — G-SOFT-003
  - src/core/guardrails/fhir_audit_guardrail.py — G-HARD-006
  - src/core/guardrails/copy_forward_guardrail.py — G-SOFT-002
  - src/core/guardrails/cdi_guardrail.py — G-SOFT-005
- CodingAgent.analyze(EncounterContext) added
- POST /api/v1/coding/analyze route added
- Total: 208 passed, 0 failed

### VALIDATE (in progress — see validate-phase.md)

**VALIDATE-001** — MIMIC-IV benchmark infrastructure (2026-04-08) — 31 tests
- specs/07-mimic-benchmark.md, docs/adr/ADR-013-mimic-benchmark-design.md
- src/benchmarks/mimic_loader.py, src/benchmarks/mimic_benchmark.py
- scripts/download_mimic4.sh
- tests/clinical/test_coding_accuracy_mimic.py: 31 always + 5 skipped (data not downloaded)
- Total suite: 239 passed, 5 skipped

**VALIDATE-002** — Known-cases benchmark (2026-04-13) — 32 tests
- tests/fixtures/known_cases/cases.py — 20 hand-labeled cases from DISC-002 §B.1
  - 15 direct-code cases, 5 CDI-query cases
  - Cases: HF, sepsis, AKI, resp failure, malnutrition, pneumonia, DM, COPD, encephalopathy,
    pressure ulcer, anemia, obesity, AFib, UTI, AMI, pancreatitis, DVT, stroke, alcohol withdrawal, HTN→HHD
- tests/clinical/test_known_cases_benchmark.py: 32 tests
- Pipeline precision: 100% (mocked LLM)
- Total suite: 271 passed, 5 skipped
