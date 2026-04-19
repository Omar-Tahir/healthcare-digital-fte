# ADR Index — Healthcare Digital FTE
# Read when: making architectural decisions (check here before deciding)
# Full files: docs/adr/ADR-NNN-*.md

| ADR | Title | Decision |
|---|---|---|
| ADR-001 | FHIR over HL7v2 | Use FHIR R4 for all EHR integration; HL7v2 not supported |
| ADR-002 | No Autonomous Claims | Claims require human approval token; never auto-submit |
| ADR-003 | Claude as LLM | Anthropic Claude API; sonnet-4-6 default, opus-4-6 for reasoning |
| ADR-004 | ICD-10 Hard Constraints | ICD-10 guidelines enforced as code constraints, not prompts |
| ADR-005 | HIPAA Logging | structlog only; PHI blocklist enforced; encounter_id OK, names never |
| ADR-006 | Rules Engine Hard Constraints | Guardrails are architectural, not LLM-configurable |
| ADR-007 | CDI Proactive Approach | CDI detects opportunities before coding, not after denial |
| ADR-008 | Guardrails as Architecture | All 12 guardrails implemented as importable Python modules |
| ADR-009 | Prompts as Clinical Knowledge | Prompts in src/prompts/ as versioned constants with PHR |
| ADR-010 | HTMX for Coder UI | HTMX + FastAPI for coder review interface (no React) |
| ADR-011 | Phase Gate Verification | Each BUILD step verified with passing tests before next starts |
| ADR-012 | Research Verification Policy | All DISC stats must be cited to primary source; no unverified claims |
| ADR-013 | MIMIC Benchmark Design | MIMIC-IV as accuracy benchmark; PhysioNet credentials required |
| ADR-014 | LLM Provider Abstraction | Thin abstraction layer for LLM calls to allow future provider swap |
