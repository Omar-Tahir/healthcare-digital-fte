# Skill: FHIR R4 Integration

**Domain:** FHIR R4 EHR integration (Epic, Cerner)  
**Source research:** DISC-003, DESIGN-005  
**Used by:** FHIR client, all agents (data source layer)  
**Read before:** Any work on `src/core/fhir/`

---

## Section 1 — Epic FHIR Production Realities

These are the real-world deviations from the FHIR R4 spec
that break AI systems in production. Source: DISC-003.

### Rate Limits

| EHR | Rate Limit | Enforcement |
|-----|-----------|-------------|
| Epic | 60-120 requests/minute (varies by hospital) | HTTP 429 with Retry-After header |
| Cerner | ~100 requests/minute (varies) | HTTP 429 |

Rate limits are per-app, per-hospital. A single coding
analysis requires 5-8 FHIR calls (encounter, notes,
conditions, observations, medications). At 120 req/min,
the system can analyze ~15-24 encounters/minute.

### Note Availability Timing

Clinical notes are NOT immediately available after creation.

| Event | Typical Delay | Variance |
|-------|--------------|----------|
| Note created | Not available via FHIR | — |
| Note signed by author | Available within minutes | 1-30 min |
| Note cosigned (resident notes) | Available after cosign | Hours |
| Amended notes | Variable — may be immediate or delayed | Minutes to hours |

**If no notes found for an active encounter:** Return
`DegradedResult(reason="notes_not_yet_available")`. Do NOT
retry aggressively — check again in 5 minutes.

### DocumentReference Content Formats

Notes arrive in 4 formats. The FHIR client must handle all:

| Format | contentType | Handling |
|--------|------------|---------|
| Plain text | `text/plain` | Use directly |
| XHTML | `text/html` | Strip HTML tags, preserve paragraph structure |
| C-CDA XML | `application/xml` | Parse CDA sections (see Section 2) |
| PDF | `application/pdf` | Text extraction; DegradedResult if OCR fails |

Base64 encoding is common — always check `content.attachment.data`
for base64 and decode before format-specific handling.

### Known Epic FHIR Deviations

1. **Token expiration:** 5 minutes by default (not the
   60-minute OAuth standard)
2. **Search parameter limitations:** Not all FHIR search
   parameters are supported. Test each in production.
3. **Claim resource:** Read-only (ExplanationOfBenefit).
   NO write support. NO create support.
4. **Binary content:** Large documents may timeout. Use
   streaming/chunked retrieval.
5. **Patient opt-out:** Returns empty results or 404,
   not a standard error.

### App Orchard Approval

Epic requires 3-6 month approval process for FHIR apps.
- Sandbox testing on fhir.epic.com (synthetic data)
- Production approval per hospital
- Annual recertification
- Sandbox ≠ production (clean data vs messy real data)

---

## Section 2 — Note Extraction Patterns

### Extracting Text from C-CDA XML

C-CDA R2 (Clinical Document Architecture) is the most common
structured document format in US EHRs. Key sections:

| Section | LOINC Code | Content |
|---------|-----------|---------|
| History of Present Illness | 10164-2 | HPI narrative |
| Assessment | 51848-0 | Physician assessment |
| Plan of Treatment | 18776-5 | Treatment plan |
| Hospital Course | 8648-8 | Discharge summary narrative |
| Physical Examination | 29545-1 | Physical exam findings |
| Medications | 10160-0 | Current medications |
| Problems | 11450-4 | Problem list |
| Results | 30954-2 | Lab results |

**Extraction approach:** Parse XML, locate `<section>` elements
by LOINC templateId, extract `<text>` child content, strip
markup, preserve section boundaries for NLP pipeline.

### Detecting Note Type

Note type is encoded in `DocumentReference.type.coding`:

| LOINC Code | Note Type | Coding Relevance |
|-----------|-----------|-----------------|
| 11506-3 | Progress Note | Daily clinical assessment |
| 18842-5 | Discharge Summary | Primary coding document |
| 34117-2 | H&P Note | Admission documentation |
| 11504-8 | Operative Note | Surgical procedure detail |
| 28570-0 | Procedure Note | Non-surgical procedures |
| 11488-4 | Consultation Note | Specialist assessment |

### Amended Note Handling

Three patterns for amendments:

1. **relatesTo.code = "appends"** — Addendum. Both original
   and addendum must be analyzed. Concatenate for NLP.
2. **relatesTo.code = "replaces"** — Supersedes original.
   Only analyze replacement document. Ignore original.
3. **In-place edit (no relatesTo)** — Some Epic configs
   update content without creating a new DocumentReference.
   Track content hashes to detect changes.

**Always sort notes by date descending.** Analyze most recent
version. Track document hashes for change detection.

---

## Section 3 — Encounter Class Mapping

This mapping determines which ICD-10 coding rules apply.
Getting this wrong means applying inpatient rules to outpatient
encounters (or vice versa) — a hard guardrail violation.

| Encounter.class.code | Display | Coding Setting | Key Rule Difference |
|---------------------|---------|---------------|-------------------|
| IMP | Inpatient | INPATIENT | Uncertain dx coded as confirmed |
| AMB | Ambulatory | OUTPATIENT | Uncertain dx → code symptom |
| EMER | Emergency | OUTPATIENT | Uncertain dx → code symptom |
| OBSENC | Observation | **OUTPATIENT** | Uncertain dx → code symptom |
| HH | Home Health | OUTPATIENT | Uncertain dx → code symptom |

### Why OBSENC = OUTPATIENT Matters

A patient in observation status is physically in the hospital
but classified as outpatient for coding and billing purposes.
This means:

- "Possible pneumonia" in observation → code R05.9 (cough),
  NOT J18.9 (pneumonia)
- POA indicators do NOT apply
- Different DRG rules apply (observation = outpatient APC,
  not inpatient MS-DRG)

### Observation-to-Inpatient Conversion

When encounter class changes from OBSENC to IMP:
1. **Discard all previous coding analysis**
2. Re-fetch encounter data from FHIR
3. Re-analyze under INPATIENT coding rules
4. Uncertain diagnoses now coded as confirmed
5. POA indicators now required
6. MS-DRG grouping now applies

This transition requires monitoring encounter status via
polling or FHIR Subscription (R5).

---

## Section 4 — Error Handling Patterns

### Retryable vs Terminal Errors

| HTTP Status | Category | Action |
|------------|----------|--------|
| 429 | Rate limited | Retry after Retry-After header delay |
| 500 | Server error | Retry once with backoff |
| 502 | Bad gateway | Retry with exponential backoff |
| 503 | Service unavailable | Circuit breaker; DegradedResult |
| 504 | Gateway timeout | Retry once; DegradedResult |
| 401 | Unauthorized | Refresh token; retry once |
| 403 | Forbidden | Terminal — check scope; DegradedResult |
| 404 | Not found | Terminal — patient opt-out or invalid ID |

### Retry Parameters

```
max_retries: 3
base_delay: 1 second
max_delay: 30 seconds
backoff: exponential (1s, 2s, 4s)
retryable_codes: [429, 500, 502, 503, 504]
```

### DegradedResult Pattern

Per Constitution Article II.5, the system NEVER blocks the
coder's workflow. When FHIR calls fail:

```python
# Return DegradedResult instead of raising exception
return DegradedResult(
    is_degraded=True,
    source="observations",
    reason="FHIR API returned 503 after 3 retries",
    error_code="503",
    retry_after_seconds=60,
)
```

The coder sees "Some data unavailable — manual mode enabled"
and can continue working without AI assistance.

### Circuit Breaker

```
CLOSED → 3 consecutive failures → OPEN
OPEN → wait 60 seconds → HALF_OPEN
HALF_OPEN → test request succeeds → CLOSED
HALF_OPEN → test request fails → OPEN (reset timer)
```

When circuit is OPEN, all requests immediately return
DegradedResult without making network calls. This prevents
flooding a struggling EHR with retry requests.

---

## Section 5 — Authentication Gotchas

### Token Expiry in Long Sessions

Epic access tokens expire in 5 minutes by default. A coding
session may last 30+ minutes. The TokenManager must:

1. Track token expiry timestamp
2. Proactively refresh when <60 seconds remain
3. If refresh token unavailable (some Epic launch contexts
   don't support refresh), prompt user to re-launch from EHR
4. Never let a token expire mid-request (check before call)

### Scope Requirements

| Scope | Required For | If Missing |
|-------|-------------|-----------|
| patient/DocumentReference.read | Clinical notes | **HARD STOP** — cannot function |
| patient/Encounter.read | Encounter context | Hard stop — cannot determine coding setting |
| patient/Patient.read | Demographics | Degraded — limited context |
| patient/Condition.read | Problem list | Degraded — may miss Excludes 1 |
| patient/Observation.read | Labs/vitals | Degraded — no CDI lab triggers |
| patient/MedicationRequest.read | Medications | Degraded — miss medication-implied dx |
| patient/Binary.read | PDF/CDA content | Degraded — some notes unreadable |

### Patient Opt-Out

21st Century Cures Act allows patients to opt out of FHIR
data sharing. When a patient has opted out:

- API returns empty results or 404
- NEVER attempt to circumvent
- Display "Patient data not available" to coder
- Enable manual coding workflow
- Log opt-out encounter (encounter_id only, no PHI)

---

## MCP Tool Usage

- `mcp_fhir_fetch(resource, id)` — retrieve a specific FHIR
  resource by ID
- `mcp_fhir_search(resource, params)` — search for FHIR
  resources with query parameters
- Use MCP tools for individual resource fetches. Use the
  FHIRClient's `get_coding_context()` for aggregated data
  retrieval (parallel sub-queries).
