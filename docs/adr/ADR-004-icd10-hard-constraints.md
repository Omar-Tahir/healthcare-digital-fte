# ADR-004: ICD-10 Guidelines as Hard Constraints

**Status:** ACCEPTED
**Date:** 2026-03-30
**Decision makers:** Engineering team
**Constitution references:** Article II.3 (ICD-10 Hard Constraints)

---

## Context

ICD-10-CM Official Coding Guidelines (150+ pages from CMS)
define mandatory rules for medical code assignment: Excludes 1
mutual exclusion, sequencing rules, combination codes,
outpatient uncertain diagnosis prohibition, and more.

These rules could be implemented as:
- (a) Soft suggestions the LLM tries to follow in its prompt
- (b) Post-processing filters that fix LLM output
- (c) Hard architectural constraints enforced by a deterministic
  rules engine that halts the pipeline on violation

LLMs achieve <50% exact match on full-code ICD-10 prediction
tasks (33.9% for GPT-4 per DISC-005). Relying on the LLM alone
for guideline compliance is insufficient.

---

## Decision

**ICD-10 guidelines are HARD CONSTRAINTS enforced by a
deterministic rules engine. They are NOT configurable, NOT
overridable by administrators, NOT dependent on LLM compliance.**

Specifically:

1. **Rules engine** (DESIGN-001) validates every suggestion
   set through a 9-step pipeline before results reach the
   coder review interface
2. **Violations** raise `CodingGuidelineViolationError` —
   a hard stop that prevents the suggestion set from reaching
   any user
3. **CRITICAL and HIGH severity violations** make the
   suggestion set invalid (`is_valid = False`). The coding
   agent must resolve violations and resubmit.
4. **Key hard constraints:**
   - Excludes 1 pairs can NEVER coexist (RULE-EX1-001)
   - Outpatient uncertain diagnoses are NEVER coded as
     confirmed (RULE-SET-001)
   - Manifestation codes are NEVER principal (RULE-SEQ-004)
   - Evidence quotes must be verbatim substrings of the
     source note (G-HARD-002)
5. **Annual update process** — CMS releases new ICD-10 codes
   each October 1. The rules engine data tables (Excludes
   pairs, CC/MCC designations, DRG weights) are updated
   annually from CMS public data.

---

## Alternatives Considered

### Alternative 1: LLM-Only Enforcement

Include all ICD-10 rules in the prompt and trust the LLM
to follow them.

**Rejected because:**
- LLMs achieve <50% exact match on ICD-10 coding tasks
  (DISC-005) — cannot guarantee zero Excludes 1 violations
- Prompt-only enforcement is probabilistic, not deterministic.
  The same input may produce different rule compliance across
  runs.
- No audit trail for "the LLM followed the rule" — only
  for "the rules engine verified compliance"
- A single Excludes 1 violation submitted to a payer triggers
  automatic denial and may trigger fraud investigation

### Alternative 2: Configurable Rules Engine

Implement rules as configurable settings that administrators
can adjust per facility.

**Rejected because:**
- Excludes 1 is a clinical fact — E10 and E11 are mutually
  exclusive regardless of facility preference. There is no
  legitimate reason to make this configurable.
- Configurability creates compliance gaps — an administrator
  could inadvertently disable a safety rule
- Configuration drift across facilities makes testing and
  auditing impractical
- Exception: facility-specific charge master mappings and
  payer-specific rules ARE configurable (they genuinely vary).
  ICD-10 coding guidelines do not.

### Alternative 3: Post-Hoc Audit Without Enforcement

Let all suggestions through and audit for compliance
after submission.

**Rejected because:**
- Catching violations after claim submission is too late
  for FCA defense — the false claim has already been made
- Post-hoc correction requires claim resubmission, which
  triggers payer scrutiny
- OIG audits examine whether the system prevented violations,
  not whether it detected them after the fact

---

## Consequences

### Positive

1. **Zero tolerance for known violations** — Excludes 1,
   outpatient uncertain dx, manifestation-as-principal are
   architecturally impossible in system output
2. **Deterministic behavior** — same input always produces
   same validation result (unlike LLM-only approach)
3. **Fast validation** — <200ms for a 15-code set (Section 6
   of DESIGN-001), no LLM call needed
4. **Auditable** — every validation result is logged with
   rule IDs, enabling compliance audit
5. **Testable** — 100% test coverage required (Constitution
   Article I.2), every rule has explicit PASS and FAIL cases

### Negative

1. **LLM regeneration cost** — suggestions that violate rules
   are rejected, requiring the coding agent to fix and
   resubmit. Adds latency (~1-3 seconds per retry).
2. **Annual maintenance** — rules engine data tables require
   update when CMS releases new ICD-10 codes (October 1
   each year). Mitigation: CMS publishes data in standard
   formats; update is semi-automated.
3. **Complex implementation** — sepsis sequencing alone has
   5 variants (POA, not POA, postprocedural, obstetrical,
   newborn). Mitigation: each variant is a separate,
   testable rule.

---

## References

- Constitution Article II.3 (ICD-10 Hard Constraints)
- DESIGN-001 (Coding Rules Engine Specification)
- DISC-001 (ICD-10 Official Guidelines)
- DISC-005 (Competitor Analysis — LLM accuracy benchmarks)
- CMS ICD-10-CM Official Guidelines for Coding and Reporting
