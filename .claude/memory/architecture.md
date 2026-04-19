# Architecture Reference — Healthcare Digital FTE
# Read when: making structural changes, adding new components

## Data Flow
```
CLINICAL NOTE (FHIR DocumentReference)
    │
    ▼
NLPPipeline.analyze()          src/nlp/pipeline.py
(section_parser→ner→negation→temporal)
    │
    ▼
CodingAgent (7-step pipeline)  src/agents/coding_agent.py
NLP→LLM→parse→rules→sort→cap→return
    │
    ├──► CDIAgent               src/agents/cdi_agent.py
    │    detect_opportunities (KDIGO thresholds, deterministic)
    │    analyze (LLM query generation)
    │
    ├──► DRGAgent               src/agents/drg_agent.py
    │    generate_narrative (CFO-facing plain English)
    │
    └──► CodingAnalysisResult   src/core/models/coding.py
         (suggestions + CDI queries + DRG narrative)
             │
             ▼
         Coder Review API       src/api/
         GET  /queue
         GET  /review/{id}
         POST /review/{id}/approve  ← HMAC token required
             │
             ▼
         FHIR Claim (status=draft → human approves → active)
```

## Key Components

| Component | File | Purpose |
|---|---|---|
| ICD10RulesEngine | src/core/icd10/rules_engine.py | Excludes1, uncertain dx, DRG impact |
| ICD10DataLoader | src/core/icd10/data_loader.py | Embedded CC/MCC, paired codes, DRG weights |
| DRGGrouper | src/core/drg/grouper.py | calculate_drg, calculate_impact |
| FHIRClient | src/core/fhir/client.py | get/write resources, DegradedResult on all failures |
| FHIRAuthenticator | src/core/fhir/auth.py | SMART on FHIR JWT assertion |
| ApprovalTokenService | src/api/security/approval_token.py | HMAC-SHA256, 15-min, single-use |

## Guardrail Modules

| Module | Guardrail | Rule |
|---|---|---|
| src/core/guardrails/claim_guardrail.py | G-HARD-001 | Single-use HMAC approval token |
| src/core/guardrails/evidence_guardrail.py | G-HARD-002 | Evidence citation required |
| src/core/guardrails/icd10_guardrail.py | G-HARD-003/004 | Excludes1 + uncertain dx |
| src/api/middleware/phi_filter.py | G-HARD-005 | PHI blocklist in logs |
| src/core/guardrails/fhir_audit_guardrail.py | G-HARD-006 | Audit FHIR writes |
| src/core/guardrails/confidence_guardrail.py | G-HARD-007 | Confidence threshold |
| src/core/guardrails/copy_forward_guardrail.py | G-SOFT-002 | Copy-forward detection |
| src/core/guardrails/specificity_guardrail.py | G-SOFT-003 | Conservative code selection |
| src/core/guardrails/drg_guardrail.py | G-SOFT-003 | $5k compliance threshold |
| src/core/guardrails/cdi_guardrail.py | G-SOFT-005 | CDI escalation |

## MCP Tools

| Tool | File | Returns |
|---|---|---|
| mcp_icd10_lookup | src/mcp/icd10_tools.py | CC/MCC status for a code |
| mcp_excludes1_check | src/mcp/icd10_tools.py | Excludes1 conflict check |
| mcp_drg_calculate | src/mcp/drg_tools.py | DRGResult for a code set |
| mcp_drg_impact | src/mcp/drg_tools.py | DRGImpact (revenue delta) |
| mcp_fhir_get_encounter | src/mcp/fhir_tools.py | FHIREncounter |
| mcp_fhir_get_clinical_notes | src/mcp/fhir_tools.py | List[FHIRDocumentReference] |
| mcp_fhir_get_recent_labs | src/mcp/fhir_tools.py | List[FHIRObservation] |

## Prompts (versioned constants)

| File | PHR | Current Version |
|---|---|---|
| src/prompts/coding_extraction.py | PHR-001 | CODING_EXTRACTION_V1_0 |
| src/prompts/cdi_query.py | PHR-002 | CDI_QUERY_V1_0 |
| src/prompts/drg_analysis.py | PHR-003 | DRG_ANALYSIS_V1_0 |
| src/prompts/appeal_letter.py | PHR-004 | (not yet implemented) |

## File Structure
```
healthcare-fte/
├── constitution.md, claude.md
├── docs/adr/          ← 14 ADRs + README
├── docs/phr/          ← PHR-001..004 + template
├── docs/research/     ← DISC-001..005
├── specs/             ← 00..07 specs
├── src/
│   ├── agents/        ← coding_agent.py, cdi_agent.py, drg_agent.py
│   ├── benchmarks/    ← mimic_loader.py, mimic_benchmark.py
│   ├── core/
│   │   ├── icd10/     ← rules_engine.py, data_loader.py, validator.py
│   │   ├── fhir/      ← client.py, auth.py, resources.py
│   │   ├── drg/       ← grouper.py
│   │   ├── models/    ← 8 Pydantic model files
│   │   └── guardrails/ ← 8 guardrail modules + exceptions.py
│   ├── nlp/           ← pipeline.py, section_parser.py, ner.py, negation.py, temporal.py
│   ├── prompts/       ← coding_extraction.py, cdi_query.py, drg_analysis.py, appeal_letter.py
│   ├── mcp/           ← icd10_tools.py, fhir_tools.py, drg_tools.py
│   └── api/
│       ├── main.py
│       ├── routes/    ← health.py, coding.py
│       └── middleware/ ← auth.py, audit.py, phi_filter.py
├── tests/
│   ├── clinical/      ← compliance, MIMIC, known-cases benchmarks (written FIRST)
│   ├── unit/
│   ├── integration/
│   └── fixtures/known_cases/cases.py
├── scripts/           ← bash only
├── data/icd10/, data/drg/, data/mimic/ (gitignored)
├── .env.example, pyproject.toml, uv.lock
```

## Tech Stack
- Python 3.10+, strict type hints everywhere
- uv (never pip), FastAPI, Pydantic v2, pytest + pytest-asyncio, structlog
- LLM: claude-sonnet-4-6 (default), claude-opus-4-6 (complex reasoning)
- Functions always under 40 lines
