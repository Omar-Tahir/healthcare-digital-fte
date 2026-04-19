# DESIGN-001: ICD-10 Coding Rules Engine Specification

**Status:** COMPLETE  
**Date:** 2026-04-01  
**Author:** Claude (AI Engineering Partner)  
**Research inputs:** DISC-001 (ICD-10 Official Guidelines), DISC-002 (Documentation Failure Patterns)  
**Constitution references:** Article I.1 (Spec-Driven), Article II.3 (ICD-10 Hard Constraints), Article II.6 (Conservative Defaults)  
**Implementation target:** `src/core/icd10/rules_engine.py`, `src/core/icd10/validator.py`, `src/core/icd10/guidelines.py`

---

## Purpose

This spec defines the ICD-10 coding rules engine that validates
every AI-generated code suggestion before it reaches the coder
review interface. The engine encodes ICD-10-CM Official Coding
Guidelines as **hard constraints** — violations raise
`CodingGuidelineViolationError` and are never downgraded to
warnings or made configurable.

The engine is the compliance backbone of the system. Without it,
every AI suggestion is a potential False Claims Act violation.

---

## 1. Data Structures

All data structures are Pydantic v2 models in
`src/core/icd10/models.py`.

### 1.1 ICD10Code

```python
class ICD10Code(BaseModel):
    """A single ICD-10-CM code with metadata from the Tabular List."""

    code: str = Field(
        description="ICD-10-CM code (e.g., 'E11.22'). "
                    "3-7 characters, alphanumeric with optional dot.",
        pattern=r"^[A-Z]\d{2}(\.\w{1,4})?$",
    )
    description: str = Field(
        description="Official short description from CMS code table.",
    )
    chapter: int = Field(
        ge=1, le=22,
        description="ICD-10-CM chapter number (1-22).",
    )
    is_billable: bool = Field(
        description="True if this is a valid billable code "
                    "(full specificity). Non-billable header codes "
                    "cannot appear on claims.",
    )
    valid_7th_chars: list[str] | None = Field(
        default=None,
        description="List of valid 7th character extensions "
                    "(A, D, S, etc.). None if code does not require "
                    "a 7th character.",
    )
    requires_additional: str | None = Field(
        default=None,
        description="If this code has a 'Use Additional Code' "
                    "instruction, the category or code that must follow. "
                    "None if no instruction exists.",
    )
    code_first: str | None = Field(
        default=None,
        description="If this code has a 'Code First' instruction, "
                    "the category or code that must precede it. "
                    "None if no instruction exists.",
    )
    code_also: str | None = Field(
        default=None,
        description="If this code has a 'Code Also' instruction, "
                    "the category or code that should also appear. "
                    "Sequencing is discretionary for Code Also.",
    )
    is_manifestation: bool = Field(
        default=False,
        description="True if this is a manifestation code "
                    "('in diseases classified elsewhere'). "
                    "Manifestation codes can NEVER be principal.",
    )
    cc_status: Literal["non_cc", "cc", "mcc"] = Field(
        description="Complication/Comorbidity status per CMS "
                    "MS-DRG CC/MCC list. Affects DRG weight.",
    )
    poa_exempt: bool = Field(
        default=False,
        description="True if this code is exempt from POA reporting "
                    "(external cause codes, certain perinatal/congenital).",
    )
    laterality: Literal["left", "right", "bilateral", "unspecified", "not_applicable"] = Field(
        default="not_applicable",
        description="Laterality specification for this code.",
    )
    excludes1: list[str] = Field(
        default_factory=list,
        description="List of code categories/codes with Excludes 1 "
                    "relationship. These codes can NEVER coexist.",
    )
    excludes2: list[str] = Field(
        default_factory=list,
        description="List of code categories/codes with Excludes 2 "
                    "relationship. May coexist if both documented.",
    )
```

### 1.2 Excludes1Pair

```python
class Excludes1Pair(BaseModel):
    """Two codes with an Excludes 1 (mutually exclusive) relationship.

    Per ICD-10-CM Section I.A.12.a: 'NOT CODED HERE.' These
    conditions cannot occur together. Suggesting both is ALWAYS
    an error.
    """

    code_a: str = Field(description="First code or category.")
    code_b: str = Field(description="Second code or category.")
    reason: str = Field(
        description="Clinical/coding rationale for mutual exclusion "
                    "(e.g., 'congenital vs acquired form').",
    )
    guideline_ref: str = Field(
        description="Section reference in ICD-10-CM guidelines.",
    )
    hierarchy_level: Literal["chapter", "category", "subcategory", "code"] = Field(
        description="Level at which the Excludes 1 note appears. "
                    "Chapter-level overrides all lower levels.",
    )
```

### 1.3 Excludes2Pair

```python
class Excludes2Pair(BaseModel):
    """Two codes with an Excludes 2 (not included here) relationship.

    Per ICD-10-CM Section I.A.12.b: 'Not included here' but
    may coexist. Both codes CAN be reported together when
    the patient genuinely has both conditions documented.
    """

    code_a: str = Field(description="First code or category.")
    code_b: str = Field(description="Second code or category.")
    condition_for_both: str = Field(
        description="Clinical condition under which both codes "
                    "may be reported together. Requires documentation "
                    "supporting both conditions independently.",
    )
    documentation_required: str = Field(
        description="Specific documentation that must be present "
                    "to justify reporting both codes.",
    )
```

### 1.4 SequencingRule

```python
class SequencingRule(BaseModel):
    """Defines mandatory sequencing between two or more codes.

    Sequencing rules come from 'Code First', 'Use Additional
    Code', and specific guideline sections (e.g., sepsis,
    etiology/manifestation).
    """

    rule_id: str = Field(description="Unique rule identifier (e.g., 'RULE-SEQ-001').")
    primary_code: str = Field(
        description="The code or category that must be sequenced first.",
    )
    must_follow: list[str] = Field(
        description="Code(s) or categories that must follow the "
                    "primary code, in order.",
    )
    guideline_ref: str = Field(
        description="Section reference in ICD-10-CM guidelines.",
    )
    context: str = Field(
        description="Clinical context where this rule applies "
                    "(e.g., 'sepsis POA', 'postprocedural sepsis').",
    )
    is_conditional: bool = Field(
        default=False,
        description="True if sequencing depends on clinical context "
                    "(e.g., sepsis POA vs developed after admission).",
    )
    condition_description: str | None = Field(
        default=None,
        description="When is_conditional is True, describes the "
                    "condition that determines sequencing.",
    )
```

### 1.5 CombinationCode

```python
class CombinationCode(BaseModel):
    """Defines when a combination code must replace separate codes.

    Per Section I.B.9: when a combination code exists, use it
    instead of coding components separately.
    """

    rule_id: str = Field(description="Unique rule identifier (e.g., 'RULE-COMBO-001').")
    separate_codes: list[str] = Field(
        description="The individual codes that should NOT be "
                    "reported separately when the combination exists.",
    )
    combination_code: str = Field(
        description="The combination code that must be used instead.",
    )
    condition: str = Field(
        description="Clinical condition under which the combination "
                    "code is mandatory (e.g., 'DM and CKD coexist "
                    "without explicit denial of causal relationship').",
    )
    assumed_causal: bool = Field(
        default=False,
        description="True if ICD-10-CM assumes a causal relationship "
                    "(e.g., diabetes + CKD, hypertension + heart disease). "
                    "Only the provider explicitly denying the relationship "
                    "overrides the combination.",
    )
    guideline_ref: str = Field(
        description="Section reference in ICD-10-CM guidelines.",
    )
```

### 1.6 POARule

```python
class POAIndicator(str, Enum):
    """Present on Admission indicator values per Appendix I."""

    YES = "Y"           # Condition present at admission
    NO = "N"            # Condition NOT present at admission
    UNKNOWN = "U"       # Documentation insufficient
    UNDETERMINED = "W"  # Provider clinically unable to determine
    EXEMPT = ""         # Exempt from POA reporting (blank)


class POARule(BaseModel):
    """Rules for assigning POA indicators to diagnoses."""

    code: str = Field(description="ICD-10-CM code or category.")
    indicator: POAIndicator = Field(description="Required POA indicator.")
    rationale: str = Field(
        description="Clinical rationale for indicator assignment.",
    )
    is_hac_relevant: bool = Field(
        default=False,
        description="True if this code is in one of the 14 HAC "
                    "categories. Incorrect POA on HAC codes triggers "
                    "CMS payment reductions.",
    )
    hac_category: int | None = Field(
        default=None,
        ge=1, le=14,
        description="HAC category number (1-14) if applicable.",
    )
    timing_rule: str = Field(
        default="",
        description="Timing-specific rule (e.g., 'ER conditions are "
                    "considered POA even if diagnosed after ER arrival "
                    "but before inpatient admission order').",
    )
```

### 1.7 ValidationResult

```python
class Violation(BaseModel):
    """A single validation violation found by the rules engine."""

    rule_id: str = Field(description="The rule that was violated (e.g., 'RULE-EX1-001').")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Severity level per error classification.",
    )
    message: str = Field(
        description="Human-readable explanation of the violation.",
    )
    codes_involved: list[str] = Field(
        description="The specific codes that triggered the violation.",
    )
    guideline_ref: str = Field(
        description="ICD-10-CM guideline section reference.",
    )
    suggested_fix: str = Field(
        description="Recommended corrective action.",
    )
    revenue_impact: str = Field(
        default="",
        description="Estimated revenue/compliance impact if not fixed.",
    )


class ValidationResult(BaseModel):
    """Complete result of validating a code suggestion set."""

    is_valid: bool = Field(
        description="True only if zero CRITICAL or HIGH violations exist.",
    )
    violations: list[Violation] = Field(
        default_factory=list,
        description="All violations found, ordered by severity.",
    )
    warnings: list[Violation] = Field(
        default_factory=list,
        description="MEDIUM and LOW severity items (informational).",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Optimization suggestions (missing combination codes, "
                    "CC/MCC opportunities, etc.).",
    )
    codes_validated: list[str] = Field(
        description="The code set that was validated.",
    )
    encounter_setting: Literal["inpatient", "outpatient"] = Field(
        description="The encounter setting used for validation.",
    )
    drg_impact: DRGImpact | None = Field(
        default=None,
        description="DRG impact calculation if inpatient.",
    )
    validation_duration_ms: float = Field(
        description="Time taken for validation in milliseconds.",
    )


class DRGImpact(BaseModel):
    """DRG impact analysis for a validated code set."""

    current_drg: str = Field(description="MS-DRG assigned with current codes.")
    current_weight: float = Field(description="Relative weight of current DRG.")
    current_revenue_estimate: float = Field(
        description="Estimated revenue at national average base rate.",
    )
    cc_count: int = Field(description="Number of CC codes in the set.")
    mcc_count: int = Field(description="Number of MCC codes in the set.")
    missed_cc_opportunities: list[str] = Field(
        default_factory=list,
        description="Codes that could be added/upgraded to capture CC status.",
    )
    missed_mcc_opportunities: list[str] = Field(
        default_factory=list,
        description="Codes that could be added/upgraded to capture MCC status.",
    )
    potential_drg: str | None = Field(
        default=None,
        description="DRG if missed opportunities are captured.",
    )
    potential_weight: float | None = Field(
        default=None,
        description="Weight if missed opportunities are captured.",
    )
    revenue_difference: float | None = Field(
        default=None,
        description="Revenue difference between current and potential DRG.",
    )
    requires_compliance_review: bool = Field(
        default=False,
        description="True if revenue_difference > $5,000 (per constitution).",
    )
```

### 1.8 CodingSuggestion (Input to Validation)

```python
class CodingSuggestion(BaseModel):
    """A single code suggestion from the coding agent.

    This is the input to the rules engine. Every suggestion
    must have an evidence_quote (constitution Article II.2).
    """

    code: str = Field(description="Suggested ICD-10-CM code.")
    description: str = Field(description="Code description.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Model confidence score.",
    )
    evidence_quote: str = Field(
        description="Verbatim text from the clinical note supporting "
                    "this code. Required — never Optional.",
    )
    is_principal: bool = Field(
        default=False,
        description="True if suggested as principal diagnosis.",
    )
    poa_indicator: POAIndicator | None = Field(
        default=None,
        description="Suggested POA indicator (inpatient only).",
    )
    qualifier_words: list[str] = Field(
        default_factory=list,
        description="Any uncertainty qualifier words found near the "
                    "evidence text (e.g., 'probable', 'suspected').",
    )
    is_from_copied_text: bool = Field(
        default=False,
        description="True if the evidence_quote was flagged as "
                    "copy-forward text by the NLP pipeline.",
    )


class CodingSuggestionSet(BaseModel):
    """Complete set of suggestions for one encounter.

    This is the primary input to the validation pipeline.
    """

    encounter_id: str = Field(description="FHIR encounter ID.")
    encounter_setting: Literal["inpatient", "outpatient"] = Field(
        description="Critical for uncertain diagnosis rules.",
    )
    suggestions: list[CodingSuggestion] = Field(
        min_length=1,
        description="All code suggestions for this encounter.",
    )
    source_note_text: str = Field(
        description="Full text of the source clinical note for "
                    "evidence_quote validation.",
    )
    note_similarity_score: float | None = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Similarity score vs prior notes (copy-forward). "
                    "Flag if > 0.85.",
    )
```

---

## 2. Validation Rules

### A. Sequencing Rules

#### RULE-SEQ-001: Sepsis Sequencing (Sepsis Present on Admission)

- **Rule name:** Sepsis principal diagnosis sequencing (POA)
- **Guideline section:** Section I.C.1.d.1, Section I.C.1.d.2
- **Input:** `CodingSuggestionSet` where encounter is inpatient and suggestion set contains a sepsis code (A40.-, A41.-)
- **Logic:**
  ```
  IF sepsis_code in suggestions AND poa_indicator == "Y":
      ASSERT sepsis_code is sequenced BEFORE localized_infection_code
      IF R65.20 or R65.21 in suggestions:
          ASSERT R65.2x is sequenced AFTER sepsis_code
          ASSERT R65.2x is NOT principal diagnosis
          ASSERT organ_dysfunction_codes follow R65.2x
      IF R65.21 in suggestions AND is_postprocedural:
          RAISE violation: "Use T81.12XA instead of R65.21 for postprocedural septic shock"

  IF sepsis_code in suggestions AND poa_indicator == "N":
      ASSERT localized_infection_code is sequenced BEFORE sepsis_code
      # Sepsis developed after admission: local infection is principal
  ```
- **Output:** `Violation` with severity CRITICAL if sequencing is wrong
- **Test case PASS:** Patient admitted with sepsis (A41.01, POA=Y) and pneumonia (J18.9). A41.01 is principal. Validation passes.
- **Test case FAIL:** Patient admitted with pneumonia (J18.9) that progresses to sepsis (A41.9, POA=N). A41.9 is listed as principal. Violation: "Sepsis not present on admission — localized infection J18.9 must be sequenced first."
- **Revenue/compliance impact:** DRG 870-872 (sepsis) relative weights 1.5-4.5. Incorrect sequencing can swing reimbursement by $5,000-$20,000 per case. Systematic errors trigger OIG audit.

#### RULE-SEQ-002: Diabetes + Complication Sequencing

- **Rule name:** Diabetes combination code sequencing
- **Guideline section:** Section I.C.4.a, Section I.C.4.a.6 (assumed causal relationship)
- **Input:** `CodingSuggestionSet` containing a diabetes code (E08-E13) and a complication code (CKD, neuropathy, retinopathy, etc.)
- **Logic:**
  ```
  IF diabetes_code (E08-E13) in suggestions:
      IF complication_code in suggestions (N18.x, G63, H36, etc.):
          IF diabetes_combination_code_exists(diabetes_type, complication):
              IF separate_codes_used_instead_of_combination:
                  RAISE violation: "Use combination code {combo} instead of
                      separate {dm} + {complication}. ICD-10-CM assumes causal
                      relationship unless provider explicitly denies it."
              ASSERT combination_code sequenced BEFORE stage/detail code
              # E.g., E11.22 before N18.3
          IF diabetes_type_code has "Use Additional Code" note:
              ASSERT additional_code is present
              # E.g., E11.22 must have N18.x for CKD stage
      IF Z79.4 in suggestions AND diabetes_type == E10:
          RAISE violation: "Z79.4 (long-term insulin) must not be assigned
              for Type 1 diabetes — insulin use is inherent."
  ```
- **Output:** `Violation` with severity HIGH if combination code is missed; CRITICAL if Excludes 1 violation (E10 + E11)
- **Test case PASS:** E11.22 (T2DM with diabetic CKD) + N18.3 (CKD stage 3) with E11.22 sequenced first. Validation passes.
- **Test case FAIL:** E11.9 (T2DM without complications) + N18.3 (CKD stage 3) coded separately. Violation: "Use combination code E11.22 (T2DM with diabetic CKD) — assumed causal relationship per Section I.C.4.a.6."
- **Revenue/compliance impact:** Missing E11.22 loses CC designation. $2,000-$5,000 per case in DRG revenue loss (DISC-002 Section B.1.7).

#### RULE-SEQ-003: Code First / Use Additional Code Mandatory Pairs

- **Rule name:** Mandatory paired code detection
- **Guideline section:** Section I.A.13 (Etiology/Manifestation)
- **Input:** `CodingSuggestionSet` containing any code with a "Code First" or "Use Additional Code" instruction
- **Logic:**
  ```
  FOR each suggestion in suggestions:
      code_metadata = lookup_code(suggestion.code)
      IF code_metadata.code_first IS NOT None:
          ASSERT code_metadata.code_first category present in suggestions
          ASSERT code_metadata.code_first is sequenced BEFORE this code
          IF code_metadata.code_first NOT in suggestions:
              RAISE violation: "Code {code} has 'Code First {cf}' instruction.
                  The underlying condition must be sequenced first."
      IF code_metadata.requires_additional IS NOT None:
          IF additional_code NOT in suggestions:
              RAISE warning: "Code {code} has 'Use Additional Code'
                  instruction for {additional}. Consider adding."
  ```
- **Output:** `Violation` with severity CRITICAL for missing Code First pair; HIGH for missing Use Additional Code
- **Test case PASS:** E85.4 (Amyloidosis) sequenced first, H42 (Glaucoma in diseases classified elsewhere) sequenced second. Passes.
- **Test case FAIL:** H42 listed as principal diagnosis without E85.4 preceding it. Violation: "H42 is a manifestation code — cannot be principal. Code First underlying condition."
- **Revenue/compliance impact:** Manifestation code as principal = automatic claim denial. Audit risk for systematic errors.

#### RULE-SEQ-004: Etiology + Manifestation Sequencing

- **Rule name:** Manifestation code never principal
- **Guideline section:** Section I.A.13
- **Input:** `CodingSuggestionSet` where any suggestion has `is_principal=True`
- **Logic:**
  ```
  principal = get_principal(suggestions)
  code_metadata = lookup_code(principal.code)
  IF code_metadata.is_manifestation:
      RAISE violation: "Manifestation code {code} ('{desc}') cannot be
          principal diagnosis. Manifestation codes (identified by 'in
          diseases classified elsewhere' in title) must always follow
          the underlying etiology code."
  ```
- **Output:** `Violation` with severity CRITICAL
- **Test case PASS:** E08.36 (Diabetes due to underlying condition with diabetic cataract) as principal, H28 (Cataract in diseases classified elsewhere) as secondary. Passes.
- **Test case FAIL:** H28 listed as principal. Violation raised.
- **Revenue/compliance impact:** Claim denial. Potentially flags entire claim for manual review.

#### RULE-SEQ-005: Hypertension + CKD Combination

- **Rule name:** Hypertensive CKD combination code requirement
- **Guideline section:** Section I.C.9.a.2, Section I.C.9.a.3
- **Input:** `CodingSuggestionSet` containing hypertension (I10) and CKD (N18.-)
- **Logic:**
  ```
  IF I10 in suggestions AND N18.x in suggestions:
      IF heart_disease_code in suggestions:
          RAISE violation: "Use I13.x (Hypertensive heart and CKD)
              when hypertension, heart disease, and CKD all present.
              Separate I10 + heart_code + N18.x is incorrect."
      ELSE:
          RAISE violation: "Use I12.x (Hypertensive CKD) when
              hypertension and CKD coexist. ICD-10-CM assumes
              causal relationship. I10 + N18.x separately is incorrect."
      # N18.x stage code must still follow the combination code
      ASSERT N18.x is present as additional code after I12/I13

  IF I13.x in suggestions:
      ASSERT N18.x is present (required additional code for CKD stage)
      IF heart_failure_code in suggestions:
          ASSERT heart_failure_code is present (required for I13.0, I13.2)
  ```
- **Output:** `Violation` with severity HIGH
- **Test case PASS:** I13.0 (Hypertensive heart and CKD with HF) + N18.3 + I50.23. Passes.
- **Test case FAIL:** I10 + I50.9 + N18.3 coded separately. Violation: "Use I13.0 — assumed causal relationship."
- **Revenue/compliance impact:** I13.0 captures severity for CC/MCC. Separate coding misses the combination, potentially losing $3,000-$9,000 per case (DISC-002 Section B.1.20).

#### RULE-SEQ-006: Acute vs Chronic Condition Sequencing

- **Rule name:** Acute condition takes sequencing priority
- **Guideline section:** Section II (Principal Diagnosis), Section I.C.9.a (specific to cardiovascular)
- **Input:** `CodingSuggestionSet` containing both acute and chronic forms of same condition
- **Logic:**
  ```
  FOR each acute_code in suggestions where is_acute(code):
      chronic_equivalent = find_chronic_equivalent(acute_code)
      IF chronic_equivalent in suggestions:
          IF acute_code is NOT sequenced before chronic_equivalent:
              RAISE warning: "Acute condition {acute} should generally
                  be sequenced before chronic form {chronic} when both
                  are present, unless the chronic condition is the
                  reason for admission."
          # Exception: "acute on chronic" combination codes
          IF acute_on_chronic_code_exists(acute_code, chronic_equivalent):
              RAISE suggestion: "Consider combination code {combo}
                  for acute on chronic presentation."
  ```
- **Output:** `Violation` with severity MEDIUM (sequencing preference) or HIGH (missed combination code)
- **Test case PASS:** I50.23 (Acute on chronic systolic HF) used instead of separate I50.21 + I50.22. Passes.
- **Test case FAIL:** I50.22 (Chronic systolic HF) and I50.21 (Acute systolic HF) coded separately. Warning: "Use I50.23 (Acute on chronic systolic HF)."
- **Revenue/compliance impact:** I50.23 is MCC. Missing it means DRG 293 ($3,900) instead of DRG 291 ($11,400) = $7,500 per case (DISC-002 Section B.1.1).

---

### B. Setting-Specific Rules

#### RULE-SET-001: Outpatient Uncertain Diagnosis Prohibition

- **Rule name:** Outpatient uncertain diagnosis hard stop
- **Guideline section:** Section IV.H
- **Input:** `CodingSuggestionSet` where `encounter_setting == "outpatient"`
- **Logic:**
  ```
  QUALIFIER_WORDS = [
      "probable", "suspected", "likely", "questionable", "possible",
      "rule out", "still to be ruled out", "working diagnosis",
      "concern for", "appears to be", "consistent with",
      "compatible with", "indicative of", "suggestive of",
      "comparable with"
  ]

  FOR each suggestion in suggestions:
      IF suggestion.qualifier_words intersects QUALIFIER_WORDS:
          RAISE violation: "CRITICAL: Outpatient encounter — cannot code
              uncertain diagnosis '{code}' qualified by '{qualifier}'.
              Per Section IV.H, code the presenting sign/symptom instead.
              Evidence: '{evidence_quote}'"
  ```
- **Output:** `Violation` with severity CRITICAL — this is a hard stop
- **Test case PASS:** Outpatient encounter. Note says "cough and fever." J06.9 (URI) coded only after physician confirms diagnosis. Passes.
- **Test case FAIL:** Outpatient encounter. Note says "suspected pneumonia." J18.9 coded. Violation: "Cannot code suspected pneumonia in outpatient setting. Code R05.9 (Cough) or presenting symptoms instead."
- **Revenue/compliance impact:** Outpatient overcoding of uncertain diagnoses = FCA liability. OIG specifically targets this pattern. Payer audits can trigger recoupment of all claims with the pattern.

#### RULE-SET-002: Inpatient Uncertain Diagnosis Allowance

- **Rule name:** Inpatient uncertain diagnosis coding
- **Guideline section:** Section II.H
- **Input:** `CodingSuggestionSet` where `encounter_setting == "inpatient"`
- **Logic:**
  ```
  # Same QUALIFIER_WORDS as RULE-SET-001
  # EXCEPTION: "ruled out" means DO NOT code in any setting

  FOR each suggestion in suggestions:
      IF "ruled out" in suggestion.qualifier_words:
          RAISE violation: "'Ruled out' condition must NOT be coded
              in any setting. The diagnosis has been eliminated."
      ELIF suggestion.qualifier_words intersects QUALIFIER_WORDS:
          # This is ALLOWED for inpatient per Section II.H
          # But evidence_quote must still be validated
          ASSERT suggestion.evidence_quote is substring of source_note_text
          ADD info: "Uncertain diagnosis '{code}' coded per inpatient
              guideline Section II.H. Qualifier: '{qualifier}'."
  ```
- **Output:** Info note (not a violation) for allowed uncertain coding; CRITICAL violation for "ruled out" conditions
- **Test case PASS:** Inpatient encounter. Note says "probable pneumonia." J18.9 coded with evidence_quote showing "probable pneumonia." Passes per Section II.H.
- **Test case FAIL:** Inpatient encounter. Note says "pneumonia has been ruled out." J18.9 coded. Violation: "'Ruled out' condition must not be coded."
- **Revenue/compliance impact:** Missing inpatient uncertain diagnoses loses legitimate CC/MCC capture — $3,000-$8,000 per case (DISC-001 Section B.1). Coding "ruled out" conditions is overcoding = FCA risk.

#### RULE-SET-003: Signs/Symptoms vs Definitive Diagnosis

- **Rule name:** Symptom code suppression when definitive diagnosis exists
- **Guideline section:** Section II.A
- **Input:** `CodingSuggestionSet` containing both a symptom code (R00-R99) and a definitive diagnosis
- **Logic:**
  ```
  FOR each symptom_code in suggestions where chapter == 18 (R codes):
      FOR each definitive_code in suggestions where chapter != 18:
          IF symptom_is_routinely_associated_with(symptom_code, definitive_code):
              RAISE violation: "Remove symptom code {symptom} — it is
                  routinely associated with definitive diagnosis {definitive}.
                  Per Section II.A, symptom codes are not reported when a
                  related definitive diagnosis is established."
          ELSE:
              # Symptom not routinely associated — both may be coded
              ADD info: "Symptom {symptom} retained alongside {definitive}
                  — not a routine association."
  ```
- **Output:** `Violation` with severity HIGH for redundant symptom codes
- **Test case PASS:** J18.9 (Pneumonia) + R04.2 (Hemoptysis). Hemoptysis is NOT a routine symptom of pneumonia. Both retained. Passes.
- **Test case FAIL:** K35.80 (Acute appendicitis) + R10.9 (Abdominal pain) both coded. Violation: "Remove R10.9 — abdominal pain is routinely associated with appendicitis."
- **Revenue/compliance impact:** Redundant symptom codes can inflate severity inappropriately. Audit risk.

#### RULE-SET-004: Chronic Condition Coding Frequency

- **Rule name:** Chronic condition documentation requirements
- **Guideline section:** Section IV.I (Outpatient), Section III (Inpatient — MEAT criteria)
- **Input:** `CodingSuggestionSet` with chronic condition codes
- **Logic:**
  ```
  FOR each suggestion where is_chronic_condition(suggestion.code):
      IF encounter_setting == "outpatient":
          # Section IV.I: Chronic conditions may be coded at each
          # encounter where treated/managed
          ASSERT evidence_quote shows condition addressed this visit
      IF encounter_setting == "inpatient":
          # Section III + MEAT criteria: condition must require
          # monitoring, evaluation, assessment, or treatment
          IF suggestion.evidence_quote lacks MEAT indicators:
              RAISE warning: "Chronic condition {code} present in note
                  but may not meet MEAT criteria for reporting as
                  additional diagnosis. Verify active management."
      IF suggestion.is_from_copied_text:
          RAISE warning: "Chronic condition {code} appears to be from
              copy-forward text. Verify condition is current and
              actively managed this encounter."
  ```
- **Output:** `Violation` with severity MEDIUM for MEAT concerns; HIGH for copy-forward without verification
- **Test case PASS:** Inpatient with E11.22 (T2DM with CKD). Evidence quote: "Diabetes management: continued metformin, adjusted insulin per sliding scale." MEAT criteria met.
- **Test case FAIL:** Inpatient with E11.22 in problem list. Evidence only from copied past medical history section. No current management documented. Warning raised.
- **Revenue/compliance impact:** Coding chronic conditions without MEAT documentation = HCC audit risk, potential FCA exposure for inflated risk scores (DISC-002 Section A.3).

---

### C. Combination Code Rules

#### RULE-COMBO-001: When Combination Code Is Mandatory

- **Rule name:** Combination code requirement
- **Guideline section:** Section I.B.9
- **Input:** `CodingSuggestionSet` where separate codes exist for a condition that has a combination code
- **Logic:**
  ```
  FOR each pair (code_a, code_b) in suggestions:
      combo = lookup_combination_code(code_a, code_b)
      IF combo exists:
          RAISE violation: "Combination code {combo} must be used
              instead of separate codes {code_a} + {code_b}.
              Per Section I.B.9, combination codes take precedence."
  ```
- **Output:** `Violation` with severity HIGH
- **Test case PASS:** J44.0 (COPD with acute lower respiratory infection) used instead of J44.9 + J18.9. Passes.
- **Test case FAIL:** J44.9 (COPD) + J18.9 (Pneumonia) coded separately. Violation: "Use J44.0 (COPD with acute lower respiratory infection)."
- **Revenue/compliance impact:** Missed combination codes may lose CC/MCC status. Varies by combination, typically $2,000-$8,000 per case.

#### RULE-COMBO-002: E11.xx Diabetes Combination Code Logic

- **Rule name:** Type 2 diabetes combination code enforcement
- **Guideline section:** Section I.C.4.a, Section I.C.4.a.6
- **Input:** `CodingSuggestionSet` containing E11.9 (T2DM without complications) alongside a diabetic complication
- **Logic:**
  ```
  ASSUMED_CAUSAL = {
      "N18.*": "E11.22",   # CKD → DM with diabetic CKD
      "G63":  "E11.42",    # Polyneuropathy → DM with diabetic neuropathy
      "H36":  "E11.3*",    # Retinal disorder → DM with diabetic retinopathy
      "L97.*": "E11.622",  # Foot ulcer → DM with other skin complication
  }

  IF E11.9 in suggestions:
      FOR each suggestion in suggestions:
          FOR pattern, combo in ASSUMED_CAUSAL:
              IF suggestion.code matches pattern:
                  RAISE violation: "Replace E11.9 + {code} with
                      combination code {combo}. ICD-10-CM assumes
                      causal relationship between T2DM and {condition}
                      per Section I.C.4.a.6. Only override if provider
                      explicitly documents DM did NOT cause {condition}."

  # Also check Z79.4 for T2DM on insulin
  IF E11.* in suggestions AND insulin_documented AND Z79.4 NOT in suggestions:
      IF insulin_is_long_term (not temporary for acute illness):
          RAISE suggestion: "Add Z79.4 (Long-term insulin use) for
              T2DM patient on insulin."
  ```
- **Output:** `Violation` with severity HIGH for missed combination; suggestion for Z79.4
- **Test case PASS:** E11.22 + N18.3 (T2DM with diabetic CKD, stage 3). Passes.
- **Test case FAIL:** E11.9 + N18.3 (T2DM without complications + CKD stage 3). Violation: "Use E11.22 — assumed causal relationship."
- **Revenue/compliance impact:** E11.22 is CC; E11.9 is Non-CC. Missing = $1,500-$4,000 per case (DISC-002 Section B.1.7).

#### RULE-COMBO-003: J44.x COPD Combination Code Logic

- **Rule name:** COPD combination code enforcement
- **Guideline section:** Section I.B.9, COPD-specific guidance
- **Input:** `CodingSuggestionSet` containing COPD codes
- **Logic:**
  ```
  IF J44.9 in suggestions:
      IF acute_lower_respiratory_infection in suggestions:
          RAISE violation: "Use J44.0 (COPD with acute lower
              respiratory infection) instead of J44.9 + infection code.
              J44.0 also requires 'Use Additional Code' for the
              specific infection."
      IF exacerbation_documented:
          RAISE violation: "Use J44.1 (COPD with acute exacerbation)
              instead of J44.9 when exacerbation is documented."

  IF J44.0 in suggestions AND exacerbation_documented:
      IF J44.1 NOT in suggestions:
          RAISE suggestion: "Documentation shows both infection and
              exacerbation. Both J44.0 AND J44.1 may be assigned
              together per coding guidance."

  IF J44.0 in suggestions:
      IF specific_infection_code NOT in suggestions:
          RAISE violation: "J44.0 has 'Use Additional Code' instruction.
              Add the specific infection code (e.g., J15.9, J20.9)."
  ```
- **Output:** `Violation` with severity HIGH
- **Test case PASS:** J44.0 + J44.1 + J15.9 (COPD with infection and exacerbation, bacterial pneumonia). Passes.
- **Test case FAIL:** J44.9 + J18.9 coded when patient has COPD with pneumonia. Violation: "Use J44.0."
- **Revenue/compliance impact:** J44.1 (exacerbation) can shift to MCC when principal. $2,000-$5,000 per case (DISC-002 Section B.1.8).

#### RULE-COMBO-004: I50.xx Heart Failure Specificity Chain

- **Rule name:** Heart failure specificity validation
- **Guideline section:** Section I.B.9, CC/MCC implications
- **Input:** `CodingSuggestionSet` containing heart failure codes
- **Logic:**
  ```
  IF I50.9 in suggestions:  # Unspecified HF
      RAISE suggestion: "I50.9 (HF unspecified) is Non-CC. Consider
          querying for type (systolic/diastolic) and acuity
          (acute/chronic/acute on chronic). Specific HF codes are
          MCC — potential $7,500 per case revenue impact."

  # Validate specificity chain exists
  HF_SPECIFICITY = {
      "I50.1":  "Non-CC (Left ventricular failure, unspecified)",
      "I50.20": "MCC (Unspecified systolic HF)",
      "I50.21": "MCC (Acute systolic HF)",
      "I50.22": "CC (Chronic systolic HF)",
      "I50.23": "MCC (Acute on chronic systolic HF)",
      "I50.30": "MCC (Unspecified diastolic HF)",
      "I50.31": "MCC (Acute diastolic HF)",
      "I50.32": "CC (Chronic diastolic HF)",
      "I50.33": "MCC (Acute on chronic diastolic HF)",
      "I50.40": "MCC (Unspecified combined HF)",
      "I50.41": "MCC (Acute combined HF)",
      "I50.42": "CC (Chronic combined HF)",
      "I50.43": "MCC (Acute on chronic combined HF)",
      "I50.9":  "Non-CC (HF unspecified)",
  }

  # Check hypertension linkage
  IF I50.* in suggestions AND I10 in suggestions:
      RAISE violation: "Hypertension and HF coexist — use I11.0
          (Hypertensive heart disease with HF) per assumed causal
          relationship (Section I.C.9.a.1). Add I50.x as additional."
  ```
- **Output:** Suggestion for specificity; `Violation` with severity HIGH for missed hypertension linkage
- **Test case PASS:** I11.0 + I50.23 (Hypertensive heart disease with acute on chronic systolic HF). Passes.
- **Test case FAIL:** I10 + I50.9 (Essential HTN + unspecified HF). Violations: (1) use I11.0, (2) I50.9 lacks specificity.
- **Revenue/compliance impact:** I50.9 Non-CC → I50.23 MCC = DRG 293 ($3,900) vs DRG 291 ($11,400). $7,500 per case (DISC-002 Section B.1.1).

---

### D. Excludes Rules

#### RULE-EX1-001: Excludes 1 Absolute Prohibition

- **Rule name:** Excludes 1 mutual exclusion enforcement
- **Guideline section:** Section I.A.12.a
- **Input:** `CodingSuggestionSet`
- **Logic:**
  ```
  # Build a set of all code categories present
  FOR each pair (suggestion_a, suggestion_b) in suggestions:
      IF has_excludes1_relationship(suggestion_a.code, suggestion_b.code):
          # Check at ALL hierarchy levels:
          # 1. Code level
          # 2. Subcategory level
          # 3. Category level (3-char)
          # 4. Chapter level
          excludes1 = find_excludes1_at_any_level(
              suggestion_a.code, suggestion_b.code
          )
          IF excludes1 is not None:
              RAISE violation: "CRITICAL: Excludes 1 violation.
                  {code_a} and {code_b} are mutually exclusive per
                  {excludes1.guideline_ref}. Reason: {excludes1.reason}.
                  Remove one code. The Excludes 1 note appears at
                  the {excludes1.hierarchy_level} level."
  ```
- **Output:** `Violation` with severity CRITICAL — always
- **Test case PASS:** E11.22 (T2DM with diabetic CKD) without E10.x. Passes.
- **Test case FAIL:** E10.9 (T1DM) + E11.9 (T2DM) both suggested. Violation: "Excludes 1 — Type 1 and Type 2 diabetes are mutually exclusive."
- **Revenue/compliance impact:** Automatic claim denial by most payers. Excludes 1 violations are caught by payer automated edits. Systematic violations trigger fraud investigation.

#### RULE-EX2-001: Excludes 2 Conditional Allowance

- **Rule name:** Excludes 2 documentation verification
- **Guideline section:** Section I.A.12.b
- **Input:** `CodingSuggestionSet` containing codes with Excludes 2 relationship
- **Logic:**
  ```
  FOR each pair (suggestion_a, suggestion_b) in suggestions:
      IF has_excludes2_relationship(suggestion_a.code, suggestion_b.code):
          # Both codes CAN be reported IF both conditions are
          # independently documented
          ASSERT suggestion_a.evidence_quote supports condition_a
          ASSERT suggestion_b.evidence_quote supports condition_b
          ASSERT suggestion_a.evidence_quote != suggestion_b.evidence_quote
              # Same quote supporting both = likely single condition
          IF evidence is insufficient:
              RAISE warning: "Excludes 2 pair {code_a} + {code_b}:
                  both may be reported but require independent
                  documentation for each condition. Verify both
                  are genuinely present."
  ```
- **Output:** Warning with severity MEDIUM if documentation is thin
- **Test case PASS:** Patient has both obesity (E66.01) and sleep apnea (G47.33) documented independently. Excludes 2 relationship. Both retained with separate evidence quotes.
- **Test case FAIL:** Same evidence quote supports both codes. Warning raised for documentation review.
- **Revenue/compliance impact:** Overcoding two conditions from a single documentation element = audit risk.

#### RULE-EX1-TOP10: The 10 Most Clinically Common Excludes 1 Pairs

- **Rule name:** Top 10 Excludes 1 pair detection
- **Guideline section:** Section I.A.12.a (specific pairs from DISC-001 Section E.3)
- **Input:** `CodingSuggestionSet`
- **Logic:**
  ```
  TOP_10_EXCLUDES1 = [
      Excludes1Pair(code_a="E10", code_b="E11",
          reason="Type 1 and Type 2 diabetes are mutually exclusive",
          guideline_ref="E10/E11 Excludes 1 note",
          hierarchy_level="category"),
      Excludes1Pair(code_a="J44.9", code_b="J45.909",
          reason="Unspecified COPD excludes unspecified asthma. "
                 "Specific asthma codes (e.g., J45.901) MAY coexist.",
          guideline_ref="J44 Excludes 1 note",
          hierarchy_level="category"),
      Excludes1Pair(code_a="E03.0", code_b="E03.9",
          reason="Congenital vs acquired hypothyroidism",
          guideline_ref="E03 Excludes 1 note",
          hierarchy_level="subcategory"),
      Excludes1Pair(code_a="E66.0*", code_b="E66.3",
          reason="Obesity and overweight are mutually exclusive",
          guideline_ref="E66 Excludes 1 note",
          hierarchy_level="category"),
      Excludes1Pair(code_a="E78.5", code_b="E78.0",
          reason="Unspecified hyperlipidemia excludes specific types",
          guideline_ref="E78 Excludes 1 note",
          hierarchy_level="category"),
      Excludes1Pair(code_a="N17.*", code_b="N18.5",
          reason="Certain acute and chronic kidney codes exclude. "
                 "Check Tabular List for specific pair.",
          guideline_ref="N17/N18 Excludes 1 note",
          hierarchy_level="code"),
      Excludes1Pair(code_a="F32.A", code_b="F32.0-F32.5",
          reason="Unspecified and specific depression codes are exclusive",
          guideline_ref="F32 Excludes 1 note",
          hierarchy_level="subcategory"),
      Excludes1Pair(code_a="D63.1", code_b="D50.*",
          reason="Anemia of chronic disease excludes certain iron "
                 "deficiency anemia codes",
          guideline_ref="D63.1 Excludes 1 note",
          hierarchy_level="code"),
      Excludes1Pair(code_a="Z86.*", code_b="active_equivalent",
          reason="History of condition excludes active condition. "
                 "Code active condition only if currently present.",
          guideline_ref="Z86/Z87 Excludes 1 notes",
          hierarchy_level="category"),
      Excludes1Pair(code_a="E83.52", code_b="E21.*",
          reason="Hypercalcemia excludes hyperparathyroidism — "
                 "hypercalcemia is encompassed by E21.x.",
          guideline_ref="E83.52 Excludes 1 note",
          hierarchy_level="code"),
  ]

  # These pairs are checked FIRST due to high clinical frequency.
  # The full Excludes 1 table (RULE-EX1-001) is checked afterward.
  FOR each pair in TOP_10_EXCLUDES1:
      IF both codes present in suggestions:
          RAISE violation with pair-specific reason and guidance
  ```
- **Output:** `Violation` with severity CRITICAL for each match
- **Test case PASS:** E11.22 + N18.3 (no Excludes 1). Passes.
- **Test case FAIL:** E10.65 + E11.9 (T1DM + T2DM). Violation with specific guidance: "Query provider to clarify diabetes type."
- **Revenue/compliance impact:** These 10 pairs are the most common automated denial triggers. Catching them prevents claim rejection before submission.

---

### E. POA Indicator Rules

#### RULE-POA-001: When Y (Present on Admission) Is Correct

- **Rule name:** POA Y indicator assignment
- **Guideline section:** Appendix I
- **Input:** `CodingSuggestion` with `poa_indicator` in inpatient encounter
- **Logic:**
  ```
  POA = "Y" WHEN:
      1. Condition was present at the time of inpatient admission order
      2. Condition developed during an outpatient encounter
         (including ER, observation, outpatient surgery) BEFORE
         the inpatient admission order was written
      3. Condition is a chronic condition that predates admission

  CRITICAL EDGE CASE:
      Patient in ER develops cardiac arrest BEFORE inpatient
      admission order → POA = "Y" (ER is pre-admission)

  IF suggestion.poa_indicator == "N":
      IF evidence suggests condition existed before admission order:
          RAISE violation: "POA should be 'Y' — condition appears
              to have been present before inpatient admission order.
              Conditions developing in ER/observation prior to
              admission order are considered POA."
  ```
- **Output:** `Violation` with severity HIGH if POA=Y should have been assigned
- **Test case PASS:** Pressure ulcer documented in ER assessment note (before admission order). POA=Y. Passes.
- **Test case FAIL:** Patient developed AKI in ER (documented before admission order). POA=N assigned. Violation: "Condition present before admission order is POA=Y."
- **Revenue/compliance impact:** Incorrect POA=N on HAC-associated codes triggers CMS payment reduction. 1% total Medicare payment reduction for bottom-quartile hospitals.

#### RULE-POA-002: When N (Not Present on Admission) Is Correct

- **Rule name:** POA N indicator assignment
- **Guideline section:** Appendix I
- **Input:** `CodingSuggestion` with `poa_indicator` in inpatient encounter
- **Logic:**
  ```
  POA = "N" WHEN:
      Condition developed AFTER the inpatient admission order
      AND condition was not present or incubating at admission

  IF suggestion.poa_indicator == "Y":
      IF code is HAC-relevant:
          IF onset documented AFTER admission date:
              RAISE warning: "Verify POA=Y for HAC-relevant code
                  {code}. Onset appears to be after admission.
                  If POA=N is correct, this triggers HAC review."
  ```
- **Output:** Warning for HAC-relevant code verification
- **Test case PASS:** Catheter-associated UTI (T83.51xA) diagnosed on hospital day 5, catheter placed day 1. POA=N. Passes.
- **Test case FAIL:** Catheter-associated UTI marked POA=Y when urine culture was negative on admission and positive day 4. Warning raised.
- **Revenue/compliance impact:** Marking hospital-acquired conditions as POA=Y avoids HAC penalty but constitutes fraudulent reporting.

#### RULE-POA-003: When W (Clinically Undetermined) Is Appropriate

- **Rule name:** POA W vs U distinction
- **Guideline section:** Appendix I
- **Input:** `CodingSuggestion` with POA indicator
- **Logic:**
  ```
  # W = Provider evaluated and CANNOT clinically determine POA
  # U = Documentation is insufficient (a documentation problem)
  # These are NOT interchangeable

  IF suggestion.poa_indicator == "U":
      IF evidence_quote contains provider statement about inability
          to determine POA (e.g., "unable to determine if present
          on admission"):
          RAISE violation: "POA should be 'W' (clinically undetermined),
              not 'U' (unknown). The provider made a clinical
              determination of uncertainty. 'U' is reserved for
              cases where documentation is simply lacking."

  IF suggestion.poa_indicator == "W":
      IF no provider statement about POA determination exists:
          RAISE warning: "POA 'W' requires that the provider
              evaluated and could not clinically determine POA status.
              If documentation is simply lacking, use 'U'."
  ```
- **Output:** `Violation` with severity HIGH for U/W confusion
- **Test case PASS:** Provider documents "unable to clinically determine if DVT was present on admission." POA=W assigned. Passes.
- **Test case FAIL:** Provider documents "unable to determine POA." POA=U assigned. Violation: "Use W — provider made a clinical determination."
- **Revenue/compliance impact:** "U" may be treated as "N" by some payers, triggering inappropriate HAC penalties.

#### RULE-POA-004: Exempt Conditions List

- **Rule name:** POA exempt code handling
- **Guideline section:** Appendix I
- **Input:** `CodingSuggestion` where code is POA-exempt
- **Logic:**
  ```
  POA_EXEMPT_CATEGORIES = [
      "V*", "W*", "X*", "Y*",    # External cause codes
      # Plus specific perinatal, congenital, and Z codes
      # per CMS POA exempt list
  ]

  IF code matches POA_EXEMPT_CATEGORIES:
      IF suggestion.poa_indicator IS NOT None:
          RAISE violation: "Code {code} is POA-exempt. POA field
              must be blank (empty), not '{indicator}'. Do NOT
              assign Y, N, U, or W to exempt codes."
  ELSE:
      IF suggestion.poa_indicator IS None AND encounter_setting == "inpatient":
          RAISE violation: "Inpatient code {code} requires a POA
              indicator (Y, N, U, or W). Field cannot be blank
              for non-exempt codes."
  ```
- **Output:** `Violation` with severity HIGH
- **Test case PASS:** External cause code W01.0xxA (Fall on same level from slipping). POA field blank. Passes.
- **Test case FAIL:** W01.0xxA assigned POA=Y. Violation: "External cause codes are POA-exempt — leave blank."
- **Revenue/compliance impact:** Assigning POA to exempt codes generates claim edits and rejections.

#### RULE-POA-005: HAC Implications of Incorrect POA

- **Rule name:** HAC code POA validation
- **Guideline section:** Appendix I, DRA 2005, CMS HAC program
- **Input:** `CodingSuggestionSet` containing HAC-relevant codes
- **Logic:**
  ```
  HAC_CODES = {
      1:  ["T81.50*-T81.59*"],        # Foreign object retained
      2:  ["T80.0*"],                  # Air embolism
      3:  ["T80.30*-T80.39*"],         # Blood incompatibility
      4:  ["L89.*03", "L89.*04"],      # Pressure ulcer stage 3-4
      5:  ["S00-T14"],                 # Falls and trauma (various)
      6:  ["T83.51*"],                 # Catheter-associated UTI
      7:  ["T80.211*-T80.219*"],       # Vascular catheter infection
      8:  ["J98.51", "T81.41*"],       # SSI mediastinitis post-CABG
      9:  ["E08.00-E13.01"],           # Poor glycemic control
      10: ["I26.*", "I82.4*"],         # DVT/PE post knee/hip
      11: ["T81.41*", "K68.11"],       # SSI post bariatric
      12: ["T81.41*", "T84.6*"],       # SSI post ortho
      13: ["T81.41*", "T82.6*", "T82.7*"], # SSI post CIED
      14: ["J95.811"],                 # Iatrogenic pneumothorax
  }

  FOR each suggestion in suggestions:
      IF suggestion.code matches any HAC_CODES:
          IF suggestion.poa_indicator == "N":
              RAISE warning: "HAC-relevant code {code} (Category {hac})
                  with POA=N. This will trigger HAC review and may
                  result in payment reduction. Verify POA indicator
                  is clinically accurate."
          IF suggestion.poa_indicator IS None OR suggestion.poa_indicator == "":
              RAISE violation: "HAC-relevant code {code} MUST have
                  an explicit POA indicator. Cannot be blank."
  ```
- **Output:** Warning with severity HIGH for HAC N; CRITICAL for missing POA on HAC codes
- **Test case PASS:** L89.153 (Pressure ulcer sacrum, stage 3) with POA=Y (documented in admission skin assessment). Passes.
- **Test case FAIL:** L89.153 with no POA indicator. Violation: "HAC code requires explicit POA."
- **Revenue/compliance impact:** HAC penalties: 1% reduction in total Medicare payments for bottom-quartile hospitals. Individual case payment adjustments for HAC diagnoses with POA=N.

---

## 3. Validation Pipeline

The validation pipeline runs on every `CodingSuggestionSet`
before results reach the coder review interface. Steps are
sequential — later steps depend on earlier ones.

```
┌────────────────────────────────────────────────────────┐
│ Input: CodingSuggestionSet                             │
│ (encounter_id, setting, suggestions[], source_note)    │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 1: Individual Code Validity ─────────────────┐
│ For each suggestion:                                   │
│   - Verify code exists in current ICD-10-CM table      │
│   - Verify code is billable (not a header code)        │
│   - Verify 7th character is valid (if required)        │
│   - Verify laterality matches documentation            │
│   - Verify evidence_quote is substring of source note  │
│   - Check confidence threshold (< 0.65 → senior queue) │
│   - Check if from copy-forward text (flag if so)       │
│ CRITICAL violations: invalid code, missing evidence    │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 2: Excludes 1 Pair Screening ────────────────┐
│ Check RULE-EX1-TOP10 first (fast path for common       │
│ violations), then full Excludes 1 table.               │
│ Check at ALL hierarchy levels:                         │
│   chapter → category → subcategory → code              │
│ CRITICAL violations: any Excludes 1 pair present       │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 3: Excludes 2 Pair Check ────────────────────┐
│ For Excludes 2 pairs found:                            │
│   - Verify independent documentation for each          │
│   - Verify evidence_quotes are distinct                │
│ MEDIUM warnings: weak documentation for both           │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 4: Sequencing Rule Validation ───────────────┐
│ Apply in order:                                        │
│   4a. Manifestation codes not principal (RULE-SEQ-004) │
│   4b. Code First / Use Additional (RULE-SEQ-003)       │
│   4c. Sepsis sequencing (RULE-SEQ-001)                 │
│   4d. Diabetes combinations (RULE-SEQ-002)             │
│   4e. Hypertension combos (RULE-SEQ-005)               │
│   4f. Acute vs chronic (RULE-SEQ-006)                  │
│   4g. Setting-specific rules (RULE-SET-001 to 004)     │
│   4h. Signs/symptoms suppression (RULE-SET-003)        │
│ CRITICAL violations: outpatient uncertain dx,          │
│   manifestation as principal                           │
│ HIGH violations: missed combinations, wrong sequencing │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 5: POA Indicator Validation ─────────────────┐
│ (Inpatient only — skip for outpatient)                 │
│   5a. Non-exempt codes must have POA indicator         │
│   5b. Exempt codes must have blank POA                 │
│   5c. U vs W distinction check                         │
│   5d. HAC code POA verification                        │
│   5e. ER timing rule (pre-admission = POA=Y)           │
│ HIGH violations: missing POA, U/W confusion            │
│ Warnings: HAC code with POA=N                          │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 6: Combination Code Opportunity Detection ───┐
│ Scan for separate codes that should be combinations:   │
│   6a. Diabetes + complication (RULE-COMBO-002)         │
│   6b. COPD + infection/exacerbation (RULE-COMBO-003)   │
│   6c. HF specificity chain (RULE-COMBO-004)            │
│   6d. HTN + heart disease + CKD (RULE-SEQ-005)         │
│   6e. General combination lookup (RULE-COMBO-001)      │
│ HIGH violations: missed mandatory combinations         │
│ Suggestions: specificity upgrades (Non-CC → CC/MCC)    │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 7: Missing Mandatory Paired Code Detection ──┐
│ For each code with "Code First" or "Use Additional":   │
│   - Verify the required paired code is present         │
│   - Verify correct sequencing of the pair              │
│ For BMI codes (Z68.x):                                 │
│   - Verify accompanying obesity/overweight diagnosis   │
│ CRITICAL: missing Code First pair                      │
│ HIGH: missing Use Additional pair                      │
│ CRITICAL: standalone BMI code                          │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 8: DRG Impact Calculation ───────────────────┐
│ (Inpatient only — skip for outpatient)                 │
│   8a. Group current code set to MS-DRG                 │
│   8b. Calculate relative weight and revenue estimate   │
│   8c. Identify missed CC/MCC opportunities             │
│   8d. Calculate potential DRG with missed opps          │
│   8e. If revenue_difference > $5,000:                  │
│       set requires_compliance_review = True            │
│ Output: DRGImpact model                                │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── STEP 9: Copy-Forward Risk Assessment ─────────────┐
│ If note_similarity_score > 0.85:                       │
│   - Flag entire suggestion set for human review        │
│   - Mark any suggestions sourced from copied text      │
│ MEDIUM warning: high similarity score                  │
│ HIGH warning: suggestions from copied text only        │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌──── OUTPUT: ValidationResult ─────────────────────────┐
│ is_valid = (zero CRITICAL or HIGH violations)          │
│ violations = [all CRITICAL + HIGH items]               │
│ warnings = [all MEDIUM + LOW items]                    │
│ suggestions = [optimization opportunities]             │
│ drg_impact = DRGImpact (inpatient only)               │
│ validation_duration_ms = elapsed time                  │
│                                                        │
│ If NOT is_valid:                                       │
│   raise CodingGuidelineViolationError(result)          │
│   → Hard stop. Suggestions do NOT reach coder UI.      │
│   → Agent must fix violations and resubmit.            │
│                                                        │
│ If is_valid with warnings:                             │
│   Pass to coder UI with warnings displayed.            │
│   Coder sees suggestions + warnings + DRG impact.      │
└────────────────────────────────────────────────────────┘
```

**Critical behavior:** When `is_valid == False`, the rules engine
raises `CodingGuidelineViolationError`. This is a hard stop, not
a warning. The coding agent must resolve all CRITICAL and HIGH
violations before the suggestion set can reach the coder interface.

This is per constitution Article II.3: ICD-10 guidelines are
hard constraints, not configurable options.

---

## 4. Error Classification

### Severity Levels

| Severity | Definition | Action | Examples |
|----------|-----------|--------|----------|
| **CRITICAL** | Will cause claim denial, FCA liability, or patient safety risk | Hard stop. `CodingGuidelineViolationError` raised. Must fix before coder sees suggestions. | Excludes 1 violation; outpatient uncertain diagnosis coded as confirmed; manifestation code as principal; invalid/non-billable code; standalone BMI code; missing evidence_quote |
| **HIGH** | Will cause DRG downgrade, audit risk, or compliance concern | Hard stop (grouped with CRITICAL for `is_valid` calculation). Must fix. | Sequencing error; missed mandatory combination code; missing Code First pair; missing POA on non-exempt code; HAC code POA issues |
| **MEDIUM** | Coding guideline deviation or documentation concern | Warning displayed to coder. Does not block. | Missing Use Additional code; Excludes 2 with thin documentation; copy-forward flagged text; MEAT criteria concern |
| **LOW** | Best practice suggestion, optimization opportunity | Suggestion displayed to coder. Informational only. | Specificity upgrade opportunity (Non-CC → CC/MCC); missing Z79.4 for insulin; CDI query recommendation |

### Escalation Rules

```
CRITICAL or HIGH violation count > 0:
    → is_valid = False
    → CodingGuidelineViolationError raised
    → Coding agent must remediate and resubmit

MEDIUM warnings present:
    → is_valid = True (with warnings)
    → Suggestions reach coder UI with warnings displayed
    → Coder makes final decision

LOW suggestions present:
    → is_valid = True
    → Displayed as "Optimization Opportunities" in coder UI
    → CDI team may follow up on high-value suggestions

DRG improvement > $5,000:
    → requires_compliance_review = True
    → Routed to compliance team before coder action
    → Per constitution Article II.6 (conservative defaults)

Confidence < 0.65 on any suggestion:
    → Route entire set to senior coder queue
    → Per CLAUDE.md clinical content rules
```

---

## 5. Edge Cases

### Edge Case 1: Sepsis Timing Ambiguity

- **Description:** Patient presents to ER with UTI. During ER stay (before inpatient admission order), urine cultures return positive and patient develops hypotension meeting SIRS criteria. Inpatient admission ordered. Is sepsis POA or not? Is UTI or sepsis the principal diagnosis?
- **Why it's hard for NLP:** The temporal boundary between "ER visit" and "inpatient admission" is defined by the admission order timestamp, not by physical location. NLP must parse order timestamps, not just note sections.
- **Our handling:** ER-to-inpatient transition rule: any condition present before the inpatient admission order is POA=Y. Sepsis that develops in the ER is POA. UTI (localized infection) present first → sepsis developed from it → but both before admission order → sepsis POA=Y → sepsis code is principal (RULE-SEQ-001 POA path).
- **Test data:** ER note timestamped 14:00. Blood cultures ordered 15:30. Admission order 17:00. Sepsis criteria met 16:00. Expected: sepsis POA=Y, A41.9 principal + N39.0 secondary.

### Edge Case 2: Copy-Forward Diabetes Documentation

- **Description:** Note contains "Type 2 DM with CKD stage 3" in the problem list (copy-forward from 6 months ago). Current labs show creatinine normalized. No diabetes management documented in assessment/plan. Note similarity to prior note is 91%.
- **Why it's hard for NLP:** The text explicitly states the diagnosis, but it's stale copy-forward text that may not reflect current clinical status. The AI must distinguish between "documented" and "currently active."
- **Our handling:** RULE-SET-004 flags copy-forward chronic conditions. Note similarity > 85% triggers full review. Evidence_quote from copied section gets `is_from_copied_text = True`. Warning raised: verify condition is current and actively managed.
- **Test data:** Note with 91% similarity to prior. Problem list has E11.22 + N18.3. Assessment/plan section has no mention of diabetes or CKD management. Labs show normal creatinine. Expected: HIGH warning on both codes.

### Edge Case 3: Acute-on-Chronic Heart Failure with Hypertension and CKD

- **Description:** Patient has hypertension, acute-on-chronic systolic heart failure, and CKD stage 3. Three assumed causal relationships must be captured simultaneously.
- **Why it's hard for NLP:** Multiple overlapping combination code rules. The system must produce I13.0 (Hypertensive heart and CKD with HF) + I50.23 (Acute on chronic systolic HF) + N18.3 (CKD stage 3) — not I10 + I50.23 + N18.3 separately.
- **Our handling:** RULE-SEQ-005 detects I10 + I50.x + N18.x and enforces I13.x. RULE-COMBO-004 ensures HF specificity. Pipeline step 6 catches both and produces unified violation set.
- **Test data:** Note documents "HTN, acute on chronic systolic heart failure, CKD stage 3." Expected codes: I13.0 + I50.23 + N18.3. Common error: I10 + I50.23 + N18.3 (misses I13.0) or I11.0 + I50.23 + N18.3 (misses CKD linkage).

### Edge Case 4: "Urosepsis" — The Query Trap

- **Description:** Physician documents "urosepsis" without clarifying whether the patient has a UTI only or true sepsis with urinary source.
- **Why it's hard for NLP:** "Urosepsis" is a natural language term with no direct ICD-10 mapping. AI systems tend to auto-code it as A41.9 + N39.0, which may be overcoding.
- **Our handling:** When NLP detects the term "urosepsis" without supporting sepsis criteria documentation (e.g., SIRS criteria, lactate, organ dysfunction), the system generates a CDI query instead of a code suggestion. Per constitution Article II.6: when uncertain, query rather than code.
- **Test data:** Note says "urosepsis" with no lactate, no SIRS criteria documented, no organ dysfunction. Expected: CDI query generated, NOT A41.9 coded. If SIRS criteria documented alongside "urosepsis": suggest A41.9 + N39.0 with evidence.

### Edge Case 5: Two Diagnoses Equally Meeting Principal Criteria

- **Description:** Patient admitted for workup of both chest pain and dyspnea. After study, diagnosed with both acute MI (I21.01) and acute respiratory failure (J96.01). Both conditions equally prompted admission. No coding guideline provides sequencing direction.
- **Why it's hard for NLP:** AI tends to always pick the higher-reimbursing code as principal (I21.01 → DRG 280 is higher than J96.01 → DRG 189). This is upcoding risk.
- **Our handling:** RULE-SEQ-006 detects this pattern and flags for human review with equal-weight notice. Per Section II.C, either may be sequenced first. Per constitution Article II.6 (conservative defaults), the system flags for human decision rather than selecting the higher-reimbursing option.
- **Test data:** Both I21.01 and J96.01 with equal clinical evidence for admission reason. Expected: flag for human coder decision with DRG impact comparison for both options.

### Edge Case 6: Postprocedural Septic Shock (R65.21 vs T81.12XA)

- **Description:** Patient develops septic shock after a surgical procedure. AI uses R65.21 (Severe sepsis with septic shock) instead of T81.12XA (Postprocedural septic shock).
- **Why it's hard for NLP:** The general sepsis rules say to use R65.21 for septic shock. But postprocedural septic shock has a specific override. The AI must recognize the postprocedural context.
- **Our handling:** RULE-SEQ-001 checks for postprocedural context when R65.21 is present. If postprocedural indicators exist (T81.44XA in the suggestion set, or "postoperative" / "post-procedure" in evidence text), R65.21 is rejected and T81.12XA is required.
- **Test data:** Suggestion set contains A41.9 + R65.21 + T81.44XA. Expected violation: "Use T81.12XA instead of R65.21 for postprocedural septic shock."

### Edge Case 7: Obstetrical Sepsis (O85 with A41.x Error)

- **Description:** Patient with puerperal sepsis (O85). AI assigns A41.9 alongside O85 to indicate the organism.
- **Why it's hard for NLP:** The general sepsis coding pattern uses A40/A41 for the organism. But obstetrical sepsis explicitly prohibits A40/A41 — B95-B96 organism codes must be used instead.
- **Our handling:** RULE-SEQ-001 has obstetrical sepsis sub-rule. When O85 is in the suggestion set, any A40/A41 code is a CRITICAL violation. The system suggests B95-B96 alternatives.
- **Test data:** O85 + A41.9 in suggestions. Expected violation: "Do not use A41.9 with O85. Use B95-B96 organism codes for puerperal sepsis."

### Edge Case 8: COPD + Unspecified Asthma (Excludes 1 Nuance)

- **Description:** Patient has both COPD and asthma. AI assigns J44.9 + J45.909 (unspecified asthma). This is an Excludes 1 violation. But J44.9 + J45.901 (asthma with acute exacerbation) IS allowed.
- **Why it's hard for NLP:** The Excludes 1 applies only to the *unspecified* asthma code, not to all asthma codes. This requires code-level Excludes checking, not just category-level.
- **Our handling:** RULE-EX1-TOP10 (pair 2) specifically checks J44.9 vs J45.909. If asthma is specified (J45.901, J45.20, etc.), the Excludes 1 does not apply. The system suggests upgrading to a specific asthma code if documentation supports it.
- **Test data:** J44.9 + J45.909 → Violation. J44.9 + J45.901 → Passes. J44.9 + "asthma" without type specified → CDI query for asthma type.

### Edge Case 9: Sequela 7th Character Applied to Wrong Code

- **Description:** Patient has chronic knee pain from old tibial fracture. AI applies 7th character "S" (sequela) to M25.561 (the residual condition) instead of S82.101S (the original injury).
- **Why it's hard for NLP:** The sequela "S" goes on the CAUSE code, not the EFFECT code. This is counterintuitive — the active problem (pain) does not get the sequela character.
- **Our handling:** Step 1 (Individual Code Validity) checks 7th character validity. When "S" is applied to a non-injury code, a violation is raised. RULE-SEQ-006 handles sequela sequencing: residual condition first, cause with "S" second.
- **Test data:** M25.561S in suggestions → Violation: "7th character S is not valid for M25.561." S82.101S in suggestions with M25.561 preceding → Passes.

### Edge Case 10: High DRG Improvement Triggering Compliance Review

- **Description:** AI suggests adding E43 (Severe protein-calorie malnutrition, MCC) based on documented BMI 16.2 and albumin 2.1. This shifts DRG from base to MCC tier, increasing reimbursement by $9,000.
- **Why it's hard for NLP:** The suggestion is clinically valid, but the revenue impact exceeds $5,000 and triggers compliance review per constitution Article II.6. The system must calculate DRG impact and route appropriately.
- **Our handling:** Step 8 (DRG Impact Calculation) identifies the $9,000 revenue difference. `requires_compliance_review = True` is set. The suggestion reaches the coder UI but is also routed to the compliance team for review before the coder can accept it.
- **Test data:** Encounter without E43: DRG 795 (weight 0.68). With E43: DRG 793 (weight 1.64). Revenue difference: ~$9,000 at $6,500 base rate. Expected: `requires_compliance_review = True`.

### Edge Case 11: Abbreviation-Driven Miscoding

- **Description:** Note says "MS" in the medication section. NLP misinterprets as "multiple sclerosis" (G35) instead of "morphine sulfate." AI suggests G35 as a secondary diagnosis.
- **Why it's hard for NLP:** "MS" has 6+ clinical meanings (DISC-002 Section D.3). Without section-aware disambiguation, the wrong interpretation produces a false code suggestion.
- **Our handling:** This is primarily an NLP pipeline responsibility (pre-rules engine). However, the rules engine provides a safety net: Step 1 validates that `evidence_quote` supports the code. If the evidence quote is just "MS" without supporting clinical context for multiple sclerosis, the evidence is insufficient. Low confidence score triggers routing to senior coder queue.
- **Test data:** Evidence_quote = "MS 4mg IV q4h PRN." Suggestion = G35 (Multiple sclerosis). Expected: evidence_quote validation fails (no MS clinical findings), suggestion removed.

### Edge Case 12: Diabetes Type Conflict in Same Note

- **Description:** Problem list (copied) says "Type 1 DM." Current assessment says "Type 2 DM on metformin." Both E10.9 and E11.9 are suggested.
- **Why it's hard for NLP:** The note genuinely contains conflicting diabetes type documentation. NLP extracts both. The rules engine must catch the Excludes 1 violation and route to CDI query.
- **Our handling:** RULE-EX1-TOP10 (pair 1) catches E10 + E11. CRITICAL violation raised. System generates CDI query: "Note contains conflicting diabetes type documentation. Please clarify: is the patient's diabetes Type 1 or Type 2?"
- **Test data:** E10.9 + E11.9 in suggestions. Expected: CRITICAL violation + CDI query suggestion.

---

## 6. Performance Requirements

### Latency Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Full validation of a 15-code suggestion set | < 50ms | All 9 pipeline steps |
| Excludes 1 lookup (single pair) | < 5ms | Hash-based lookup, not linear scan |
| Excludes 1 full screening (15-code set = 105 pairs) | < 15ms | Pre-computed pair hash + top-10 fast path |
| DRG impact calculation (Step 8) | < 100ms | MS-DRG grouper logic |
| Individual code validity check (Step 1) | < 2ms per code | Code table in-memory lookup |
| Sequencing rule evaluation (Step 4) | < 10ms | Rule engine pattern matching |
| Total pipeline for 15-code set | < 200ms | Sum of all steps with overhead |

### Throughput Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent validation requests | 100 coders | Stateless validation — scales horizontally |
| Throughput | 500 validation requests/second | Per instance, single-threaded |
| Memory per code table | < 200 MB | Full ICD-10-CM table with Excludes, sequencing metadata |
| Startup time (code table load) | < 5 seconds | Load from pre-processed binary format |

### Data Storage

| Data Source | Format | Update Frequency |
|-------------|--------|-----------------|
| ICD-10-CM code table | Pre-processed binary (msgpack or pickle) | Annually (CMS FY release, typically Oct 1) |
| Excludes 1 pair table | Hash map (code_pair → Excludes1Pair) | Annually |
| Excludes 2 pair table | Hash map | Annually |
| MS-DRG grouper weights | Lookup table | Annually (CMS FY release) |
| CC/MCC designation list | Set lookup | Annually |
| HAC code list | Set lookup | As CMS updates |
| POA exempt list | Set lookup | Annually |
| Combination code mappings | Hash map | Annually |

### Reliability

- Validation must never crash on malformed input. Invalid codes
  produce CRITICAL violations, not exceptions.
- If code table fails to load, system enters degraded mode
  (constitution Article II.5) — returns all suggestions with
  `is_degraded=True` flag for manual review.
- All validation results are logged (without PHI) for audit trail.

---

## 7. Testing Strategy

### Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| Compliance tests | 1 per rule (30+) | Written FIRST. Each rule in Section 2 has explicit PASS and FAIL cases. |
| Excludes 1 tests | 10+ | One for each top-10 pair + random sampling from full table |
| Sequencing tests | 20+ | Sepsis (5 variants), diabetes (3), HTN+CKD (3), etiology/manifestation (3), others |
| Edge case tests | 12+ | One per edge case in Section 5 |
| Performance tests | 5+ | Latency benchmarks for each target |
| Regression tests | Growing | Add a test for every bug found in production |
| MIMIC-IV benchmark | Full suite | Validate against de-identified clinical notes (DISC-002 research) |

### Test Data Sources

- **Synthetic cases:** Hand-crafted test fixtures in `tests/fixtures/`
  covering every rule's PASS and FAIL scenarios
- **MIMIC-IV:** De-identified clinical notes for real-world validation
  (local only, gitignored per `data/mimic/`)
- **CMS test claims:** Published CMS test claim files for DRG grouper
  validation

### Compliance Test Requirement

Per constitution Article I.2, compliance tests are written BEFORE
implementation and achieve 100% coverage of all rules defined
in this specification. Every rule in Section 2 must have at least
one passing and one failing test case before the implementation
code is written.

---

*This specification is the authoritative reference for the
ICD-10 coding rules engine. No implementation code may
deviate from these rules without an ADR explaining why.*
