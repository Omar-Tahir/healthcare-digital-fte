# Architecture Decision Records — Index

**Purpose:** Track all architectural decisions and research milestones
for the Healthcare Digital FTE project.

---

## Research Completed

| ID | Title | Status | Date |
|----|-------|--------|------|
| DISC-001 | ICD-10 Official Guidelines | COMPLETE | 2026-03-30 |
| DISC-002 | Documentation Failure Patterns | COMPLETE | 2026-04-01 |
| Key finding: 32.9% of admissions have clinical evidence without corresponding ICD codes, representing $22.7M annual lost revenue at a single institution (PMC11520144) |
| DISC-003 | FHIR R4 Implementation Edge Cases | COMPLETE | 2026-04-01 |
| Key finding: FHIR Claim write is not supported by major EHRs — coding output must use EHR encoder UI integration with human-in-the-loop, not direct FHIR write-back |
| DISC-004 | Payer Denial Patterns and Prior Auth Rules | COMPLETE | 2026-04-01 |
| Key finding: 15-20% of claims denied initially, 65% never appealed despite 40-70% overturn rate — NCCI edits and timely filing checks are deterministic and implementable in Phase 1 |
| DISC-005 | Competitor Technical Architecture Analysis | COMPLETE | 2026-04-01 |
| Key finding: No competitor implements ICD-10 guidelines as hard constraints or closes the CDI→Coding→DRG loop — 12 technical gaps identified as differentiation opportunities |

---

## Architecture Decisions

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | FHIR R4 Over HL7v2 for EHR Integration | ACCEPTED | 2026-03-30 |
| ADR-002 | No Autonomous Claim Submission | ACCEPTED | 2026-03-30 |
| ADR-003 | Claude as Primary LLM Provider | ACCEPTED | 2026-03-30 |
| ADR-004 | ICD-10 Guidelines as Hard Constraints | ACCEPTED | 2026-03-30 |
| ADR-005 | HIPAA-Compliant Logging Architecture | ACCEPTED | 2026-03-30 |
| ADR-006 | Rules Engine Hard Constraints Architecture | ACCEPTED | 2026-04-01 |
| ADR-007 | Proactive (Concurrent) CDI Over Reactive CDI | ACCEPTED | 2026-04-01 |
| ADR-008 | Guardrails as Architectural Primitives | ACCEPTED | 2026-04-01 |
| ADR-009 | Prompts as Clinical Knowledge Artifacts | ACCEPTED | 2026-04-01 |
| ADR-010 | HTMX for Coder Review UI | ACCEPTED | 2026-04-02 |
| ADR-011 | Phase Gate Verification (DESIGN → BUILD) | ACCEPTED | 2026-04-02 |
| ADR-012 | Research Verification Policy | ACCEPTED | 2026-04-05 |
| ADR-013 | MIMIC-IV Benchmark Design | ACCEPTED | 2026-04-08 |
| ADR-014 | LLM Provider Abstraction Layer | ACCEPTED | 2026-04-13 |

---
