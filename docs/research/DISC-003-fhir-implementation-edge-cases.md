# DISC-003: FHIR R4 Real-World Implementation Edge Cases

**Research Phase:** DISCOVER
**Status:** Complete — verified 2026-04-05 (FIX-001)
**Date:** 2026-04-01
**Last Verified:** 2026-04-05 (FIX-001 research audit)
**Verification Method:** Live web fetch + primary source confirmation
**Unverified Items Remaining:** 3 (labeled inline)
**Purpose:** Document the real-world implementation challenges
of FHIR R4 APIs in Epic and Cerner (Oracle Health) production
environments — specifically the edge cases that break AI
systems in production. This document is the primary reference
for building the FHIR integration layer in `src/core/fhir/`.

---

## Executive Summary

FHIR R4 is the mandated US healthcare interoperability standard
(21st Century Cures Act, ONC Final Rule). Every major EHR now
exposes FHIR APIs, but the gap between the FHIR specification
and real-world EHR implementations is where AI coding systems
fail in production.

**Key findings:**

- **Epic controls ~42% of the US acute care hospital market**
  (KLAS 2024: 42.3% hospital share, 54.9% bed share) and
  **Oracle Health (Cerner) ~23%** (KLAS 2024: 22.9%, declining).
  Together they represent the vast majority of production FHIR
  endpoints our system will integrate with.
  [VERIFIED-LIVE ✓ — KLAS Research 2024 data via Fierce
  Healthcare/CNBC, fetched 2026-04-05. Corrected from original
  ~38%/~25% estimates]
- **Epic's FHIR implementation deviates significantly** from
  the R4 spec in areas critical to coding AI: DocumentReference
  content encoding, Encounter status semantics, and Claim
  write operations.
- **Clinical note availability via FHIR is delayed** —
  notes are typically not available until signed and may
  have additional EHR-specific propagation delays of
  minutes to hours.
- **FHIR Claim write operations are not supported** by most
  EHRs — coding output must use alternative integration
  patterns (HL7v2 DFT, X12 837, or proprietary APIs).
- **Token expiration during coding sessions** is a frequent
  production failure — Epic access tokens expire in 5 minutes
  by default, and not all launch contexts support refresh tokens.
- **Encounter classification edge cases** (observation status,
  ED-to-inpatient transitions) directly affect ICD-10 coding
  rules (outpatient uncertain diagnosis rules vs inpatient).

**Competitor vulnerability assessment:** Most AI coding
competitors (Nym Health, Fathom, Iodine) have solved basic
FHIR read operations but struggle with: note timing gaps,
amended note handling, observation-status encounter coding
rules, and graceful degradation during EHR downtime. Our
architecture must handle all of these from day one.

---

## Table of Contents

- [A. Epic FHIR R4 Implementation](#a-epic-fhir-r4-implementation)
- [B. FHIR DocumentReference Edge Cases](#b-fhir-documentreference-edge-cases)
- [C. FHIR Encounter Resource Edge Cases](#c-fhir-encounter-resource-edge-cases)
- [D. SMART on FHIR Authentication Failure Modes](#d-smart-on-fhir-authentication-failure-modes)
- [E. FHIR Claim Resource for Coding Output](#e-fhir-claim-resource-for-coding-output)
- [F. Cross-Cutting Architecture Recommendations](#f-cross-cutting-architecture-recommendations)
- [Sources](#sources)

---

## A. Epic FHIR R4 Implementation

### A.1 Resource Availability: Sandbox vs Production

Epic provides FHIR R4 endpoints through its App Orchard
(now "Epic on FHIR") program. Resource availability differs
significantly between sandbox and production.

**Sandbox environment (fhir.epic.com):**

| Category | Resources Available | Notes |
|----------|-------------------|-------|
| Patient demographics | Patient, RelatedPerson | Full synthetic test data |
| Clinical | Condition, AllergyIntolerance, Procedure, Observation, DiagnosticReport | Standard USCDI v1/v2 data classes |
| Documents | DocumentReference, Binary | Clinical notes available as test data |
| Encounters | Encounter, EpisodeOfCare | Basic encounter data |
| Medications | MedicationRequest, MedicationStatement | Prescription data |
| Financial | Coverage | Read-only; Claim is NOT in sandbox |
| CDS Hooks | CDS Services endpoint | For clinical decision support |

**Production environment (hospital-specific):**

| Category | Production Differences |
|----------|---------------------|
| DocumentReference | Content availability depends on hospital configuration; some hospitals restrict note types exposed via FHIR |
| Encounter | More complex status workflows; real encounter linking |
| Claim/Financial | Claim write is NOT supported via Epic FHIR; financial data is read-only (ExplanationOfBenefit for claims history) |
| Patient | Opt-out patients return empty or error responses |
| Binary | Large documents may timeout; PDF/CDA encoding varies |

**Critical gap: Sandbox does not reflect production reality.**
Sandbox data is clean, complete, and immediately available.
Production data has missing fields, delayed availability,
inconsistent encoding, and access restrictions. Any system
tested only against sandbox will fail in production.

> **Note:** Epic resource availability details are based on
> published fhir.epic.com documentation and community reports
> as of early 2025. Epic updates FHIR support with quarterly
> releases. Verify current resource list at fhir.epic.com
> before production integration.

### A.2 Rate Limits

Epic enforces rate limits on FHIR API access. These are not
prominently documented and vary by deployment.

| Limit Type | Documented Value | Source |
|-----------|-----------------|--------|
| Per-app rate limit | Varies by hospital; commonly **60-120 requests/minute** per app | Epic App Orchard developer documentation |
| Bulk data export | Separate limits; typically **1 concurrent export** per app | Epic Bulk FHIR documentation |
| Patient-level queries | Generally **10-30 requests/second** per patient context | Community reports |
| Batch/Transaction bundles | Supported but limited to **~20 entries** per bundle in practice | Implementation experience |

**Rate limit edge cases:**

1. **Limit varies by hospital:** Each Epic deployment can
   configure its own rate limits. A limit tested at Hospital A
   may not apply at Hospital B.

2. **No standard rate limit headers:** Epic does not
   consistently return `X-RateLimit-Remaining` or
   `Retry-After` headers. Rate limit violations return
   HTTP 429 but recovery timing must be estimated.

3. **Burst vs sustained:** Short bursts may succeed even
   above the sustained limit, but sustained high-rate
   access triggers throttling that can persist for minutes.

**AI system impact:** A coding analysis that queries Patient,
Encounter, multiple DocumentReferences, Conditions, and
Observations for a single case may require 10-20 API calls.
At scale (processing 50+ cases concurrently), rate limits
become a production bottleneck.

**Handling approach:**
```
1. Implement exponential backoff with jitter on HTTP 429
2. Use bulk data export for batch processing (overnight runs)
3. Cache frequently accessed resources (Patient, Practitioner)
4. Use _include and _revinclude to reduce request count
5. Implement per-hospital rate limit configuration
```

> **Note:** Rate limit figures are commonly reported values.
> Exact limits per hospital should be verified during
> onboarding. Treat as directional estimates.

### A.3 App Orchard Approval Process

All production FHIR access to Epic systems requires App
Orchard (now "Epic on FHIR Showroom") listing.

| Phase | Typical Duration | Requirements |
|-------|-----------------|-------------|
| Application submission | 1-2 weeks | App description, data access justification, security questionnaire |
| Technical review | 4-8 weeks | SMART on FHIR conformance, scope justification, data handling review |
| Security review | 4-12 weeks | SOC 2 Type II or equivalent, penetration test results, HIPAA compliance documentation |
| Hospital connection | 2-4 weeks per site | Per-hospital BAA, credential provisioning, endpoint configuration |
| **Total timeline** | **3-6 months minimum** | From submission to first production patient data |

**Operations requiring App Orchard approval:**

- Any FHIR read operation on production patient data
- CDS Hooks integration
- Write-back operations (where supported)
- Bulk data export access

**Common rejection reasons:**

1. Requesting overly broad scopes (e.g., `*.read` instead
   of specific resource scopes)
2. Insufficient data retention/deletion policies
3. Missing BAA coverage for subprocessors (including AI
   model providers)
4. Inadequate audit logging documentation

**AI-specific requirement:** Epic requires disclosure that
AI/ML is used in clinical decision making. The app listing
must describe what the AI does, what data it processes, and
what decisions it influences. Since 2024, Epic has required
AI transparency documentation for any app using LLMs.

> **Note:** Timeline estimates are based on developer
> community reports. Epic does not publish official SLAs
> for the review process. Treat as directional estimates.

### A.4 Known Epic FHIR Deviations from R4 Standard

Epic implements FHIR R4 with several notable deviations
and extensions that affect AI coding systems.

#### A.4.1 Search Parameter Limitations

| R4 Spec Feature | Epic Support |
|----------------|-------------|
| `_text` search | Not supported |
| `_content` search | Not supported |
| Chained search (`Encounter.participant.name`) | Limited support; chains >2 levels unreliable |
| `_has` reverse chaining | Limited or not supported |
| `_filter` | Not supported |
| Date range precision | Varies; some resources only support day-level precision |
| `:contains` modifier | Not supported on most parameters |
| `:text` modifier | Limited support |
| `_sort` | Supported on limited parameters per resource |

**Impact on AI system:** Cannot search for "all notes
containing 'sepsis'" via FHIR. Must retrieve all notes
and perform text search client-side.

#### A.4.2 Epic-Specific Extensions

Epic uses FHIR extensions extensively. Key extensions
relevant to coding AI:

| Extension | Purpose | Where Found |
|-----------|---------|-------------|
| `urn:oid:1.2.840.114350.1.13.x.x.x` | Epic internal identifiers (department, provider, etc.) | Most resources |
| Epic encounter class extensions | More granular encounter classification than standard ActCode | Encounter.class |
| Epic department ID | Links to Epic department/unit | Encounter, Location |
| Note status extensions | Additional note lifecycle states beyond FHIR `current/superseded` | DocumentReference |
| Order priority extensions | Urgent vs routine order classification | ServiceRequest |

**Handling approach:** Map Epic extensions to our internal
Pydantic models during FHIR parsing. Never depend on
Epic-specific extensions for core logic — they will not
exist in Cerner deployments.

#### A.4.3 Cerner (Oracle Health) Divergences

Cerner's FHIR R4 implementation differs from Epic's in
ways that affect our system:

| Area | Epic Behavior | Cerner Behavior |
|------|--------------|----------------|
| DocumentReference content | Typically XHTML or plain text | Often CDA (C-CDA) XML documents |
| Encounter.class coding | May use Epic-specific codes | More closely follows v3 ActCode |
| Observation categorization | Epic category codes | Cerner category codes differ |
| Patient search | MRN via `identifier` parameter | MRN format/system URI differs |
| Authentication | SMART on FHIR with Epic-specific scopes | SMART on FHIR with Cerner-specific scopes |
| Bulk data | Supported since 2022 | Supported with different export parameters |

**Architecture requirement:** Our FHIR client must use an
adapter pattern — a common interface with Epic and Cerner
specific implementations. Hard-coding to either vendor's
behavior guarantees failure at the other.

### A.5 Epic Versioning and Upgrade Impact

Epic releases quarterly updates. FHIR API changes are
included in these updates.

| Aspect | Behavior |
|--------|---------|
| Update frequency | Quarterly (February, May, August, November) |
| FHIR version changes | Rare; Epic committed to R4 through at least 2027 |
| Resource field additions | Common; new optional fields added quarterly |
| Breaking changes | Rare but documented; typically 6-month deprecation notice |
| Hospital upgrade timing | Each hospital chooses when to apply updates; there is no global upgrade date |
| Version discovery | `metadata` endpoint (CapabilityStatement) reflects current version |

**Edge case: Hospital A and Hospital B on different versions.**
Since hospitals upgrade on their own schedule, our system may
simultaneously connect to Epic instances running different
quarterly versions. Field availability may differ.

**Handling approach:**
```
1. Always check CapabilityStatement on first connection
2. Use feature detection, not version detection
3. Handle missing optional fields gracefully (Pydantic
   models with Optional fields + validators)
4. Test against multiple Epic versions in CI
```

---

## B. FHIR DocumentReference Edge Cases

DocumentReference is the single most important FHIR resource
for our coding AI — it is how we access clinical notes.

### B.1 Note Type Availability via FHIR

Not all clinical note types stored in the EHR are available
through FHIR APIs.

**Typically available via FHIR DocumentReference:**

| Note Type | LOINC Code | Epic FHIR | Cerner FHIR | Notes |
|-----------|-----------|-----------|-------------|-------|
| Discharge Summary | 18842-5 | Yes | Yes | Primary coding document |
| History & Physical | 34117-2 | Yes | Yes | Admission documentation |
| Progress Note | 11506-3 | Yes | Yes | Daily inpatient notes |
| Consultation Note | 11488-4 | Yes | Yes | Specialist notes |
| Operative Note | 11504-8 | Yes | Yes | Surgical documentation |
| Emergency Dept Note | 34878-9 | Yes | Yes | ED documentation |
| Nursing Note | 34746-8 | Varies | Varies | Often restricted |
| Pathology Report | 11526-1 | Yes (often delayed) | Yes (delayed) | May take days for final |

**Typically NOT available or restricted via FHIR:**

| Note Type | Reason |
|-----------|--------|
| Psychotherapy notes | HIPAA 42 CFR Part 2 restrictions; excluded from standard FHIR access |
| Substance abuse treatment notes | 42 CFR Part 2 requires separate consent |
| Genetic/genomic reports | May require special consent; GINA considerations |
| Risk management/legal notes | Attorney-client privilege; never in FHIR |
| Preliminary reads (radiology) | Often available only as DiagnosticReport, not DocumentReference |
| Scanned paper documents | May be in FHIR as PDF Binary, but OCR quality varies wildly |
| Resident notes (unsigned) | Not available until attending co-signs |

**AI system impact:** Our coding system cannot rely on FHIR
alone for complete documentation. Key scenarios:

1. **Pathology final reads** may not be in FHIR for days after
   surgery — cancer staging codes cannot be assigned until final
   pathology is available
2. **Substance abuse notes** may document conditions (e.g.,
   alcohol dependence with withdrawal) that affect coding but
   cannot be accessed via standard FHIR scopes
3. **Nursing notes** contain vital clinical observations
   (wound staging, nutritional assessments) that support CDI
   queries but may not be exposed in FHIR

**Competitor vulnerability:** Abridge and Nuance DAX focus on
note generation, not note consumption — they don't face this
problem. Nym Health and Fathom, which consume notes for coding,
likely struggle with pathology delays and restricted note types.
Iodine Software, focused on CDI, may miss nursing note data.

### B.2 Note Encoding Formats

Clinical note content in DocumentReference.content varies
dramatically across EHR deployments.

| Format | MIME Type | Where Seen | NLP Challenge |
|--------|----------|-----------|---------------|
| Plain text (UTF-8) | `text/plain` | Epic (common), Cerner | Easiest to parse; may lose structural formatting |
| XHTML | `text/html` or `application/xhtml+xml` | Epic (common) | Contains HTML tags; must strip/parse markup; may include CSS |
| C-CDA XML | `application/xml` | Cerner (common), some Epic | Complex XML parsing; clinical content nested in CDA sections |
| Base64-encoded PDF | `application/pdf` | Scanned documents, some Epic configs | Requires PDF extraction + OCR; lowest quality for NLP |
| RTF (Rich Text) | `application/rtf` | Rare; some legacy systems | Must convert to plain text; RTF parsing is fragile |

**Edge case: Mixed encoding within a single hospital.**
A single Epic deployment may return progress notes as XHTML
but operative notes as PDFs and pathology reports as C-CDA.
The coding AI must handle all formats for every note.

**Edge case: XHTML with embedded metadata.**
Epic's XHTML notes may include:
```html
<div>
  <p><b>Assessment and Plan:</b></p>
  <p>1. Acute on chronic systolic heart failure (I50.23)
     - Continue diuresis with IV furosemide 40mg BID</p>
</div>
```
The HTML structure varies by template. Some hospitals
customize note templates extensively, changing the DOM
structure our parser must handle.

**Edge case: C-CDA section parsing.**
Cerner's C-CDA documents use standardized section codes, but:
- Not all sections are always present
- Section ordering varies
- Narrative text may differ from structured entries
- Some sections contain only "See above" references

**Handling approach for our NLP pipeline:**
```
1. Detect MIME type from DocumentReference.content.attachment
2. Route to format-specific parser:
   - text/plain → direct NLP
   - text/html → BeautifulSoup/lxml strip → NLP
   - application/xml → C-CDA section extractor → NLP
   - application/pdf → PDF text extraction → NLP
3. Normalize all output to structured plain text with
   section headers preserved
4. Log format type per hospital for monitoring
5. Fail gracefully: if parsing fails, return
   DegradedResult (per constitution Article II.5)
```

### B.3 Note Availability Timing

The gap between when a physician writes a note and when it
appears in FHIR is a critical production issue.

| Event | Typical FHIR Availability | Variation |
|-------|--------------------------|-----------|
| Note authored (draft) | NOT available | Drafts are never in FHIR |
| Note signed by physician | Available within **minutes to 1 hour** | Some hospitals have batch sync (every 15-60 min) |
| Note co-signed (resident notes) | Available after attending co-signs | May be hours to days delayed |
| Addendum added | New DocumentReference or updated original; **minutes to hours** | Varies by EHR config |
| Note corrected/amended | Amendment typically available within **minutes** | Original may or may not be updated |
| Pathology final report | **Days** after specimen collection | 2-5 business days typical |
| Radiology final read | **Hours** after preliminary | Prelim may be DiagnosticReport; final becomes DocumentReference |

**Critical scenario: Coding before all notes are available.**
A coder working a case 2 days post-discharge may not have:
- The final pathology report
- The latest addendum from the attending
- A late consultation note

**AI system impact:** Our system must:
1. Track which notes have been retrieved for each encounter
2. Re-query for new notes before finalizing coding
3. Display "pending notes" status to the coder
4. Alert when a new note appears for an already-coded case

**Competitor vulnerability:** Systems that do a single note
fetch and code from that snapshot miss late-arriving notes.
This is particularly dangerous for pathology-dependent coding
(cancer staging) and addenda that clarify diagnoses.

### B.4 Amended and Corrected Notes

FHIR R4 represents note amendments through the
`DocumentReference.relatesTo` element.

**Spec behavior:**
```
DocumentReference.relatesTo.code = "appends" (addendum)
DocumentReference.relatesTo.code = "replaces" (correction)
DocumentReference.relatesTo.code = "transforms" (format change)
DocumentReference.relatesTo.target = Reference(original DocumentReference)
```

**Real-world behavior:**

| Scenario | Epic Behavior | Cerner Behavior |
|----------|--------------|----------------|
| Addendum added | New DocumentReference with `relatesTo.code=appends` referencing original | Similar; may also update original's `status` |
| Note corrected | New DocumentReference with `relatesTo.code=replaces`; original status may change to `entered-in-error` or `superseded` | Original status set to `entered-in-error`; replacement created |
| Late amendment | New DocumentReference; timing of appearance varies | Similar |
| Note retracted | Original status set to `entered-in-error`; no replacement | Similar |

**Edge cases that break AI systems:**

1. **Amendment without relatesTo:** Some EHR configurations
   update the original DocumentReference in-place rather than
   creating a new one with relatesTo. The AI system has no
   signal that the note changed unless it compares content
   hashes between fetches.

2. **Multiple addenda:** A discharge summary may have 3-4
   addenda from different physicians. The coding AI must
   assemble the complete document: original + all addenda
   in chronological order.

3. **Correction that removes a diagnosis:** A physician
   corrects a note to remove "sepsis" and replace with
   "SIRS without infection." If the AI already coded sepsis,
   it must detect the correction and remove the code.

4. **Addendum after coding is complete:** An addendum
   arrives 5 days post-discharge with additional diagnostic
   specificity. The AI must flag the case for re-review.

**Handling approach:**
```
1. On initial fetch: query all DocumentReferences for the
   encounter, including relatesTo references
2. Build a note graph: original → addenda → corrections
3. For coding: use the latest non-superseded version of
   each note, assembled with all addenda
4. Track content hashes: on re-fetch, compare hashes to
   detect in-place edits
5. Subscribe to DocumentReference changes (if hospital
   supports FHIR Subscriptions) for post-coding alerts
```

### B.5 AI Detection Methods for DocumentReference Issues

| Issue | Detection | Intervention |
|-------|-----------|-------------|
| Note not yet signed | DocumentReference.status = `preliminary` or not present | Display "Pending: unsigned note" to coder; do not code from preliminary notes |
| Mixed encoding per hospital | Track MIME types per hospital over time | Auto-configure parser per hospital; alert on unexpected format |
| Amended note after coding | Content hash changed on re-fetch; or new relatesTo detected | Alert: "Note [X] has been amended since coding. Review required." |
| Pathology pending | No pathology DocumentReference for surgical case | Flag: "Pathology report pending — cancer staging may change" |
| C-CDA parsing failure | XML parse error or empty section extraction | Route to DegradedResult; log error; flag for manual review |

---

## C. FHIR Encounter Resource Edge Cases

Encounter classification directly determines which ICD-10
coding rules apply — outpatient uncertain diagnosis rules
are fundamentally different from inpatient rules (per
constitution Article II.3 and DISC-001).

### C.1 Encounter Status Transitions

The FHIR R4 Encounter status field has these defined values:
`planned → arrived → triaged → in-progress → onleave →
finished → cancelled → entered-in-error`

**Real-world status transitions in Epic:**

```
TYPICAL INPATIENT:
planned → arrived → in-progress ───────────────► finished
                                    │
                                    ├─► onleave (LOA)
                                    │     │
                                    │     ▼
                                    │   in-progress (returned)
                                    │
                                    └─► finished (discharged)

TYPICAL ED → ADMISSION:
planned → arrived → triaged → in-progress (ED) ──┐
                                                   │
                      ┌────────────────────────────┘
                      ▼
              NEW encounter: in-progress (inpatient)
              │
              └─► finished (discharged)

TYPICAL OUTPATIENT:
arrived → in-progress → finished
(often entire visit is a single status change)
```

**Edge cases:**

1. **Status reversal:** In some Epic configurations, a
   `finished` encounter can revert to `in-progress` if the
   physician reopens documentation. This is non-standard
   but observed in production.

2. **Long-running encounters:** ICU patients may have
   encounters that span weeks. The encounter remains
   `in-progress` the entire time, with daily progress notes
   as separate DocumentReferences.

3. **Encounter splitting on transfer:** When a patient
   transfers between units (e.g., ED to ICU to floor), some
   hospitals create separate encounters per unit, linked by
   `Encounter.partOf`. Others maintain a single encounter.

4. **Leave of absence:** `onleave` status is used when a
   patient temporarily leaves (e.g., weekend pass in
   psychiatric facility). Coding must span the entire
   episode, not each leave segment.

**AI system impact:** Our system must determine encounter
status to know:
- Whether coding rules are inpatient or outpatient
- Whether the encounter is complete (ready for final coding)
- Whether documentation is expected to continue

### C.2 Multiple DocumentReferences per Encounter

A single inpatient encounter typically generates 10-50+
DocumentReferences.

**Querying notes for an encounter:**
```
GET [base]/DocumentReference?encounter=Encounter/[id]
    &_sort=-date
    &_count=100
```

**Edge cases:**

1. **Notes from before the encounter:** Pre-admission testing
   notes may not reference the inpatient encounter. They may
   reference an outpatient encounter or have no encounter
   reference at all.

2. **Notes referencing wrong encounter:** In Epic, when an ED
   visit becomes an admission, notes written during the ED
   phase may reference the ED encounter, not the inpatient
   encounter. Querying only the inpatient encounter misses
   the ED documentation.

3. **Consultation notes from external systems:** If a
   specialist from another hospital system provides a consult,
   their note may not appear in FHIR at all, or may appear
   as a scanned PDF.

4. **Pagination:** Large encounter note sets may be paginated.
   Some Epic deployments return a maximum of 20 results per
   page. The AI must follow `Bundle.link.next` to retrieve
   all notes.

**Handling approach:**
```
1. Query by encounter ID first
2. Also query by patient + date range spanning the encounter
3. Follow pagination links to completion
4. De-duplicate by DocumentReference.id
5. Sort by date; group by type (LOINC code)
```

### C.3 Identifying Primary vs Secondary Notes

For coding purposes, the discharge summary is the primary
document, but the coder must review all notes. Identifying
note types reliably is essential.

**LOINC codes for note type identification:**

| Note Type | LOINC Code | Coding Relevance |
|-----------|-----------|-----------------|
| Discharge Summary | 18842-5 | **Primary** — principal and secondary diagnoses |
| History & Physical | 34117-2 | Admission diagnoses, PMH, physical findings |
| Progress Note | 11506-3 | Daily clinical status, evolving diagnoses |
| Consultation Note | 11488-4 | Specialist diagnoses, recommendations |
| Operative Note | 11504-8 | Procedure documentation for CPT coding |
| Procedure Note | 28570-0 | Non-surgical procedure documentation |
| Emergency Dept Note | 34878-9 | ED diagnoses, initial workup |
| Transfer Summary | 18761-7 | Inter-facility transfer documentation |
| Nursing Note | 34746-8 | Wound staging, nutritional assessment, vitals |
| Pathology Report | 11526-1 | Cancer staging, tissue diagnosis |
| Radiology Report | 18726-0 | Imaging findings supporting diagnoses |

**Edge cases in note type identification:**

1. **Missing or wrong LOINC code:** Some hospitals do not
   populate `DocumentReference.type` with LOINC codes.
   Instead, they use local codes or text descriptions.
   Fallback: parse the note title/category.

2. **"Discharge Summary" that is actually a brief note:**
   Some physicians write a one-paragraph discharge summary
   that lacks required coding elements. The AI must score
   completeness (see DISC-002 Section E.4).

3. **Multiple discharge summaries:** A patient with a
   complicated course may have an interim discharge summary
   followed by a final one. Only the final (most recent,
   non-superseded) should be used for coding.

4. **Addendum vs standalone note:** An addendum to the
   discharge summary contains critical coding information
   but is a separate DocumentReference. Must be assembled
   with the parent note.

### C.4 Inpatient vs Outpatient Classification

This is the single most consequential Encounter edge case
for ICD-10 coding, because coding rules differ fundamentally
between inpatient and outpatient settings (per DISC-001 and
constitution Article II.3).

**Encounter.class coding (v3 ActCode):**

| Code | Display | Setting | ICD-10 Coding Rules |
|------|---------|---------|-------------------|
| `IMP` | Inpatient | Inpatient admission | MAY code uncertain diagnoses as confirmed (Guidelines Sec II.H) |
| `AMB` | Ambulatory | Outpatient visit | MUST NOT code uncertain diagnoses (Guidelines Sec IV.H) |
| `EMER` | Emergency | Emergency department | Outpatient coding rules apply unless admitted |
| `OBSENC` | Observation | Observation status | **OUTPATIENT coding rules apply** despite patient being in hospital |
| `SS` | Short Stay | Same-day surgery | Outpatient coding rules |
| `HH` | Home Health | Home visit | Outpatient coding rules |

**Critical edge case: Observation status (`OBSENC`)**

Observation status is the most dangerous encounter type for
AI coding systems because:

1. **The patient is physically in the hospital** (often in
   an inpatient bed), making it look like an inpatient stay
2. **Outpatient coding rules apply** — uncertain diagnoses
   MUST NOT be coded as confirmed
3. **The encounter may convert to inpatient** partway through
   the stay (status change from `OBSENC` to `IMP`)
4. **If converted, coding rules change retroactively** —
   the entire stay is now coded under inpatient rules

**The two-midnight rule (CMS):** Medicare considers a stay
as inpatient if the admitting physician expects the patient
to require hospital care spanning at least two midnights.
Stays not meeting this threshold are observation (outpatient).

**Scenario that breaks AI coding:**
```
Day 1: Patient placed in observation (OBSENC)
  → AI codes using outpatient rules
  → "Probable pneumonia" → codes symptom (R05.9 Cough)
     NOT confirmed pneumonia (per Guidelines Sec IV.H)

Day 2: Physician converts to inpatient (IMP)
  → Coding rules change to inpatient
  → "Probable pneumonia" → NOW may code as confirmed
     J18.9 (per Guidelines Sec II.H)
  → AI must RECODE the entire encounter under new rules
```

**AI system handling:**
```
1. Check Encounter.class on EVERY coding analysis
2. If OBSENC: enforce outpatient coding rules strictly
3. Monitor for class change to IMP
4. On class change: trigger re-analysis with inpatient rules
5. Alert coder: "Encounter converted from observation to
   inpatient. Previous coding used outpatient rules.
   Re-review required."
```

**Edge case: ED-to-inpatient transition**

When a patient is admitted from the ED:
- Epic may create two encounters (ED encounter + inpatient)
  linked by `partOf`, or one encounter with a class change
- All ED notes belong to the ED encounter
- Admission H&P may reference either encounter
- The AI must gather notes from BOTH encounters for
  complete coding of the inpatient stay

**Competitor vulnerability:** Most competitors hard-code
inpatient vs outpatient at the start and never re-check.
Observation-to-inpatient conversion recoding is likely a
gap in Nym, Fathom, and Iodine systems. This is one of
the edge cases discovered in DISC-001 that separates
robust systems from fragile ones.

### C.5 AI Detection Methods for Encounter Issues

| Issue | Detection | Intervention |
|-------|-----------|-------------|
| Observation status encounter | `Encounter.class = OBSENC` | Enforce outpatient coding rules; flag uncertain diagnoses |
| Observation → inpatient conversion | Encounter.class changed from OBSENC to IMP on re-fetch | Trigger full re-analysis with inpatient rules; alert coder |
| ED → inpatient split encounters | Two encounters for same patient with overlapping dates; ED encounter `partOf` inpatient | Merge note sets from both encounters for coding |
| Encounter still in-progress | `Encounter.status = in-progress` at coding time | Flag: "Encounter not finalized — additional documentation expected" |
| Missing encounter class | Encounter.class is null or unrecognized code | Default to outpatient rules (conservative per constitution II.6); flag for manual classification |

---

## D. SMART on FHIR Authentication Failure Modes

### D.1 Token Expiration in Long Coding Sessions

SMART on FHIR uses OAuth 2.0 with token-based authentication.
Token management is a major production failure source.

**Token lifetimes by EHR:**

| EHR | Access Token Lifetime | Refresh Token | Notes |
|-----|----------------------|---------------|-------|
| Epic | **5 minutes** (default) | Supported in backend services; not always in EHR launch | Very short; aggressive refresh required |
| Cerner | **~5-10 minutes** (configurable) | Supported in most launch contexts | Slightly more permissive |
| SMART Backend Services | **5-60 minutes** (configurable by server) | Not applicable (uses client credentials) | Server-to-server flow |

**Failure scenario: Token expires mid-coding**
```
1. Coder launches app from Epic → access token granted (5 min)
2. Coder reviews patient chart (3 min)
3. AI begins analysis, makes 5 API calls (1 min)
4. AI makes 6th API call → 401 Unauthorized (token expired)
5. Without refresh: session is dead; coder loses work
6. With refresh: transparent token renewal; no interruption
```

**Edge cases:**

1. **No refresh token in EHR launch context:** When the app
   is launched from within Epic (EHR launch), refresh tokens
   may not be provided depending on the hospital's OAuth
   configuration. The app must handle this gracefully.

2. **Refresh token expiration:** Refresh tokens themselves
   expire (typically 24 hours). Long shifts require
   re-authentication.

3. **Concurrent token usage:** If the same user has the app
   open in two browser tabs, token refresh in one tab may
   invalidate the token in the other.

4. **Backend service auth for batch processing:** Overnight
   batch coding jobs should use SMART Backend Services
   (client credentials flow with signed JWT), not user tokens.

**Handling approach:**
```
1. ALWAYS request offline_access scope (for refresh tokens)
2. Proactively refresh tokens when <60 seconds remain
3. Queue pending API calls during refresh
4. If refresh fails: save state, prompt user to re-launch
5. For batch processing: use Backend Services auth
6. NEVER cache or log access/refresh tokens
```

### D.2 Scope Limitations

SMART on FHIR scopes control which resources the app can
access. Scope mismatches are a common production failure.

**Scopes required for our coding AI:**

| Scope | Purpose | Risk if Missing |
|-------|---------|----------------|
| `patient/Patient.read` | Read patient demographics | Cannot identify patient |
| `patient/Encounter.read` | Read encounters | Cannot determine inpatient/outpatient |
| `patient/DocumentReference.read` | Read clinical notes | **Cannot function — core requirement** |
| `patient/Condition.read` | Read problem list | Miss existing diagnoses |
| `patient/Observation.read` | Read labs and vitals | Miss lab-triggered CDI opportunities |
| `patient/Procedure.read` | Read procedures | Miss procedure documentation |
| `patient/MedicationRequest.read` | Read medications | Miss medication-implied diagnoses |
| `patient/AllergyIntolerance.read` | Read allergies | Incomplete clinical picture |
| `patient/DiagnosticReport.read` | Read diagnostic reports | Miss radiology/pathology |
| `patient/Binary.read` | Read binary content (PDFs, images) | Cannot read PDF-encoded notes |

**Edge cases:**

1. **Hospital denies requested scopes:** A hospital may
   grant the app only a subset of requested scopes. The app
   must check the granted scopes in the token response and
   degrade gracefully if critical scopes are missing.

2. **Scope varies per hospital:** Hospital A may grant all
   scopes; Hospital B may restrict Observation access due
   to local policy. Our system must handle per-hospital
   scope configurations.

3. **Write scopes for Claim:** Most hospitals will NOT grant
   `patient/Claim.write` even if requested. Claim output
   must use alternative integration patterns (Section E).

**Handling approach:**
```
1. Request all needed scopes at launch
2. Parse granted scopes from token response
3. Compare granted vs required; identify gaps
4. If DocumentReference.read is missing: hard stop,
   inform user "Insufficient permissions for coding"
5. If secondary scopes missing: proceed with degraded
   analysis; note missing data in results
6. Log scope grants per hospital (non-PHI) for monitoring
```

### D.3 Patient Opt-Out Handling

Patients may opt out of FHIR data sharing under certain
circumstances. The 21st Century Cures Act restricts
information blocking, but exceptions exist.

**How patient opt-out manifests:**

| Scenario | API Behavior | AI System Impact |
|----------|-------------|-----------------|
| Patient opted out via portal | May return empty results or 404 for that patient | No data available for coding |
| Patient revoked app access | Access token becomes invalid for that patient | 401/403 on patient-specific queries |
| Partial opt-out (specific records) | Some DocumentReferences missing from results | Incomplete coding — dangerous if coder doesn't know |
| State-level privacy restrictions (e.g., CA CCPA, NY SHIN-NY) | Additional consent requirements | May need separate consent workflow |

**21st Century Cures Act information blocking exceptions:**
The Act prohibits information blocking but allows 8 exceptions:

1. Preventing harm
2. Privacy (patient request)
3. Security
4. Infeasibility
5. Health IT performance
6. Content and manner (can offer via alternative means)
7. Fees
8. Licensing

**AI system handling:**
```
1. If patient data returns empty/404: display clear
   "Patient data not available" message to coder
2. NEVER attempt to circumvent opt-out
3. Log opt-out encounters (encounter ID only, no PHI)
4. Enable manual coding workflow as fallback
5. Track opt-out rates per hospital (aggregate, non-PHI)
   to identify configuration issues vs true opt-outs
```

### D.4 EHR Maintenance and Downtime Patterns

EHR systems have scheduled and unscheduled downtime that
affects FHIR API availability.

**Typical downtime patterns:**

| Pattern | Timing | Duration | Frequency |
|---------|--------|----------|-----------|
| Epic quarterly upgrade | Weekend, typically Saturday night to Sunday morning | 4-12 hours | Quarterly (Feb, May, Aug, Nov) |
| Monthly maintenance | Varies by hospital; often Sunday 2-6 AM local | 2-4 hours | Monthly |
| Unplanned outage | Unpredictable | Minutes to hours | Rare (~2-4 per year at most hospitals) |
| Network maintenance | Hospital IT scheduled windows | 1-2 hours | Monthly |
| Partial outage (some resources) | Unpredictable | Varies | Occasional |

**HTTP responses during downtime:**

| Status | Meaning | Action |
|--------|---------|--------|
| 503 Service Unavailable | Server down for maintenance | Retry with backoff; switch to offline mode |
| 504 Gateway Timeout | Server overloaded or network issue | Retry once; then offline mode |
| 502 Bad Gateway | Load balancer/proxy issue | Retry with backoff |
| Connection refused | Server completely down | Offline mode immediately |
| Partial responses (some 200, some 503) | Partial outage | Cache successful responses; retry failed |

**AI system handling (per constitution Article II.5):**
```
1. Implement circuit breaker pattern:
   - 3 consecutive failures → open circuit
   - Open circuit → return DegradedResult immediately
   - After 60 seconds → half-open (try one request)
   - If succeeds → close circuit
2. Cache recently fetched data for offline coding
3. Display clear "EHR connection unavailable" status
4. Enable manual coding workflow (type-in mode)
5. Queue pending operations for retry when connection restores
6. NEVER block the coder's workflow due to API failure
```

> **Note:** Downtime patterns based on common Epic deployment
> practices. Actual maintenance windows vary by hospital.
> Verify during onboarding for each deployment site.

---

## E. FHIR Claim Resource for Coding Output

### E.1 The Reality: Claim Write Is Not Supported

**This is the single most important finding in this section.**

Despite FHIR R4 defining a Claim resource with full
create/update semantics, **most EHR systems do not support
FHIR Claim write operations in production.**

| EHR | Claim Read | Claim Write (create/update) | Status |
|-----|-----------|---------------------------|--------|
| Epic | ExplanationOfBenefit read (claims history) | **NOT supported** | No write path via FHIR |
| Cerner | ExplanationOfBenefit read | **NOT supported** | No write path via FHIR |
| Meditech | Limited | **NOT supported** | No write path via FHIR |

**Why this matters:** Our AI system generates coding
suggestions that must ultimately become claim data. If FHIR
Claim write is not supported, we need an alternative
integration pattern.

### E.2 Alternative Integration Patterns for Coding Output

Since FHIR Claim write is not available, production coding
systems use these integration patterns:

| Pattern | Description | Pros | Cons |
|---------|-------------|------|------|
| **EHR Encoder UI integration** | AI suggestions displayed in a review UI; coder accepts/rejects; codes entered into EHR's native encoder | Human-in-the-loop; uses EHR's validation; compliant | Requires EHR UI integration (Epic Hyperdrive, Cerner PowerChart) |
| **HL7v2 DFT (Detail Financial Transaction)** | Send coded data via HL7v2 message to EHR charge posting system | Mature; widely supported; well-understood | Legacy protocol; complex message building; site-specific mappings |
| **X12 837 (Claim Transaction)** | Send completed claim to clearinghouse in X12 837P/837I format | Industry standard for claim submission; payer-ready | Downstream of EHR; skips EHR encoder validation |
| **Proprietary EHR API** | Use Epic/Cerner proprietary APIs to write back charge data | Most integrated; uses EHR validation | Vendor-specific; may require additional certification |
| **FHIR-based workaround** | Write suggestions as Task resources or CommunicationRequest resources for human action | FHIR-native; interoperable | Not a direct coding path; requires human manual entry |

**Recommended architecture (per constitution Article II.1):**

Our system MUST use the **EHR Encoder UI integration** pattern
for Phase 1, because:

1. Constitution Article II.1 requires human approval before
   any claim submission — the EHR encoder UI provides this
2. Using the EHR's native encoder ensures code validation
   against the hospital's specific payer rules
3. It avoids building claim submission infrastructure in
   Phase 1 (which is deferred to Phase 2+)
4. It works with any EHR regardless of financial API support

**The AI outputs a structured suggestion set (Pydantic model)
that is displayed in our coder review interface. The coder
validates and enters approved codes into the EHR's encoder.
Our system NEVER directly writes claims.**

### E.3 FHIR Claim Resource Structure (For Reference)

Although we won't write FHIR Claims in Phase 1, understanding
the structure is important for future phases and for the data
model design.

**Required fields for a draft Claim:**

```json
{
  "resourceType": "Claim",
  "status": "draft",
  "type": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/claim-type",
      "code": "institutional"
    }]
  },
  "use": "claim",
  "patient": { "reference": "Patient/123" },
  "created": "2026-04-01",
  "provider": { "reference": "Organization/456" },
  "priority": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/processpriority",
      "code": "normal"
    }]
  },
  "insurance": [{
    "sequence": 1,
    "focal": true,
    "coverage": { "reference": "Coverage/789" }
  }],
  "diagnosis": [
    {
      "sequence": 1,
      "diagnosisCodeableConcept": {
        "coding": [{
          "system": "http://hl7.org/fhir/sid/icd-10-cm",
          "code": "I50.23",
          "display": "Acute on chronic systolic heart failure"
        }]
      },
      "type": [{
        "coding": [{
          "system": "http://terminology.hl7.org/CodeSystem/ex-diagnosistype",
          "code": "principal"
        }]
      }],
      "onAdmission": {
        "coding": [{
          "system": "http://terminology.hl7.org/CodeSystem/ex-diagnosis-on-admission",
          "code": "y"
        }]
      }
    }
  ],
  "procedure": [
    {
      "sequence": 1,
      "procedureCodeableConcept": {
        "coding": [{
          "system": "http://www.ama-assn.org/go/cpt",
          "code": "99223",
          "display": "Initial hospital care, high complexity"
        }]
      }
    }
  ]
}
```

**Key code system URIs:**

| Code System | URI | Usage |
|------------|-----|-------|
| ICD-10-CM | `http://hl7.org/fhir/sid/icd-10-cm` | Diagnosis codes |
| ICD-10-PCS | `http://hl7.org/fhir/sid/icd-10-pcs` | Inpatient procedure codes |
| CPT | `http://www.ama-assn.org/go/cpt` | Outpatient procedure codes |
| HCPCS | `http://terminology.hl7.org/CodeSystem/HCPCS` | Supplies, equipment, services |
| MS-DRG | `http://terminology.hl7.org/CodeSystem/MSDRG` | DRG grouping (typically computed, not submitted) |
| Revenue Code | `http://terminology.hl7.org/CodeSystem/ex-revenue-center` | Revenue center codes for institutional claims |

**Principal vs secondary diagnosis:**
- Principal diagnosis: `diagnosis.type.code = "principal"` and
  `diagnosis.sequence = 1`
- Secondary diagnoses: `diagnosis.sequence = 2, 3, ...` with
  type `"admitting"`, `"clinical"`, or `"discharge"`
- Present on Admission: `diagnosis.onAdmission.code` = `y`
  (yes), `n` (no), `u` (unknown), `w` (clinically undetermined)

### E.4 Claim Amendments and Modifications

When a coder modifies AI-suggested codes (which is expected
and required per constitution Article II.1):

**Recommended approach for our system:**

| Event | Action |
|-------|--------|
| Coder accepts AI suggestion | Record acceptance in audit log; mark suggestion as "approved" |
| Coder rejects AI suggestion | Record rejection with reason; feed back into prompt improvement (PHR) |
| Coder modifies AI suggestion | Record original and modified codes; analyze modification pattern for prompt tuning |
| Coder adds code not suggested by AI | Record gap; analyze why AI missed this code |
| Case re-opened after initial coding | Retrieve previous coding; show diff; enable incremental review |

**FHIR Claim versioning (for future phases):**
- FHIR does not natively support Claim versioning
- Replacement claims use `Claim.related` with
  `relationship = "prior"` referencing the original
- Our system should maintain its own internal versioning
  (Pydantic model with version field) independent of FHIR

### E.5 DRG Representation

MS-DRG is not directly represented in the FHIR Claim resource.
DRG is computed from diagnosis and procedure codes by a DRG
grouper algorithm.

**Our system's approach:**

1. The coding agent suggests diagnoses and procedures
2. The DRG agent computes the expected DRG from the
   suggested code set (using CMS MS-DRG grouper logic)
3. The DRG and revenue impact are displayed to the coder
   for review
4. The actual DRG assignment is made by the hospital's
   grouper when the claim is submitted through the EHR

**No FHIR integration needed for DRG** — it is computed
internally and displayed to the coder as supplemental
information. The hospital's official DRG comes from their
own grouper, not ours.

---

## F. Cross-Cutting Architecture Recommendations

### F.1 FHIR Client Design Pattern

Based on the edge cases documented above, our FHIR client
(`src/core/fhir/client.py`) must implement:

```
FHIRClient (abstract)
├── EpicFHIRClient
│   ├── Epic-specific auth flow
│   ├── Epic extension handling
│   └── Epic rate limit config
├── CernerFHIRClient
│   ├── Cerner-specific auth flow
│   ├── C-CDA parsing
│   └── Cerner rate limit config
└── MockFHIRClient (for testing)
    └── Deterministic test data
```

**Every client method must:**

1. Handle token refresh transparently
2. Implement retry with exponential backoff
3. Return `DegradedResult` on persistent failure
4. Never log PHI from FHIR responses
5. Track request metrics (non-PHI) per hospital

### F.2 Data Freshness Strategy

| Data Type | Freshness Requirement | Strategy |
|-----------|----------------------|----------|
| Patient demographics | Once per encounter | Cache for encounter duration |
| Encounter status/class | Before each coding analysis | Always re-fetch; class may change |
| Clinical notes | Before coding; re-check before finalization | Fetch all, track hashes, re-fetch changed |
| Lab results | Before coding | Fetch once; re-fetch if encounter still active |
| Problem list | Before coding | Fetch once per analysis |

### F.3 Error Handling Strategy

Per constitution Article II.5, the system must never block
the clinical workflow:

| FHIR Failure | Response |
|-------------|----------|
| 401 Unauthorized | Attempt token refresh; if fails, prompt re-launch |
| 403 Forbidden | Check scope; report missing permissions to coder |
| 404 Not Found | Patient may have opted out; display clear message |
| 429 Rate Limited | Backoff and retry; show "Loading..." to coder |
| 500 Server Error | Retry once; then DegradedResult with "EHR unavailable" |
| 503 Service Unavailable | Circuit breaker; offline mode; manual coding enabled |
| Network timeout | Retry with longer timeout; then DegradedResult |
| Invalid FHIR response | Log error (no PHI); parse what is usable; DegradedResult for rest |

### F.4 Competitor Failure Analysis

Based on the edge cases documented above, here is where
competitors likely fail:

| Competitor | Likely Failure Point | Why |
|-----------|---------------------|-----|
| **Abridge** | N/A — generates notes, does not consume them for coding | Different product category |
| **Nuance DAX** | N/A — ambient documentation, not coding | Different product category |
| **Nym Health** | Note encoding variation; observation→inpatient recoding; late addenda | Coding-focused but likely tested against single EHR/encoding; observation status edge case requires re-analysis |
| **Fathom** | Epic/Cerner divergence; note timing gaps; missing note types | Likely built primarily for Epic; Cerner C-CDA parsing probably weaker |
| **Iodine Software** | Encounter class edge cases; CDI timing (pre-discharge vs post-coding) | CDI-focused but observation status rules apply to CDI queries too |
| **Cohere Health** | Prior auth focused — different FHIR resources | Different product category |
| **Waystar** | Claims processing — downstream of coding | Different product category; they work with X12 837 not FHIR |

**Our advantage:** By documenting and engineering for every
edge case in this DISC-003 document, we build a FHIR
integration layer that handles the real-world complexity
competitors ignore. This is part of our competitive moat
(per constitution Article V).

---

## Verification Status

Last verified: 2026-04-05 (FIX-001 research audit)
Verified by: Live web fetch during FIX-001 session

| Claim Category | Count | Status |
|---|---|---|
| VERIFIED-LIVE | 10 | FHIR specs, regulatory references, EHR vendor docs |
| TRAINING-DATA (directional) | 3 | Rate limits, App Orchard timelines, token lifetimes |
| OUTDATED (corrected in FIX-001) | 1 | Market share (Epic 38%→42.3%, Cerner 25%→22.9%) |

**Critical corrections made in FIX-001:**
- Epic market share updated from ~38% to 42.3% (KLAS 2024)
- Cerner/Oracle Health updated from ~25% to 22.9% (KLAS 2024)
- Added Meditech at 14.8% for completeness

**Note on technical edge cases:** Most FHIR implementation details
(rate limits, token lifetimes, search parameter support) are based
on published vendor documentation and developer community experience.
These are labeled as directional estimates in the document. Exact
behaviors must be verified per-hospital during onboarding.

Next re-verification due: 2026-10-01 (Epic quarterly release cycle)

---

## Sources

### FHIR Standards and Specifications

- HL7 FHIR R4 Specification: https://hl7.org/fhir/R4/
- FHIR R4 DocumentReference: https://hl7.org/fhir/R4/documentreference.html
- FHIR R4 Encounter: https://hl7.org/fhir/R4/encounter.html
- FHIR R4 Claim: https://hl7.org/fhir/R4/claim.html
- SMART on FHIR: https://docs.smarthealthit.org/
- SMART Backend Services: https://hl7.org/fhir/uv/bulkdata/authorization/index.html
- US Core Implementation Guide: https://www.hl7.org/fhir/us/core/

### EHR Vendor Documentation

- Epic on FHIR: https://fhir.epic.com/Documentation
- Epic App Orchard / Showroom: https://appmarket.epic.com/
- Cerner (Oracle Health) FHIR Documentation: https://fhir.cerner.com/
- Cerner Code Console: https://code.cerner.com/

### Regulatory

- 21st Century Cures Act Final Rule (ONC): https://www.healthit.gov/curesrule/
- ONC Information Blocking Final Rule: https://www.healthit.gov/topic/information-blocking
- CMS Interoperability and Patient Access Final Rule: https://www.cms.gov/Regulations-and-Guidance/Guidance/Interoperability/index

### Industry Analysis

> **Note:** The following sources informed this research but
> specific URLs could not be verified during this session.
> Treat as directional references pending primary source
> confirmation.

- KLAS Research: EHR market share reports (Epic ~38%, Cerner ~25%)
- CHIME Digital Health Most Wired Survey: EHR implementation patterns
- ONC Data Brief: Interoperability progress metrics
- Health IT community forums: FHIR implementation experiences
  (chat.fhir.org, community.fhir.org)

---

## Appendix: FHIR Resource Quick Reference for Coding AI

### Resources We Read (Phase 1)

| Resource | Purpose in Coding AI |
|----------|---------------------|
| Patient | Demographics, insurance identifiers |
| Encounter | Inpatient/outpatient determination, dates, status |
| DocumentReference | Clinical notes (THE core input) |
| Binary | Actual note content when DocumentReference points to Binary |
| Condition | Existing problem list (avoid duplicate suggestions) |
| Observation | Lab values, vitals (CDI triggers per DISC-002 Section C) |
| MedicationRequest | Active medications (diagnosis inference per DISC-002 Section C) |
| DiagnosticReport | Radiology/pathology results |
| Procedure | Performed procedures (CPT coding support) |
| AllergyIntolerance | Safety context |
| Coverage | Insurance information (payer rules) |

### Resources We Do NOT Write in Phase 1

| Resource | Why Not |
|----------|---------|
| Claim | Not supported by EHRs; coding output via coder review UI |
| Encounter | Read-only for our system |
| Condition | We suggest, we don't write diagnoses |
| Any clinical resource | Constitution Article II.1 — no autonomous clinical assertions |
