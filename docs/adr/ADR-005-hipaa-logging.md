# ADR-005: HIPAA-Compliant Logging Architecture

**Status:** ACCEPTED
**Date:** 2026-03-30
**Decision makers:** Engineering team
**Constitution references:** Article II.4 (No PHI in Logs)

---

## Context

The system processes PHI (patient names, dates of birth, MRNs,
clinical note text, evidence quotes) throughout its pipeline.
Logs are essential for debugging, monitoring, performance
tracking, and the audit trail required for FCA defense and
OIG compliance.

However, log data flows to places PHI should never go:
- Log aggregation services (Datadog, Splunk, CloudWatch) may
  store data in regions without BAA coverage
- Error tracking services (Sentry) display log content in
  developer notifications and dashboards
- Stack traces may expose patient data to unauthorized viewers
- Debug logs on developer machines lack PHI protections

We must decide how to maintain comprehensive logging while
ensuring zero PHI exposure.

---

## Decision

**No PHI in ANY log record, error message, or debug output.
Enforced architecturally by G-HARD-005 as a structlog processor
that executes BEFORE any log entry is written.**

Two enforcement mechanisms:

1. **Field name blocklist** — log entries containing these
   field names are blocked:
   ```
   patient_name, name, first_name, last_name,
   date_of_birth, dob, birth_date,
   ssn, social_security, mrn, medical_record_number,
   address, street, city, zip, zip_code,
   phone, phone_number, email, email_address,
   insurance_id, member_id, subscriber_id,
   note_text, clinical_text, note_content,
   evidence_quote, clinical_note,
   diagnosis_text, assessment, plan
   ```

2. **Regex pattern detection** — string values matching
   these patterns trigger a violation:
   ```
   \b\d{3}-\d{2}-\d{4}\b     # SSN format
   \b\d{2}/\d{2}/\d{4}\b     # DOB format
   \b[A-Z]{1,3}\d{6,10}\b    # MRN patterns
   ```

**What IS logged** (safe identifiers):
- encounter_id, code values (E11.22), confidence scores
- guardrail_id, rule_id, violation type
- timestamps, model version, prompt version
- validation results (is_valid, violation count)
- evidence_quote_hash (SHA-256, not the content)

**What is NEVER logged:**
- Patient name, DOB, SSN, MRN, address, phone, email
- Clinical note text (any section)
- Evidence quote content (only the hash)
- Insurance identifiers
- Any free-text clinical content

---

## Alternatives Considered

### Alternative 1: PHI-Allowed Logs with Encryption at Rest

Log everything, encrypt the log storage.

**Rejected because:**
- Encryption at rest does not prevent display in dashboards,
  Sentry alerts, developer notifications, or grep output
- Log aggregation services would require BAA agreements for
  every service in the logging pipeline
- A single misconfigured log pipeline exposes all PHI ever
  logged — blast radius is unbounded
- HIPAA minimum necessary principle: don't collect PHI in
  logs if it's not necessary for the logging purpose

### Alternative 2: De-Identified Logging (Safe Harbor)

Apply HIPAA Safe Harbor de-identification to log entries
before writing.

**Rejected for Phase 1 because:**
- Safe Harbor requires removing or generalizing 18 identifier
  categories — complex to implement correctly
- Statistical validation of de-identification quality adds
  engineering overhead
- False negatives (missed PHI) create compliance gaps
- The simpler approach (never include PHI) is more reliable
  than the complex approach (include then remove PHI)
- Could be revisited in Phase 3 if debugging needs require
  richer clinical context in logs

### Alternative 3: No Logging of Clinical Pipeline

Don't log clinical pipeline activity at all.

**Rejected because:**
- Audit trail is required for FCA defense — must prove
  every code suggestion was validated and human-reviewed
- OIG compliance requires demonstrating that guardrails
  are active and violations are caught
- Debugging production issues requires operational visibility
- The safe-identifier approach provides adequate logging
  without PHI exposure

---

## Consequences

### Positive

1. **HIPAA compliance by architecture** — PHI cannot appear
   in logs regardless of developer error, because the
   structlog processor blocks it before write
2. **Safe log aggregation** — any log service can be used
   without BAA concerns for the logging pipeline itself
3. **Audit trail integrity** — encounter_id cross-referencing
   provides full audit capability without PHI in logs
4. **Developer safety** — developers cannot accidentally
   expose PHI through logging statements

### Negative

1. **Debugging clinical issues requires EHR access** — cannot
   reproduce clinical scenarios from logs alone. Must query
   the EHR via FHIR to see the actual clinical data.
   Mitigation: encounter_id in logs enables targeted FHIR
   queries for specific cases.
2. **Evidence quote verification requires lookup** — the
   evidence_quote_hash in logs requires a database lookup
   to verify content. Mitigation: audit API provides this
   lookup for authorized users.
3. **Developer training required** — developers must use
   structlog (never print()), and must know which fields
   are safe to log. Mitigation: the structlog processor
   catches violations at runtime, providing immediate
   feedback.

---

## Implementation Notes

- Structlog processor: `src/api/middleware/phi_filter.py`
- Guardrail: G-HARD-005 in DESIGN-003
- PHI field blocklist and regex patterns: defined in
  DESIGN-003 Section 1 (G-HARD-005)
- All logging uses structlog — print() is prohibited
  (Constitution Article III)

---

## References

- Constitution Article II.4 (No PHI in Logs)
- DESIGN-003 G-HARD-005 (PHI Filter Guardrail)
- HIPAA Privacy Rule (45 CFR 164.502(b) — Minimum Necessary)
- HIPAA Security Rule (45 CFR 164.312 — Technical Safeguards)
