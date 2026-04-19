# DESIGN-003: Compliance Guardrail Architecture Specification

**Status:** COMPLETE  
**Date:** 2026-04-01  
**Author:** Claude (AI Engineering Partner)  
**Research inputs:** DISC-001 through DISC-005 (all DISCOVER phase docs)  
**Constitution references:** Article II (all clauses — Safety Law)  
**Implementation target:** `src/core/guardrails/`, `src/api/middleware/`  
**Depends on:** DESIGN-001 (Coding Rules Engine), DESIGN-002 (CDI Intelligence Layer)

---

## Purpose

This spec defines the compliance and safety guardrail architecture
that prevents the system from ever generating output that creates
legal, regulatory, or patient safety risk.

Guardrails are not features. They are architectural primitives —
structural constraints embedded in the system's execution pipeline
that cannot be bypassed, disabled, or configured away. They are the
reason a hospital legal team signs off on procurement.

Every output the system produces — code suggestions, CDI queries,
DRG calculations, audit logs — passes through guardrails before
reaching any user or external system. There is no code path that
circumvents them.

---

## 1. Guardrail Taxonomy

### Type A: Hard Guardrails

Hard guardrails raise `HardGuardrailViolation` and halt execution.
No user, administrator, or feature flag can override them.
They are enforced in code, tested in CI with 100% coverage,
and represent the constitutional safety floor of the system.

**Implementation:** Hard guardrails are implemented as middleware
that wraps every output pathway. They execute synchronously —
the request does not proceed until the guardrail passes.

```python
class HardGuardrailViolation(Exception):
    """Raised when a hard guardrail is violated.

    This exception is NEVER caught silently. It propagates
    to the API layer and returns a structured error response.
    The violation is logged (without PHI) to the audit trail.
    """

    guardrail_id: str
    violation_description: str
    constitution_article: str
    suggested_remediation: str
```

#### G-HARD-001: No Claim Submission Without Human Approval Token

- **Constitution reference:** Article II.1
- **Pipeline location:** `src/api/routes/claims.py` — claim submission endpoint
- **Input:** `ClaimSubmissionRequest` containing claim data and optional `human_approval_token`
- **Validation logic:**
  ```
  IF request.human_approval_token IS None:
      RAISE HardGuardrailViolation(
          guardrail_id="G-HARD-001",
          violation_description="Claim submission attempted without "
              "human_approval_token. No claim may be submitted to any "
              "payer or clearinghouse without explicit human review "
              "and approval from a credentialed coder.",
          constitution_article="II.1",
          suggested_remediation="Route claim to coder review interface "
              "for human approval before submission."
      )

  IF NOT validate_approval_token(request.human_approval_token):
      RAISE HardGuardrailViolation(
          guardrail_id="G-HARD-001",
          violation_description="human_approval_token is invalid, "
              "expired, or not associated with a credentialed coder.",
          constitution_article="II.1",
          suggested_remediation="Obtain fresh approval from a "
              "credentialed coder via the review interface."
      )

  # Token validation requirements:
  # - Token is cryptographically signed
  # - Token contains: coder_id, encounter_id, timestamp, code_set_hash
  # - Token was issued < 24 hours ago
  # - code_set_hash matches the current claim's code set
  #   (prevents approving one set and submitting a different one)
  # - coder_id maps to a user with 'credentialed_coder' role
  ```
- **Violation logging:**
  ```
  log.critical("hard_guardrail_violation",
      guardrail_id="G-HARD-001",
      encounter_id=request.encounter_id,
      has_token=request.human_approval_token is not None,
      # NEVER log token contents, coder name, or claim details
  )
  ```
- **Test case:** Submit claim with `human_approval_token=None`. Assert `HardGuardrailViolation` raised. Submit claim with expired token. Assert violation raised. Submit claim with token whose `code_set_hash` doesn't match current codes. Assert violation raised.
- **FCA relevance:** 31 USC §3729 penalties: $13,946-$27,894 per false claim. Autonomous claim submission without human review is the single highest legal risk in healthcare AI. Olive AI's partial collapse was linked to autonomous billing without adequate oversight (DISC-001 A.3).

#### G-HARD-002: No Code Suggestion Without Evidence Quote

- **Constitution reference:** Article II.2
- **Pipeline location:** `src/agents/coding_agent.py` — suggestion generation output; `src/core/icd10/rules_engine.py` — validation step 1
- **Input:** `CodingSuggestion` from the coding agent
- **Validation logic:**
  ```
  FOR each suggestion in suggestion_set.suggestions:
      IF suggestion.evidence_quote IS None OR suggestion.evidence_quote == "":
          RAISE HardGuardrailViolation(
              guardrail_id="G-HARD-002",
              violation_description=f"Code suggestion {suggestion.code} "
                  "has no evidence_quote. Every clinical assertion must "
                  "include a verbatim quote from the source document.",
              constitution_article="II.2",
              suggested_remediation="Remove suggestion or provide "
                  "verbatim text from the clinical note."
          )

      IF suggestion.evidence_quote NOT IN suggestion_set.source_note_text:
          RAISE HardGuardrailViolation(
              guardrail_id="G-HARD-002",
              violation_description=f"evidence_quote for {suggestion.code} "
                  "is not a substring of the source clinical note. "
                  "The quote may be fabricated or from a different note.",
              constitution_article="II.2",
              suggested_remediation="Verify evidence_quote is extracted "
                  "verbatim from the source note."
          )
  ```
- **Violation logging:**
  ```
  log.critical("hard_guardrail_violation",
      guardrail_id="G-HARD-002",
      encounter_id=suggestion_set.encounter_id,
      code=suggestion.code,
      has_quote=suggestion.evidence_quote is not None,
      quote_in_note=suggestion.evidence_quote in source_note_text,
      # NEVER log the evidence_quote itself (contains clinical text)
  )
  ```
- **Test case:** Create `CodingSuggestion` with `evidence_quote=""`. Assert violation. Create suggestion with quote not found in source note. Assert violation. Create suggestion with valid quote. Assert passes.
- **FCA relevance:** A code suggestion without source citation is a hallucination. Hallucinated diagnoses in medical records are patient safety events and legal liabilities. This guardrail ensures every AI assertion is traceable to physician documentation.

#### G-HARD-003: No Excludes 1 Code Pair in Same Suggestion Set

- **Constitution reference:** Article II.3
- **Pipeline location:** `src/core/icd10/rules_engine.py` — validation step 2
- **Input:** `CodingSuggestionSet`
- **Validation logic:**
  ```
  FOR each pair (code_a, code_b) in suggestion_set.suggestions:
      IF has_excludes1_relationship(code_a.code, code_b.code):
          RAISE HardGuardrailViolation(
              guardrail_id="G-HARD-003",
              violation_description=f"Excludes 1 violation: "
                  "{code_a.code} and {code_b.code} are mutually "
                  "exclusive per ICD-10-CM Section I.A.12.a. "
                  "These codes can NEVER appear together.",
              constitution_article="II.3",
              suggested_remediation="Remove one code. If clinical "
                  "documentation supports both conditions, generate "
                  "a CDI query to clarify which is correct."
          )
  ```
- **Violation logging:**
  ```
  log.critical("hard_guardrail_violation",
      guardrail_id="G-HARD-003",
      encounter_id=suggestion_set.encounter_id,
      code_a=code_a.code,
      code_b=code_b.code,
  )
  ```
- **Test case:** Submit E10.9 + E11.9 (Type 1 + Type 2 DM). Assert violation. Submit E11.22 + N18.3 (no Excludes 1). Assert passes. Test all 10 top Excludes 1 pairs from DISC-001 Section E.3.
- **FCA relevance:** Excludes 1 violations are automatically caught by payer edits and result in claim denial. Systematic violations trigger fraud investigation.

#### G-HARD-004: No Uncertain Diagnosis Coded as Confirmed (Outpatient)

- **Constitution reference:** Article II.3
- **Pipeline location:** `src/core/icd10/rules_engine.py` — validation step 4g
- **Input:** `CodingSuggestionSet` with `encounter_setting == "outpatient"`
- **Validation logic:**
  ```
  QUALIFIER_WORDS = [
      "probable", "suspected", "likely", "questionable",
      "possible", "rule out", "still to be ruled out",
      "working diagnosis", "concern for", "appears to be",
      "consistent with", "compatible with", "indicative of",
      "suggestive of", "comparable with"
  ]

  IF suggestion_set.encounter_setting == "outpatient":
      FOR each suggestion in suggestion_set.suggestions:
          IF any(q in suggestion.qualifier_words for q in QUALIFIER_WORDS):
              RAISE HardGuardrailViolation(
                  guardrail_id="G-HARD-004",
                  violation_description=f"Outpatient encounter: "
                      "uncertain diagnosis '{suggestion.code}' "
                      "qualified by '{qualifier}' cannot be coded "
                      "as confirmed. Per ICD-10-CM Section IV.H, "
                      "code the presenting sign/symptom instead.",
                  constitution_article="II.3",
                  suggested_remediation="Replace with appropriate "
                      "symptom code (Chapter 18, R00-R99)."
              )
  ```
- **Violation logging:**
  ```
  log.critical("hard_guardrail_violation",
      guardrail_id="G-HARD-004",
      encounter_id=suggestion_set.encounter_id,
      code=suggestion.code,
      setting="outpatient",
      qualifier_detected=qualifier,
  )
  ```
- **Test case:** Outpatient + "suspected pneumonia" coded as J18.9. Assert violation. Inpatient + "suspected pneumonia" coded as J18.9. Assert passes (per Section II.H). Outpatient + confirmed pneumonia coded as J18.9. Assert passes.
- **FCA relevance:** Coding uncertain outpatient diagnoses as confirmed is a False Claims Act violation when done systematically. OIG specifically targets this pattern (DISC-001 Section B.1).

#### G-HARD-005: No PHI in Any Log Record

- **Constitution reference:** Article II.4
- **Pipeline location:** `src/api/middleware/phi_filter.py` — logging middleware (wraps all log output)
- **Input:** Every structured log entry before it is written
- **Validation logic:**
  ```
  PHI_FIELD_NAMES = [
      "patient_name", "name", "first_name", "last_name",
      "date_of_birth", "dob", "birth_date",
      "ssn", "social_security", "mrn", "medical_record_number",
      "address", "street", "city", "zip", "zip_code",
      "phone", "phone_number", "email", "email_address",
      "insurance_id", "member_id", "subscriber_id",
      "note_text", "clinical_text", "note_content",
      "evidence_quote", "clinical_note",
      "diagnosis_text", "assessment", "plan",
  ]

  PHI_PATTERNS = [
      r"\b\d{3}-\d{2}-\d{4}\b",           # SSN
      r"\b\d{2}/\d{2}/\d{4}\b",           # DOB format
      r"\b[A-Z]{1,3}\d{6,10}\b",          # MRN patterns
      # Additional regex patterns for PHI detection
  ]

  FOR each log_entry in log_output:
      FOR field_name, field_value in log_entry.items():
          IF field_name.lower() IN PHI_FIELD_NAMES:
              RAISE HardGuardrailViolation(
                  guardrail_id="G-HARD-005",
                  violation_description=f"PHI field '{field_name}' "
                      "detected in log record. PHI must never appear "
                      "in logs, error messages, or debug output.",
                  constitution_article="II.4",
                  suggested_remediation="Remove the field or replace "
                      "with '[PHI-REDACTED]'."
              )
          IF isinstance(field_value, str):
              FOR pattern in PHI_PATTERNS:
                  IF regex_match(pattern, field_value):
                      RAISE HardGuardrailViolation(
                          guardrail_id="G-HARD-005",
                          violation_description="Potential PHI pattern "
                              f"detected in log field '{field_name}'.",
                          constitution_article="II.4",
                          suggested_remediation="Review log content and "
                              "replace PHI with identifiers only."
                      )
  ```
- **Implementation note:** This guardrail runs as a structlog processor in the logging pipeline. It executes BEFORE the log entry is written to any output (file, stdout, log aggregator). If PHI is detected, the entry is blocked and an alert is raised.
- **Violation logging:** The violation itself is logged WITHOUT the offending PHI content — only the field name and guardrail ID.
- **Test case:** Log entry with `patient_name="John Doe"`. Assert violation. Log entry with `encounter_id="ENC-12345"`. Assert passes. Log entry with string containing SSN pattern. Assert violation.
- **HIPAA relevance:** PHI in logs is a HIPAA violation. Log aggregation services (Datadog, Splunk, CloudWatch) may store data in regions or systems without BAA coverage. PHI in error messages can appear in stack traces, Sentry alerts, and developer notifications.

#### G-HARD-006: No FHIR Write Without Valid HIPAA Audit Log Entry

- **Constitution reference:** Article II.4
- **Pipeline location:** `src/core/fhir/client.py` — all FHIR write operations
- **Input:** Any FHIR create, update, or delete request
- **Validation logic:**
  ```
  FUNCTION fhir_write(resource_type, resource_data, operation):
      audit_entry = AuditLogEntry(
          timestamp=utcnow(),
          operation=operation,  # create, update, delete
          resource_type=resource_type,
          resource_id=resource_data.id,
          user_id=current_user.id,
          user_role=current_user.role,
          encounter_id=extract_encounter_id(resource_data),
          justification=resource_data.write_justification,
      )

      IF NOT audit_entry.is_complete():
          RAISE HardGuardrailViolation(
              guardrail_id="G-HARD-006",
              violation_description="FHIR write attempted without "
                  "complete HIPAA audit log entry. All writes to "
                  "patient data systems must be auditable.",
              constitution_article="II.4",
              suggested_remediation="Provide user_id, justification, "
                  "and encounter context for the write operation."
          )

      # Write audit entry BEFORE the FHIR operation
      # If audit write fails, FHIR write does not proceed
      audit_result = write_audit_log(audit_entry)
      IF NOT audit_result.success:
          RAISE HardGuardrailViolation(
              guardrail_id="G-HARD-006",
              violation_description="Audit log write failed. FHIR "
                  "operation cannot proceed without audit trail.",
              constitution_article="II.4",
              suggested_remediation="Retry or escalate audit system "
                  "failure. Do NOT proceed with FHIR write."
          )

      # Only now execute the FHIR write
      return execute_fhir_write(resource_type, resource_data, operation)
  ```
- **Violation logging:**
  ```
  log.critical("hard_guardrail_violation",
      guardrail_id="G-HARD-006",
      operation=operation,
      resource_type=resource_type,
      # NEVER log resource content
  )
  ```
- **Test case:** FHIR write with no user_id. Assert violation. FHIR write with audit log service unavailable. Assert violation (write does not proceed). FHIR write with complete audit entry and healthy audit service. Assert write proceeds.
- **HIPAA relevance:** HIPAA requires audit trails for all access to PHI. A FHIR write without an audit entry is an untracked modification to patient data — a compliance gap that OIG auditors specifically examine.

#### G-HARD-007: No AI Output Accepted if LLM Confidence < 0.40

- **Constitution reference:** Article II.6 (Conservative Defaults)
- **Pipeline location:** `src/agents/coding_agent.py` — post-LLM output processing
- **Input:** LLM response with confidence scores per suggestion
- **Validation logic:**
  ```
  FOR each suggestion in llm_output.suggestions:
      IF suggestion.confidence < 0.40:
          RAISE HardGuardrailViolation(
              guardrail_id="G-HARD-007",
              violation_description=f"LLM confidence for code "
                  "{suggestion.code} is {suggestion.confidence:.2f}, "
                  "below the minimum threshold of 0.40. Output is "
                  "too uncertain to present to any user.",
              constitution_article="II.6",
              suggested_remediation="Remove suggestion. If the "
                  "clinical scenario is genuinely ambiguous, generate "
                  "a CDI query instead of a code suggestion."
          )
  ```
- **Test case:** Suggestion with confidence 0.35. Assert violation. Suggestion with confidence 0.40. Assert passes (enters soft guardrail range). Suggestion with confidence 0.66. Assert passes fully.
- **FCA relevance:** An AI system that outputs low-confidence code suggestions is generating speculative clinical assertions. Per constitution Article II.6, uncertainty must always resolve toward the conservative option (CDI query, not code suggestion).

---

### Type B: Soft Guardrails

Soft guardrails generate `GuardrailWarning` and present the
warning to a human reviewer. The human explicitly accepts
or rejects the flagged output. The system does not proceed
until the human decision is recorded.

**Implementation:** Soft guardrails add warning annotations
to the output. The coder review UI displays these warnings
prominently. The coder must acknowledge each warning before
accepting the associated suggestion.

```python
class GuardrailWarning(BaseModel):
    """Warning attached to output that requires human review."""

    guardrail_id: str
    severity: Literal["high", "medium"]
    warning_message: str
    requires_explicit_acknowledgment: bool = True
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    acknowledgment_reason: str | None = None
```

#### G-SOFT-001: Confidence 0.40-0.65 Routes to Senior Coder

- **Pipeline location:** `src/agents/coding_agent.py` — post-LLM output processing
- **Input:** `CodingSuggestion` with `0.40 <= confidence < 0.65`
- **Validation logic:**
  ```
  FOR each suggestion in suggestion_set.suggestions:
      IF 0.40 <= suggestion.confidence < 0.65:
          suggestion.warnings.append(GuardrailWarning(
              guardrail_id="G-SOFT-001",
              severity="high",
              warning_message=f"Low confidence ({suggestion.confidence:.2f}) "
                  "for code {suggestion.code}. This suggestion requires "
                  "review by a senior coder before acceptance.",
              requires_explicit_acknowledgment=True,
          ))
          suggestion.routing = "senior_coder_queue"
  ```
- **UI behavior:** Suggestion appears in the senior coder queue with a prominent confidence warning. Senior coder must explicitly accept or reject with a documented reason.
- **Test case:** Suggestion with confidence 0.55. Assert routed to senior queue with warning. Suggestion with confidence 0.66. Assert normal routing without warning.

#### G-SOFT-002: Note Similarity > 85% Flags Copy-Forward

- **Pipeline location:** `src/nlp/copy_forward_detector.py` — pre-coding analysis
- **Input:** `CodingSuggestionSet` with `note_similarity_score > 0.85`
- **Validation logic:**
  ```
  IF suggestion_set.note_similarity_score IS NOT None:
      IF suggestion_set.note_similarity_score > 0.85:
          FOR each suggestion in suggestion_set.suggestions:
              IF suggestion.is_from_copied_text:
                  suggestion.warnings.append(GuardrailWarning(
                      guardrail_id="G-SOFT-002",
                      severity="high",
                      warning_message=f"Note similarity "
                          "{suggestion_set.note_similarity_score:.0%} "
                          "to prior note. Code {suggestion.code} appears "
                          "sourced from copy-forward text. Verify clinical "
                          "findings are current before accepting.",
                      requires_explicit_acknowledgment=True,
                  ))
          suggestion_set.warnings.append(GuardrailWarning(
              guardrail_id="G-SOFT-002",
              severity="medium",
              warning_message=f"Overall note similarity "
                  "{suggestion_set.note_similarity_score:.0%} exceeds "
                  "85% threshold. Review for copy-forward documentation.",
              requires_explicit_acknowledgment=True,
          ))
  ```
- **UI behavior:** Yellow banner on the code review screen: "This note has high similarity to a prior note. Verify all clinical findings are current." Each suggestion from copied text has an individual warning badge.
- **Test case:** Note with 91% similarity. Assert warning on all suggestions from copied sections. Note with 72% similarity. Assert no warning.
- **Compliance relevance:** Copy-forward documentation supporting billing for higher-level services without genuine clinical activity is FCA exposure (DISC-002 Section A.3). OIG specifically identifies copy-paste as a fraud vulnerability.

#### G-SOFT-003: DRG Increase > $5,000 Flags for Compliance Review

- **Pipeline location:** `src/core/drg/grouper.py` — DRG impact calculation (DESIGN-001 Step 8)
- **Input:** `DRGImpact` from the rules engine
- **Validation logic:**
  ```
  IF drg_impact.revenue_difference IS NOT None:
      IF drg_impact.revenue_difference > 5000:
          drg_impact.requires_compliance_review = True
          suggestion_set.warnings.append(GuardrailWarning(
              guardrail_id="G-SOFT-003",
              severity="high",
              warning_message=f"DRG improvement of "
                  "${drg_impact.revenue_difference:,.0f} exceeds "
                  "$5,000 threshold. Routed to compliance team for "
                  "review before coder action.",
              requires_explicit_acknowledgment=True,
          ))
  ```
- **UI behavior:** Suggestion set is dual-routed: appears in the coder queue AND the compliance review queue. Coder cannot accept until compliance team clears the review. Compliance team sees the full evidence trail, DRG calculation, and clinical documentation.
- **Test case:** DRG delta of $7,500. Assert compliance review flag. DRG delta of $4,999. Assert no flag. DRG delta of $42,000 (sepsis MCC upgrade). Assert flag with high-priority compliance routing.
- **Compliance relevance:** Constitution Article II.6. Large DRG improvements from AI suggestions are exactly what OIG auditors examine. Proactive compliance review demonstrates good faith and creates an audit defense.

#### G-SOFT-004: Excludes 2 Pair Requires Human Confirmation

- **Pipeline location:** `src/core/icd10/rules_engine.py` — validation step 3
- **Input:** `CodingSuggestionSet` containing codes with Excludes 2 relationship
- **Validation logic:**
  ```
  FOR each pair (code_a, code_b) in suggestion_set.suggestions:
      IF has_excludes2_relationship(code_a.code, code_b.code):
          shared_warning = GuardrailWarning(
              guardrail_id="G-SOFT-004",
              severity="medium",
              warning_message=f"Excludes 2 pair detected: "
                  "{code_a.code} and {code_b.code}. Both codes "
                  "may be reported together IF both conditions "
                  "are independently documented. Please confirm "
                  "documentation supports both conditions.",
              requires_explicit_acknowledgment=True,
          )
          code_a.warnings.append(shared_warning)
          code_b.warnings.append(shared_warning)
  ```
- **UI behavior:** Both codes highlighted with linked warning. Coder must confirm documentation supports both conditions independently before accepting the pair.
- **Test case:** E66.01 (Morbid obesity) + G47.33 (Sleep apnea) with Excludes 2. Assert warning requiring confirmation. Same pair with coder acknowledgment. Assert accepted.

#### G-SOFT-005: Third CDI Query on Same Case Triggers Escalation

- **Pipeline location:** `src/agents/cdi_agent.py` — query generation
- **Input:** CDI opportunity for an encounter that already has 2+ active/resolved queries
- **Validation logic:**
  ```
  existing_queries = get_queries_for_encounter(encounter_id)
  active_or_resolved = [q for q in existing_queries
                        if q.status in ("pending", "resolved_positive",
                                        "resolved_negative")]

  IF len(active_or_resolved) >= 2:
      new_opportunity.warnings.append(GuardrailWarning(
          guardrail_id="G-SOFT-005",
          severity="medium",
          warning_message=f"This would be CDI query #{len(active_or_resolved) + 1} "
              "for encounter {encounter_id}. Multiple queries on the "
              "same case may indicate documentation quality issues "
              "or physician notification fatigue risk. CDI specialist "
              "should review before sending.",
          requires_explicit_acknowledgment=True,
      ))
      new_opportunity.routing = "cdi_specialist_review"
  ```
- **UI behavior:** Query appears in CDI specialist review queue instead of being sent directly to physician. CDI specialist decides whether to send, batch with other queries, or defer.
- **Test case:** Third CDI opportunity on same encounter. Assert routed to CDI specialist. First CDI opportunity. Assert direct routing to physician.
- **Compliance relevance:** Excessive querying can constitute physician harassment and may lead to "query fatigue" where physicians reflexively answer "yes" without clinical assessment — an OIG compliance concern (DISC-002 Section E).

---

### Type C: Monitoring Guardrails

Monitoring guardrails do not block or flag individual
transactions. They aggregate data over time and generate
alerts when patterns deviate from expected baselines.
They detect systematic issues that individual-transaction
guardrails cannot catch.

**Implementation:** Monitoring guardrails run as background
processes that query the audit database on configurable
schedules. Alerts are delivered to administrators and
compliance officers.

```python
class MonitoringAlert(BaseModel):
    """Alert generated by monitoring guardrail."""

    guardrail_id: str
    alert_type: Literal["threshold_exceeded", "anomaly_detected",
                        "trend_change", "system_health"]
    metric_name: str
    current_value: float
    threshold_value: float
    time_period: str
    recommended_action: str
    recipients: list[str]  # Role-based: "compliance_officer", "admin"
```

#### G-MON-001: Override Rate Per Suggestion Type (Weekly)

- **Metric:** Percentage of AI code suggestions that coders override (change or reject) per code category
- **Schedule:** Weekly report generated every Monday 06:00 UTC
- **Thresholds:**
  - Normal: override rate 10-30%
  - Warning: override rate > 40% for any category → model may need retraining for that category
  - Critical: override rate > 60% → AI suggestions for that category may be doing more harm than good
- **Alert recipients:** AI engineering team, CDI director
- **Data source:** `audit_log` table: compare AI-suggested codes vs final submitted codes per encounter
- **Why it matters:** High override rates indicate the AI model is producing inaccurate suggestions for certain clinical scenarios. This is a model quality signal, not a compliance issue per se, but sustained inaccuracy undermines trust and may indicate training data gaps.

#### G-MON-002: DRG Distribution vs National Benchmark (Monthly)

- **Metric:** Facility's DRG distribution compared to national CMS benchmarks (PEPPER report equivalence)
- **Schedule:** Monthly report generated on 1st of each month
- **Thresholds:**
  - Normal: facility DRG distribution within 1 standard deviation of national benchmark per DRG family
  - Warning: any DRG family > 1.5 SD above national rate → potential systematic upcoding
  - Critical: any DRG family > 2 SD above national rate → OIG audit risk
  - Also flag: any DRG family > 1.5 SD BELOW national rate → potential undercoding (revenue opportunity or model failure)
- **Alert recipients:** Compliance officer, CFO, CDI director
- **Data source:** Monthly aggregate of submitted DRGs vs CMS PEPPER target data
- **Why it matters:** OIG uses PEPPER (Program for Evaluating Payment Patterns Electronic Report) to identify hospitals with outlier DRG distributions. Our system must ensure it does not systematically shift DRG distributions above national benchmarks. This is the most important systemic compliance monitoring metric.

#### G-MON-003: CDI Query Response Rate by Physician (Weekly)

- **Metric:** CDI query response rate per attending physician
- **Schedule:** Weekly report
- **Thresholds:**
  - Normal: > 80% response rate
  - Warning: 50-80% response rate → physician education/outreach needed
  - Critical: < 50% response rate → escalate to department chief
  - Also flag: > 95% "Yes" response rate → possible reflexive acceptance, compliance concern
- **Alert recipients:** CDI director, department chief (for critical)
- **Data source:** CDI query delivery and response records
- **Why it matters:** Low response rates undermine CDI program effectiveness. Excessively high "yes" rates may indicate leading queries or physician fatigue (OIG compliance concern).

#### G-MON-004: FHIR API Error Rate by Endpoint (Real-Time)

- **Metric:** HTTP error rate (4xx, 5xx) per FHIR endpoint
- **Schedule:** Real-time monitoring with 5-minute aggregation windows
- **Thresholds:**
  - Normal: < 1% error rate
  - Warning: 1-5% error rate → potential EHR connectivity issue
  - Critical: > 5% error rate → trigger graceful degradation (Section 6)
  - Also monitor: latency p95 > 5 seconds → EHR performance degradation
- **Alert recipients:** DevOps, on-call engineer
- **Data source:** FHIR client request/response logs (no PHI)
- **Why it matters:** FHIR API failures directly impact the system's ability to retrieve clinical data. Sustained failures require graceful degradation to ensure clinical workflows continue (Constitution Article II.5).

#### G-MON-005: LLM Latency Percentiles (Real-Time)

- **Metric:** Claude API response latency at p50, p95, p99
- **Schedule:** Real-time monitoring with 1-minute aggregation
- **Thresholds:**
  - p50 normal: < 3 seconds
  - p95 normal: < 10 seconds
  - p99 normal: < 20 seconds
  - p99 warning: > 30 seconds → degraded user experience
  - p99 critical: > 60 seconds → trigger timeout and degraded result
- **Alert recipients:** DevOps, on-call engineer
- **Data source:** Claude API client timing logs
- **Why it matters:** Coder productivity depends on responsive AI suggestions. Sustained high latency impacts workflow. Timeouts must produce graceful degradation, not errors (Constitution Article II.5).

---

## 2. Implementation Architecture

### 2.1 Guardrail Execution Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    REQUEST ENTRY POINT                        │
│                    (FastAPI endpoint)                         │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 1: Input Validation ────────────────────────────────┐
│ G-HARD-005: PHI filter on request logging                     │
│ G-HARD-006: Audit log entry for any data access               │
│                                                               │
│ Implementation: FastAPI middleware                             │
│ Runs: BEFORE any business logic                               │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 2: LLM Output Guardrails ──────────────────────────┐
│ G-HARD-007: Reject confidence < 0.40                          │
│ G-HARD-002: Require evidence_quote on every suggestion        │
│ G-SOFT-001: Route confidence 0.40-0.65 to senior coder       │
│                                                               │
│ Implementation: Post-processing in coding_agent.py            │
│ Runs: AFTER LLM returns suggestions, BEFORE rules engine      │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 3: Rules Engine Guardrails ────────────────────────┐
│ G-HARD-003: Excludes 1 prohibition                            │
│ G-HARD-004: Outpatient uncertain diagnosis prohibition        │
│ G-SOFT-004: Excludes 2 human confirmation                     │
│ G-SOFT-002: Copy-forward flag                                 │
│                                                               │
│ Implementation: rules_engine.py validation pipeline           │
│ Runs: AFTER LLM output guardrails, BEFORE DRG calculation     │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 4: Revenue Impact Guardrails ──────────────────────┐
│ G-SOFT-003: DRG increase > $5,000 compliance review           │
│                                                               │
│ Implementation: drg/grouper.py                                │
│ Runs: AFTER rules engine, BEFORE output to coder UI           │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 5: CDI Query Guardrails ───────────────────────────┐
│ G-SOFT-005: 3rd+ CDI query escalation                         │
│                                                               │
│ Implementation: cdi_agent.py                                  │
│ Runs: BEFORE CDI query is sent to physician                   │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 6: Output Guardrails ──────────────────────────────┐
│ G-HARD-001: Human approval token for claim submission         │
│ G-HARD-005: PHI filter on response logging                    │
│ G-HARD-006: Audit log for any data write                      │
│                                                               │
│ Implementation: FastAPI middleware + claims route              │
│ Runs: BEFORE any external write operation                     │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌──── LAYER 7: Monitoring (Background) ────────────────────────┐
│ G-MON-001 through G-MON-005                                   │
│                                                               │
│ Implementation: Background workers + scheduled reports        │
│ Runs: Continuously / on schedule                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Guardrail Registry

All guardrails are registered in a central registry that enables:
- Enumeration of all active guardrails
- Runtime verification that all guardrails are loaded
- Health check that confirms guardrail middleware is active

```python
class GuardrailRegistry:
    """Central registry of all system guardrails.

    At startup, the system verifies that every registered
    guardrail is loaded and active. If any hard guardrail
    fails to load, the system refuses to start.
    """

    _hard_guardrails: dict[str, HardGuardrail]
    _soft_guardrails: dict[str, SoftGuardrail]
    _monitoring_guardrails: dict[str, MonitoringGuardrail]

    def verify_all_loaded(self) -> bool:
        """Called at startup. Returns False if any hard guardrail
        is missing. System MUST NOT start if this returns False."""
        ...

    def get_guardrail(self, guardrail_id: str) -> Guardrail:
        """Retrieve a guardrail by ID for testing or inspection."""
        ...

    def health_check(self) -> GuardrailHealthReport:
        """Returns status of all guardrails. Exposed at /health."""
        ...
```

---

## 3. Guardrail Test Matrix

### 3.1 Hard Guardrail Tests

| Guardrail | Test ID | Scenario | Input | Expected Output | Priority |
|-----------|---------|----------|-------|-----------------|----------|
| G-HARD-001 | T-001-01 | No approval token | Claim submission, token=None | HardGuardrailViolation | P0 |
| G-HARD-001 | T-001-02 | Expired token | Claim, token issued 25h ago | HardGuardrailViolation | P0 |
| G-HARD-001 | T-001-03 | Token for different code set | Claim, token.code_set_hash != current hash | HardGuardrailViolation | P0 |
| G-HARD-001 | T-001-04 | Non-credentialed user token | Token from user without coder role | HardGuardrailViolation | P0 |
| G-HARD-001 | T-001-05 | Valid token, matching codes | Correct token, matching hash, < 24h | Claim proceeds | P0 |
| G-HARD-001 | T-001-06 | Tampered token signature | Token with invalid cryptographic signature | HardGuardrailViolation | P0 |
| G-HARD-002 | T-002-01 | Empty evidence_quote | Suggestion with evidence_quote="" | HardGuardrailViolation | P0 |
| G-HARD-002 | T-002-02 | None evidence_quote | Suggestion with evidence_quote=None | HardGuardrailViolation | P0 |
| G-HARD-002 | T-002-03 | Quote not in note | evidence_quote="chest pain" but note says "no chest pain" | HardGuardrailViolation | P0 |
| G-HARD-002 | T-002-04 | Valid quote | evidence_quote is substring of source_note_text | Passes | P0 |
| G-HARD-002 | T-002-05 | Quote from different note | evidence_quote from a prior note, not current | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-01 | E10 + E11 (DM types) | E10.9 + E11.9 in suggestion set | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-02 | J44.9 + J45.909 (COPD + asthma unspecified) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-03 | J44.9 + J45.901 (COPD + asthma specified) | Both codes present | Passes (Excl1 is only for unspecified) | P0 |
| G-HARD-003 | T-003-04 | E66.01 + E66.3 (obesity + overweight) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-05 | Z87.x + active code for same condition | History + active code | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-06 | E83.52 + E21.x (hypercalcemia + hyperPTH) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-07 | E78.5 + E78.0 (lipid unspecified + specific) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-08 | D63.1 + D50.x (anemia chronic + iron def) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-09 | F32.A + F32.1 (depression unspec + specific) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-10 | E03.0 + E03.9 (hypothyroid congenital + acquired) | Both codes present | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-11 | Category-level Excludes 1 | Two codes where Excludes 1 is at category level | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-12 | Chapter-level Excludes 1 | Two codes where Excludes 1 is at chapter level | HardGuardrailViolation | P0 |
| G-HARD-003 | T-003-13 | No Excludes 1 relationship | E11.22 + N18.3 | Passes | P0 |
| G-HARD-004 | T-004-01 | Outpatient + "suspected" | Outpatient, qualifier="suspected", J18.9 | HardGuardrailViolation | P0 |
| G-HARD-004 | T-004-02 | Outpatient + "probable" | Outpatient, qualifier="probable", J18.9 | HardGuardrailViolation | P0 |
| G-HARD-004 | T-004-03 | Outpatient + "rule out" | Outpatient, qualifier="rule out", I21.9 | HardGuardrailViolation | P0 |
| G-HARD-004 | T-004-04 | Outpatient + "concern for" | Outpatient, qualifier="concern for" | HardGuardrailViolation | P0 |
| G-HARD-004 | T-004-05 | Outpatient + "suggestive of" | Outpatient, qualifier="suggestive of" | HardGuardrailViolation | P0 |
| G-HARD-004 | T-004-06 | Inpatient + "suspected" | Inpatient, qualifier="suspected", J18.9 | Passes (Section II.H) | P0 |
| G-HARD-004 | T-004-07 | Inpatient + "ruled out" | Inpatient, qualifier="ruled out", J18.9 | HardGuardrailViolation (never code) | P0 |
| G-HARD-004 | T-004-08 | Outpatient + confirmed dx | Outpatient, no qualifier, J18.9 | Passes | P0 |
| G-HARD-004 | T-004-09 | Outpatient + all 15 qualifiers | Test each qualifier word | 15 violations | P0 |
| G-HARD-005 | T-005-01 | Patient name in log | log.info("processing", patient_name="John Doe") | HardGuardrailViolation | P0 |
| G-HARD-005 | T-005-02 | DOB in log | log.info("check", dob="01/15/1980") | HardGuardrailViolation | P0 |
| G-HARD-005 | T-005-03 | SSN pattern in log | log.info("id", value="123-45-6789") | HardGuardrailViolation | P0 |
| G-HARD-005 | T-005-04 | MRN in log | log.info("record", mrn="MRN12345678") | HardGuardrailViolation | P0 |
| G-HARD-005 | T-005-05 | Evidence quote in log | log.info("result", evidence_quote="patient has...") | HardGuardrailViolation | P0 |
| G-HARD-005 | T-005-06 | Safe log fields only | log.info("result", encounter_id="ENC-123", code="E11.22") | Passes | P0 |
| G-HARD-005 | T-005-07 | Clinical text in error message | raise ValueError(f"Failed for {note_text}") | HardGuardrailViolation | P0 |
| G-HARD-006 | T-006-01 | FHIR write without user_id | FHIR create, audit missing user_id | HardGuardrailViolation | P0 |
| G-HARD-006 | T-006-02 | FHIR write, audit service down | FHIR create, audit_log write fails | HardGuardrailViolation (write blocked) | P0 |
| G-HARD-006 | T-006-03 | FHIR write with complete audit | All audit fields present, service healthy | Write proceeds | P0 |
| G-HARD-006 | T-006-04 | Audit precedes FHIR write | Verify audit timestamp < FHIR write timestamp | Audit logged first | P0 |
| G-HARD-007 | T-007-01 | Confidence 0.35 | suggestion.confidence = 0.35 | HardGuardrailViolation | P0 |
| G-HARD-007 | T-007-02 | Confidence 0.10 | suggestion.confidence = 0.10 | HardGuardrailViolation | P0 |
| G-HARD-007 | T-007-03 | Confidence 0.00 | suggestion.confidence = 0.00 | HardGuardrailViolation | P0 |
| G-HARD-007 | T-007-04 | Confidence 0.40 (boundary) | suggestion.confidence = 0.40 | Passes (enters soft guardrail) | P0 |
| G-HARD-007 | T-007-05 | Confidence 0.39 (boundary) | suggestion.confidence = 0.39 | HardGuardrailViolation | P0 |

### 3.2 Soft Guardrail Tests

| Guardrail | Test ID | Scenario | Input | Expected Output | Priority |
|-----------|---------|----------|-------|-----------------|----------|
| G-SOFT-001 | T-101-01 | Confidence 0.55 | suggestion.confidence = 0.55 | Warning + senior queue routing | P0 |
| G-SOFT-001 | T-101-02 | Confidence 0.65 (boundary) | suggestion.confidence = 0.65 | No warning (threshold is <0.65) | P0 |
| G-SOFT-001 | T-101-03 | Confidence 0.40 (lower boundary) | suggestion.confidence = 0.40 | Warning + senior queue | P0 |
| G-SOFT-002 | T-102-01 | Note similarity 91% | note_similarity_score = 0.91 | Warning on all copy-forward suggestions | P1 |
| G-SOFT-002 | T-102-02 | Note similarity 85% (boundary) | note_similarity_score = 0.85 | No warning (threshold is >0.85) | P1 |
| G-SOFT-002 | T-102-03 | Note similarity 86% | note_similarity_score = 0.86 | Warning | P1 |
| G-SOFT-003 | T-103-01 | DRG delta $7,500 | revenue_difference = 7500 | Compliance review flag | P0 |
| G-SOFT-003 | T-103-02 | DRG delta $4,999 | revenue_difference = 4999 | No flag | P0 |
| G-SOFT-003 | T-103-03 | DRG delta $5,001 | revenue_difference = 5001 | Compliance review flag | P0 |
| G-SOFT-004 | T-104-01 | Excludes 2 pair with docs | Two codes with Excludes 2, both documented | Warning requiring confirmation | P1 |
| G-SOFT-005 | T-105-01 | 3rd CDI query | Encounter with 2 existing queries | Warning + CDI specialist routing | P1 |
| G-SOFT-005 | T-105-02 | 1st CDI query | Encounter with 0 existing queries | No warning, direct routing | P1 |

### 3.3 Test Coverage Requirements

- **Hard guardrails:** 100% test coverage. Every hard guardrail has at minimum: 1 violation test, 1 boundary test, 1 pass test. Tests are written BEFORE implementation (Constitution Article I.2).
- **Soft guardrails:** 100% test coverage for warning generation. UI acknowledgment flow tested in integration tests.
- **Monitoring guardrails:** Threshold logic tested in unit tests. Alert delivery tested in integration tests.
- **Total minimum test count:** 50 (listed above) + additional edge cases as discovered.

---

## 4. False Claims Act Specific Design

### 4.1 How the System Prevents Upcoding

```
UPCODING PREVENTION CHAIN:

1. EVIDENCE REQUIREMENT (G-HARD-002)
   Every code suggestion must cite verbatim text from the
   clinical note. No evidence = no suggestion. This prevents
   the AI from generating codes that sound plausible but
   have no documentation basis.

2. CONSERVATIVE DEFAULTS (G-HARD-007 + G-SOFT-001)
   Low-confidence suggestions are either blocked (< 0.40)
   or routed to senior coders (0.40-0.65). The system
   never presents speculative codes to junior coders.

3. ICD-10 HARD CONSTRAINTS (G-HARD-003, G-HARD-004)
   The rules engine prevents structurally invalid code
   combinations. Excludes 1 violations and outpatient
   uncertain diagnosis coding are architecturally
   impossible.

4. DRG COMPLIANCE REVIEW (G-SOFT-003)
   Any suggestion that increases DRG revenue by > $5,000
   is routed to compliance review. This catches high-value
   upcoding opportunities and ensures they are clinically
   justified, not AI-optimized.

5. HUMAN APPROVAL (G-HARD-001)
   No claim is submitted without a credentialed coder's
   explicit approval. The approval token is cryptographically
   bound to the specific code set — the coder cannot
   approve one set and submit a different one.

6. DISTRIBUTION MONITORING (G-MON-002)
   Monthly DRG distribution analysis catches systematic
   upcoding patterns that individual-transaction guardrails
   cannot detect. OIG uses the same PEPPER methodology.
```

### 4.2 Audit Trail for FCA Defense

Every code suggestion creates an audit chain:

```
AUDIT CHAIN PER CODE:

1. SOURCE NOTE
   - Note ID, author, timestamp, encounter_id
   - Note signed by attending physician (not AI-generated)

2. AI SUGGESTION
   - Suggested code
   - evidence_quote (verbatim from note)
   - Confidence score
   - Model version (Claude model ID)
   - Prompt version (PHR reference)
   - Rules engine validation result
   - Guardrail warnings (if any)
   - Timestamp

3. HUMAN REVIEW
   - Coder ID, credentials, timestamp
   - Action: accepted, modified, rejected
   - If modified: what was changed and why
   - If rejected: reason for rejection
   - Guardrail acknowledgments (if any warnings present)
   - Time spent reviewing (for productivity metrics)

4. COMPLIANCE REVIEW (if G-SOFT-003 triggered)
   - Compliance reviewer ID, timestamp
   - Action: approved, modified, rejected
   - Clinical justification documented

5. CLAIM SUBMISSION
   - human_approval_token
   - Final code set submitted
   - DRG assigned
   - Revenue amount
   - Payer
   - Submission timestamp

This chain creates an unbroken provenance trail from
physician documentation → AI suggestion → human review →
claim submission. Every link is timestamped and attributed
to a specific user.

In an FCA investigation, this chain demonstrates:
- The code was based on physician documentation (not AI fabrication)
- The AI provided supporting evidence (not just a code)
- A credentialed human reviewed and approved (not autonomous)
- Compliance reviewed high-value cases (proactive good faith)
- The system was architecturally incapable of submitting
  without human approval (not just a policy — a technical fact)
```

### 4.3 Conservative Default Architecture

Per Constitution Article II.6, when the system is uncertain:

| Uncertainty Scenario | Conservative Default | Alternative (Rejected) |
|---------------------|---------------------|----------------------|
| Higher vs lower specificity code | Lower specificity | Always maximize specificity |
| Code the condition vs CDI query | CDI query | Code and hope |
| Submit claim vs flag for review | Flag for review | Submit and check later |
| Confident suggestion vs hedged | Hedged | Present as certain |
| DRG improvement > $5,000 | Compliance review | Auto-accept |
| Two codes equally qualify as principal | Flag for human decision | Pick higher-paying DRG |
| Uncertain diagnosis (outpatient) | Code symptom only | Code as confirmed |
| Copy-forward text detected | Flag all sourced suggestions | Treat as current |

Every conservative default has a corresponding guardrail that enforces it.

---

## 5. OIG Audit Readiness

### 5.1 Audit Log Specification

```python
class AuditLogEntry(BaseModel):
    """Immutable audit log entry for every system action.

    Stored in append-only audit table. Never modified.
    Never deleted (except per retention policy).
    """

    # Identity
    entry_id: str = Field(description="UUID for this entry")
    timestamp: datetime = Field(description="UTC timestamp")

    # Actor
    actor_type: Literal["system", "coder", "physician",
                        "cdi_specialist", "compliance_officer", "admin"]
    actor_id: str = Field(description="User ID or 'system'")
    actor_role: str = Field(description="Role at time of action")

    # Action
    action: Literal[
        "suggestion_generated", "suggestion_validated",
        "suggestion_accepted", "suggestion_modified",
        "suggestion_rejected", "guardrail_violation",
        "guardrail_warning_acknowledged", "cdi_query_generated",
        "cdi_query_responded", "claim_submitted",
        "claim_approved", "fhir_read", "fhir_write",
        "compliance_review_completed", "system_degradation",
    ]
    action_detail: str = Field(description="Specific detail of action")

    # Context (NO PHI)
    encounter_id: str
    code: str | None = None
    guardrail_id: str | None = None
    confidence: float | None = None
    drg_impact: float | None = None

    # Provenance
    model_version: str | None = None  # Claude model ID
    prompt_version: str | None = None  # PHR reference
    rules_engine_version: str | None = None
```

### 5.2 Retention Policy

| Data Category | Retention Period | Rationale |
|--------------|-----------------|-----------|
| Audit log entries | 7 years | FCA statute of limitations (6 years + 1 year buffer) |
| Code suggestion provenance | 7 years | Must be able to reconstruct the decision chain for any claim |
| Human approval tokens | 7 years | Prove human review occurred for every submitted claim |
| Guardrail violation logs | 7 years | Demonstrate system caught and prevented violations |
| Monitoring alert history | 3 years | Demonstrate ongoing compliance monitoring |
| CDI query/response records | 7 years | Prove CDI queries were non-leading and clinically grounded |
| DRG distribution reports | 7 years | PEPPER-equivalent data for OIG comparison |

### 5.3 OIG Audit Response Package

When an OIG audit occurs, the system produces this evidence package:

```
OIG AUDIT RESPONSE PACKAGE

Section 1: System Architecture
  - Guardrail taxonomy (this spec)
  - ADR-008 (guardrails as architecture)
  - Constitution Article II (safety law)
  - Test coverage reports showing 100% guardrail test pass

Section 2: Per-Claim Evidence (for each audited claim)
  - Source clinical note (with physician attestation)
  - AI suggestion with evidence_quote
  - Rules engine validation result
  - Guardrail evaluation result
  - Human reviewer identity and credentials
  - human_approval_token with timestamp
  - Any guardrail warnings acknowledged and rationale
  - Compliance review record (if G-SOFT-003 triggered)

Section 3: Systemic Evidence
  - Monthly DRG distribution reports vs PEPPER benchmarks
  - Weekly override rate reports
  - CDI query compliance audit results
  - Guardrail violation log summary (how many blocked)
  - False positive CDI rates

Section 4: Process Documentation
  - Coder training records
  - Compliance review protocols
  - Guardrail update procedures
  - Annual ICD-10 code table update procedures

Retrieval time target: Any single claim's full audit
chain retrievable within 5 minutes via audit API.
```

### 5.4 Code Suggestion Provenance

Every code in a submitted claim has a complete provenance trail:

```
PROVENANCE RECORD PER CODE:

{
  "code": "E11.22",
  "encounter_id": "ENC-2026-04-001",
  "source": {
    "note_id": "DOC-2026-04-001-PN3",
    "note_author": "DR-12345",  # physician ID, not name
    "note_signed_at": "2026-04-01T14:30:00Z",
    "evidence_quote_hash": "sha256:abc123...",
    // evidence_quote content available on authorized request
  },
  "ai_suggestion": {
    "model": "claude-sonnet-4-6",
    "prompt_version": "PHR-001-v2.1",
    "confidence": 0.87,
    "rules_engine_result": "VALID",
    "guardrail_result": "PASS",
    "guardrail_warnings": [],
    "suggested_at": "2026-04-01T14:32:15Z"
  },
  "human_review": {
    "reviewer_id": "CODER-789",
    "reviewer_credentials": "CCS, RHIA",
    "action": "accepted",
    "modification": null,
    "reviewed_at": "2026-04-01T15:10:22Z"
  },
  "claim_submission": {
    "approval_token_hash": "sha256:def456...",
    "submitted_at": "2026-04-01T15:12:01Z",
    "drg": "638",
    "drg_weight": 1.0234
  }
}
```

### 5.5 Override Documentation

When a coder modifies an AI suggestion, the override is documented:

```python
class CoderOverride(BaseModel):
    """Records when a coder changes or rejects an AI suggestion."""

    encounter_id: str
    original_code: str
    original_confidence: float
    action: Literal["modified", "rejected", "added_code"]
    new_code: str | None = None  # If modified
    reason: str  # Free-text reason from coder
    coder_id: str
    timestamp: datetime
    guardrail_warnings_present: list[str]  # Any warnings on the original
```

---

## 6. Graceful Degradation Specification

Per Constitution Article II.5: if any AI component fails,
clinical and administrative workflows MUST continue
uninterrupted. AI assists humans. AI never blocks humans.

### 6.1 Failure Mode: FHIR API Unavailable

```
TRIGGER: G-MON-004 detects FHIR error rate > 5% for > 2 minutes

FALLBACK BEHAVIOR:
  - Coding agent returns DegradedResult(is_degraded=True)
  - Coder review UI shows "AI Assist Unavailable" banner
  - Manual coding mode is activated (coder codes without AI)
  - CDI queries in flight are held in outbox queue
  - Note: coder can ALWAYS code manually without AI

USER SEES:
  "AI-assisted coding is temporarily unavailable due to a
  connection issue with the clinical data system. You may
  continue coding manually. AI assistance will resume
  automatically when the connection is restored."

LOGGING:
  log.warning("system_degradation",
      component="fhir_client",
      error_rate=current_error_rate,
      degradation_mode="manual_coding",
      # No PHI
  )

RECOVERY:
  - Background health check pings FHIR endpoint every 30s
  - When 3 consecutive successful pings: restore AI mode
  - Re-process any cases that were coded manually during
    degradation (post-coding AI review for missed opportunities)
  - CDI query outbox is flushed

ESCALATION:
  T+2min:   G-MON-004 warning alert to DevOps
  T+15min:  Escalate to on-call engineer
  T+60min:  Escalate to engineering lead
  T+4hrs:   Page hospital IT liaison (may be EHR-side issue)
```

### 6.2 Failure Mode: LLM API Timeout / Unavailable

```
TRIGGER: Claude API returns timeout or 5xx for > 3 consecutive requests

FALLBACK BEHAVIOR:
  - Coding agent returns DegradedResult(is_degraded=True)
  - Rules engine STILL validates any previously cached suggestions
  - CDI agent pauses new opportunity detection
  - Coder review UI shows "AI Suggestions Unavailable" banner
  - Manual coding mode activated

USER SEES:
  "AI code suggestions are temporarily unavailable. You may
  continue coding from clinical documentation. The rules
  engine will validate any codes you assign."

LOGGING:
  log.warning("system_degradation",
      component="llm_client",
      error_type="timeout" or "5xx",
      consecutive_failures=count,
      degradation_mode="manual_coding_with_rules_engine",
  )

RECOVERY:
  - Exponential backoff retry: 5s, 10s, 30s, 60s
  - After 5 successful responses: restore AI suggestion mode
  - Reprocess pending encounters from degradation window

ESCALATION:
  T+1min:   Warning alert to DevOps
  T+10min:  Escalate to on-call engineer
  T+30min:  Check Anthropic status page
  T+2hrs:   Escalate to engineering lead
```

### 6.3 Failure Mode: Rules Engine Data Load Failure

```
TRIGGER: Code table, Excludes table, or DRG weights fail to load at startup

FALLBACK BEHAVIOR:
  - System enters RESTRICTED MODE
  - All AI suggestions are marked is_degraded=True
  - G-HARD-003 (Excludes 1) cannot execute → ALL suggestions
    require manual verification
  - DRG impact calculation unavailable
  - Coder review UI shows "Validation Limited" banner

USER SEES:
  "Code validation is operating in limited mode. All AI
  suggestions require manual verification. Excludes 1
  checking and DRG impact are temporarily unavailable."

LOGGING:
  log.error("system_degradation",
      component="rules_engine",
      error_type="data_load_failure",
      missing_data=["excludes1_table", "drg_weights"],
      degradation_mode="restricted",
  )

RECOVERY:
  - Retry data load every 60 seconds
  - On successful load: re-validate any pending suggestion sets
  - System exits restricted mode only after ALL data tables
    are loaded and verified

CRITICAL: The system NEVER skips Excludes 1 validation
silently. If it cannot validate, it tells the user.

ESCALATION:
  T+0:      Critical alert to DevOps + engineering lead
  T+5min:   Page on-call engineer
  T+30min:  If data files missing/corrupt: investigate data pipeline
```

### 6.4 Failure Mode: Database Unavailable

```
TRIGGER: Audit database or application database connection fails

FALLBACK BEHAVIOR:
  AUDIT DATABASE DOWN:
    - G-HARD-006 is violated: NO FHIR writes proceed
    - Coding suggestions can still be generated and displayed
    - Claims CANNOT be submitted (no audit trail)
    - Suggestions are cached locally until DB restores
    - User sees: "Claim submission temporarily unavailable.
      Code review is available but submissions are paused."

  APPLICATION DATABASE DOWN:
    - System enters full degradation
    - Manual coding mode activated
    - No AI features available
    - User sees: "System is temporarily unavailable.
      Please use manual coding procedures."

LOGGING:
  - Log to local file if database is unavailable
  - Include degradation start timestamp
  - Recovery: replay local logs to database on restoration

ESCALATION:
  T+0:      Critical alert (multiple channels)
  T+5min:   Page DBA + on-call engineer
  T+15min:  Escalate to engineering lead
```

### 6.5 Failure Mode: Guardrail Middleware Failure

```
TRIGGER: Any guardrail middleware raises an unexpected exception
(not HardGuardrailViolation — an actual runtime error)

FALLBACK BEHAVIOR:
  - THE REQUEST IS BLOCKED. Not allowed to proceed.
  - A guardrail failure is treated as a guardrail violation,
    not as a pass. The fail-safe is to deny, not to allow.
  - User sees: "Safety validation encountered an unexpected
    error. This request has been paused for review."

RATIONALE:
  If the guardrail that checks for Excludes 1 violations
  crashes, we cannot know whether the suggestion set has
  an Excludes 1 violation. The safe default is to block,
  not to allow through unchecked.

  "When the guardrail breaks, the gate stays closed."

ESCALATION:
  T+0:      Critical alert — guardrail failure
  T+1min:   Page on-call engineer
  T+5min:   Engineering lead notified
```

### 6.6 Degradation Summary Matrix

| Component | Failure Mode | Coding Available | CDI Available | Claims Submittable | Rules Validation |
|-----------|-------------|-----------------|--------------|-------------------|-----------------|
| FHIR API | Unavailable | Manual only | Paused | Yes (if already coded) | Yes (cached data) |
| LLM API | Timeout/5xx | Manual only | Paused | Yes (if already coded) | Yes |
| Rules Engine Data | Load failure | Manual with warnings | Available | Yes with manual verify | Limited |
| Audit DB | Down | Yes (suggestions only) | Yes | **NO** (blocked by G-HARD-006) | Yes |
| App DB | Down | **NO** | **NO** | **NO** | **NO** |
| Guardrail middleware | Crash | **NO** (blocked) | **NO** (blocked) | **NO** (blocked) | N/A |

**Key principle:** The system degrades toward manual operation,
never toward unchecked AI operation. When AI components fail,
humans take over. When guardrails fail, the gate stays closed.

---

*This specification is the authoritative reference for the
compliance guardrail architecture. No guardrail may be removed,
weakened, or made configurable without amending Constitution
Article II — the bar for which is intentionally high.*
