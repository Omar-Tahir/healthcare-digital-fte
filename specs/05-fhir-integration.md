# DESIGN-005: FHIR R4 Integration Specification

**Status:** COMPLETE  
**Date:** 2026-04-02  
**Author:** Claude (AI Engineering Partner)  
**Research inputs:** DISC-003 (FHIR R4 Implementation Edge Cases)  
**Constitution references:** Article II.4 (HIPAA), Article II.5
(Graceful Degradation), Article III.4 (Pydantic), Article III.8
(FastAPI)  
**Implementation target:** `src/core/fhir/client.py`,
`src/core/fhir/auth.py`, `src/core/fhir/resources.py`  
**Depends on:** None (data source layer)  
**Used by:** DESIGN-001 (Coding Rules Engine),
DESIGN-002 (CDI Intelligence Layer)  
**ADR references:** ADR-001 (FHIR R4 Over HL7v2)

---

## Purpose

This spec defines the FHIR R4 integration layer that retrieves
clinical data from hospital EHR systems (Epic, Cerner/Oracle
Health) for use by the coding and CDI agents.

The FHIR client is the system's only connection to patient
clinical data. Every downstream component — NLP pipeline,
coding agent, CDI agent, DRG calculator — depends on the
quality, completeness, and reliability of data this layer
provides.

**Design priorities (in order):**
1. Never expose PHI in logs or error messages
2. Never block the coder's workflow (graceful degradation)
3. Handle real-world EHR deviations from the FHIR spec
4. Minimize API calls (token efficiency, rate limit compliance)

---

## 1. FHIR Resources

The system uses 7 FHIR R4 resources. Each resource has specific
fields required for coding and CDI analysis, and specific edge
cases documented in DISC-003.

### 1.1 Patient

**Purpose:** Minimal demographics for encounter context.
Patient data is NEVER stored beyond the active session.

**Required fields:**

| Field | FHIR Path | Usage | PHI? |
|-------|----------|-------|------|
| Patient ID | Patient.id | Cross-reference only | Yes — logged as encounter context, never stored |
| Birth date | Patient.birthDate | Age calculation for age-specific codes | Yes — used in memory only, never logged |
| Gender | Patient.gender | Gender-specific code validation | No |

**Edge cases (DISC-003):**
- Patient opt-out: returns empty or 404. Display "Patient
  data not available" to coder. Never attempt to circumvent.
- Partial opt-out: some resources missing. Proceed with
  degraded analysis; flag missing data in results.

**PHI handling:** Patient name, address, phone, email, SSN,
MRN are NEVER read from the FHIR response. The Pydantic model
excludes these fields entirely — they are not parsed, not
stored in memory, not available to any downstream component.

### 1.2 Encounter

**Purpose:** Determines inpatient vs outpatient setting, which
controls ICD-10 coding rules (uncertain diagnosis handling,
POA requirements).

**Required fields:**

| Field | FHIR Path | Usage |
|-------|----------|-------|
| Encounter ID | Encounter.id | Primary identifier for all logging and audit |
| Status | Encounter.status | Active, finished, cancelled |
| Class | Encounter.class | IMP (inpatient), AMB (outpatient), EMER (ED), OBSENC (observation) |
| Type | Encounter.type | Visit type detail |
| Period | Encounter.period | Admission/discharge dates |
| Diagnosis list | Encounter.diagnosis | Existing coded diagnoses |
| Hospitalization | Encounter.hospitalization | Admit source, discharge disposition |

**Edge cases (DISC-003 Section C):**

1. **OBSENC (Observation status):** Patient is physically in
   the hospital but classified as outpatient for coding
   purposes. MUST use outpatient coding rules (uncertain
   diagnosis = code symptom, not condition).
   ```
   IF encounter.class.code == "OBSENC":
       coding_setting = "OUTPATIENT"  # NOT inpatient
   ```

2. **Observation-to-inpatient conversion:** Patient status
   changes from OBSENC to IMP mid-encounter. Requires full
   re-analysis with inpatient coding rules.
   ```
   IF encounter.class changed from "OBSENC" to "IMP":
       discard_previous_analysis()
       re_analyze(setting="INPATIENT")
   ```

3. **ED-to-inpatient transition:** Emergency encounter
   transitions to inpatient admission. Encounter.class may
   update from EMER to IMP. Same re-analysis requirement.

4. **Encounter linking:** Epic uses `Encounter.partOf` to link
   ED encounters to inpatient stays. Must follow the chain to
   find the final encounter class.

### 1.3 DocumentReference

**Purpose:** Clinical notes — the primary input for coding
analysis. This is the most critical resource.

**Required fields:**

| Field | FHIR Path | Usage |
|-------|----------|-------|
| Document ID | DocumentReference.id | Track which notes were analyzed |
| Status | DocumentReference.status | current, superseded, entered-in-error |
| Type | DocumentReference.type | Note type (H&P, Progress, Discharge Summary, Op Note) |
| Date | DocumentReference.date | When note was created/signed |
| Content | DocumentReference.content | Attachment with note text |
| Context | DocumentReference.context.encounter | Link to encounter |
| RelatesTo | DocumentReference.relatesTo | Amendment/addendum tracking |

**Content encoding formats (DISC-003 Section B):**

The note content in `DocumentReference.content.attachment` can
be encoded in 4 formats. The FHIR client must handle all:

| Format | contentType | Handling |
|--------|------------|---------|
| Plain text | `text/plain` | Use directly |
| XHTML | `text/html` | Strip HTML tags, preserve structure |
| C-CDA XML | `application/xml` | Parse CDA sections, extract text |
| PDF | `application/pdf` | OCR or text extraction; return DegradedResult if extraction fails |
| Base64 Binary | (any, base64 encoded) | Decode first, then handle by contentType |

**Edge cases (DISC-003 Section B):**

1. **Note timing gap:** Notes may not appear in FHIR for
   minutes to hours after physician signing. If no notes
   found for an active encounter, return DegradedResult
   with `reason="notes_not_yet_available"`.

2. **Amended notes:** Three patterns:
   - `relatesTo.code = "appends"` — addendum; original +
     addendum must both be analyzed
   - `relatesTo.code = "replaces"` — supersedes original;
     only analyze replacement
   - In-place edit without relatesTo — some Epic configs
     update note content without creating a new
     DocumentReference. Track content hashes to detect.

3. **Missing note types:** Not all note types are exposed via
   FHIR at every hospital. The system must work with whatever
   note types are available and flag when critical types
   (Discharge Summary, H&P) are missing.

4. **Large documents:** Binary content may timeout for large
   documents. Implement streaming/chunked retrieval with
   timeout handling.

### 1.4 Condition

**Purpose:** Existing diagnoses on the patient's problem list.
Used to check for Excludes 1 conflicts with new suggestions
and to avoid duplicate coding.

**Required fields:**

| Field | FHIR Path | Usage |
|-------|----------|-------|
| Code | Condition.code | ICD-10 code of existing condition |
| Clinical status | Condition.clinicalStatus | active, recurrence, relapse, inactive, remission, resolved |
| Verification status | Condition.verificationStatus | confirmed, unconfirmed, provisional, refuted |
| Category | Condition.category | encounter-diagnosis, problem-list-item |
| Onset | Condition.onsetDateTime | When condition started |

**Edge cases:**
- Problem list bloat: some patients have 50+ conditions.
  Filter to `clinicalStatus = active` and
  `category = encounter-diagnosis` for coding relevance.
- Unconfirmed conditions: `verificationStatus = unconfirmed`
  must NOT be treated as confirmed diagnoses.

### 1.5 Observation

**Purpose:** Lab results and vital signs that corroborate
CDI opportunities (e.g., creatinine rise for AKI, lactate
for sepsis, BMI for malnutrition).

**Required fields:**

| Field | FHIR Path | Usage |
|-------|----------|-------|
| Code | Observation.code | LOINC code identifying the test |
| Value | Observation.valueQuantity | Numeric result with units |
| Status | Observation.status | final, preliminary, amended |
| Effective | Observation.effectiveDateTime | When measured |
| Reference range | Observation.referenceRange | Normal range |

**Key LOINC codes for CDI triggers:**

| Lab | LOINC | CDI Trigger |
|-----|-------|-------------|
| Creatinine | 2160-0 | AKI detection (CDI-SEV-001) |
| Lactate | 2524-7 | Sepsis detection (CDI-SEV-002) |
| WBC | 6690-2 | Sepsis SIRS criteria |
| Albumin | 1751-7 | Malnutrition (CDI-SEV-003) |
| Prealbumin | 14338-8 | Malnutrition (CDI-SEV-003) |
| BNP | 30934-4 | Heart failure specificity (CDI-SPEC-001) |
| Hemoglobin | 718-7 | Anemia type (CDI-SPEC-004) |
| eGFR | 33914-3 | Renal failure staging (CDI-SPEC-005) |

**Edge cases:**
- Preliminary vs final results: use `status = final` for CDI
  triggers. Preliminary results may change.
- Units variation: creatinine may be mg/dL or µmol/L. The
  FHIR client normalizes units before returning to agents.
- Multiple results: return all results within encounter
  period, sorted by effectiveDateTime descending.

### 1.6 MedicationRequest

**Purpose:** Active medications that imply diagnoses not
documented in notes (e.g., insulin implies diabetes,
levothyroxine implies hypothyroidism).

**Required fields:**

| Field | FHIR Path | Usage |
|-------|----------|-------|
| Medication | MedicationRequest.medicationCodeableConcept | RxNorm code |
| Status | MedicationRequest.status | active, on-hold, cancelled |
| Intent | MedicationRequest.intent | order, plan |
| Authored on | MedicationRequest.authoredOn | When prescribed |

**Edge cases:**
- Home medications vs inpatient orders: both are relevant
  for coding but serve different purposes. Home medications
  suggest pre-existing conditions; inpatient orders may
  indicate new diagnoses.
- PRN medications: ordered but may not be administered.
  Lower weight in CDI analysis.

### 1.7 Claim

**Purpose:** Read-only. Used to check existing claim status
for the encounter. NOT used for claim creation or submission
(DISC-003 Section E — Claim write not supported by major EHRs).

**Required fields:**

| Field | FHIR Path | Usage |
|-------|----------|-------|
| Status | Claim.status | draft, active, cancelled |
| Diagnosis | Claim.diagnosis | Existing coded diagnoses |
| Procedure | Claim.procedure | Existing coded procedures |

**Critical constraint:** The system NEVER creates or updates
FHIR Claim resources. Coding output is presented in the coder
review UI. The coder enters approved codes into the EHR's
native encoder. This is enforced by architecture (ADR-001,
ADR-002, Constitution Article II.1).

**Alternative integration patterns (DISC-003 Section E.2):**
Phase 1 uses EHR Encoder UI integration exclusively. Future
phases may add HL7v2 DFT or X12 837 for downstream claim
processing.

---

## 2. FHIRClient Class

### 2.1 Class Hierarchy

```python
class FHIRClient(ABC):
    """Abstract base for FHIR R4 client implementations.

    All methods return Pydantic models or DegradedResult.
    All methods handle token refresh transparently.
    No method ever logs PHI.
    """

class EpicFHIRClient(FHIRClient):
    """Epic-specific FHIR client.

    Handles Epic deviations:
    - 5-minute token expiration (default)
    - Rate limits: 60-120 requests/minute
    - App Orchard-specific auth flow
    - Epic FHIR extensions
    """

class CernerFHIRClient(FHIRClient):
    """Cerner/Oracle Health-specific FHIR client.

    Handles Cerner deviations:
    - C-CDA document parsing
    - Cerner-specific rate limits
    - Cerner auth flow
    """

class MockFHIRClient(FHIRClient):
    """Deterministic test client.

    Returns predictable data for unit and integration tests.
    Never makes network calls.
    """
```

### 2.2 Method Signatures

```python
async def get_encounter(
    self,
    encounter_id: str,
) -> FHIREncounter | DegradedResult:
    """Retrieve encounter with class, status, and period.

    Returns DegradedResult if encounter not found or
    FHIR API unavailable. Encounter class determines
    inpatient vs outpatient coding rules.

    Raises:
        Never raises — returns DegradedResult on any failure
        (Constitution Article II.5)
    """

async def get_clinical_notes(
    self,
    encounter_id: str,
) -> list[FHIRDocumentReference] | DegradedResult:
    """Retrieve all clinical notes for an encounter.

    Handles content encoding (plain text, XHTML, C-CDA, PDF).
    Tracks document hashes for amendment detection.
    Returns DegradedResult if no notes available (timing gap)
    or FHIR API unavailable.

    Returns notes sorted by date descending (most recent first).
    Follows relatesTo links to resolve amendments.
    """

async def get_conditions(
    self,
    patient_id: str,
    encounter_id: str | None = None,
) -> list[FHIRCondition] | DegradedResult:
    """Retrieve active conditions from problem list.

    Filters to clinicalStatus=active by default.
    If encounter_id provided, also includes
    encounter-specific diagnoses.
    """

async def get_observations(
    self,
    patient_id: str,
    encounter_id: str,
    loinc_codes: list[str] | None = None,
) -> list[FHIRObservation] | DegradedResult:
    """Retrieve lab results and vitals for an encounter.

    If loinc_codes provided, filters to those specific labs.
    Normalizes units (e.g., creatinine to mg/dL).
    Returns results sorted by effectiveDateTime descending.
    """

async def get_medications(
    self,
    patient_id: str,
    encounter_id: str | None = None,
) -> list[FHIRMedicationRequest] | DegradedResult:
    """Retrieve active medication requests.

    Returns both inpatient orders and home medications.
    Filters to status=active.
    """

async def get_coding_context(
    self,
    encounter_id: str,
) -> CodingContext | DegradedResult:
    """Retrieve all data needed for coding analysis.

    This is the primary entry point for the coding agent.
    Aggregates: encounter, clinical notes, conditions,
    observations, medications into a single CodingContext
    object.

    Executes sub-queries in parallel where possible.
    Returns DegradedResult with partial data if some
    queries fail (includes which data sources succeeded
    and which degraded).
    """
```

### 2.3 Return Types (Pydantic Models)

```python
class FHIREncounter(BaseModel):
    """Encounter data relevant to coding analysis."""

    encounter_id: str
    status: Literal["planned", "arrived", "triaged",
                     "in-progress", "onleave", "finished",
                     "cancelled", "entered-in-error",
                     "unknown"]
    encounter_class: Literal["IMP", "AMB", "EMER", "OBSENC",
                              "HH", "OTHER"]
    coding_setting: Literal["INPATIENT", "OUTPATIENT"]
    period_start: datetime | None = None
    period_end: datetime | None = None
    existing_diagnoses: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_coding_setting(self) -> "FHIREncounter":
        """Derive coding setting from encounter class.

        OBSENC (observation) uses OUTPATIENT rules despite
        patient being physically in the hospital.
        """
        inpatient_classes = {"IMP"}
        if self.encounter_class in inpatient_classes:
            self.coding_setting = "INPATIENT"
        else:
            self.coding_setting = "OUTPATIENT"
        return self


class FHIRDocumentReference(BaseModel):
    """Clinical note content for coding analysis."""

    document_id: str
    status: Literal["current", "superseded",
                     "entered-in-error"]
    note_type: str
    date: datetime
    content_text: str  # Always plain text after parsing
    content_hash: str  # SHA-256 for amendment tracking
    is_amendment: bool = False
    amends_document_id: str | None = None
    amendment_type: Literal["appends", "replaces"] | None = None


class FHIRCondition(BaseModel):
    """Condition from problem list."""

    code: str  # ICD-10 code
    display: str
    clinical_status: Literal["active", "recurrence", "relapse",
                              "inactive", "remission", "resolved"]
    verification_status: Literal["confirmed", "unconfirmed",
                                  "provisional", "refuted",
                                  "entered-in-error"]
    category: Literal["encounter-diagnosis",
                       "problem-list-item"]


class FHIRObservation(BaseModel):
    """Lab result or vital sign."""

    code: str  # LOINC code
    display: str
    value: float | None = None
    unit: str | None = None
    status: Literal["registered", "preliminary", "final",
                     "amended", "corrected", "cancelled",
                     "entered-in-error", "unknown"]
    effective_datetime: datetime
    reference_range_low: float | None = None
    reference_range_high: float | None = None


class FHIRMedicationRequest(BaseModel):
    """Active medication request."""

    medication_code: str  # RxNorm code
    medication_display: str
    status: Literal["active", "on-hold", "cancelled",
                     "completed", "entered-in-error",
                     "stopped", "draft", "unknown"]
    intent: Literal["proposal", "plan", "order",
                     "original-order", "reflex-order",
                     "filler-order", "instance-order",
                     "option"]
    authored_on: datetime | None = None


class CodingContext(BaseModel):
    """Aggregated data for a single coding analysis.

    This is the primary input to the coding agent.
    """

    encounter: FHIREncounter
    clinical_notes: list[FHIRDocumentReference]
    conditions: list[FHIRCondition]
    observations: list[FHIRObservation]
    medications: list[FHIRMedicationRequest]
    degraded_sources: list[str] = Field(
        default_factory=list,
        description="List of data sources that returned "
                    "DegradedResult (e.g., 'observations', "
                    "'medications'). Empty if all succeeded.",
    )


class DegradedResult(BaseModel):
    """Returned when a FHIR operation fails gracefully.

    Per Constitution Article II.5, the system never blocks
    the coder's workflow. DegradedResult provides context
    about what failed and why.
    """

    is_degraded: bool = True
    source: str  # Which FHIR resource/operation failed
    reason: str  # Human-readable reason
    error_code: str | None = None  # HTTP status or error type
    retry_after_seconds: int | None = None  # For rate limits
```

---

## 3. SMART on FHIR Authentication

### 3.1 Auth Flow

The system uses the SMART on FHIR EHR Launch flow for
interactive sessions (coder launches from EHR) and SMART
Backend Services for automated/batch operations.

**EHR Launch flow (primary):**

```
Step 1: EHR launches our app with launch parameter
        GET /launch?iss={fhir_base_url}&launch={launch_token}

Step 2: App discovers auth endpoints from FHIR server
        GET {fhir_base_url}/.well-known/smart-configuration
        OR GET {fhir_base_url}/metadata (CapabilityStatement)

Step 3: App redirects to authorization endpoint
        GET {auth_url}?response_type=code
            &client_id={client_id}
            &redirect_uri={redirect_uri}
            &launch={launch_token}
            &scope={scopes}
            &state={csrf_token}
            &aud={fhir_base_url}

Step 4: Auth server redirects back with authorization code
        GET {redirect_uri}?code={auth_code}&state={csrf_token}

Step 5: App exchanges code for access token
        POST {token_url}
            grant_type=authorization_code
            &code={auth_code}
            &redirect_uri={redirect_uri}
            &client_id={client_id}

Step 6: Token response includes access token, scope, patient
        {
            "access_token": "...",
            "token_type": "bearer",
            "expires_in": 300,     # Epic: 5 minutes default
            "scope": "patient/Patient.read ...",
            "patient": "123",
            "encounter": "456"     # If EHR provides it
        }
```

### 3.2 Required Scopes

```
patient/Patient.read
patient/Encounter.read
patient/DocumentReference.read
patient/Condition.read
patient/Observation.read
patient/MedicationRequest.read
patient/Binary.read
```

**Scope handling (DISC-003 Section D.2):**

```
1. Request all scopes at launch
2. Parse granted scopes from token response
3. Compare granted vs required
4. IF DocumentReference.read missing:
       HARD STOP — cannot function without notes
       Display "Insufficient permissions for coding"
5. IF secondary scopes missing:
       PROCEED with degraded analysis
       Add missing source to CodingContext.degraded_sources
6. Log scope grants per hospital (non-PHI) for monitoring
```

### 3.3 Token Management

```python
class TokenManager:
    """Manages SMART on FHIR access tokens.

    Handles the critical Epic edge case: 5-minute token
    expiration. Must refresh proactively before expiry.
    """

    async def get_valid_token(self) -> str:
        """Return a valid access token.

        If current token expires within 60 seconds,
        proactively refresh. If refresh fails, attempt
        full re-authorization.

        Never raises — returns empty string on total
        auth failure (triggers DegradedResult upstream).
        """

    async def refresh_token(self) -> bool:
        """Attempt token refresh.

        Epic tokens expire in 5 minutes. Refresh tokens
        may not be available in all launch contexts
        (EHR launch contexts that don't support refresh
        require full re-launch).

        Returns True if refresh succeeded, False otherwise.
        """
```

**Token expiration handling:**

| Scenario | Action |
|----------|--------|
| Token valid (>60s remaining) | Use current token |
| Token expiring (<60s remaining) | Proactive refresh |
| Token expired | Attempt refresh; if fails, prompt re-launch |
| Refresh token unavailable | Prompt user to re-launch from EHR |
| Token revoked by patient | Return DegradedResult("patient_access_revoked") |

---

## 4. Error Handling

### 4.1 Circuit Breaker Pattern

The FHIR client implements a circuit breaker to prevent
cascading failures during EHR downtime (DISC-003 Section D.4).

```
States:
    CLOSED (normal) → requests pass through
    OPEN (tripped)  → requests return DegradedResult immediately
    HALF_OPEN       → one test request allowed

Transitions:
    CLOSED → OPEN:    3 consecutive failures
    OPEN → HALF_OPEN: after 60 seconds
    HALF_OPEN → CLOSED: test request succeeds
    HALF_OPEN → OPEN:   test request fails
```

### 4.2 HTTP Error Handling

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | Success | Parse response |
| 401 | Unauthorized | Refresh token; retry once |
| 403 | Forbidden | Check scope; DegradedResult("insufficient_scope") |
| 404 | Not Found | Patient opt-out or invalid ID; DegradedResult |
| 429 | Rate Limited | Backoff per Retry-After header; retry |
| 500 | Server Error | Retry once; then DegradedResult |
| 503 | Service Unavailable | Circuit breaker; DegradedResult |
| Timeout | Network timeout | Retry with 2x timeout; then DegradedResult |

### 4.3 Retry Strategy

```python
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay_seconds": 1.0,
    "max_delay_seconds": 30.0,
    "exponential_base": 2,
    "retryable_status_codes": {429, 500, 502, 503, 504},
    "non_retryable_status_codes": {400, 401, 403, 404},
}
```

---

## 5. Performance Requirements

### 5.1 Latency Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| get_encounter | <500ms | Single resource fetch |
| get_clinical_notes | <2s | May involve multiple DocumentReferences + Binary fetches |
| get_conditions | <500ms | Filtered query |
| get_observations | <1s | May return many results |
| get_medications | <500ms | Filtered query |
| get_coding_context | <5s | Parallel sub-queries; bounded by slowest |

### 5.2 Rate Limit Compliance

| EHR | Rate Limit | Strategy |
|-----|-----------|----------|
| Epic | 60-120 req/min (varies by hospital) | Token bucket with configurable rate per hospital |
| Cerner | ~100 req/min (varies) | Token bucket with configurable rate per hospital |

**Rate limit approach:**
- Configure rate limit per hospital during onboarding
- Use token bucket algorithm for request throttling
- Respect Retry-After headers on 429 responses
- Log rate limit events (non-PHI) for capacity planning

### 5.3 Caching Strategy

| Data | Cache Duration | Invalidation |
|------|---------------|-------------|
| Patient demographics | Encounter duration | Encounter close |
| Encounter class/status | Do not cache | Always re-fetch (class may change) |
| Clinical notes | 5 minutes | Content hash change (amendment) |
| Lab results | 5 minutes | New result with later effectiveDateTime |
| Problem list | Encounter duration | Manual invalidation |

**Cache constraints:**
- Cache is in-memory only (never persisted to disk)
- Cache keys use encounter_id (never patient name/MRN)
- Cache entries are cleared when encounter is closed
- No PHI in cache keys or cache metadata

---

## 6. Testing Strategy

### 6.1 Test Categories

| Category | Count | Coverage |
|----------|-------|----------|
| Unit tests (MockFHIRClient) | ≥30 | Each method, each error path |
| Content encoding tests | ≥8 | Plain text, XHTML, C-CDA, PDF, base64 |
| Auth flow tests | ≥10 | Token refresh, expiry, scope validation |
| Circuit breaker tests | ≥5 | State transitions, recovery |
| Integration tests (Epic sandbox) | ≥10 | Real API calls against fhir.epic.com |
| Degraded result tests | ≥15 | Every failure mode returns DegradedResult |

### 6.2 Critical Test Cases

```python
# 1. OBSENC uses outpatient coding rules
def test_observation_encounter_uses_outpatient_rules():
    encounter = FHIREncounter(
        encounter_id="E001",
        status="in-progress",
        encounter_class="OBSENC",
    )
    assert encounter.coding_setting == "OUTPATIENT"

# 2. Observation-to-inpatient conversion triggers re-analysis
def test_obs_to_inpatient_conversion():
    # Previous analysis with OBSENC
    # Encounter class changes to IMP
    # System must discard previous and re-analyze

# 3. Amended note with relatesTo="replaces"
def test_amended_note_replaces_original():
    # Original note + replacement note
    # Only replacement should be analyzed

# 4. Amended note with relatesTo="appends"
def test_amended_note_appends_addendum():
    # Original note + addendum
    # Both must be analyzed together

# 5. Token expiration mid-session
def test_token_refresh_on_expiry():
    # Token expires during multi-resource fetch
    # Client refreshes transparently
    # All resources still returned

# 6. Epic rate limit handling
def test_rate_limit_backoff():
    # 429 response with Retry-After header
    # Client backs off and retries

# 7. Circuit breaker opens after failures
def test_circuit_breaker_opens():
    # 3 consecutive 503 responses
    # Circuit opens
    # Subsequent calls return DegradedResult immediately

# 8. Missing DocumentReference.read scope
def test_missing_critical_scope():
    # Token response missing DocumentReference.read
    # Hard stop with clear error message

# 9. Patient opt-out
def test_patient_opt_out_handling():
    # 404 on Patient resource
    # DegradedResult with clear message, no retry

# 10. Content encoding: C-CDA XML parsing
def test_ccda_content_extraction():
    # DocumentReference with C-CDA XML content
    # Text extracted from CDA sections
    # Plain text returned in FHIRDocumentReference

# 11. Partial degradation in get_coding_context
def test_partial_degradation():
    # Notes succeed, observations fail
    # CodingContext returned with observations degraded
    # degraded_sources = ["observations"]

# 12. No PHI in logs on any error path
def test_no_phi_in_error_logs():
    # Trigger every error path
    # Verify no log entry contains PHI fields
```

### 6.3 Compliance Tests (Written FIRST)

```python
# These tests exist before any implementation code

def test_phi_never_logged_on_fhir_error():
    """G-HARD-005: No PHI in logs, even on FHIR errors."""

def test_graceful_degradation_on_fhir_failure():
    """Article II.5: Never block coder workflow."""

def test_claim_write_not_implemented():
    """ADR-001, Article II.1: No FHIR Claim write path."""

def test_patient_name_never_parsed():
    """Article II.4: Patient PII excluded from models."""
```

---

## 7. Acceptance Criteria

- [ ] FHIRClient retrieves all 7 resource types from
      Epic sandbox (fhir.epic.com)
- [ ] Content encoding handles plain text, XHTML, C-CDA, PDF
- [ ] OBSENC encounter classified as OUTPATIENT for coding rules
- [ ] Token refresh handles Epic 5-minute expiration
- [ ] Circuit breaker opens after 3 failures, recovers after 60s
- [ ] DegradedResult returned on every failure path (never 500)
- [ ] No PHI in any log entry from any FHIR operation
- [ ] Rate limits respected (configurable per hospital)
- [ ] get_coding_context returns partial results when some
      sources fail
- [ ] Amended notes correctly handled (appends and replaces)
- [ ] No FHIR Claim write path exists in the codebase

---

## References

- ADR-001 (FHIR R4 Over HL7v2)
- DISC-003 (FHIR R4 Implementation Edge Cases)
- Constitution Article II.4 (HIPAA)
- Constitution Article II.5 (Graceful Degradation)
- HL7 FHIR R4 Specification
- SMART on FHIR Authorization
