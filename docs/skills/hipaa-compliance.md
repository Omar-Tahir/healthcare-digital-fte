# Skill: HIPAA Compliance

**Domain:** HIPAA privacy and security requirements  
**Source research:** Constitution Article II.4, DISC-003, ADR-005  
**Used by:** ALL components during BUILD  
**Read before:** Any work that touches logging, error handling,
external service integration, or data storage

---

## Section 1 — The 18 PHI Identifiers

HIPAA defines 18 categories of Protected Health Information
(PHI) identifiers. These cannot appear in ANY log, error
message, debug output, or external communication.

| # | Identifier | Examples | Appears In |
|---|-----------|---------|-----------|
| 1 | Names | Patient name, family name | Patient resource, notes |
| 2 | Geographic data (below state) | Street address, city, ZIP | Patient resource |
| 3 | Dates (except year) | Birth date, admission date, discharge date, death date | Patient, Encounter |
| 4 | Phone numbers | Home, cell, work | Patient resource |
| 5 | Fax numbers | Fax | Patient resource |
| 6 | Email addresses | Patient email | Patient resource |
| 7 | Social Security Numbers | SSN | Patient resource |
| 8 | Medical Record Numbers | MRN, chart number | Patient resource |
| 9 | Health plan beneficiary numbers | Insurance member ID | Coverage resource |
| 10 | Account numbers | Hospital account number | Account resource |
| 11 | Certificate/license numbers | DEA, NPI (when linked to patient) | Practitioner |
| 12 | Vehicle identifiers | VIN, license plate | Rare in clinical data |
| 13 | Device identifiers | Serial numbers (implants, devices) | Device resource |
| 14 | Web URLs | Patient portal URLs | Rare |
| 15 | IP addresses | Patient-associated IPs | Access logs |
| 16 | Biometric identifiers | Fingerprints, voiceprints | Rare in coding context |
| 17 | Full-face photographs | Patient photos | Media resource |
| 18 | Any unique identifying number | Any number that could identify a patient | Various |

**Rule of thumb:** If a data element could be used, alone or
in combination, to identify a specific patient, it is PHI.

---

## Section 2 — What Is Safe to Log

### Safe (YES — log freely)

| Data Element | Why Safe | Example |
|-------------|---------|---------|
| Encounter ID | System-generated, not PHI | `encounter_id="ENC-789456"` |
| Coder user ID | Internal system identifier | `coder_id="USR-123"` |
| ICD-10 codes | Not linked to patient in logs | `code="E11.22"` |
| CPT codes | Not linked to patient in logs | `code="99223"` |
| Confidence scores | AI metric, no patient data | `confidence=0.94` |
| Timestamps | System event times (not DOB) | `timestamp="2026-04-02T14:30:00Z"` |
| Error codes | System codes, no clinical data | `error_code="FHIR_503"` |
| Guardrail IDs | System identifiers | `guardrail_id="G-HARD-003"` |
| Rule IDs | System identifiers | `rule_id="RULE-EX1-001"` |
| Model version | System metadata | `model_version="claude-sonnet-4-6"` |
| Suggestion count | Aggregate, no detail | `suggestion_count=7` |
| Duration metrics | Performance data | `duration_ms=1247` |
| Evidence quote hash | SHA-256 of quote, not content | `evidence_hash="a3f2..."` |
| Validation results | Pass/fail, no content | `is_valid=True` |

### NOT Safe (NEVER log)

| Data Element | Why Unsafe | Risk |
|-------------|-----------|------|
| Patient name | PHI identifier #1 | HIPAA violation |
| Date of birth | PHI identifier #3 | HIPAA violation |
| MRN | PHI identifier #8 | HIPAA violation |
| SSN | PHI identifier #7 | HIPAA violation |
| Address, phone, email | PHI identifiers #2, 4, 6 | HIPAA violation |
| Clinical note text | Contains patient information | HIPAA violation |
| Evidence quote content | Verbatim clinical text | HIPAA violation |
| Lab values | Clinical data linked to encounter | PHI when linked |
| Diagnosis descriptions with patient context | "Patient John has diabetes" | HIPAA violation |
| Insurance member ID | PHI identifier #9 | HIPAA violation |
| Any free-text clinical content | May contain embedded PHI | HIPAA violation |

**Even without a patient name:** Lab values, diagnosis
descriptions, and clinical note fragments are PHI when they
can be linked to an individual through encounter context.

---

## Section 3 — Structlog Pattern for Safe Logging

### CORRECT Patterns

```python
import structlog
log = structlog.get_logger()

# Coding analysis complete
log.info("coding_analysis_complete",
         encounter_id=encounter.id,
         suggestion_count=len(suggestions),
         is_valid=validation.is_valid,
         duration_ms=elapsed)

# Guardrail violation
log.warning("guardrail_violation",
            guardrail_id="G-HARD-003",
            violation_type="excludes_1",
            code_a=code1,       # ICD-10 code is safe
            code_b=code2,       # ICD-10 code is safe
            encounter_id=encounter.id)

# FHIR error
log.error("fhir_request_failed",
          resource_type="DocumentReference",
          encounter_id=encounter.id,
          status_code=503,
          retry_count=3)

# CDI query generated
log.info("cdi_query_generated",
         encounter_id=encounter.id,
         category="CDI-SEV-001",
         target_code="N17.9",
         confidence=0.87)
```

### WRONG Patterns (Constitution violations)

```python
# WRONG — patient name in log
log.info(f"Processing note for {patient.name}")

# WRONG — clinical content in log
log.info("suggestion", diagnosis=suggestion.description,
         evidence=suggestion.evidence_quote)

# WRONG — DOB in log
log.info("patient_age", dob=patient.birth_date)

# WRONG — clinical note text in error
log.error(f"Failed to parse note: {note_content[:100]}")

# WRONG — lab value in log
log.info("lab_result", creatinine=observation.value)

# WRONG — full exception with PHI in traceback
log.exception("Error processing patient data")
# ↑ traceback may include variable values containing PHI
```

### How the PHI Filter Works (ADR-005)

A structlog processor executes BEFORE any log entry is written.
It checks:

1. **Field name blocklist:** `patient_name`, `name`, `dob`,
   `ssn`, `mrn`, `address`, `phone`, `email`, `note_text`,
   `clinical_text`, `evidence_quote`, etc.
2. **Regex patterns:** SSN format (`\d{3}-\d{2}-\d{4}`),
   DOB format (`\d{2}/\d{2}/\d{4}`), MRN patterns
   (`[A-Z]{1,3}\d{6,10}`)

If either check triggers, the log entry is blocked and a
separate violation log entry is created (without the PHI).

---

## Section 4 — Audit Trail Requirements

### What Must Be Logged

| Event | Required Fields |
|-------|----------------|
| Coder opens encounter | encounter_id, coder_id, timestamp |
| AI suggestion generated | encounter_id, code, confidence, timestamp |
| Suggestion accepted | encounter_id, code, coder_id, timestamp |
| Suggestion rejected | encounter_id, code, coder_id, reason_code, timestamp |
| Approval token generated | encounter_id, coder_id, token_id, code_count, timestamp |
| Guardrail violation | encounter_id, guardrail_id, violation_type, timestamp |
| CDI query generated | encounter_id, cdi_category, target_code, timestamp |
| Session start/end | coder_id, timestamp, duration, ip_hash |

### What Must NEVER Be Logged

- Clinical note content (any section)
- Evidence quote text (only SHA-256 hash)
- Patient name, DOB, SSN, MRN, address, phone, email
- Lab values (even without patient name)
- Diagnosis descriptions with patient context
- Insurance identifiers

### Retention

- **Required retention:** 6 years (2,190 days) per HIPAA
  §164.530(j) and FCA statute of limitations
- **Storage:** Append-only audit log table, separate from
  application database
- **Access control:** Read-only for compliance role. No delete
  capability. No modification capability.

### Audit Log Model

```python
class AuditLogEntry(BaseModel):
    event_id: str  # UUID
    event_type: str
    timestamp: datetime
    coder_id: str
    encounter_id: str | None
    details: dict[str, str | int | float | bool]
    # details dict validated against PHI blocklist
```

---

## Section 5 — BAA Requirements

A Business Associate Agreement (BAA) is required with any
third-party service that processes, stores, or transmits PHI.

### Services Requiring BAA

| Service | PHI Exposure | BAA Required |
|---------|-------------|-------------|
| Anthropic Claude API | Clinical note text sent for analysis | YES — must have BAA with Anthropic |
| FHIR API (EHR) | Clinical data retrieved | Covered under hospital's existing BAA with EHR vendor |
| Log aggregation (Datadog, Splunk) | Only if PHI could leak into logs | YES if external; NO if logs guaranteed PHI-free (our architecture ensures this via G-HARD-005) |
| Error tracking (Sentry) | Only if PHI in error messages | Same as logging — our architecture prevents PHI in errors |
| Cloud hosting (AWS, GCP, Azure) | PHI in database, file storage | YES |
| Email/notification services | Only if PHI in notifications | YES if used; our system does not email PHI |

### Development Environment Rules

- **No real PHI in development environments.** Ever.
- Use synthetic/de-identified data for development
- MIMIC-IV dataset (de-identified) for accuracy testing
- Epic sandbox (fhir.epic.com) uses synthetic patients
- `.env` files with API keys are gitignored, never committed

### Anthropic BAA Considerations

Our system sends clinical note text to Claude API for analysis.
This means Anthropic processes PHI. Requirements:

1. BAA must be in place with Anthropic before processing
   real patient data
2. Anthropic's data retention policies must comply with HIPAA
3. Prompt caching does not change BAA requirements
4. PHI placeholder tokens (PROMPT-004) reduce PHI exposure
   for appeal letters but do not eliminate BAA requirement

---

## MCP Tool Usage

- No MCP tools specific to HIPAA compliance
- The PHI filter is implemented as a structlog processor,
  not as an MCP tool
- All MCP tools that return FHIR data must strip PHI before
  returning results to the agent context
