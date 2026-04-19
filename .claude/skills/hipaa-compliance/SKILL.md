---
name: hipaa-compliance
version: "2.0.0"
description: >
  MANDATORY for ANY code change in this healthcare project. Use this skill when writing, reviewing, or modifying ANY function that touches logging (structlog, print, log.*), error handling (try/except, raise, Error classes), API responses, middleware, audit trails, Pydantic models with patient fields, FHIR resource parsing, test fixtures containing clinical data, or .env/secrets configuration. If you are writing code in src/, tests/, or scripts/ — load this skill. If you see the words "log", "error", "patient", "encounter", "clinical", "note", "PHI", "HIPAA", "audit", "redact", or "filter" in the task — load this skill. When in doubt, load this skill. It is practically impossible to write code in this project without needing HIPAA guidance.
allowed-tools: Read
license: Proprietary
---

# HIPAA Compliance — Safe Coding Rules

## The Non-Negotiable Rule

Constitution Article II.4: PHI never appears in any log,
error message, stack trace, or external communication.

## The 18 PHI Identifiers — Never Log These

| # | Identifier | Examples |
|---|-----------|---------|
| 1 | Names | Patient name, family name |
| 2 | Geographic data (below state) | Street address, city, ZIP |
| 3 | Dates (except year) | Birth date, admission date, discharge date, death date |
| 4 | Phone numbers | Home, cell, work |
| 5 | Fax numbers | Fax |
| 6 | Email addresses | Patient email |
| 7 | Social Security Numbers | SSN |
| 8 | Medical Record Numbers | MRN, chart number |
| 9 | Health plan beneficiary numbers | Insurance member ID |
| 10 | Account numbers | Hospital account number |
| 11 | Certificate/license numbers | DEA, NPI (when linked to patient) |
| 12 | Vehicle identifiers | VIN, license plate |
| 13 | Device identifiers | Serial numbers (implants, devices) |
| 14 | Web URLs | Patient portal URLs |
| 15 | IP addresses | Patient-associated IPs |
| 16 | Biometric identifiers | Fingerprints, voiceprints |
| 17 | Full-face photographs | Patient photos |
| 18 | Any unique identifying number | Any number that could identify a patient |

**Rule of thumb:** If a data element could be used, alone or
in combination, to identify a specific patient, it is PHI.

## What IS Safe to Log

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

**NOT Safe (NEVER log):** Patient name, DOB, MRN, SSN, address,
phone, email, clinical note text, evidence quote content, lab
values, diagnosis descriptions with patient context, insurance
member ID, any free-text clinical content.

## Correct Logging Pattern (structlog)

```python
import structlog
log = structlog.get_logger()

# CORRECT — identifiers only
log.info("coding_analysis_complete",
         encounter_id=encounter.id,
         suggestion_count=len(suggestions),
         is_valid=validation.is_valid,
         duration_ms=elapsed)

# CORRECT — guardrail violation
log.warning("guardrail_violation",
            guardrail_id="G-HARD-003",
            violation_type="excludes_1",
            code_a=code1,
            code_b=code2,
            encounter_id=encounter.id)

# WRONG — PHI in log
log.info(f"Processing note for {patient.name}")

# WRONG — clinical content in log
log.info("suggestion", diagnosis=suggestion.description,
         evidence=suggestion.evidence_quote)

# WRONG — DOB in log
log.info("patient_age", dob=patient.birth_date)

# WRONG — clinical note text in error
log.error(f"Failed to parse note: {note_content[:100]}")
```

## PHI Filter (ADR-005)

A structlog processor executes BEFORE any log entry is written:

1. **Field name blocklist:** `patient_name`, `name`, `dob`,
   `ssn`, `mrn`, `address`, `phone`, `email`, `note_text`,
   `clinical_text`, `evidence_quote`, etc.
2. **Regex patterns:** SSN format (`\d{3}-\d{2}-\d{4}`),
   DOB format (`\d{2}/\d{2}/\d{4}`), MRN patterns
   (`[A-Z]{1,3}\d{6,10}`)

If either check triggers, the log entry is blocked and a
separate violation log entry is created (without the PHI).

## Audit Log Requirements

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

### Retention

- **Required retention:** 6 years (2,190 days) per HIPAA
  164.530(j) and FCA statute of limitations
- **Storage:** Append-only audit log table, separate from
  application database
- **Access control:** Read-only for compliance role. No delete
  capability. No modification capability.

## BAA Requirements

A Business Associate Agreement (BAA) is required with any
third-party service that processes, stores, or transmits PHI.

| Service | BAA Required |
|---------|-------------|
| Anthropic Claude API | YES — clinical note text sent for analysis |
| FHIR API (EHR) | Covered under hospital's existing BAA with EHR vendor |
| Log aggregation (Datadog, Splunk) | YES if external; NO if logs guaranteed PHI-free |
| Cloud hosting (AWS, GCP, Azure) | YES |
| Error tracking (Sentry) | YES if PHI could appear in errors |

### Development Environment Rules

- **No real PHI in development environments.** Ever.
- Use synthetic/de-identified data for development
- MIMIC-IV dataset (de-identified) for accuracy testing
- Epic sandbox (fhir.epic.com) uses synthetic patients
- `.env` files with API keys are gitignored, never committed
