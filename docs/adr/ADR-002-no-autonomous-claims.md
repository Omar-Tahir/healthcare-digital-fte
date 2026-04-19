# ADR-002: No Autonomous Claim Submission

**Status:** ACCEPTED
**Date:** 2026-03-30
**Decision makers:** Engineering team
**Constitution references:** Article II.1 (No Autonomous Claims)

---

## Context

AI-generated code suggestions could theoretically be submitted
directly to payers or clearinghouses without human intervention.
This would maximize throughput and reduce labor costs. However,
the False Claims Act (31 USC 3729) imposes penalties of
$13,946-$27,894 per false claim, with treble damages. A single
AI error propagated across thousands of claims creates
catastrophic legal exposure.

We must decide: can the system ever submit a claim without
explicit human review and approval?

---

## Decision

**No claim is EVER submitted to any payer or clearinghouse
without explicit human review and approval from a credentialed
coder. This is enforced architecturally, not by policy.**

Implementation (G-HARD-001 in DESIGN-003):

1. **Human approval token** — a cryptographically signed token
   containing: coder_id, encounter_id, timestamp, code_set_hash
2. **Token requirements:**
   - Issued only to users with `credentialed_coder` role
   - Expires after 24 hours
   - code_set_hash binds the approval to the exact code set
     reviewed (prevents approving one set, submitting another)
   - Cryptographic signature prevents forgery
3. **Architectural enforcement** — the claim submission endpoint
   raises `HardGuardrailViolation` if the token is missing,
   expired, invalid, or mismatched. There is no code path,
   admin override, or feature flag that bypasses this check.

---

## Alternatives Considered

### Alternative 1: Full Autonomy

AI submits claims directly when confidence exceeds a threshold.

**Rejected because:**
- Even 99% accuracy = 1% error rate. At 1,000 claims/day,
  that is 10 false claims/day = $139,460-$278,940 daily
  FCA exposure
- Olive AI's partial collapse was linked to autonomous billing
  without adequate oversight (DISC-001 A.3)
- No hospital legal team would approve procurement of an
  autonomous claim submission system
- Patient safety: AI-fabricated diagnoses in medical records
  can affect downstream clinical decisions

### Alternative 2: Tiered Autonomy

Auto-submit above 0.95 confidence; human review below.

**Rejected because:**
- Confidence scores are model-calibrated, not ground truth.
  A 0.95 confidence score does not mean 95% accuracy
- Creates a "rubber stamp" incentive — coders may stop
  carefully reviewing auto-submitted claims
- Compliance auditors cannot distinguish "AI decided to
  auto-submit" from "human reviewed" — loses audit trail
  integrity
- FCA liability attaches regardless of confidence score

### Alternative 3: Autonomous Draft + Batch Approval

AI creates draft claims; human approves in batches.

**Rejected because:**
- Batch approval becomes rubber-stamping — cognitive load
  of reviewing 100 claims at once leads to approval fatigue
- Cannot verify that the human actually reviewed each claim
  vs clicking "approve all"
- The code_set_hash mechanism in our approach ensures the
  coder reviewed the specific codes being submitted

---

## Consequences

### Positive

1. **FCA defense** — every claim has a provenance chain:
   physician documentation -> AI suggestion -> human review ->
   cryptographic approval token -> submission
2. **Hospital procurement** — legal teams can verify that
   autonomous submission is architecturally impossible
3. **Trust building** — coders trust a tool that assists
   rather than replaces them
4. **Audit trail** — every claim is traceable to a specific
   credentialed coder who reviewed and approved it

### Negative

1. **Every claim requires human touch** — limits throughput
   to human review speed. Mitigation: AI reduces per-claim
   review time from 15-20 minutes to 2-3 minutes by doing
   the research/suggestion work
2. **Coder workforce still required** — the system augments
   coders, does not eliminate them. This is a feature for
   hospital adoption (no workforce displacement fear) but
   limits the "full automation" pitch

---

## References

- Constitution Article II.1 (No Autonomous Claims)
- DESIGN-003 G-HARD-001 (Human Approval Token)
- 31 USC 3729 (False Claims Act)
- DISC-004 (Payer Denial Patterns — appeal context)
