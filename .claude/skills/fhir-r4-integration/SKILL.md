---
name: fhir-r4-integration
version: "2.0.0"
description: >
  Use this skill whenever working on FHIR client code, EHR integration, clinical data retrieval, encounter/patient/observation resource parsing, authentication with Epic or Cerner, or any component that reads from or writes to a FHIR API. Triggers on: FHIR, HL7, Epic, Cerner, DocumentReference, Encounter, Patient, Observation, SMART on FHIR, OAuth token, rate limit, circuit breaker, DegradedResult from API calls, C-CDA, LOINC code, note extraction, encounter class mapping, observation-to-inpatient conversion, or HTTP 429/503 retry logic for clinical APIs. Also use when editing src/core/fhir/, src/mcp/fhir_tools.py, or any code that makes HTTP calls to an EHR system. If the task involves getting clinical data from an external system or parsing FHIR resources — load this skill.
allowed-tools: Read, Bash
license: Proprietary
---

# FHIR R4 Integration — Epic Production Specifics

## Critical: Read hipaa-compliance Skill First

No FHIR response data goes into any log. Patient identifiers
in FHIR responses are PHI — strip before logging.

## The OBS Mapping (Most Commonly Wrong)

EncounterClass.OBSERVATION -> CodingClass.OUTPATIENT
OBS patients use outpatient coding rules.
Not inpatient — even though the patient is in the hospital.
This affects every uncertain diagnosis coding decision.

## Note Content Formats — Epic Sends Four Types

| Format | contentType | Handling |
|--------|------------|---------|
| Plain text | text/plain | Use directly |
| XHTML | text/html | Strip HTML tags, preserve paragraph structure |
| C-CDA XML | application/xml | Parse CDA sections by LOINC templateId |
| PDF | application/pdf | Text extraction; DegradedResult if OCR fails |

Base64 encoding is common — always check
`content.attachment.data` for base64 and decode before
format-specific handling.

## Note Type LOINC Codes

| LOINC Code | Note Type | Coding Relevance |
|-----------|-----------|-----------------|
| 11506-3 | Progress Note | Daily clinical assessment |
| 18842-5 | Discharge Summary | Primary coding document |
| 34117-2 | H&P Note | Admission documentation |
| 11504-8 | Operative Note | Surgical procedure detail |
| 28570-0 | Procedure Note | Non-surgical procedures |
| 11488-4 | Consultation Note | Specialist assessment |

## C-CDA Section LOINC Codes

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

## Rate Limits and Retry

| EHR | Rate Limit | Enforcement |
|-----|-----------|-------------|
| Epic | 60-120 req/min (varies by hospital) | HTTP 429 + Retry-After |
| Cerner | ~100 req/min (varies) | HTTP 429 |

A single coding analysis requires 5-8 FHIR calls. At 120
req/min, the system can analyze ~15-24 encounters/minute.

### Retry Parameters

```
max_retries: 3
base_delay: 1 second
max_delay: 30 seconds
backoff: exponential (1s, 2s, 4s)
retryable_codes: [429, 500, 502, 503, 504]
```

### Error Classification

| HTTP Status | Category | Action |
|------------|----------|--------|
| 429 | Rate limited | Retry after Retry-After header |
| 500 | Server error | Retry once with backoff |
| 502 | Bad gateway | Retry with exponential backoff |
| 503 | Service unavailable | Circuit breaker; DegradedResult |
| 504 | Gateway timeout | Retry once; DegradedResult |
| 401 | Unauthorized | Refresh token; retry once |
| 403 | Forbidden | Terminal — check scope; DegradedResult |
| 404 | Not found | Terminal — patient opt-out or invalid ID |

Always return DegradedResult — never raise to caller
(Constitution Article II.5).

### Circuit Breaker

```
CLOSED -> 3 consecutive failures -> OPEN
OPEN -> wait 60 seconds -> HALF_OPEN
HALF_OPEN -> test request succeeds -> CLOSED
HALF_OPEN -> test request fails -> OPEN (reset timer)
```

## Authentication Gotchas

### Token Expiry

Epic access tokens expire in **5 minutes** by default (not
the 60-minute OAuth standard). TokenManager must:

1. Track token expiry timestamp
2. Proactively refresh when < 60 seconds remain
3. If refresh unavailable, prompt user to re-launch from EHR
4. Never let a token expire mid-request

### Required Scopes

| Scope | Required For | If Missing |
|-------|-------------|-----------|
| patient/DocumentReference.read | Clinical notes | HARD STOP |
| patient/Encounter.read | Encounter context | HARD STOP |
| patient/Patient.read | Demographics | Degraded |
| patient/Condition.read | Problem list | Degraded |
| patient/Observation.read | Labs/vitals | Degraded |
| patient/MedicationRequest.read | Medications | Degraded |
| patient/Binary.read | PDF/CDA content | Degraded |

### Patient Opt-Out

21st Century Cures Act allows patients to opt out.
API returns empty results or 404. NEVER circumvent.
Display "Patient data not available" and enable manual mode.

## Amended Note Handling

Three patterns:
1. **relatesTo.code = "appends"** — Addendum. Analyze both.
2. **relatesTo.code = "replaces"** — Supersedes. Only analyze replacement.
3. **In-place edit (no relatesTo)** — Track content hashes.

Always sort notes by date descending. Analyze most recent.

## Encounter Class Mapping

| Encounter.class.code | Coding Setting | Key Difference |
|---------------------|---------------|----------------|
| IMP | INPATIENT | Uncertain dx coded as confirmed |
| AMB | OUTPATIENT | Uncertain dx -> code symptom |
| EMER | OUTPATIENT | Uncertain dx -> code symptom |
| OBSENC | **OUTPATIENT** | Uncertain dx -> code symptom |
| HH | OUTPATIENT | Uncertain dx -> code symptom |

### Observation-to-Inpatient Conversion

When encounter class changes from OBSENC to IMP:
1. Discard all previous coding analysis
2. Re-fetch encounter data from FHIR
3. Re-analyze under INPATIENT coding rules
4. Uncertain diagnoses now coded as confirmed
5. POA indicators now required
6. MS-DRG grouping now applies

## MCP Tools Available

- mcp_fhir_get_patient(patient_id)
- mcp_fhir_get_encounter(encounter_id)
- mcp_fhir_get_notes(patient_id, encounter_id)
- mcp_fhir_get_labs(patient_id, encounter_id, loinc_codes)
- mcp_fhir_fetch(resource, id) — generic resource retrieval
- mcp_fhir_search(resource, params) — search with query params

## For Full Reference

See references/epic-deviations.md (Epic-specific FHIR quirks)
See references/loinc-note-types.md (note type LOINC codes)
