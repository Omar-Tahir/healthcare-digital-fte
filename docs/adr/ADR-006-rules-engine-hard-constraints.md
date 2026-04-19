# ADR-006: ICD-10 Rules Engine Hard Constraints Architecture

**Status:** ACCEPTED  
**Date:** 2026-04-01  
**Decision makers:** Engineering team  
**Constitution references:** Article II.3 (ICD-10 Hard Constraints), Article II.6 (Conservative Defaults)

---

## Context

We are building the ICD-10 coding rules engine
(`src/core/icd10/rules_engine.py`) that validates every
AI-generated code suggestion before it reaches the coder
review interface.

A fundamental architectural decision must be made: should
ICD-10-CM Official Coding Guidelines be encoded as **hard
constraints** (violations raise errors, block output) or
as **soft suggestions** (violations produce warnings, AI
can override)?

Every competitor in the market treats coding guidelines as
soft rules that the model "learns" from training data
(DISC-005). No competitor implements guidelines as
deterministic hard constraints enforced by a rules engine
separate from the AI model.

---

## Decision

**ICD-10-CM Official Coding Guidelines are encoded as hard
constraints in a deterministic rules engine that runs
independently of the LLM.**

Specifically:

1. **Validation is separate from suggestion.** The LLM
   (Claude) generates code suggestions. A separate rules
   engine validates them. The rules engine has veto power
   over the LLM.

2. **CRITICAL and HIGH violations are hard stops.** When
   the rules engine detects a violation at CRITICAL or HIGH
   severity, it raises `CodingGuidelineViolationError`.
   The suggestion set does not reach the coder interface.
   The coding agent must fix the violations and resubmit.

3. **Guidelines are not configurable.** There is no admin
   panel to disable Excludes 1 checking. There is no feature
   flag to allow outpatient uncertain diagnosis coding.
   There is no override token. The rules are the rules.

4. **The rules engine is deterministic.** Given the same
   code set and encounter setting, the rules engine always
   produces the same validation result. No randomness, no
   model inference, no probabilistic reasoning.

---

## Alternatives Considered

### Alternative 1: Soft Suggestions (Warnings Only)

The rules engine detects violations but only produces
warnings. The LLM or the coder can override any warning.

**Rejected because:**

- When overrides are possible, they will be used. Coders
  under time pressure will dismiss warnings. This is
  documented behavior in clinical decision support
  literature — alert fatigue causes 49-96% of alerts to
  be overridden (DISC-002 Section E).
- A system that CAN produce incorrect coding WILL produce
  incorrect coding at scale. With 100 coders processing
  50 charts/day, even a 1% override-error rate produces
  50 incorrect claims per day.
- Hospital legal teams evaluating our system for purchase
  will ask: "Can the system generate a coding guideline
  violation?" If the answer is "yes, but we show a warning,"
  the procurement review fails. If the answer is "no, it is
  architecturally impossible," we pass.
- FCA liability: the False Claims Act imposes penalties of
  $13,946-$27,894 per false claim. A system that allows
  Excludes 1 violations to reach claim submission is a
  liability, not a product.

### Alternative 2: LLM-Only Validation (No Separate Engine)

The LLM is prompted to check its own suggestions against
coding guidelines. No separate rules engine exists.

**Rejected because:**

- LLMs are probabilistic. They will sometimes miss
  violations, especially for rare edge cases outside their
  training distribution (DISC-005: "guideline violations
  occur when the model encounters edge cases outside its
  training distribution").
- NEJM AI (2024) found GPT-4 achieved < 50% exact match
  for ICD-10-CM codes, with frequent Excludes 1 violations
  and missing Code First instructions (DISC-001 Section G.5).
- Deterministic rules must be checked by deterministic code,
  not by probabilistic inference.
- A rules engine is auditable — a hospital can inspect the
  rule logic. An LLM's internal reasoning is not auditable.
- The rules engine runs in < 50ms. Adding validation to
  the LLM prompt increases latency by 5-10 seconds and
  token cost by 2-5x.

### Alternative 3: Hybrid (Hard Constraints for Safety, Soft for Optimization)

CRITICAL violations (Excludes 1, outpatient uncertain dx)
are hard stops. HIGH violations (sequencing, combinations)
are warnings.

**Partially adopted:** This is close to our approach, but we
extend hard stops to include HIGH violations as well. The
reasoning: sequencing errors and missed combination codes
are not merely optimization issues — they directly affect
DRG assignment and can constitute incorrect billing. A
missed E11.22 → E11.9 substitution is not a "suggestion"
— it is a coding error that misrepresents the clinical
situation.

The distinction we DO make: MEDIUM and LOW items are
informational (warnings and suggestions) that display to
the coder but do not block. This preserves coder autonomy
for documentation-quality issues while preventing coding-
rule violations.

---

## Consequences

### Positive

1. **Compliance moat.** Competitors who treat guidelines
   as soft rules cannot match our compliance posture without
   rebuilding their architecture. This is not a feature
   toggle — it is a fundamental design choice that permeates
   every component.

2. **Hospital procurement advantage.** Legal teams can
   audit our rules engine and verify that guideline
   violations are architecturally impossible. This
   accelerates procurement cycles by 2-4 months vs
   competitors who must demonstrate compliance through
   statistical testing.

3. **FCA risk elimination.** The system cannot submit a
   claim with an Excludes 1 violation, an outpatient
   uncertain diagnosis, or a manifestation code as
   principal. This is not a policy — it is a technical
   guarantee enforced by code.

4. **Deterministic auditability.** Every validation result
   is reproducible. Given the same inputs, the same output
   is produced. This satisfies audit requirements and
   enables regression testing.

5. **Separation of concerns.** The LLM focuses on clinical
   understanding and code suggestion. The rules engine
   focuses on guideline compliance. Neither needs to be
   good at the other's job.

6. **Performance.** Rules engine validation (< 50ms) is
   orders of magnitude faster than LLM re-evaluation.

### Negative

1. **False positives block legitimate suggestions.** If the
   rules engine has a bug that incorrectly flags a valid
   code combination, it blocks a correct suggestion. This
   is mitigated by comprehensive testing (100% compliance
   test coverage per constitution Article I.2) and the
   annual update cycle aligned with CMS FY releases.

2. **Annual maintenance burden.** The rules engine must be
   updated annually when CMS publishes new ICD-10-CM
   guidelines, code tables, and CC/MCC lists. This is a
   fixed cost (~2 weeks of engineering per annual update).

3. **Rigidity.** Edge cases that are ambiguous in the
   guidelines cannot be handled flexibly. The system will
   block or pass — it cannot say "this is a gray area."
   Mitigation: ambiguous cases route to CDI query
   generation per constitution Article II.6 (conservative
   defaults).

4. **Code First / Use Additional data dependency.** The
   rules engine requires a complete mapping of Code First
   and Use Additional instructions from the Tabular List.
   This data must be extracted from CMS publications and
   maintained. Incomplete data means incomplete validation.

---

## Implementation Notes

- Rules engine lives in `src/core/icd10/rules_engine.py`
- Data models in `src/core/icd10/models.py`
- Code table and Excludes data in `data/icd10/`
- Validation pipeline defined in spec
  `specs/01-coding-rules-engine.md`
- `CodingGuidelineViolationError` is a hard stop — never
  caught silently (constitution Article II.3)
- Compliance tests written FIRST, before implementation
  (constitution Article I.2)

---

## References

- Constitution Article II.3 (ICD-10 Hard Constraints)
- Constitution Article II.6 (Conservative Defaults)
- ADR-004 (ICD-10 Hard Constraints — the constitutional
  basis; this ADR documents the implementation architecture)
- DISC-001 (ICD-10 Official Guidelines — the rules being
  encoded)
- DISC-002 (Documentation Failure Patterns — the errors
  being caught)
- DISC-005 (Competitor Analysis — why no competitor does
  this)
- `specs/01-coding-rules-engine.md` (the full specification)
