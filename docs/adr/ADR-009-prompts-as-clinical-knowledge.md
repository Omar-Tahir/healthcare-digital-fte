# ADR-009: Prompts as Clinical Knowledge Artifacts

**Status:** ACCEPTED  
**Date:** 2026-04-01  
**Decision makers:** Engineering team  
**Constitution references:** Article I.4 (Prompts Are Preserved),
Article I.5 (Domain Knowledge in Skills),
Article II.2 (Source Citation Required)

---

## Context

Every LLM-powered system has prompts. The question is whether
those prompts are treated as implementation details (like
variable names or formatting choices) or as architectural
artifacts (like database schemas or API contracts).

In our system, prompts encode:
- ICD-10-CM Official Coding Guidelines distilled from 150+
  pages of CMS documentation (DISC-001)
- Documentation failure patterns extracted from peer-reviewed
  literature across 47 studies (DISC-002)
- AHIMA CDI Standards translated into generative constraints
- False Claims Act compliance rules expressed as LLM behavior
- Clinical reasoning patterns (KDIGO criteria, SIRS criteria,
  sepsis sequencing) encoded as extraction logic
- Confidence calibration anchors tuned to downstream guardrail
  thresholds

This knowledge took months to compile in the DISCOVER phase.
A prompt change has the same blast radius as a schema change —
it affects every output downstream.

We must decide how prompts are governed.

---

## Decision

**Prompts are architectural artifacts — clinical knowledge
encoded in executable form. They are versioned, tested,
reviewed, and preserved with the same rigor as database
schemas and API contracts.**

Specifically:

1. **Prompts are versioned constants.** Every prompt lives
   in `src/prompts/` as a named Python constant with a
   version suffix (e.g., `CODING_EXTRACTION_V1_0`). Previous
   versions are preserved in the same file for regression
   testing. There are no inline prompt strings anywhere in
   agent code.

2. **Prompts have history records.** Every prompt has a
   corresponding PHR entry in `docs/phr/` that records
   design decisions, test cases, failure modes, and version
   history. The PHR is updated whenever the prompt changes.

3. **Prompt changes require testing.** A prompt change must
   pass on the MIMIC-IV test set with minimum accuracy
   thresholds before deployment. Compliance metrics (evidence
   grounding rate, Excludes 1 violation rate, outpatient
   uncertain diagnosis rate, AHIMA compliance rate) cannot
   degrade.

4. **Prompt changes require review.** In clinical deployment,
   prompt changes require engineering review (technical),
   HIM/coder review (clinical), and compliance review
   (regulatory). This mirrors the review required for
   changes to clinical decision support rules.

5. **Prompt versions are auditable.** Every LLM call records
   the prompt version used. In an investigation, every
   output can be traced to the exact prompt that produced
   it. Audit records are retained for 7 years per DESIGN-003.

---

## Alternatives Considered

### Alternative 1: Prompts as Implementation Details

Prompts are treated like any other code — edited freely,
stored inline in agent files, versioned only via git history,
no special documentation.

**Rejected because:**

- **Knowledge loss between sessions.** The LLM has no memory
  between sessions. If a prompt encodes a subtle clinical
  rule (e.g., "creatinine rise of 0.3 mg/dL within 48 hours
  meets KDIGO Stage 1") and a future developer modifies
  the prompt without understanding why that threshold exists,
  the clinical accuracy of the system degrades silently.
  PHR entries preserve the "why" behind each design decision.

- **Untestable changes.** Without a testing protocol, prompt
  changes are deployed based on intuition. A change that
  improves accuracy on one case type may degrade accuracy
  on another. The MIMIC-IV benchmark catches regressions
  that spot-checking misses.

- **Audit trail gaps.** If prompt versions are only in git
  history, reconstructing which prompt version was active
  when a specific claim was processed requires git archaeology.
  Explicit version tracking makes this a simple lookup.

- **Competitor replication.** If prompts are undocumented
  implementation details, the clinical knowledge they encode
  exists only in the head of the engineer who wrote them.
  When that engineer leaves, the knowledge leaves. PHR
  entries make prompts organization-owned knowledge.

### Alternative 2: Prompts Managed by Non-Technical Staff

Prompts are managed through a CMS-style interface by clinical
staff (CDI specialists, coders) who understand the domain
but not the code.

**Deferred (not rejected):**

- This is a valid Phase 3+ approach when the system has
  enough clinical users to warrant a prompt management UI.
- In Phase 1, the engineering team has sufficient clinical
  knowledge (from the DISCOVER phase research) to design
  prompts correctly.
- The PHR documentation makes prompts accessible to clinical
  reviewers even without a management UI.

### Alternative 3: Prompt Optimization via Automated Tuning

Use automated prompt optimization techniques (DSPy, prompt
evolution) to find optimal prompts programmatically.

**Deferred (not rejected):**

- Automated optimization requires a large labeled dataset
  (MIMIC-IV benchmark) and a well-defined objective function.
  Both are in development but not available for Phase 1.
- The risk of automated optimization in a healthcare context
  is that it may find prompts that optimize for accuracy
  metrics while violating compliance constraints in subtle
  ways. Human review remains essential.
- Automated optimization is a Phase 2+ enhancement that
  builds on the manual prompt engineering foundation.

---

## Consequences

### Positive

1. **Clinical knowledge preservation.** The DISCOVER phase
   research (DISC-001 through DISC-005) is encoded in
   prompts and preserved in PHR entries. Future developers
   can understand why each prompt design decision was made
   without repeating the research.

2. **Regression prevention.** The testing protocol catches
   prompt changes that degrade accuracy or compliance before
   they reach production. A prompt that breaks Excludes 1
   detection is caught in CI, not in an OIG audit.

3. **Audit trail completeness.** Every claim can be traced
   to the exact prompt version that generated its code
   suggestions. This is powerful FCA defense evidence —
   it demonstrates systematic, documented prompt governance.

4. **Competitive moat.** Competitors cannot replicate our
   prompt architecture without replicating our research.
   The prompts encode clinical knowledge that took months
   to compile from ICD-10 guidelines, peer-reviewed
   literature, and clinical expert consultation. The PHR
   entries document the reasoning chain that produced each
   design decision. Copying the prompt text without
   understanding the PHR context produces brittle replicas
   that fail on edge cases.

5. **Team scalability.** New engineers can read PHR entries
   to understand prompt design decisions. They do not need
   to reverse-engineer clinical reasoning from prompt text
   alone. This reduces onboarding time for healthcare AI
   domain expertise.

### Negative

1. **Development velocity.** Prompt changes require PHR
   updates, test runs, and (in clinical deployment) multi-
   stakeholder review. Quick iteration on prompts is slower
   than a "just edit the string" approach. Mitigation: the
   testing protocol is automated, and PHR updates are
   lightweight markdown edits.

2. **Documentation overhead.** Each prompt generates a PHR
   entry, test cases, and version history. This is more
   documentation than most engineering teams maintain for
   prompt engineering. Mitigation: the PHR template is
   structured and fast to fill. The documentation investment
   pays for itself in knowledge preservation.

3. **Version proliferation.** Preserving all versions in the
   prompt file may create large files over time. Mitigation:
   archive versions older than 3 major versions to a separate
   archive file. Keep the last 3 versions in the active file
   for regression testing.

---

## Implementation Notes

- Prompt files: `src/prompts/coding_extraction.py` (PHR-001),
  `src/prompts/cdi_query.py` (PHR-002),
  `src/prompts/drg_analysis.py` (PHR-003),
  `src/prompts/appeal_letter.py` (PHR-004)
- PHR entries: `docs/phr/PHR-001-coding-extraction.md`,
  `docs/phr/PHR-002-cdi-query.md`,
  `docs/phr/PHR-003-drg-analysis.md`,
  `docs/phr/PHR-004-appeal-letter.md`
- Prompt audit model: `src/core/audit/prompt_audit.py`
- Version control protocol: `specs/04-prompt-engineering-architecture.md`
  Section 4
- Full specification: `specs/04-prompt-engineering-architecture.md`

---

## References

- Constitution Article I.4 (Prompts Are Preserved)
- Constitution Article I.5 (Domain Knowledge in Skills)
- Constitution Article I.6 (Skills + MCP)
- Constitution Article II.2 (Source Citation Required)
- ADR-006 (Rules Engine Hard Constraints — post-LLM validation)
- ADR-008 (Guardrails as Architecture — prompt output enforcement)
- DISC-001 (ICD-10 Official Guidelines — encoded in PROMPT-001)
- DISC-002 (Documentation Failure Patterns — encoded in PROMPT-002)
- DISC-004 (Payer Denial Patterns — encoded in PROMPT-004)
- DISC-005 (Competitor Analysis — no competitor documents prompts)
- `specs/04-prompt-engineering-architecture.md`
