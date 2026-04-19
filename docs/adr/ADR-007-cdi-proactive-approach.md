# ADR-007: Proactive (Concurrent) CDI Over Reactive (Post-Coding) CDI

**Status:** ACCEPTED  
**Date:** 2026-04-01  
**Decision makers:** Engineering team  
**Constitution references:** Article II.6 (Conservative Defaults), Article IV.1 (Revenue North Star), Article V.1 (Research Before Building)

---

## Context

Clinical Documentation Improvement (CDI) programs operate
in two fundamentally different modes:

**Reactive CDI (post-coding):** The traditional model.
Coders complete coding from existing documentation. A CDI
specialist reviews the coded chart, identifies documentation
gaps, and sends physician queries AFTER coding is done.
The query-response-recode cycle adds 24-72 hours to each
case, extending bill-hold periods and delaying revenue.

**Proactive CDI (concurrent):** The modern approach. CDI
analysis runs DURING the hospital stay, while the physician
is still caring for the patient and actively documenting.
Queries are delivered while the clinical context is fresh.
Documentation updates happen before coding begins.

We must decide which model our CDI Intelligence Layer
implements.

---

## Decision

**The CDI Intelligence Layer operates in proactive
(concurrent) mode: it detects documentation gaps and
generates physician queries during the hospital stay,
triggered by note-signing and critical lab events,
BEFORE coding begins.**

Specifically:

1. **CDI detection triggers on note signing events.**
   When a physician signs a progress note, H&P,
   consultation, or operative report, the CDI pipeline
   processes the note within 5 minutes.

2. **Lab-triggered re-analysis.** When critical lab results
   post (e.g., creatinine doubling, positive blood cultures),
   the CDI pipeline re-evaluates against the most recent
   clinical documentation.

3. **Pre-discharge final sweep.** A comprehensive CDI
   analysis runs when a discharge order is placed, catching
   any remaining documentation gaps before the coder
   touches the chart.

4. **CDI queries go to physicians during the stay.** The
   physician receives queries while they are still caring
   for the patient, while the clinical situation is fresh
   in their memory, and while they can most accurately
   answer documentation questions.

5. **Coding receives CDI-enriched documentation.** By the
   time the coder begins work, the documentation has
   already been improved by CDI query responses. The coder
   codes from complete documentation rather than incomplete
   documentation that requires post-coding queries.

---

## Alternatives Considered

### Alternative 1: Reactive CDI (Post-Coding)

CDI analysis runs after the coder has completed initial
coding. CDI specialists review coded charts and generate
queries for documentation gaps.

**Rejected because:**

- **24-72 hour delay per case.** After coding is complete,
  the CDI query must be sent, the physician must respond,
  the documentation must be updated, and the coder must
  recode. This adds 24-72 hours to the revenue cycle for
  every case with a CDI opportunity (DISC-002 Section E).

- **Physician memory degradation.** Research shows that
  documentation quality degrades significantly when
  physicians respond to queries > 24 hours after the
  clinical encounter (DISC-002 Section E.3). A query
  about Day 2 labs sent on Day 7 (post-coding) gets a
  less accurate response than one sent on Day 3
  (concurrent).

- **Bill-hold extension.** Most hospitals target a 3-5 day
  bill hold. Reactive CDI extends this by 1-3 days per
  queried case. At scale (100+ cases/day with CDI
  opportunities), this creates millions in delayed cash
  flow annually.

- **Double coding work.** The coder codes the chart, then
  recodes after documentation updates. Concurrent CDI
  means the coder codes once from complete documentation.

- **Lower query response rates.** Post-discharge queries
  have lower response rates than concurrent queries because
  the physician has moved on to new patients and the
  clinical context is no longer fresh.

### Alternative 2: Real-Time CDI (During Documentation)

CDI analysis runs in real-time as the physician types,
providing inline suggestions and documentation guidance
before the note is even signed.

**Deferred (not rejected):**

- Real-time CDI requires deep EHR integration at the note
  editor level (similar to Abridge/Nuance DAX ambient
  approach).

- This level of EHR integration is not available in
  Phase 1. Most EHR vendors do not expose real-time
  documentation APIs.

- Real-time CDI is a Phase 4+ feature that builds on the
  concurrent CDI foundation we establish now.

- The concurrent model (trigger on note signing) achieves
  80%+ of the value of real-time CDI with 20% of the
  integration complexity.

### Alternative 3: Hybrid (Concurrent + Post-Coding Review)

Run concurrent CDI during the stay, then a post-coding
audit pass to catch anything missed.

**Partially adopted:** Our pre-discharge final sweep
serves a similar purpose. However, we do NOT implement a
full post-coding CDI re-review because:

- It duplicates effort (the concurrent CDI already ran)
- Post-coding CDI queries face the same delay problems
  as purely reactive CDI
- The rules engine (DESIGN-001) already validates coding
  accuracy — a post-coding CDI layer would be redundant
  with the rules engine's combination code detection and
  CC/MCC opportunity identification

The pre-discharge final sweep is sufficient to catch
documentation gaps that emerged between the last note
signing event and discharge.

---

## Consequences

### Positive

1. **Eliminates 24-72 hour CDI delay.** Documentation
   improvement happens during the stay. By the time
   coding begins, documentation is already complete.
   This directly reduces bill-hold periods and
   accelerates cash flow.

2. **Higher physician response accuracy.** Physicians
   respond to queries about patients they are currently
   treating. Clinical context is fresh. Response
   quality is higher than post-discharge queries.

3. **Higher query response rates.** Concurrent queries
   achieve higher response rates because the physician
   is actively engaged with the patient's care.
   Industry benchmark: 69% of facilities report
   91-100% response rates for concurrent CDI (ACDIS).

4. **Single coding pass.** Coders code once from
   complete, CDI-enriched documentation instead of
   coding twice (initial + recode after CDI response).
   This reduces coder workload by an estimated 15-20%
   on CDI-flagged cases.

5. **Competitive differentiation.** Iodine Software
   (AwareCDI) does concurrent CDI but without LLM-powered
   clinical reasoning. Our system combines concurrent
   timing with LLM analysis depth — a combination no
   competitor offers (DISC-005).

6. **CDI-to-coding closed loop.** The CDI agent and
   coding agent share the same NLP pipeline, FHIR data
   layer, and rules engine. CDI query resolution
   automatically flows into updated code suggestions.
   No manual handoff, no information loss between
   CDI and coding teams.

### Negative

1. **Requires EHR event subscription.** We need to receive
   note-signing and lab-result events from the EHR in
   near-real-time. This requires FHIR Subscription or
   webhook integration, which varies by EHR vendor.
   Mitigation: FHIR R4 Subscription is supported by
   Epic (2024+), Cerner (Oracle Health), and most modern
   EHR platforms.

2. **Higher compute cost during patient stay.** CDI
   analysis runs multiple times per stay (on each note
   signing event), not once after discharge. Mitigation:
   incremental analysis — only re-evaluate entities that
   changed since last analysis.

3. **Physician notification fatigue risk.** Multiple CDI
   queries during a single stay could annoy physicians.
   Mitigation: batch queries (no more than 2 queries per
   note signing event), priority filtering (only P0/P1
   concurrent; P2 batched for pre-discharge sweep), and
   intelligent deduplication (do not re-query the same
   clinical question).

4. **Partial data risk.** Concurrent CDI runs before the
   case is complete. Lab results, consultation notes, and
   imaging may still be pending. Mitigation: the
   pre-discharge final sweep catches gaps that emerge
   late in the stay. Lab-triggered re-analysis catches
   significant new results.

---

## Implementation Notes

- CDI agent implementation: `src/agents/cdi_agent.py`
- CDI query prompts: `src/prompts/cdi_query.py` (PHR-002)
- Detection algorithms: defined in
  `specs/02-cdi-intelligence-layer.md` Section 2
- FHIR Subscription for note events:
  `src/core/fhir/subscriptions.py`
- Pre-discharge sweep: triggered by discharge order event
- Query delivery: via EHR inbox integration
  (`src/core/fhir/communication.py`)
- Response handling: webhook from EHR →
  `src/api/routes/cdi_response.py`

---

## References

- Constitution Article II.6 (Conservative Defaults)
- Constitution Article IV.1 (Revenue North Star)
- DISC-002 Section E (Documentation Timing Failures)
- DISC-002 Section F (Cross-Cutting Detection Architecture)
- DISC-005 (Competitor Analysis — Iodine Software AwareCDI)
- AHIMA Standards for CDI (2016 updated)
- ACDIS Code of Ethics for CDI Professionals
- `specs/02-cdi-intelligence-layer.md` (full specification)
