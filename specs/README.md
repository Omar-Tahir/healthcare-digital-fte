# Specifications — Index

**Purpose:** Track all design specifications for the
Healthcare Digital FTE system.

---

## Specification Status

| ID | Title | Status | Date |
|----|-------|--------|------|
| DESIGN-000 | System Overview | COMPLETE | 2026-04-02 |
| DESIGN-001 | Coding Rules Engine | COMPLETE | 2026-04-01 |
| DESIGN-002 | CDI Intelligence Layer | COMPLETE | 2026-04-01 |
| DESIGN-003 | Compliance Guardrail Architecture | COMPLETE | 2026-04-01 |
| DESIGN-004 | Prompt Engineering Architecture | COMPLETE | 2026-04-01 |
| DESIGN-005 | FHIR Integration | COMPLETE | 2026-04-02 |
| DESIGN-006 | Coder Review UI | COMPLETE | 2026-04-02 |
| DESIGN-007 | MIMIC-IV Accuracy Benchmark | COMPLETE | 2026-04-08 |
| DESIGN-008 | End-to-End Performance Benchmark | COMPLETE | 2026-04-27 |
| DESIGN-009 | Epic End-to-End Coding Pipeline | COMPLETE | 2026-04-27 |

---

## Specification Template

Each spec follows this structure:

1. **Purpose** — What this component does and why it exists
2. **Data Structures** — Pydantic models for inputs and outputs
3. **Logic** — Validation rules, detection algorithms, or
   pipeline steps with pseudocode
4. **Edge Cases** — Scenarios that are hard to get right
5. **Performance Requirements** — Latency and throughput targets
6. **Testing Strategy** — Test categories and coverage requirements

---

## Dependencies

```
DESIGN-001 (Coding Rules Engine)
    ← No dependencies
    → Used by DESIGN-002, DESIGN-003, DESIGN-004

DESIGN-002 (CDI Intelligence Layer)
    ← Depends on DESIGN-001 (DRG impact calculation)
    → Used by DESIGN-003, DESIGN-004

DESIGN-003 (Compliance Guardrail Architecture)
    ← Depends on DESIGN-001, DESIGN-002
    → Used by DESIGN-004

DESIGN-004 (Prompt Engineering Architecture)
    ← Depends on DESIGN-001, DESIGN-002, DESIGN-003
    → Standalone (prompts reference all other specs)

DESIGN-005 (FHIR Integration)
    ← No spec dependencies (data source layer)
    → Used by DESIGN-001, DESIGN-002

DESIGN-006 (Coder Review UI)
    ← Depends on DESIGN-001, DESIGN-002, DESIGN-003
    → Standalone (presentation layer)
```
