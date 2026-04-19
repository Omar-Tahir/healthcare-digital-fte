# ADR-008: Compliance Guardrails as Architectural Primitives

**Status:** ACCEPTED  
**Date:** 2026-04-01  
**Decision makers:** Engineering team  
**Constitution references:** Article II (all clauses — Safety Law)

---

## Context

Every healthcare AI system must prevent harmful outputs.
The question is how: as application-level features that
can be configured, disabled, or bypassed — or as
architectural primitives that are structurally embedded
in the execution pipeline and cannot be removed without
rewriting the system.

Our system handles ICD-10 code suggestions, CDI physician
queries, DRG revenue calculations, and clinical claim
data. Every output carries False Claims Act liability
($13,946-$27,894 per false claim), HIPAA penalty exposure
($100-$50,000 per violation, up to $1.5M per category
per year), and patient safety implications.

We must decide whether compliance guardrails are features
or architecture.

---

## Decision

**Compliance guardrails are architectural primitives, not
features. They are implemented as middleware layers in
the execution pipeline that every request passes through.
They cannot be disabled by configuration, feature flags,
admin panels, or API parameters.**

Specifically:

1. **Hard guardrails are middleware.** They execute
   synchronously in the request pipeline. No output
   reaches any user or external system without passing
   through every hard guardrail. There is no code path
   that bypasses them.

2. **Guardrails are not configurable.** There is no admin
   panel to disable G-HARD-003 (Excludes 1 checking).
   There is no environment variable to skip G-HARD-001
   (human approval requirement). There is no feature
   flag to relax G-HARD-005 (PHI in logs). The only
   way to change a hard guardrail is to change the
   source code, which requires code review, test
   coverage, and — per Constitution Article VI.2 —
   explicit written rationale addressing the specific
   compliance risk.

3. **Guardrail failure is treated as guardrail violation.**
   If a guardrail middleware crashes (not a violation
   detection, but an actual runtime error), the request
   is blocked. The fail-safe mode is deny, not allow.
   "When the guardrail breaks, the gate stays closed."

4. **Guardrails are tested with 100% coverage.** Every
   hard guardrail has unit tests that verify both
   violation detection and pass-through. These tests
   run in CI on every commit. Guardrail test failure
   blocks deployment.

5. **Guardrail registry enforces completeness.** At
   system startup, a registry verifies that every
   registered guardrail is loaded and active. If any
   hard guardrail fails to load, the system refuses
   to start.

---

## Alternatives Considered

### Alternative 1: Feature-Flag Guardrails

Guardrails are implemented as features that can be toggled
via configuration. Administrators can enable/disable
specific guardrails per deployment or per client.

**Rejected because:**

- **Configuration drift creates liability.** If a client
  asks to "relax" Excludes 1 checking for their workflow,
  and we provide a flag to do so, every claim processed
  with that flag carries FCA liability. The flag's existence
  is itself a compliance risk because it demonstrates
  capability to bypass a safety control.

- **Feature flags are discoverable.** In an OIG audit or
  FCA qui tam lawsuit, the discovery process will reveal
  that the system has the ability to bypass coding
  guidelines. "We had the capability to skip validation
  but chose not to" is a weaker legal position than "the
  system is architecturally incapable of skipping
  validation."

- **Human nature.** If a flag exists, it will eventually
  be toggled. Under deadline pressure, during a system
  issue, or at a client's request. The only reliable way
  to prevent bypass is to make bypass impossible.

### Alternative 2: Application-Layer Validation

Guardrails are implemented as validation functions called
by business logic. Each component is responsible for
calling the appropriate validation before its output.

**Rejected because:**

- **Inconsistent enforcement.** When validation is opt-in
  (each component must call it), some code paths will miss
  it. A new endpoint, a batch processing job, a debug
  utility — all become potential bypass vectors.

- **Refactoring risk.** When code is refactored, validation
  calls can be accidentally removed or moved. Middleware
  enforcement is independent of business logic structure.

- **Testing burden.** Each component must be tested both
  with and without validation. With middleware, the
  validation is tested once at the pipeline level.

### Alternative 3: Post-Processing Validation

All output is generated freely, then a final validation
step checks everything before it reaches the user.
Violations are caught at the last moment.

**Partially adopted for monitoring guardrails only.**
Post-processing alone is rejected for hard guardrails
because:

- **Wasted computation.** Processing a full coding
  analysis only to reject it at the end wastes resources.
  Middleware catches violations early, at the layer
  where they originate.

- **Error feedback quality.** A middleware guardrail
  at the rules engine layer can say "Excludes 1 violation
  between E10 and E11." A post-processing guardrail at
  the output layer can only say "output validation failed"
  without layer-specific context.

- **Monitoring guardrails are post-processing by nature.**
  G-MON-001 through G-MON-005 analyze aggregate patterns
  over time, which inherently requires post-processing.
  This is appropriate for their purpose.

---

## Consequences

### Positive

1. **Hospital-grade trust floor.** When a hospital
   procurement team asks "can your system generate an
   Excludes 1 violation?", our answer is "no, it is
   architecturally impossible." This is a stronger
   statement than "no, our model has been trained not
   to." The former is a provable technical property.
   The latter is a statistical claim.

2. **FCA defense.** In a False Claims Act investigation,
   the system's architecture demonstrates that certain
   violations are structurally impossible. This is
   powerful evidence of compliance good faith. The audit
   trail shows every guardrail check, every human
   approval, and every compliance review.

3. **Competitor differentiation.** No competitor in our
   analysis (DISC-005) implements coding guidelines as
   hard architectural constraints. Nym Health uses
   rule-based validation but it is configurable.
   Iodine Software flags documentation gaps but does
   not enforce coding rules. Our guardrail architecture
   creates a compliance moat that requires fundamental
   re-architecture to replicate.

4. **Developer safety.** Engineers building new features
   cannot accidentally create a code path that bypasses
   compliance checks. The middleware catches violations
   regardless of what business logic produces. This
   reduces the compliance knowledge required of every
   developer.

5. **Predictable degradation.** The fail-closed design
   means that guardrail failures are always visible.
   A broken guardrail blocks requests rather than
   silently allowing violations. This makes failures
   obvious and urgent, not hidden and cumulative.

### Negative

1. **Rigidity.** Legitimate edge cases that a human
   would handle with judgment cannot be processed
   through the system if they trigger a hard guardrail.
   Mitigation: the system degrades to manual mode,
   where the human coder processes the case without
   AI assistance. The guardrail doesn't block the
   human — it blocks the AI from contributing to
   that specific case.

2. **False positive blocking.** A bug in guardrail
   logic (e.g., an incorrect Excludes 1 pair in the
   data table) blocks valid suggestions. Mitigation:
   comprehensive testing, annual data table updates
   aligned with CMS releases, and the ability to
   correct data table errors without changing guardrail
   code.

3. **Startup dependency.** The system refuses to start
   if any hard guardrail fails to load. This increases
   deployment risk. Mitigation: guardrail loading is
   tested in staging before production deployment.
   Health check endpoint at `/health` reports guardrail
   status.

4. **Performance overhead.** Every request passes
   through all guardrail layers. Mitigation: guardrails
   are designed for performance (< 5ms each, < 20ms
   total for all hard guardrails). The rules engine
   validation (which includes G-HARD-003 and G-HARD-004)
   targets < 50ms per DESIGN-001.

---

## Implementation Notes

- Guardrail base classes: `src/core/guardrails/base.py`
- Hard guardrails: `src/core/guardrails/hard.py`
- Soft guardrails: `src/core/guardrails/soft.py`
- Monitoring guardrails: `src/core/guardrails/monitoring.py`
- Guardrail registry: `src/core/guardrails/registry.py`
- PHI filter middleware: `src/api/middleware/phi_filter.py`
- Audit logging: `src/core/audit/logger.py`
- FastAPI middleware integration: `src/api/middleware/guardrails.py`
- Full specification: `specs/03-compliance-guardrail-architecture.md`
- Guardrail tests: `tests/clinical/test_compliance_guardrails.py`
  (written FIRST, before implementation)

---

## References

- Constitution Article II (Safety Law — all clauses)
- Constitution Article VI.2 (Amendment bar for safety law)
- ADR-002 (No Autonomous Claims)
- ADR-004 (ICD-10 Hard Constraints)
- ADR-005 (HIPAA Logging)
- ADR-006 (Rules Engine Hard Constraints Architecture)
- DISC-001 (ICD-10 Guidelines — rules being enforced)
- DISC-003 (FHIR Edge Cases — degradation scenarios)
- DISC-004 (Payer Denial Patterns — claim-level risks)
- DISC-005 (Competitor Analysis — no competitor has this)
- `specs/03-compliance-guardrail-architecture.md`
