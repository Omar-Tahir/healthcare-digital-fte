# ADR-011: Phase Gate Verification — DESIGN → BUILD

**Status:** ACCEPTED  
**Date:** 2026-04-02  
**Author:** Claude (AI Engineering Partner)  
**Context:** VERIFY-001, VERIFY-002, VERIFY-003 results

---

## Decision

The DESIGN phase is complete. BUILD phase is approved to begin.

## Verification Results

### VERIFY-001: Spec Completeness Check

All 7 specifications verified complete:

| Spec | Status | Date |
|------|--------|------|
| DESIGN-000: System Overview | COMPLETE | 2026-04-02 |
| DESIGN-001: Coding Rules Engine | COMPLETE | 2026-04-01 |
| DESIGN-002: CDI Intelligence Layer | COMPLETE | 2026-04-01 |
| DESIGN-003: Compliance Guardrail Architecture | COMPLETE | 2026-04-01 |
| DESIGN-004: Prompt Engineering Architecture | COMPLETE | 2026-04-01 |
| DESIGN-005: FHIR Integration | COMPLETE | 2026-04-02 |
| DESIGN-006: Coder Review UI | COMPLETE | 2026-04-02 |

### VERIFY-002: Cross-Reference Integrity

- All ADR references in specs point to existing ADRs
- All constitution Article references verified
- All inter-spec references (DESIGN-00X) verified
- All DISC research references verified
- Skills ↔ Spec cross-references validated

### VERIFY-003: Build Readiness Audit

**Developer Test:** 7/7 specs pass 10-point check  
**Test Writability:** 15/15 named tests writable from specs  
**Skills Completeness:** 6/6 skills pass 4-point check  
**MCP Readiness:** Interfaces defined in specs and skills;
implementations are BUILD phase deliverables

**Critical gaps found:** None blocking BUILD.

**Non-blocking gap:** `src/mcp/` contains only `__init__.py`.
MCP tool implementations (icd10_tools.py, fhir_tools.py,
drg_tools.py) will be built as BUILD-008 in the build
sequence after the core engines they wrap are implemented.

## BUILD Phase Sequence

The following build sequence is approved:

```
BUILD-001: Compliance guardrail tests (write FIRST — TDD red)
BUILD-002: Pydantic domain models (all specs)
BUILD-003: ICD-10 rules engine (DESIGN-001)
BUILD-004: NLP pipeline (section parser, NER, negation, temporal)
BUILD-005: Coding agent + PROMPT-001 (DESIGN-004)
BUILD-006: CDI agent + PROMPT-002 (DESIGN-002, DESIGN-004)
BUILD-007: DRG agent + PROMPT-003 (DESIGN-004)
BUILD-008: MCP tools (DESIGN-004 + Skills)
BUILD-009: FHIR client (DESIGN-005)
BUILD-010: Coder review UI (DESIGN-006)
BUILD-011: Integration tests + MIMIC-IV benchmark
```

**Build rules:**
- Compliance tests (BUILD-001) are written before any
  implementation code (Constitution Article I.2)
- Each BUILD step follows TDD: red → green → refactor
- Each BUILD step references its spec, not improvisation
- Use claude-sonnet-4-6 for build phase code generation
- Use claude-opus-4-6 for complex reasoning and architecture

## Consequences

- No further DESIGN work is needed for Phase 1
- Any design changes during BUILD require an ADR amendment
- BUILD-001 starts immediately after this ADR is accepted
- Phase 1 exit criteria defined in DESIGN-000 §4

## References

- Constitution Article IV.4 (Phase Discipline)
- specs/README.md (spec index)
- docs/skills/README.md (skills index)
- docs/adr/README.md (ADR index)
