# DESIGN-000: System Overview

**Status:** COMPLETE  
**Date:** 2026-04-02  
**Author:** Claude (AI Engineering Partner)  
**Constitution references:** Article IV.4 (Phase Discipline),
Article II (Safety Law — all clauses)  
**Scope:** Architectural overview connecting all system components

---

## 1. System Purpose

Healthcare Digital FTE is an AI system that automates medical
coding, clinical documentation improvement (CDI), and revenue
cycle workflows for US hospitals and health systems.

The system replaces the administrative and knowledge-intensive
tasks performed by human coders and CDI specialists — not by
eliminating human review, but by reducing per-chart analysis
time from 15-20 minutes to 2-3 minutes while enforcing ICD-10
compliance that exceeds human consistency.

**Core value proposition:**
- Extract ICD-10-CM/CPT codes from clinical notes with
  evidence citations
- Identify documentation gaps that suppress DRG revenue
- Generate AHIMA-compliant physician queries to close gaps
- Calculate DRG impact of every coding suggestion
- Present all suggestions to a credentialed human coder
  for review and approval before any claim submission

**What this system is NOT:**
- Not an autonomous billing system (Constitution Article II.1)
- Not a clinical decision support tool for patient care
- Not an ambient documentation / ASR system (Phase 4)
- Not a prior authorization engine (Phase 2)

---

## 2. Component Map

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                          │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐     │
│  │ Epic EHR │  │ Cerner   │  │ CMS Public Data       │     │
│  │ FHIR R4  │  │ FHIR R4  │  │ (ICD-10, DRG weights) │     │
│  └────┬─────┘  └────┬─────┘  └──────────┬────────────┘     │
│       │              │                   │                  │
└───────┼──────────────┼───────────────────┼──────────────────┘
        │              │                   │
        ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                         │
│                                                             │
│  ┌──────────────────────────┐  ┌────────────────────────┐   │
│  │ FHIR Client (DESIGN-005)│  │ ICD-10 Data Tables     │   │
│  │ src/core/fhir/           │  │ data/icd10/, data/drg/ │   │
│  │                          │  │                        │   │
│  │ • SMART on FHIR auth     │  │ • Excludes pairs       │   │
│  │ • Token refresh          │  │ • CC/MCC designations  │   │
│  │ • Circuit breaker        │  │ • DRG weights          │   │
│  │ • Vendor abstraction     │  │ • Code descriptions    │   │
│  └────────────┬─────────────┘  └───────────┬────────────┘   │
│               │                            │                │
└───────────────┼────────────────────────────┼────────────────┘
                │                            │
                ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER                          │
│                                                             │
│  ┌─────────────────────┐                                    │
│  │ NLP Pipeline         │                                   │
│  │ src/nlp/             │                                   │
│  │                      │                                   │
│  │ • Section parsing    │                                   │
│  │ • Named entity recog │                                   │
│  │ • Negation detection │                                   │
│  │ • Temporal reasoning │                                   │
│  └──────────┬──────────┘                                    │
│             │                                               │
│             ▼                                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ Coding Agent         │  │ CDI Agent (DESIGN-002)      │   │
│  │ src/agents/          │  │ src/agents/cdi_agent.py     │   │
│  │ coding_agent.py      │  │                             │   │
│  │                      │  │ • Gap detection (SEV, SPEC, │   │
│  │ • Claude API call    │  │   CAUSE, POA categories)    │   │
│  │ • PROMPT-001         │  │ • PROMPT-002 physician      │   │
│  │ • Code extraction    │  │   query generation          │   │
│  │ • Evidence citation  │  │ • AHIMA compliance          │   │
│  └──────────┬──────────┘  └──────────┬──────────────────┘   │
│             │                        │                      │
│             ▼                        │                      │
│  ┌─────────────────────┐             │                      │
│  │ ICD-10 Rules Engine  │            │                      │
│  │ (DESIGN-001)         │            │                      │
│  │ src/core/icd10/      │            │                      │
│  │                      │            │                      │
│  │ • 9-step validation  │            │                      │
│  │ • Excludes 1 check   │            │                      │
│  │ • Sequencing rules   │            │                      │
│  │ • Hard stop on       │            │                      │
│  │   violation           │            │                      │
│  └──────────┬──────────┘             │                      │
│             │                        │                      │
│             ▼                        ▼                      │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ DRG Agent            │  │ MCP Tools (DESIGN-004)      │   │
│  │ src/agents/          │  │ src/mcp/                    │   │
│  │ drg_agent.py         │  │                             │   │
│  │                      │  │ • icd10_tools.py            │   │
│  │ • DRG grouper        │  │ • fhir_tools.py             │   │
│  │ • Revenue impact     │  │ • drg_tools.py              │   │
│  │ • PROMPT-003         │  │                             │   │
│  └──────────┬──────────┘  └─────────────────────────────┘   │
│             │                                               │
└─────────────┼───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GUARDRAIL LAYER (DESIGN-003)              │
│                    src/core/guardrails/                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Hard Guardrails (G-HARD-001 through G-HARD-007)       │   │
│  │ • No claim without human approval token               │   │
│  │ • Evidence quote must be verbatim substring            │   │
│  │ • Excludes 1 pairs never coexist                      │   │
│  │ • Outpatient uncertain dx never coded as confirmed    │   │
│  │ • PHI never in logs                                   │   │
│  │ • Graceful degradation on failure                     │   │
│  │ • All codes must be billable                          │   │
│  └───────────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Soft Guardrails (G-SOFT-001 through G-SOFT-005)       │   │
│  │ Warnings requiring human acknowledgment               │   │
│  └───────────────────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Monitoring Guardrails (G-MON-001 through G-MON-005)   │   │
│  │ Aggregate pattern detection                           │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ FastAPI Application (DESIGN-006)                     │     │
│  │ src/api/                                             │     │
│  │                                                     │     │
│  │ • /queue — worklist of encounters pending review     │     │
│  │ • /review/{id} — three-panel coding review UI       │     │
│  │ • POST /approve — human approval token generation   │     │
│  │ • /health — system health check                     │     │
│  │                                                     │     │
│  │ Frontend: HTMX + server-rendered HTML (ADR-010)     │     │
│  │ No React, no npm, no build step                     │     │
│  │ PHI logging middleware (ADR-005)                     │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow

### 3.1 Primary Coding Flow

```
Step 1: FHIR Client retrieves clinical note
        (DocumentReference + Encounter + Condition + Observation)
        Source: EHR via FHIR R4 REST API
        Auth: SMART on FHIR (OAuth 2.0)

Step 2: NLP Pipeline processes note
        • Section parsing (HPI, Assessment, Plan, etc.)
        • Named entity recognition (conditions, medications)
        • Negation detection ("no evidence of", "denies")
        • Temporal reasoning ("history of" vs active)

Step 3: Coding Agent analyzes processed note
        • Calls Claude API with PROMPT-001
        • Uses MCP tools for ICD-10 lookups (not context injection)
        • Returns CodingSuggestionSet with evidence quotes

Step 4: ICD-10 Rules Engine validates suggestions
        • 9-step validation pipeline (DESIGN-001 Section 3)
        • Excludes 1 check, sequencing rules, billability check
        • Violations → CodingGuidelineViolationError (hard stop)
        • Agent must fix and resubmit

Step 5: CDI Agent identifies documentation gaps
        • Analyzes same note for missing diagnoses
        • Detects severity, specificity, causality, POA gaps
        • Generates AHIMA-compliant physician queries (PROMPT-002)

Step 6: DRG Agent calculates revenue impact
        • Groups validated codes into MS-DRG
        • Calculates base DRG vs optimized DRG
        • Generates narrative for coder (PROMPT-003)

Step 7: Guardrails execute final checks
        • All hard guardrails must pass
        • Soft guardrails generate warnings
        • Results packaged for coder review

Step 8: Coder Review Interface presents results
        • Three-panel layout: note | suggestions | DRG impact
        • Human coder reviews each suggestion
        • Coder approves → human approval token generated
        • Token: HMAC-SHA256, time-limited, hash-bound

Step 9: Coder enters approved codes into EHR encoder
        • System NEVER writes claims directly (Article II.1)
        • EHR's native encoder validates against payer rules
        • Audit log records: who approved, what codes, when
```

### 3.2 Data Flow Constraints

| Constraint | Enforcement | Reference |
|-----------|------------|-----------|
| PHI never in logs | structlog processor strips PHI fields before write | G-HARD-005, ADR-005 |
| Evidence quotes must be verbatim substrings | Validated against source note text | G-HARD-002 |
| No claim without human approval | Cryptographic token required at submission | G-HARD-001, ADR-002 |
| Uncertain dx never confirmed (outpatient) | Rules engine rejects; agent must suggest symptom code | G-HARD-004 |
| Excludes 1 pairs never coexist | Rules engine rejects; agent must resolve | G-HARD-003 |
| Graceful degradation on any failure | DegradedResult returned; coder can work manually | Article II.5 |

---

## 4. Phase Boundaries

### Phase 1 — Coding AI + CDI Intelligence (CURRENT)

**Scope:**
- ICD-10-CM/CPT code extraction from clinical notes
- CDI documentation gap detection and physician queries
- DRG impact calculation and narrative
- Coder review interface with human approval workflow
- FHIR R4 integration with Epic and Cerner
- Compliance guardrail architecture

**Not in Phase 1:**
- Prior authorization automation
- Denial prediction
- Appeal letter generation (prompt designed, not integrated)
- Audio/ASR/ambient documentation
- Patient-facing interfaces
- HL7v2 integration
- Direct claim submission to payers

**Phase 1 exit criteria:**
- All 7 hard guardrails passing with 100% test coverage
- ICD-10 rules engine validating all 12 edge cases (DESIGN-001)
- CDI detection for P0 categories (AKI, Sepsis, HF specificity)
- FHIR client handling Epic and Cerner with graceful degradation
- Coder review UI functional with human approval token flow
- MIMIC-IV benchmark demonstrating coding accuracy

### Phase 2 — Prior Authorization Automation

**Scope:** Automate prior auth submissions using clinical data
already extracted in Phase 1. Requires payer API integration.

### Phase 3 — Denial Prediction + Appeal Generation

**Scope:** Predict claim denials before submission; generate
appeal letters (PROMPT-004) when denials occur. Requires
denial pattern data from Phase 1 deployments.

### Phase 4 — Ambient Documentation (ASR)

**Scope:** Whisper-based audio transcription of clinical
encounters. Feeds into Phase 1 coding pipeline. Requires
Phase 1 revenue to fund GPU infrastructure.

**Phase discipline (Constitution Article IV.4):** No Phase N+1
features are built while Phase N is incomplete. No exceptions.

---

## 5. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | Python 3.10+ with strict type hints | Constitution Article III.1 |
| Package manager | uv | Constitution Article III.2; never pip |
| Web framework | FastAPI | Constitution Article III.8 |
| Data validation | Pydantic v2 | Constitution Article III.4 |
| LLM | Anthropic Claude (Sonnet default, Opus complex) | ADR-003 |
| EHR integration | FHIR R4 REST API | ADR-001 |
| Logging | structlog (no PHI) | ADR-005, Constitution Article III.5 |
| Testing | pytest + pytest-asyncio | Constitution Article I.2 |
| Frontend | HTMX + Jinja2 server-rendered HTML | ADR-010 |
| Environment | Linux/bash (WSL2) | Constitution Article III.3 |

---

## 6. Acceptance Criteria (System Level)

### Safety

- [ ] No code path exists that submits a claim without
      human_approval_token (G-HARD-001)
- [ ] Every AI suggestion includes evidence_quote that is a
      verbatim substring of source note (G-HARD-002)
- [ ] Excludes 1 pairs never appear together in output
      (G-HARD-003)
- [ ] Outpatient uncertain diagnoses never coded as confirmed
      (G-HARD-004)
- [ ] Zero PHI in any log entry under any circumstance
      (G-HARD-005)
- [ ] System continues functioning when any AI component fails
      (Article II.5)

### Accuracy

- [ ] ICD-10 rules engine validates all 12 edge cases from
      DESIGN-001 Section 4
- [ ] CDI detection identifies AKI, Sepsis, and HF specificity
      gaps (P0 categories from DESIGN-002)
- [ ] DRG impact calculation matches CMS MS-DRG grouper for
      test cases

### Integration

- [ ] FHIR client retrieves clinical notes from Epic sandbox
- [ ] FHIR client handles token refresh, rate limits, and
      downtime with graceful degradation
- [ ] Coder review UI displays suggestions in three-panel
      layout with human approval workflow

### Performance

- [ ] ICD-10 validation completes in <200ms for 15-code set
      (DESIGN-001 Section 6)
- [ ] End-to-end coding analysis completes in <30 seconds
- [ ] FHIR API calls complete within rate limits (60-120
      req/min for Epic)

---

## 7. Spec Cross-References

| Spec | Component | Key Interfaces |
|------|-----------|---------------|
| DESIGN-001 | ICD-10 Rules Engine | CodingSuggestionSet → ValidationResult |
| DESIGN-002 | CDI Intelligence Layer | CDIOpportunity → PhysicianQuery |
| DESIGN-003 | Compliance Guardrails | HardGuardrailViolation, DegradedResult |
| DESIGN-004 | Prompt Engineering | PROMPT-001 through PROMPT-004 |
| DESIGN-005 | FHIR Integration | FHIRClient → FHIR resources |
| DESIGN-006 | Coder Review UI | Three-panel layout, human approval token |

---

## References

- Constitution (all Articles)
- ADR-001 through ADR-005, ADR-010
- DISC-001 through DISC-005
- DESIGN-001 through DESIGN-006
