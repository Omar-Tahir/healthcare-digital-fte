# DESIGN-004: Prompt Engineering Architecture

**Status:** COMPLETE  
**Date:** 2026-04-01  
**Author:** Claude (AI Engineering Partner)  
**Research inputs:** DISC-001 (ICD-10 Official Guidelines),
DISC-002 (Documentation Failure Patterns),
DISC-005 (Competitor Technical Analysis)  
**Constitution references:** Article I.4 (Prompts Are Preserved),
Article I.5 (Domain Knowledge in Skills),
Article I.6 (Skills + MCP),
Article II.2 (Source Citation Required),
Article II.3 (ICD-10 Hard Constraints),
Article II.6 (Conservative Defaults)  
**Implementation target:** `src/prompts/coding_extraction.py`,
`src/prompts/cdi_query.py`, `src/prompts/drg_analysis.py`,
`src/prompts/appeal_letter.py`  
**Depends on:** DESIGN-001 (Coding Rules Engine — output schema),
DESIGN-002 (CDI Intelligence Layer — query templates),
DESIGN-003 (Compliance Guardrails — enforcement pipeline)

---

## Purpose

This spec defines the prompt engineering architecture for all
LLM interactions in the Healthcare Digital FTE system. Every
prompt is a clinical knowledge artifact — it encodes months
of research (DISC-001 through DISC-005), regulatory constraints
(ICD-10-CM Official Coding Guidelines, AHIMA Standards, FCA
compliance), and domain expertise into executable instructions.

Prompts are not implementation details. They are architectural
primitives. The clinical accuracy, regulatory compliance, and
competitive differentiation of the entire system depends on
prompt design. A prompt change has the same blast radius as a
schema change — it affects every output downstream.

This spec covers:
1. Five design principles governing all prompts
2. Four prompt designs (full text + test cases)
3. Token optimization strategy per prompt
4. Version control protocol for prompt evolution

---

## 1. Prompt Design Principles

These five principles govern every prompt in the system.
No prompt is deployed unless it satisfies all five.

### P1: Source Grounding Principle

**Statement:** Every clinical assertion in LLM output must
be traceable to a specific phrase in the input clinical note.
If a condition cannot be cited with a verbatim evidence quote,
it cannot be asserted as a code suggestion.

**Enforcement mechanism:**

1. **Prompt-level:** Every coding prompt includes the
   instruction: "For each condition you identify, extract
   the EXACT phrase from the clinical note that supports
   this finding. If you cannot identify a verbatim quote,
   do NOT include the condition."

2. **Schema-level:** The `CodingSuggestion` Pydantic model
   requires `evidence_quote: str` as a mandatory field
   (not `Optional`). A suggestion without an evidence quote
   fails Pydantic validation before reaching any downstream
   component.

3. **Guardrail-level:** G-HARD-002 (evidence quote required)
   validates that every `evidence_quote` appears verbatim
   in the source note text. Fuzzy matching is NOT used —
   the quote must be a substring of `source_note_text`.
   This catches LLM hallucination of evidence.

4. **Audit-level:** The audit trail records
   `(code, evidence_quote, source_note_id)` triples.
   In an FCA investigation, each code can be traced from
   the claim back to the specific clinical documentation
   that supports it.

**Why this matters:**
- ICD-10-CM Guidelines Section I.A.19: codes must be
  supported by documentation in the health record
- FCA defense requires demonstrable evidence chain
- Hallucinated evidence quotes are the highest-risk
  failure mode for clinical AI — they create liability
  with no documentation basis

**Anti-patterns this prevents:**
```
WRONG: "Patient likely has pneumonia" → code J18.9
       (no evidence quote — inference without citation)

WRONG: "Patient has fever and cough" → evidence_quote:
       "productive cough with yellow sputum, temp 101.4"
       (fabricated quote — not verbatim from note)

RIGHT: evidence_quote: "Chest X-ray consistent with
       right lower lobe pneumonia" → code J18.1
       (verbatim quote exists in source note)
```

---

### P2: Conservative Default Principle

**Statement:** When the LLM is uncertain between a higher-
specificity code and a lower-specificity code, it must
default to the lower-specificity code AND generate a CDI
query for the missing specificity.

**Enforcement mechanism:**

1. **Prompt-level:** Every coding prompt includes: "When
   the documentation supports a general condition but lacks
   the specificity needed for the most specific code, assign
   the less specific code and flag a CDI opportunity for the
   missing detail."

2. **Confidence scoring:** The prompt requires the LLM to
   assign a confidence score (0.0-1.0) to each suggestion.
   The prompt defines confidence anchors:
   ```
   0.95-1.00: Explicitly documented, exact terminology match
   0.85-0.94: Strongly implied by documentation + clinical context
   0.65-0.84: Supported by evidence but requires clinical judgment
   0.40-0.64: Possible but documentation is ambiguous
   0.00-0.39: Speculative — insufficient documentation
   ```

3. **Setting-aware conservatism:** The conservative default
   changes by encounter setting:
   - **Outpatient:** Uncertain diagnoses (with qualifier
     words) are NEVER coded — code the symptom/sign instead.
     This is a hard coding rule, not a preference.
   - **Inpatient:** Uncertain diagnoses MAY be coded per
     Section II.H, but at reduced confidence (0.65-0.75
     range) with a CDI query suggesting the physician
     clarify the diagnosis.

4. **Guardrail enforcement:** G-HARD-004 blocks outpatient
   uncertain diagnoses at the middleware layer. G-SOFT-001
   routes confidence 0.40-0.65 suggestions to senior coder.
   G-HARD-007 blocks confidence < 0.40 entirely.

**Revenue trade-off acknowledged:** Conservative defaults
may leave revenue on the table in the short term. This is
acceptable because (a) the CDI query captures the revenue
by prompting physician documentation, and (b) the False
Claims Act risk of overcoding far exceeds the revenue loss
of undercoding. Per Constitution Article II.6: "The system
chooses the less risky option."

---

### P3: Setting Awareness Principle

**Statement:** Every clinical reasoning prompt must receive
`encounter_class` (inpatient / outpatient) as a required
variable. The prompt logic branches on this value because
ICD-10-CM coding rules differ fundamentally between settings.

**Branch logic:**

```
IF encounter_class == "outpatient":
    UNCERTAIN DIAGNOSIS RULE:
        Words: "probable", "suspected", "likely",
               "questionable", "possible", "rule out",
               "working diagnosis", "consistent with",
               "compatible with", "indicative of",
               "suggestive of", "apparent",
               "presumptive", "borderline",
               "preliminary diagnosis"
        → NEVER code the uncertain condition
        → Code the documented sign/symptom instead
        → DO NOT generate a CDI query (outpatient CDI
          is not in Phase 1 scope)

    SEQUENCING RULE:
        → First-listed diagnosis = reason for encounter
        → Additional diagnoses = conditions treated or
          affecting management during the encounter

    CHRONIC CONDITIONS:
        → Only code chronic conditions if documented
          AND they were addressed during this encounter

IF encounter_class == "inpatient":
    UNCERTAIN DIAGNOSIS RULE:
        Same qualifier words as above
        → MAY code as if confirmed per Section II.H
        → Confidence reduced to 0.65-0.75 range
        → CDI query generated to request physician
          confirmation

    SEQUENCING RULE:
        → Principal diagnosis = condition established
          after study to be chiefly responsible for
          the admission
        → "After study" includes the entire stay

    SECONDARY DIAGNOSES:
        → Code ALL documented conditions that affect
          treatment, require clinical evaluation,
          increase nursing care, or extend LOS

    POA INDICATORS:
        → Required for every diagnosis
        → HAC categories require special attention
```

**Why a required variable (not inferred):**
The encounter class MUST come from the FHIR Encounter
resource (`Encounter.class`), not from LLM inference of
the note. Notes do not always state the encounter setting.
Inferring the wrong setting and applying the wrong coding
rules is a compliance violation that affects every code
in the encounter.

---

### P4: Structured Output Principle

**Statement:** All prompts return structured JSON that is
Pydantic-validated before any downstream use. No prompt
returns free-text that is parsed with regex or string
manipulation.

**Enforcement mechanism:**

1. **Prompt-level:** Every prompt ends with a strict JSON
   output schema and the instruction: "Return ONLY valid
   JSON matching this schema. No additional text, no
   markdown formatting, no code blocks."

2. **Parsing:** The application uses `json.loads()` on the
   raw LLM response. If parsing fails, the request is
   retried once with an error correction prompt. If the
   retry also fails, the request returns a structured error.

3. **Validation:** Parsed JSON is passed to the corresponding
   Pydantic model. Validation failures are logged with
   `structlog` and the specific field that failed. The
   request is NOT retried on Pydantic validation failure
   (the LLM produced structurally valid but semantically
   incorrect output — retrying is unlikely to fix this).

4. **Anthropic tool_use mode:** Where supported, prompts
   use Anthropic's `tool_use` feature to constrain output
   to the schema. This is the preferred approach as it
   provides token-level schema enforcement.

**Schema design rules:**
- Every output field has a Pydantic `Field(description=...)`
- No `dict[str, Any]` — all nested structures are typed
- `Optional` is never used for fields that are always
  expected — use default values instead
- Enum fields use `Literal[...]` for closed sets
- Confidence scores use `float = Field(ge=0.0, le=1.0)`

---

### P5: Role Priming Principle

**Statement:** Every coding and clinical reasoning prompt
establishes the AI as a certified medical professional
with specific credentials and responsibilities. Role
priming reduces hallucination rate and increases coding
accuracy by anchoring the LLM in professional standards.

**Role priming template:**

```
You are a senior certified medical coder (CCS, CCS-P, RHIA)
with 15 years of experience in inpatient and outpatient
coding for academic medical centers. You hold current
credentials from AHIMA and follow ICD-10-CM Official
Coding Guidelines (FY{fiscal_year}) exactly as published.

Your responsibilities:
1. Extract codeable conditions from clinical documentation
2. Assign ICD-10-CM codes supported by documentation
3. Apply sequencing rules per official guidelines
4. Identify CC/MCC opportunities from documented conditions
5. Flag documentation gaps for CDI review

You NEVER:
- Infer diagnoses not supported by physician documentation
- Code conditions the physician has ruled out
- Suggest codes without verbatim evidence from the note
- Override ICD-10-CM Official Coding Guidelines for any reason
- Consider revenue impact when selecting codes (code what
  is documented, let DRG follow from accurate coding)
```

**Why this specific role:**
- CCS (Certified Coding Specialist) and RHIA (Registered
  Health Information Administrator) are AHIMA credentials
  recognized by all US hospitals
- "Academic medical center" experience implies complex
  cases (teaching hospitals have higher CMI)
- "15 years" implies seniority sufficient for independent
  judgment on edge cases
- The "You NEVER" section creates explicit negative
  constraints that reduce hallucination

**Role priming is NOT a substitute for guardrails.**
Role priming reduces the probability of violations.
Guardrails (DESIGN-003) make violations impossible.
Both layers are required.

---

## 2. Prompt Designs

### PROMPT-001: ICD-10 Code Extraction

**PHR reference:** `docs/phr/PHR-001-coding-extraction.md`  
**Implementation:** `src/prompts/coding_extraction.py`  
**Current version:** v1.0  
**Model:** claude-sonnet-4-6 (default), claude-opus-4-6
(complex multi-system cases)  
**Constitution references:** Article II.2 (Source Citation),
Article II.3 (ICD-10 Hard Constraints),
Article II.6 (Conservative Defaults)

#### 2.1.1 System Prompt

```
SYSTEM_PROMPT_CODING_EXTRACTION_V1_0 = """
You are a senior certified medical coder (CCS, CCS-P, RHIA)
with 15 years of experience in inpatient and outpatient
coding for academic medical centers. You hold current
credentials from AHIMA and follow ICD-10-CM Official
Coding Guidelines (FY2026) exactly as published.

YOUR TASK:
Analyze the clinical note provided and extract ALL codeable
conditions. For each condition, assign the most specific
ICD-10-CM code supported by the documentation and provide
a verbatim evidence quote from the note.

CRITICAL RULES — VIOLATIONS ARE HARD STOPS:

1. EVIDENCE GROUNDING (Constitution Article II.2):
   Every code suggestion MUST include an exact verbatim
   quote from the clinical note. If you cannot find a
   direct quote supporting a condition, DO NOT include it.
   Never paraphrase — copy the exact text.

2. ENCOUNTER SETTING ({encounter_class}):
   {setting_specific_rules}

3. UNCERTAIN DIAGNOSIS HANDLING:
   IF encounter_class == "outpatient":
     The following qualifier words mean the condition
     is NOT confirmed and MUST NOT be coded:
     "probable", "suspected", "likely", "questionable",
     "possible", "rule out", "working diagnosis",
     "consistent with", "compatible with", "indicative of",
     "suggestive of", "apparent", "presumptive",
     "borderline", "preliminary diagnosis"
     → Instead, code the documented sign or symptom.

   IF encounter_class == "inpatient":
     Per ICD-10-CM Section II.H, conditions described
     with the above qualifier words MAY be coded as if
     confirmed. Assign confidence 0.65-0.75 for uncertain
     diagnoses and flag for CDI clarification.

4. EXCLUDES 1 PAIRS:
   NEVER suggest two codes that have an Excludes 1
   relationship. These conditions are mutually exclusive
   by definition. If you identify both conditions in
   documentation, select the one with stronger evidence
   and flag the conflict.

5. COMBINATION CODES:
   When a single combination code exists for two related
   conditions (e.g., diabetes + CKD = E11.22), use the
   combination code instead of coding separately.
   ICD-10-CM assumes causal relationships for:
   - Diabetes + any complication (E08-E13 combination)
   - Hypertension + heart disease (I11.-)
   - Hypertension + CKD (I12.-)
   - Hypertension + heart disease + CKD (I13.-)
   Unless the physician explicitly states the conditions
   are unrelated.

6. SEQUENCING:
   IF inpatient:
     - Principal diagnosis = condition chiefly responsible
       for the admission AFTER STUDY
     - Sequence per Code First / Use Additional / Code Also
     - Sepsis (A40-A41) sequencing per Section I.C.1.d
   IF outpatient:
     - First-listed = reason for encounter
     - Additional = conditions treated/managed

7. CC/MCC IDENTIFICATION:
   For every suggested code, determine:
   - Is this code on the CMS CC list?
   - Is this code on the CMS MCC list?
   This affects DRG weight and revenue impact calculation
   downstream. Do NOT let CC/MCC status influence your
   code selection — code accurately, let DRG follow.

8. CDI OPPORTUNITIES:
   After completing code extraction, identify documentation
   gaps where:
   - Clinical evidence (labs, vitals, meds) suggests a
     condition that is not explicitly documented
   - A documented condition lacks the specificity needed
     for the most specific available code
   - A causal relationship between conditions is implied
     but not stated
   - POA status cannot be determined from documentation
   Report these as CDI opportunities, NOT as code suggestions.

9. COPY-FORWARD DETECTION:
   If any evidence quote appears identical or near-identical
   to documentation from a prior encounter (indicated by
   is_copy_forward_text markers in the input), flag the
   suggestion with is_from_copied_text=true and reduce
   confidence by 0.15.

CONFIDENCE SCORING:
  0.95-1.00: Explicitly documented, exact terminology
  0.85-0.94: Strongly implied by documentation + context
  0.65-0.84: Supported but requires clinical judgment
  0.40-0.64: Possible but documentation is ambiguous
  0.00-0.39: Speculative — insufficient documentation
"""
```

#### 2.1.2 Setting-Specific Rule Inserts

```python
INPATIENT_RULES = """
This is an INPATIENT encounter.

Principal diagnosis rules:
- The principal diagnosis is the condition established
  after study to be chiefly responsible for occasioning
  the admission.
- "After study" means the entire inpatient stay, including
  all workup results.
- If two conditions equally meet the principal definition,
  either may be sequenced first unless a guideline-specific
  rule applies (e.g., sepsis must be principal if POA).

Secondary diagnosis rules:
- Code ALL conditions that coexist at the time of admission
  or develop subsequently AND that affect patient care in
  terms of requiring: clinical evaluation, therapeutic
  treatment, diagnostic procedures, extended length of
  stay, or increased nursing care/monitoring.

POA indicators:
- Assign a POA indicator to every diagnosis:
  Y = present at time of inpatient admission
  N = not present at time of inpatient admission
  U = documentation insufficient to determine
  W = clinically undeterminable
- ER diagnoses confirmed before admission order = POA Y
- Conditions diagnosed during admission workup from
  pre-admission symptoms = POA Y

Uncertain diagnoses:
- Per Section II.H, conditions qualified as "probable",
  "suspected", "likely", "questionable", "possible", or
  "rule out" at the time of DISCHARGE may be coded as
  if confirmed. Assign reduced confidence (0.65-0.75).
"""

OUTPATIENT_RULES = """
This is an OUTPATIENT encounter.

First-listed diagnosis:
- The diagnosis, condition, problem, or reason for
  encounter shown in the medical record to be chiefly
  responsible for the services provided.

Uncertain diagnoses:
- NEVER code diagnoses qualified as "probable",
  "suspected", "likely", "questionable", "possible",
  "rule out", "working diagnosis", "consistent with",
  "compatible with", "indicative of", "suggestive of",
  "apparent", "presumptive", "borderline", or
  "preliminary diagnosis".
- Code the sign, symptom, or documented condition
  instead.
- This is a HARD RULE — no exceptions.

Chronic conditions:
- Only code chronic conditions if they are addressed
  or managed during this specific encounter.
"""
```

#### 2.1.3 User Prompt Template

```python
USER_PROMPT_CODING_EXTRACTION_V1_0 = """
ENCOUNTER INFORMATION:
- Encounter ID: {encounter_id}
- Encounter class: {encounter_class}
- Admission date: {admission_date}
- Discharge date: {discharge_date}
- Patient age: {patient_age}
- Patient sex: {patient_sex}
- Attending physician: {attending_physician}

CLINICAL NOTE:
─────────────────────────────────────────────
{note_text}
─────────────────────────────────────────────

{copy_forward_markers}

AVAILABLE CLINICAL DATA:
- Lab results: {lab_summary}
- Medications: {medication_summary}
- Procedures: {procedure_summary}

INSTRUCTIONS:
1. Read the entire clinical note carefully.
2. Identify ALL codeable conditions present in the note.
3. For each condition, extract the EXACT verbatim quote.
4. Assign the most specific ICD-10-CM code supported.
5. Apply sequencing rules for {encounter_class} setting.
6. Identify CC/MCC status for each code.
7. Flag any CDI opportunities (documentation gaps).
8. Return structured JSON per the output schema below.

OUTPUT SCHEMA:
Return ONLY valid JSON matching this structure.
No additional text, no markdown, no code blocks.

{{
  "encounter_id": "{encounter_id}",
  "encounter_class": "{encounter_class}",
  "principal_diagnosis": {{
    "code": "ICD-10-CM code",
    "description": "Code description",
    "confidence": 0.0-1.0,
    "evidence_quote": "Exact verbatim text from note",
    "qualifier_words": ["any", "uncertainty", "qualifiers"],
    "is_cc": true/false,
    "is_mcc": true/false,
    "poa_indicator": "Y|N|U|W" (inpatient only, null for outpatient),
    "is_from_copied_text": true/false,
    "rationale": "Brief explanation of code selection"
  }},
  "secondary_diagnoses": [
    {{
      "code": "ICD-10-CM code",
      "description": "Code description",
      "confidence": 0.0-1.0,
      "evidence_quote": "Exact verbatim text from note",
      "qualifier_words": [],
      "is_cc": true/false,
      "is_mcc": true/false,
      "poa_indicator": "Y|N|U|W|null",
      "is_from_copied_text": true/false,
      "rationale": "Brief explanation"
    }}
  ],
  "cdi_opportunities": [
    {{
      "category": "severity|specificity|causality|poa",
      "description": "What documentation is missing",
      "clinical_evidence": "What evidence suggests the gap",
      "potential_codes": ["Codes that could apply if documented"],
      "estimated_cc_impact": "non_cc|cc|mcc",
      "priority": "P0|P1|P2"
    }}
  ],
  "coding_notes": "Any relevant coding observations"
}}
"""
```

#### 2.1.4 Test Cases

**Test Case 1: Inpatient — Sepsis with AKI (PASS)**

Input note (abbreviated):
```
DISCHARGE SUMMARY
72M admitted from ED with fever 102.4F, HR 112, RR 24,
WBC 18.2K. Blood cultures positive for E. coli.
Diagnosed with urosepsis. Started on piperacillin-
tazobactam. Developed hypotension requiring vasopressors
on Day 2 — septic shock. Creatinine rose from baseline
1.1 to 2.8 mg/dL. Nephrology consulted — acute kidney
injury secondary to sepsis. Improved with IV fluids
and antibiotics. Discharged Day 7 on oral antibiotics.
```

Expected output:
```json
{
  "encounter_id": "ENC-001",
  "encounter_class": "inpatient",
  "principal_diagnosis": {
    "code": "A41.51",
    "description": "Sepsis due to Escherichia coli",
    "confidence": 0.95,
    "evidence_quote": "Blood cultures positive for E. coli. Diagnosed with urosepsis",
    "qualifier_words": [],
    "is_cc": false,
    "is_mcc": true,
    "poa_indicator": "Y",
    "is_from_copied_text": false,
    "rationale": "Sepsis POA with identified organism E. coli. Sequenced as principal per Section I.C.1.d.1."
  },
  "secondary_diagnoses": [
    {
      "code": "R65.21",
      "description": "Severe sepsis with septic shock",
      "confidence": 0.95,
      "evidence_quote": "Developed hypotension requiring vasopressors on Day 2 — septic shock",
      "qualifier_words": [],
      "is_cc": false,
      "is_mcc": true,
      "poa_indicator": "N",
      "is_from_copied_text": false,
      "rationale": "Septic shock developed Day 2 — not POA. Sequenced after sepsis code per guidelines."
    },
    {
      "code": "N17.9",
      "description": "Acute kidney failure, unspecified",
      "confidence": 0.95,
      "evidence_quote": "Nephrology consulted — acute kidney injury secondary to sepsis",
      "qualifier_words": [],
      "is_cc": false,
      "is_mcc": true,
      "poa_indicator": "N",
      "is_from_copied_text": false,
      "rationale": "AKI explicitly documented by nephrology. Developed during stay (creatinine rose from baseline)."
    },
    {
      "code": "N39.0",
      "description": "Urinary tract infection, site not specified",
      "confidence": 0.90,
      "evidence_quote": "Diagnosed with urosepsis",
      "qualifier_words": [],
      "is_cc": false,
      "is_mcc": false,
      "poa_indicator": "Y",
      "is_from_copied_text": false,
      "rationale": "Localized infection source for sepsis. Sequenced after sepsis per guidelines."
    }
  ],
  "cdi_opportunities": [
    {
      "category": "specificity",
      "description": "AKI stage not documented — N17.9 (unspecified) used instead of stage-specific code",
      "clinical_evidence": "Creatinine rose from 1.1 to 2.8 (2.5x baseline) — suggests KDIGO Stage 2",
      "potential_codes": ["N17.0"],
      "estimated_cc_impact": "mcc",
      "priority": "P1"
    }
  ],
  "coding_notes": "Sepsis sequencing follows Section I.C.1.d.1 — sepsis POA as principal, R65.21 and organ dysfunction follow. AKI is organ dysfunction related to sepsis."
}
```

**Test Case 2: Outpatient — Uncertain Diagnosis (PASS)**

Input note (abbreviated):
```
OFFICE VISIT
45F presents with 2-week history of fatigue, weight gain
of 8 lbs, and cold intolerance. TSH drawn today.
Assessment: Probable hypothyroidism. Plan: Await TSH
results, follow up in 1 week.
```

Expected output:
```json
{
  "encounter_id": "ENC-002",
  "encounter_class": "outpatient",
  "principal_diagnosis": {
    "code": "R53.83",
    "description": "Other fatigue",
    "confidence": 0.92,
    "evidence_quote": "2-week history of fatigue",
    "qualifier_words": [],
    "is_cc": false,
    "is_mcc": false,
    "poa_indicator": null,
    "is_from_copied_text": false,
    "rationale": "Fatigue is the documented sign. Hypothyroidism is qualified as 'probable' — cannot code in outpatient per Section IV.H."
  },
  "secondary_diagnoses": [
    {
      "code": "R63.5",
      "description": "Abnormal weight gain",
      "confidence": 0.90,
      "evidence_quote": "weight gain of 8 lbs",
      "qualifier_words": [],
      "is_cc": false,
      "is_mcc": false,
      "poa_indicator": null,
      "is_from_copied_text": false,
      "rationale": "Documented sign supporting the encounter."
    },
    {
      "code": "R89.09",
      "description": "Abnormal level of other specified substances in other specimens",
      "confidence": 0.70,
      "evidence_quote": "TSH drawn today",
      "qualifier_words": [],
      "is_cc": false,
      "is_mcc": false,
      "poa_indicator": null,
      "is_from_copied_text": false,
      "rationale": "Lab test ordered — appropriate to code as reason for the diagnostic test."
    }
  ],
  "cdi_opportunities": [],
  "coding_notes": "Hypothyroidism qualified as 'probable' — outpatient uncertain diagnosis rule applies. Coded documented signs/symptoms instead. No CDI opportunity — outpatient CDI not in Phase 1 scope."
}
```

**Test Case 3: Inpatient — Copy-Forward Detection (PASS)**

Input note (abbreviated):
```
PROGRESS NOTE (Day 3)
[COPY-FORWARD DETECTED: 94% similarity to Day 1 H&P]
72M with history of type 2 diabetes mellitus with diabetic
chronic kidney disease, stage 3. Patient also has
essential hypertension. Continues on metformin, lisinopril.
Assessment unchanged from admission. Plan: continue
current management, PT/OT consult, social work for
discharge planning.
```

Expected output: Suggestions include `is_from_copied_text:
true` and confidence scores reduced by 0.15. CDI opportunity
flagged for copy-forward risk — physician should document
any interval changes.

#### 2.1.5 Known Failure Modes

| Failure Mode | Detection | Mitigation |
|---|---|---|
| Hallucinated evidence quote | G-HARD-002 substring check | Suggestion removed; not retried |
| Wrong encounter setting rules | Encounter class is a required input, not inferred | System-level enforcement |
| Missed Excludes 1 conflict | Rules engine RULE-EX1 post-validation | Deterministic check catches what LLM misses |
| Overcoding uncertain dx (outpatient) | G-HARD-004 qualifier word scan | Hard stop at guardrail layer |
| Missed CC/MCC identification | Rules engine DRG impact step | Deterministic CC/MCC list lookup post-LLM |
| Copy-forward text coded as new finding | NLP pipeline copy-forward score | Confidence reduction + soft guardrail |
| JSON parse failure | `json.loads()` exception | One retry with error correction prompt |
| Laterality omission | Rules engine billable code check | Flags non-billable unspecified laterality codes |

---

### PROMPT-002: CDI Physician Query Generator

**PHR reference:** `docs/phr/PHR-002-cdi-query.md`  
**Implementation:** `src/prompts/cdi_query.py`  
**Current version:** v1.0  
**Model:** claude-sonnet-4-6  
**Constitution references:** Article II.2 (Source Citation),
Article II.6 (Conservative Defaults)  
**Compliance:** AHIMA Standards for CDI, ACDIS Code of Ethics

#### 2.2.1 System Prompt

```
SYSTEM_PROMPT_CDI_QUERY_V1_0 = """
You are a senior Clinical Documentation Improvement (CDI)
specialist (CCDS, CDIP) with 12 years of experience at
academic medical centers. You hold current ACDIS and AHIMA
certifications. You follow AHIMA Standards for Clinical
Documentation Improvement and the ACDIS Code of Ethics.

YOUR TASK:
Generate a physician query for the identified documentation
gap. The query must be non-leading, clinically grounded,
and AHIMA-compliant.

AHIMA COMPLIANCE REQUIREMENTS — NON-NEGOTIABLE:

1. NON-LEADING QUERIES ONLY:
   - Present objective clinical data (labs, vitals, imaging)
   - Ask an open-ended clinical question
   - Provide multiple response options including "No" and
     "Clinically undetermined"
   - NEVER suggest a specific diagnosis in the question
   - NEVER mention revenue, DRG, reimbursement, or coding
   - NEVER use language that implies the "correct" answer

2. WHAT MAKES A QUERY LEADING (PROHIBITED):
   - "This patient appears to have sepsis, do you agree?"
     → Leading because it suggests the answer
   - "Please document AKI so we can capture the MCC"
     → Leading AND mentions revenue impact
   - "The creatinine rise indicates AKI, correct?"
     → Leading — asserts diagnosis as fact
   - "Don't you think this meets sepsis criteria?"
     → Leading — implies expected answer

3. WHAT MAKES A QUERY NON-LEADING (REQUIRED):
   - "Based on the clinical picture, does this patient
     have acute kidney injury?"
     → Open-ended, presents clinical context
   - "Given the documented clinical indicators, please
     clarify the underlying etiology of the acute
     respiratory failure."
     → Asks for physician's clinical judgment
   - "Is there a clinical relationship between the
     documented hypertension and heart failure?"
     → Neutral question about documented conditions

4. CLINICAL RATIONALE SECTION:
   Every query includes a brief educational note explaining
   why accurate documentation matters CLINICALLY (for care
   continuity, medication decisions, treatment planning).
   NEVER explain why it matters financially.

5. RESPONSE OPTIONS:
   Every query must include:
   - At least one "Yes" option (with space for specificity)
   - A "No" option (always valid and accessible)
   - A "Clinically undetermined" option
   - An "Other" option with free-text

6. TONE:
   Collegial and respectful. You are a peer asking for
   clinical clarification, not an auditor demanding
   documentation. The physician is the clinical expert.
"""
```

#### 2.2.2 User Prompt Template

```python
USER_PROMPT_CDI_QUERY_V1_0 = """
DOCUMENTATION GAP IDENTIFIED:

Category: {opportunity_category}
Subcategory: {opportunity_subcategory}
Priority: {priority}

CLINICAL EVIDENCE SUPPORTING THIS QUERY:

{clinical_indicators}

LAB / VITALS DATA:

{lab_evidence}

CURRENT MEDICATIONS RELEVANT TO THIS GAP:

{medication_evidence}

ENCOUNTER CONTEXT:
- Encounter ID: {encounter_id}
- Encounter class: {encounter_class}
- Day of stay: {day_of_stay}
- Attending: {attending_physician}

INSTRUCTIONS:
1. Generate an AHIMA-compliant physician query.
2. Present the clinical evidence objectively.
3. Ask a non-leading clinical question.
4. Provide multiple response options.
5. Include a brief clinical rationale (NOT financial).
6. Format for physician mobile interface (concise).

OUTPUT SCHEMA:
Return ONLY valid JSON matching this structure.

{{
  "query_type": "clinical_clarification|specificity|causality|poa_determination",
  "clinical_indicators_formatted": "Formatted clinical evidence paragraph",
  "clinical_question": "The non-leading question to the physician",
  "response_options": [
    {{
      "option_id": "A",
      "label": "Response option text",
      "requires_free_text": true/false,
      "follow_up_needed": true/false
    }}
  ],
  "clinical_rationale": "Brief clinical (not financial) rationale",
  "compliance_flags": {{
    "is_non_leading": true,
    "mentions_revenue": false,
    "has_no_option": true,
    "has_undetermined_option": true
  }}
}}
"""
```

#### 2.2.3 Query Examples

**Example 1: AKI on CKD**

Input:
```
Category: severity
Subcategory: AKI not documented — patient has baseline CKD
Clinical evidence:
  - Baseline creatinine: 1.8 mg/dL (CKD stage 3, documented)
  - Current creatinine: 3.2 mg/dL (78% increase over 3 days)
  - IV fluids started, nephrotoxic meds held
  - Progress note mentions "worsening renal function"
```

Expected query output:
```json
{
  "query_type": "clinical_clarification",
  "clinical_indicators_formatted": "Laboratory findings indicate a change in renal function in the setting of documented chronic kidney disease, stage 3:\n  - Baseline creatinine: 1.8 mg/dL\n  - Current creatinine: 3.2 mg/dL (78% increase over 3 days)\n  - IV fluid resuscitation initiated\n  - Nephrotoxic medications held\n  - Progress note documents \"worsening renal function\"",
  "clinical_question": "In the setting of this patient's known chronic kidney disease, does the acute change in renal function represent a superimposed acute kidney injury?",
  "response_options": [
    {
      "option_id": "A",
      "label": "Yes — acute kidney injury superimposed on CKD is present. Etiology (if known): ___",
      "requires_free_text": true,
      "follow_up_needed": false
    },
    {
      "option_id": "B",
      "label": "No — creatinine change represents progression of chronic kidney disease",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "C",
      "label": "No — creatinine change is related to a different process. Please clarify: ___",
      "requires_free_text": true,
      "follow_up_needed": false
    },
    {
      "option_id": "D",
      "label": "Clinically undetermined at this time",
      "requires_free_text": false,
      "follow_up_needed": true
    },
    {
      "option_id": "E",
      "label": "Other: ___",
      "requires_free_text": true,
      "follow_up_needed": false
    }
  ],
  "clinical_rationale": "Distinguishing acute kidney injury from chronic kidney disease progression ensures appropriate nephrology follow-up, medication dosing, and discharge planning for renal recovery monitoring.",
  "compliance_flags": {
    "is_non_leading": true,
    "mentions_revenue": false,
    "has_no_option": true,
    "has_undetermined_option": true
  }
}
```

**Example 2: Sepsis Undocumented**

Input:
```
Category: severity
Subcategory: Sepsis criteria met without explicit documentation
Clinical evidence:
  - Temp: 101.8°F, HR: 108, RR: 22 (2 of 4 SIRS criteria)
  - WBC: 16.4K (3 of 4 SIRS criteria)
  - Blood cultures drawn, pending
  - Documented: "pneumonia" (infection source)
  - Lactate: 3.2 mmol/L (elevated)
  - IV antibiotics started: vancomycin + cefepime
```

Expected query output:
```json
{
  "query_type": "clinical_clarification",
  "clinical_indicators_formatted": "The patient presents with the following clinical findings:\n  - Temperature: 101.8°F\n  - Heart rate: 108 bpm\n  - Respiratory rate: 22 breaths/min\n  - WBC: 16.4K\n  - Lactate: 3.2 mmol/L\n  - Documented pneumonia (infection source identified)\n  - Blood cultures drawn\n  - IV antibiotics initiated (vancomycin, cefepime)",
  "clinical_question": "Given the documented infection and the clinical indicators above, does this clinical presentation represent sepsis?",
  "response_options": [
    {
      "option_id": "A",
      "label": "Yes — sepsis is present due to pneumonia",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "B",
      "label": "Yes — severe sepsis / sepsis with organ dysfunction is present",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "C",
      "label": "No — clinical findings represent the infectious process without systemic sepsis",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "D",
      "label": "Clinically undetermined at this time",
      "requires_free_text": false,
      "follow_up_needed": true
    },
    {
      "option_id": "E",
      "label": "Other: ___",
      "requires_free_text": true,
      "follow_up_needed": false
    }
  ],
  "clinical_rationale": "Accurate documentation of sepsis, when present, ensures appropriate clinical escalation protocols, ICU monitoring decisions, and care team communication regarding systemic infection severity.",
  "compliance_flags": {
    "is_non_leading": true,
    "mentions_revenue": false,
    "has_no_option": true,
    "has_undetermined_option": true
  }
}
```

**Example 3: Heart Failure Specificity**

Input:
```
Category: specificity
Subcategory: Heart failure type/acuity not specified
Clinical evidence:
  - Note documents: "heart failure"
  - BNP: 1,840 pg/mL (markedly elevated)
  - Echo: EF 30% (reduced), moderate MR
  - IV furosemide started for volume overload
  - Daily weights, fluid restriction ordered
```

Expected query output:
```json
{
  "query_type": "specificity",
  "clinical_indicators_formatted": "Documentation currently states \"heart failure\" without further specification:\n  - BNP: 1,840 pg/mL (markedly elevated)\n  - Echocardiogram: EF 30% (reduced), moderate mitral regurgitation\n  - IV diuretics initiated\n  - Daily weights and fluid restriction ordered",
  "clinical_question": "Can the type and acuity of this patient's heart failure be further specified?",
  "response_options": [
    {
      "option_id": "A",
      "label": "Acute systolic (HFrEF) heart failure",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "B",
      "label": "Acute on chronic systolic (HFrEF) heart failure",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "C",
      "label": "Chronic systolic (HFrEF) heart failure",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "D",
      "label": "Heart failure, type/acuity as documented is accurate",
      "requires_free_text": false,
      "follow_up_needed": false
    },
    {
      "option_id": "E",
      "label": "Other (please specify): ___",
      "requires_free_text": true,
      "follow_up_needed": false
    }
  ],
  "clinical_rationale": "Specifying heart failure type (systolic vs. diastolic) and acuity (acute, chronic, acute-on-chronic) guides treatment protocols, discharge medication reconciliation, and outpatient cardiology follow-up planning.",
  "compliance_flags": {
    "is_non_leading": true,
    "mentions_revenue": false,
    "has_no_option": true,
    "has_undetermined_option": false
  }
}
```

#### 2.2.4 Known Failure Modes

| Failure Mode | Detection | Mitigation |
|---|---|---|
| Leading question generated | Compliance flag check + AHIMA 10-point verification | Regenerate with explicit non-leading instruction |
| Revenue/DRG language leaked | Keyword scan for "revenue", "DRG", "reimbursement", "weight", "payment" | Hard rejection + regenerate |
| Missing "No" response option | Schema validation (`has_no_option` must be true) | Schema enforcement — Pydantic rejects |
| Query too long for mobile | Character count check (max 1,500 chars) | Truncation prompt with "Summarize clinical indicators concisely" |
| Clinical rationale mentions coding | Keyword scan for "code", "coding", "ICD", "classification" | Hard rejection + regenerate |

---

### PROMPT-003: DRG Impact Narrative

**PHR reference:** `docs/phr/PHR-003-drg-analysis.md`  
**Implementation:** `src/prompts/drg_analysis.py`  
**Current version:** v1.0  
**Model:** claude-sonnet-4-6  
**Constitution references:** Article IV.1 (Revenue North Star)

#### 2.3.1 System Prompt

```
SYSTEM_PROMPT_DRG_NARRATIVE_V1_0 = """
You are a revenue cycle analyst with expertise in MS-DRG
methodology and clinical documentation improvement. You
communicate complex DRG impact data in plain English for
HIM directors and CFOs who are not medical coders.

YOUR TASK:
Generate a clear, concise revenue impact narrative that
explains how documentation improvements and accurate coding
affect hospital reimbursement.

RULES:

1. PLAIN ENGLISH:
   - No ICD-10 codes in the narrative body (reference
     them in a footnote if needed)
   - No coding jargon ("CC", "MCC", "MDC") without
     explanation
   - Write for a reader who understands business but
     not medical coding

2. FORMAT:
   - 2-3 sentence executive summary
   - Dollar amount prominently displayed
   - Before/after comparison in plain language
   - Footnote with technical details for coders

3. ACCURACY:
   - Dollar amounts come from DRG weight × base rate
   - Never fabricate or estimate dollar amounts beyond
     the provided DRG data
   - Clearly state when an amount is an estimate vs exact

4. TONE:
   - Professional, factual, not promotional
   - Present opportunities, not accusations of missed revenue
   - Frame as documentation accuracy, not upcoding

5. COMPLIANCE:
   - Never suggest documentation changes for revenue purposes
   - Frame all improvements as clinical accuracy improvements
     that happen to affect reimbursement
   - Never imply physicians should document differently to
     increase revenue
"""
```

#### 2.3.2 User Prompt Template

```python
USER_PROMPT_DRG_NARRATIVE_V1_0 = """
DRG IMPACT DATA:

Current coding:
  - MS-DRG: {current_drg} ({current_drg_description})
  - Relative weight: {current_weight}
  - Estimated reimbursement: ${current_revenue}

If documentation improvements are accepted:
  - MS-DRG: {potential_drg} ({potential_drg_description})
  - Relative weight: {potential_weight}
  - Estimated reimbursement: ${potential_revenue}

Revenue difference: ${revenue_difference}

Documentation improvements:
{documentation_improvements}

Base rate used: ${base_rate} (national average)

INSTRUCTIONS:
Generate a revenue impact narrative per your rules.
Return ONLY valid JSON.

OUTPUT SCHEMA:
{{
  "executive_summary": "2-3 sentence plain-English summary",
  "revenue_impact_display": "$X,XXX",
  "before_after": {{
    "before": "Plain description of current DRG",
    "after": "Plain description of potential DRG",
    "what_changed": "What documentation improvement drives the change"
  }},
  "technical_footnote": "ICD-10 codes and DRG details for coders",
  "compliance_note": "Statement that this reflects documentation accuracy, not upcoding",
  "requires_compliance_review": true/false
}}
"""
```

#### 2.3.3 Test Case

Input:
```
Current: MS-DRG 872 (Sepsis without MCC), weight 0.9841,
         revenue $6,931
Potential: MS-DRG 871 (Sepsis with MCC), weight 1.8346,
           revenue $12,919
Difference: $5,988
Documentation improvement: Physician confirmed AKI
  (acute kidney injury) via CDI query — previously
  undocumented despite creatinine meeting KDIGO criteria
```

Expected output:
```json
{
  "executive_summary": "When the physician confirmed the presence of acute kidney injury — supported by laboratory evidence of significant creatinine elevation — the documentation now fully reflects the clinical complexity of this sepsis case. This accurate documentation changes the severity classification from a standard sepsis case to one with a major complication, resulting in an estimated reimbursement difference of $5,988.",
  "revenue_impact_display": "$5,988",
  "before_after": {
    "before": "Sepsis case classified at standard complexity level (no major complications documented)",
    "after": "Sepsis case with physician-confirmed acute kidney injury as a major complication",
    "what_changed": "Physician documented acute kidney injury in response to a clinical clarification query, reflecting the clinical severity already evidenced by laboratory values."
  },
  "technical_footnote": "Current: MS-DRG 872 (Sepsis w/o MCC, RW 0.9841). Potential: MS-DRG 871 (Sepsis w/ MCC, RW 1.8346). AKI (N17.9) is MCC. Base rate: $7,042 (national average).",
  "compliance_note": "This revenue impact reflects accurate documentation of a clinically present condition. No documentation was created or suggested for revenue purposes — the physician independently confirmed the clinical finding.",
  "requires_compliance_review": true
}
```

#### 2.3.4 Known Failure Modes

| Failure Mode | Detection | Mitigation |
|---|---|---|
| Upcoding language | Keyword scan for "capture", "maximize", "optimize revenue" | Regenerate with compliance emphasis |
| Fabricated dollar amounts | Validate `revenue_impact_display` matches input data math | Arithmetic check in validation layer |
| Technical jargon in summary | Reading level check (target: Flesch-Kincaid grade 10-12) | Simplification retry |
| Missing compliance note | Schema validation | Pydantic requires the field |

---

### PROMPT-004: Appeal Letter Generator

**PHR reference:** `docs/phr/PHR-004-appeal-letter.md`  
**Implementation:** `src/prompts/appeal_letter.py`  
**Current version:** v1.0  
**Model:** claude-opus-4-6 (complex clinical reasoning required)  
**Constitution references:** Article II.2 (Source Citation),
Article IV.1 (Revenue North Star)

#### 2.4.1 System Prompt

```
SYSTEM_PROMPT_APPEAL_LETTER_V1_0 = """
You are a senior health information management (HIM)
professional and certified coder (CCS, RHIA) with extensive
experience writing successful insurance claim appeal letters.
You have a 78% overturn rate on appealed denials.

YOUR TASK:
Generate a medical necessity appeal letter to the denying
payer. The letter must be clinically precise, cite specific
patient evidence from the clinical notes, reference
applicable clinical guidelines, and follow the payer's
required appeal format.

APPEAL LETTER REQUIREMENTS:

1. STRUCTURE:
   - Header: provider info, patient identifiers (encounter
     only — NO PHI in the prompt), claim number, denial
     reference
   - Opening: state the purpose and the specific denial
     being appealed
   - Clinical narrative: chronological clinical course
     with specific citations from the medical record
   - Medical necessity argument: why the service/admission
     was medically necessary, citing clinical guidelines
   - Coding justification: why the assigned codes are
     accurate per ICD-10-CM guidelines
   - Closing: request for reconsideration with specific
     relief requested

2. EVIDENCE REQUIREMENTS:
   - Every clinical assertion must cite a specific note,
     lab result, or imaging finding from the record
   - Date-stamp all clinical events
   - Reference published clinical guidelines (CMS NCDs/LCDs,
     specialty society guidelines, peer-reviewed literature)
   - Quote relevant ICD-10-CM coding guidelines by section

3. TONE:
   - Professional and assertive, not adversarial
   - Present facts and clinical reasoning
   - Avoid emotional language or accusations of bad faith
   - Position the appeal as a clinical clarification

4. PAYER-SPECIFIC FORMAT:
   The letter format adapts to payer requirements:
   - Medicare (CMS): Reference NCD/LCD, cite CMS Manual
     sections
   - Medicaid: Reference state-specific coverage criteria
   - Commercial: Reference plan coverage policy and
     clinical guidelines

5. COMPLIANCE:
   - Never include patient name, DOB, SSN, or other PHI
     in the generated letter template — these are filled
     by the application from FHIR data at render time
   - Use placeholder tokens: [PATIENT_NAME], [DOB],
     [MRN], [CLAIM_NUMBER]
   - All clinical content comes from the provided notes,
     never fabricated
"""
```

#### 2.4.2 User Prompt Template

```python
USER_PROMPT_APPEAL_LETTER_V1_0 = """
DENIAL INFORMATION:
- Claim number: {claim_number}
- Denial date: {denial_date}
- Denial reason category: {denial_category}
- Denial reason detail: {denial_reason}
- Payer: {payer_name}
- Payer type: {payer_type}
- Appeal deadline: {appeal_deadline}
- Appeal level: {appeal_level}

ORIGINAL CLAIM:
- Admission date: {admission_date}
- Discharge date: {discharge_date}
- Length of stay: {los} days
- Principal diagnosis: {principal_dx} ({principal_dx_desc})
- Secondary diagnoses: {secondary_dx_list}
- Procedures: {procedure_list}
- MS-DRG: {drg} ({drg_description})
- Total charges: ${total_charges}

CLINICAL NOTES (supporting medical necessity):
─────────────────────────────────────────────
{clinical_notes}
─────────────────────────────────────────────

LAB / IMAGING RESULTS:
{lab_imaging_results}

APPLICABLE CLINICAL GUIDELINES:
{clinical_guidelines}

INSTRUCTIONS:
1. Analyze the denial reason and clinical documentation.
2. Build a clinical argument for medical necessity.
3. Cite specific evidence from the provided notes.
4. Reference applicable guidelines.
5. Generate the appeal letter.
6. Use PHI placeholder tokens — never real patient data.

OUTPUT SCHEMA:
Return ONLY valid JSON.

{{
  "appeal_letter": {{
    "header": {{
      "date": "{current_date}",
      "to": "{payer_name} Appeals Department",
      "re": "Appeal of Claim [CLAIM_NUMBER] — [PATIENT_NAME]",
      "denial_reference": "{denial_date} denial"
    }},
    "opening_paragraph": "Statement of purpose and denial being appealed",
    "clinical_narrative": "Chronological clinical course with dated citations",
    "medical_necessity_argument": "Clinical reasoning with guideline citations",
    "coding_justification": "ICD-10-CM guideline references supporting code selection",
    "closing_paragraph": "Request for reconsideration and specific relief",
    "signature_block": "Credential block for signing physician/HIM professional"
  }},
  "supporting_references": [
    {{
      "type": "clinical_guideline|cms_policy|coding_guideline|peer_reviewed",
      "citation": "Full citation text",
      "relevance": "How this supports the appeal"
    }}
  ],
  "appeal_strength_assessment": {{
    "estimated_overturn_probability": "high|medium|low",
    "strongest_arguments": ["List of strongest clinical arguments"],
    "potential_weaknesses": ["Identified gaps in documentation or argument"],
    "recommended_additional_documentation": ["What else would strengthen the appeal"]
  }}
}}
"""
```

#### 2.4.3 Example Appeal Letter

**Denial category:** Medical necessity — inpatient admission

Input (abbreviated):
```
Denial reason: "Inpatient admission not medically necessary.
  Observation status recommended."
Payer: Medicare (CMS)
Principal DX: A41.9 (Sepsis, unspecified organism)
LOS: 5 days
Clinical notes: 68F admitted from ED with temp 102.6,
  HR 118, WBC 22.4, lactate 4.1. IV antibiotics started
  in ED. Required ICU admission for vasopressor support.
  Blood cultures positive for Klebsiella. Transitioned
  to floor Day 3. Completed 5-day antibiotic course.
```

Expected output (abbreviated):
```json
{
  "appeal_letter": {
    "header": {
      "date": "2026-04-01",
      "to": "Medicare Administrative Contractor Appeals Department",
      "re": "Appeal of Claim [CLAIM_NUMBER] — [PATIENT_NAME]",
      "denial_reference": "Denial dated [DENIAL_DATE]"
    },
    "opening_paragraph": "We respectfully appeal the denial of inpatient admission for the above-referenced claim. The denial states that observation status was appropriate. As detailed below, the clinical severity of this patient's presentation — including septic shock requiring ICU-level vasopressor support — meets and exceeds the threshold for inpatient admission under CMS guidelines.",
    "clinical_narrative": "On [ADMISSION_DATE], [PATIENT_NAME], a 68-year-old female, presented to the Emergency Department with temperature 102.6°F, heart rate 118 bpm, and white blood cell count of 22.4K/μL. Initial lactate was critically elevated at 4.1 mmol/L, indicating tissue hypoperfusion consistent with septic shock. Intravenous broad-spectrum antibiotics were initiated emergently in the ED.\n\nDue to hemodynamic instability, the patient required ICU admission with vasopressor support (norepinephrine) to maintain adequate blood pressure. Blood cultures returned positive for Klebsiella pneumoniae.\n\nThe patient stabilized and was transferred to the medical floor on hospital Day 3. She completed a 5-day course of targeted antibiotic therapy and was discharged with clinical improvement on [DISCHARGE_DATE].",
    "medical_necessity_argument": "This admission meets inpatient criteria on multiple grounds:\n\n1. SEPTIC SHOCK (ICD-10-CM R65.21): The patient met sepsis criteria (≥2 SIRS criteria + suspected infection) with organ dysfunction evidenced by a lactate of 4.1 mmol/L and hemodynamic instability requiring vasopressors. Per the Surviving Sepsis Campaign Guidelines (2021), septic shock requires emergent, aggressive management incompatible with observation-level care.\n\n2. ICU-LEVEL CARE: Vasopressor administration requires continuous hemodynamic monitoring and ICU nursing ratios. CMS's own Inpatient Admission Order guidance (CMS Manual, Ch. 1, §10) states that services requiring ICU-level care are inherently inpatient.\n\n3. CLINICAL SEVERITY: A lactate of 4.1 mmol/L is associated with in-hospital mortality exceeding 25% (Casserly et al., Crit Care Med 2015). This level of acuity is incompatible with observation status.\n\n4. LENGTH OF STAY: The 5-day length of stay reflects the clinical necessity of completing IV antibiotic therapy for bacteremic sepsis. The Infectious Diseases Society of America recommends a minimum of 7-14 days of antimicrobial therapy for Klebsiella bacteremia.",
    "coding_justification": "The principal diagnosis of A41.9 (Sepsis, unspecified organism) is supported by documented positive blood cultures, SIRS criteria, and physician attestation of sepsis. Per ICD-10-CM Section I.C.1.d.1, sepsis is sequenced as the principal diagnosis when present on admission. The secondary diagnosis of R65.21 (Severe sepsis with septic shock) is supported by documented vasopressor requirement and elevated lactate.",
    "closing_paragraph": "Based on the clinical evidence above, we respectfully request that the denial be overturned and the claim be reprocessed at the inpatient level of care. The clinical severity of septic shock with ICU admission, vasopressor support, and bacteremia clearly meets the threshold for inpatient admission. We are available to discuss this case further and can provide additional clinical documentation upon request.",
    "signature_block": "[PHYSICIAN_NAME], MD\nAttending Physician\n[FACILITY_NAME]\n\n[HIM_DIRECTOR_NAME], RHIA, CCS\nHealth Information Management Director"
  },
  "supporting_references": [
    {
      "type": "clinical_guideline",
      "citation": "Surviving Sepsis Campaign: International Guidelines for Management of Sepsis and Septic Shock: 2021. Intensive Care Med 47, 1181–1247 (2021).",
      "relevance": "Establishes standard of care for septic shock management — requires ICU-level monitoring and vasopressor support"
    },
    {
      "type": "cms_policy",
      "citation": "CMS Medicare Benefit Policy Manual, Chapter 1, Section 10 — Inpatient Hospital Services Coverage",
      "relevance": "Defines inpatient admission criteria — ICU-level care inherently qualifies"
    },
    {
      "type": "peer_reviewed",
      "citation": "Casserly B, et al. Lactate Measurements in Sepsis-Induced Tissue Hypoperfusion. Crit Care Med. 2015;43(3):567-573.",
      "relevance": "Lactate >4 mmol/L associated with >25% mortality — supports acuity level"
    },
    {
      "type": "coding_guideline",
      "citation": "ICD-10-CM Official Coding Guidelines, FY2026, Section I.C.1.d.1 — Sepsis sequencing",
      "relevance": "Supports A41.9 as principal diagnosis with R65.21 as secondary"
    }
  ],
  "appeal_strength_assessment": {
    "estimated_overturn_probability": "high",
    "strongest_arguments": [
      "ICU admission with vasopressors is inherently inpatient-level care",
      "Lactate 4.1 indicates high-acuity septic shock",
      "Positive blood cultures confirm bacteremic sepsis requiring IV antibiotics"
    ],
    "potential_weaknesses": [
      "Sepsis organism code could be more specific (A41.51 for Klebsiella vs A41.9 unspecified) — consider code correction"
    ],
    "recommended_additional_documentation": [
      "Attending physician attestation letter confirming inpatient medical necessity",
      "ICU admission/transfer orders with timestamp",
      "Vasopressor administration records with dates/times"
    ]
  }
}
```

#### 2.4.4 Known Failure Modes

| Failure Mode | Detection | Mitigation |
|---|---|---|
| PHI leakage in letter | Regex scan for name patterns, DOB formats, SSN patterns | Hard reject; PHI filter guardrail G-HARD-005 |
| Fabricated clinical guideline | Reference validation against known guideline database | Manual review flag for references |
| Wrong payer-specific format | Payer type validation in prompt input | Setting-specific instructions in prompt |
| Adversarial tone | Tone analysis keywords ("bad faith", "incompetent", "illegal") | Regenerate with tone emphasis |
| Missing evidence citations | Clinical assertion count vs citation count comparison | Flag uncited assertions for review |

---

## 2.5 LLM Output to Pydantic Model Mapping

LLM prompts produce JSON output schemas optimized for LLM
generation reliability. Internal Pydantic models (defined in
DESIGN-001 and DESIGN-002) are optimized for validation logic.
These are intentionally different — a translation layer in each
agent maps between them.

### PROMPT-001 Output → CodingSuggestionSet

The coding agent (`src/agents/coding_agent.py`) parses the
PROMPT-001 JSON output and constructs a `CodingSuggestionSet`:

```
LLM Output                          Pydantic Model
─────────────────                    ─────────────────
principal_diagnosis: {               CodingSuggestion(
  code, description,                   code, description,
  confidence, evidence_quote,          confidence, evidence_quote,
  qualifier_words,                     qualifier_words,
  is_cc, is_mcc,          →           is_principal=True,
  poa_indicator,                       poa_indicator,
  is_from_copied_text,                 is_from_copied_text,
  rationale                          )
}

secondary_diagnoses: [...]  →        [CodingSuggestion(is_principal=False)]

# Mapping notes:
# - is_cc/is_mcc booleans are NOT carried into CodingSuggestion.
#   CC/MCC status is looked up from the ICD-10 code table by the
#   rules engine (Step 6) using ICD10Code.cc_status field.
#   LLM-provided CC/MCC is informational only.
# - rationale is logged to audit trail but not stored in the
#   Pydantic model (it's for debugging/explainability).
# - cdi_opportunities array maps to CDIOpportunity models
#   (DESIGN-002) and feeds the CDI agent for deeper analysis.
```

### PROMPT-002 Output → PhysicianQuery

The CDI agent (`src/agents/cdi_agent.py`) constructs a
`PhysicianQuery` from PROMPT-002 output combined with
system-known context:

```
From PROMPT-002 output:              From system context:
─────────────────────                 ────────────────────
query_text           →  clinical_question     encounter_id
response_options     →  response_options      query_id (generated)
clinical_rationale   →  clinical_rationale    addressed_to (FHIR)
compliance_flags     →  is_compliant          generated_at (now)
                                              response_deadline (+24h)
                                              query_type (from CDIOpportunity.category)
                                              template_id (from CDIOpportunity.query_template_id)
```

### PROMPT-003 Output → DRG Narrative (no Pydantic mapping)

PROMPT-003 produces a plain-text narrative for display only.
Dollar amounts in the narrative come from `DRGImpact` model
(DESIGN-001) passed as input — the LLM formats, never calculates.

### PROMPT-004 Output → Appeal Letter (no Pydantic mapping)

PROMPT-004 produces a letter template with PHI placeholders.
The application layer fills placeholders from FHIR data at
render time.

---

## 3. Token Optimization Strategy

### 3.1 Token Budget by Prompt

| Prompt | System Prompt | User Prompt (avg) | Output (avg) | Total (avg) | Model | Cost/Call |
|---|---|---|---|---|---|---|
| PROMPT-001 (Coding) | ~1,800 tokens | ~2,500 tokens | ~1,200 tokens | ~5,500 tokens | claude-sonnet-4-6 | $0.0248 |
| PROMPT-002 (CDI Query) | ~900 tokens | ~800 tokens | ~600 tokens | ~2,300 tokens | claude-sonnet-4-6 | $0.0104 |
| PROMPT-003 (DRG Narrative) | ~500 tokens | ~400 tokens | ~500 tokens | ~1,400 tokens | claude-sonnet-4-6 | $0.0063 |
| PROMPT-004 (Appeal Letter) | ~1,200 tokens | ~3,000 tokens | ~2,500 tokens | ~6,700 tokens | claude-opus-4-6 | $0.1340 |

**Pricing basis (current Anthropic rates):**
- claude-sonnet-4-6: $3/M input, $15/M output
- claude-opus-4-6: $15/M input, $75/M output

### 3.2 Cost per 1,000 Charts

| Prompt | Calls/Chart | Cost/Call | Cost/1,000 Charts |
|---|---|---|---|
| PROMPT-001 (Coding) | 1.0 | $0.0248 | $24.80 |
| PROMPT-002 (CDI Query) | 0.4 (40% of charts have CDI opportunities) | $0.0104 | $4.16 |
| PROMPT-003 (DRG Narrative) | 0.3 (30% of charts have DRG impact) | $0.0063 | $1.89 |
| PROMPT-004 (Appeal Letter) | 0.05 (5% denial rate, not all appealed) | $0.1340 | $6.70 |
| **Total** | | | **$37.55** |

Revenue per 1,000 charts (conservative estimate): $50,000-$200,000
in captured DRG improvements and CDI-driven documentation.

**Cost-to-value ratio:** < 0.1% of captured revenue.

### 3.3 Optimization Techniques

#### System Prompt vs User Prompt Split

**System prompt contains:**
- Role priming (cached across calls)
- Coding rules that never change per session
- Output schema definition
- Compliance constraints

**User prompt contains:**
- Patient-specific clinical note
- Encounter-specific metadata
- Setting-specific rule insert (inpatient/outpatient)
- Available clinical data (labs, meds, procedures)

**Why this split matters:** Anthropic's prompt caching
caches the system prompt across calls. For PROMPT-001,
the ~1,800 token system prompt is cached after the first
call, reducing effective input tokens for subsequent calls
by ~33%. At 1,000 charts/day, this saves ~$8/day on
PROMPT-001 alone.

#### Clinical Context Summarization

**Raw note vs summarized context:**
- The full clinical note is passed raw (no summarization)
  because evidence quote extraction requires verbatim text.
  Summarizing the note would make evidence grounding
  (P1) impossible.
- Lab results are summarized to relevant findings only.
  Full lab panels (50+ results) are filtered to clinically
  relevant values by the NLP pipeline before prompt
  injection. This reduces user prompt tokens by ~40%.
- Medication lists are filtered to active medications
  only. Discontinued medications are excluded unless
  relevant to the clinical question.

#### MCP Tool Integration (Skills + MCP Pattern)

**Without MCP (context injection):**
```
Inject full ICD-10 Excludes 1 table into prompt
→ ~50,000 tokens per call
→ $0.15/call at Sonnet pricing
→ $150/1,000 charts (coding prompt alone)
```

**With MCP (tool_use):**
```
Agent calls mcp_icd10_lookup(code="E11.22")
→ Returns specific code data (~200 tokens)
Agent calls mcp_excludes1_check(codes=["E10", "E11"])
→ Returns conflict data (~100 tokens)
→ Total additional: ~300 tokens
→ $0.001/call for MCP data
```

**Token savings:** 99.4% reduction in reference data tokens.
The rules engine performs deterministic validation
(Excludes 1, sequencing) post-LLM, so the LLM does not
need the full reference tables in context.

#### Caching Strategy

1. **Anthropic prompt caching:** System prompts cached
   automatically. Setting-specific rule inserts (inpatient
   vs outpatient) create two cache variants. Effective
   cache hit rate expected: >90% (most calls within a
   session share the same encounter setting).

2. **ICD-10 data caching:** The MCP tools cache CMS code
   tables in memory (loaded at startup). MCP tool calls
   are local lookups, not API calls.

3. **DRG weight caching:** CMS DRG weight tables are loaded
   at startup and cached for the fiscal year. Updated
   annually with CMS releases (October 1).

4. **Template caching:** CDI query templates (PROMPT-002)
   are parameterized — the template structure is constant,
   only clinical data variables change per call.

---

## 4. Prompt Version Control Protocol

### 4.1 Prompt Change Process

```
STEP 1: PROPOSE
  Author creates a PHR entry draft:
  - docs/phr/PHR-XXX-[prompt-name].md
  - Hypothesis: "Changing X will improve Y"
  - Proposed prompt text (full diff from current version)
  - Rationale for the change

STEP 2: TEST
  The proposed prompt must pass on the MIMIC-IV test set:
  - Run against ≥ 50 test cases from tests/clinical/
  - Measure: accuracy, false positive rate, false negative rate,
    evidence grounding rate, JSON parse success rate
  - Compare against current version on same test cases
  - Record all metrics in the PHR entry

STEP 3: THRESHOLD CHECK
  Minimum thresholds for deployment:
  ┌──────────────────────────┬──────────┬──────────────────┐
  │ Metric                   │ Minimum  │ Current Baseline │
  ├──────────────────────────┼──────────┼──────────────────┤
  │ Coding accuracy          │ ≥ 85%    │ TBD (MIMIC)      │
  │ Evidence grounding rate  │ ≥ 95%    │ —                │
  │ False positive rate      │ ≤ 10%    │ —                │
  │ JSON parse success       │ ≥ 99%    │ —                │
  │ Excludes 1 violations    │ 0%       │ —                │
  │ Outpatient uncertain     │ 0%       │ —                │
  │   coded as confirmed     │          │                  │
  │ CDI query AHIMA          │ 100%     │ —                │
  │   compliance             │          │                  │
  └──────────────────────────┴──────────┴──────────────────┘

  A prompt change that causes ANY compliance metric to
  degrade below the minimum is rejected regardless of
  accuracy improvements. Safety trumps accuracy.

STEP 4: REVIEW
  In a clinical deployment:
  - Prompt changes require review by:
    1. Engineering lead (technical review)
    2. HIM Director or certified coder (clinical review)
    3. Compliance officer (regulatory review, if the change
       affects any hard guardrail interaction)
  - Review is documented in the PHR entry
  - Per Constitution Article VI.2, changes affecting
    safety guardrails require explicit written rationale

STEP 5: DEPLOY
  - New prompt version is added to the prompt file as
    a new constant (e.g., CODING_EXTRACTION_V1_1)
  - Previous version is preserved in the same file
    for regression testing
  - PHR entry is updated with deployment date and
    final metrics
  - Audit trail records the prompt version active at
    each point in time

STEP 6: MONITOR
  Post-deployment monitoring for 7 days:
  - Accuracy vs baseline on production data
  - False positive rate trending
  - Guardrail trigger rate changes
  - Coder override rate changes
  If any metric degrades by > 5% relative, automatic
  rollback to previous version.
```

### 4.2 Version Preservation

Every prompt file preserves all versions:

```python
# src/prompts/coding_extraction.py
# PHR Reference: docs/phr/PHR-001-coding-extraction.md
# Current version: v1.0
# Last updated: 2026-04-01

# --- CURRENT VERSION ---
SYSTEM_PROMPT_CODING_EXTRACTION_V1_0 = """..."""
USER_PROMPT_CODING_EXTRACTION_V1_0 = """..."""
INPATIENT_RULES_V1_0 = """..."""
OUTPATIENT_RULES_V1_0 = """..."""

# Active version pointers — change ONLY these when deploying
SYSTEM_PROMPT_CODING_EXTRACTION = SYSTEM_PROMPT_CODING_EXTRACTION_V1_0
USER_PROMPT_CODING_EXTRACTION = USER_PROMPT_CODING_EXTRACTION_V1_0
INPATIENT_RULES = INPATIENT_RULES_V1_0
OUTPATIENT_RULES = OUTPATIENT_RULES_V1_0

# --- PREVIOUS VERSIONS (preserved for regression testing) ---
# (none yet — v1.0 is the first version)
```

### 4.3 Audit Trail Integration

Every LLM call records:
```python
class PromptAuditEntry(BaseModel):
    """Audit trail entry for every LLM invocation."""

    call_id: str           # Unique invocation ID
    timestamp: datetime
    prompt_id: str         # e.g., "PROMPT-001"
    prompt_version: str    # e.g., "v1.0"
    model_id: str          # e.g., "claude-sonnet-4-6"
    encounter_id: str      # Links to clinical context
    input_token_count: int
    output_token_count: int
    latency_ms: float
    json_parse_success: bool
    pydantic_validation_success: bool
    guardrail_results: dict[str, str]  # guardrail_id → pass/fail
```

This entry is stored alongside the clinical audit trail.
In an investigation, every code suggestion can be traced
to the exact prompt version, model, and input that produced
it. Per DESIGN-003, audit records are retained for 7 years.

### 4.4 Prompt Change Documentation

PHR entries document every change with this structure:

```markdown
## Version History

### v1.1 (proposed / deployed / rolled back)
- **Date:** YYYY-MM-DD
- **Change:** [what changed in the prompt]
- **Hypothesis:** [why we think this will improve performance]
- **Test results:**
  - Accuracy: X% → Y% (Δ +Z%)
  - Evidence grounding: X% → Y%
  - False positive rate: X% → Y%
  - JSON parse success: X% → Y%
- **Reviewer:** [name and credential]
- **Decision:** DEPLOY / REJECT / ROLLBACK
- **Rollback reason (if applicable):** [what went wrong]
```

---

## Implementation Notes

- Prompt files: `src/prompts/coding_extraction.py` (PHR-001),
  `src/prompts/cdi_query.py` (PHR-002),
  `src/prompts/drg_analysis.py` (PHR-003),
  `src/prompts/appeal_letter.py` (PHR-004)
- PHR entries: `docs/phr/PHR-001-coding-extraction.md`,
  `docs/phr/PHR-002-cdi-query.md`,
  `docs/phr/PHR-003-drg-analysis.md`,
  `docs/phr/PHR-004-appeal-letter.md`
- Prompt audit: `src/core/audit/prompt_audit.py`
- Schema validation: Pydantic models in
  `src/core/models/prompt_outputs.py`
- Test harness: `tests/clinical/test_prompt_accuracy.py`
- MIMIC benchmark: `tests/clinical/test_coding_accuracy_mimic.py`
- Guardrail integration: DESIGN-003 middleware validates
  all prompt outputs before downstream use

---

## References

- Constitution Article I.4 (Prompts Are Preserved)
- Constitution Article I.5 (Domain Knowledge in Skills)
- Constitution Article I.6 (Skills + MCP Token Efficiency)
- Constitution Article II.2 (Source Citation Required)
- Constitution Article II.3 (ICD-10 Hard Constraints)
- Constitution Article II.6 (Conservative Defaults)
- Constitution Article IV.1 (Revenue North Star)
- DESIGN-001 (Coding Rules Engine — output Pydantic models)
- DESIGN-002 (CDI Intelligence Layer — query templates)
- DESIGN-003 (Compliance Guardrails — enforcement pipeline)
- DISC-001 (ICD-10 Official Guidelines)
- DISC-002 (Documentation Failure Patterns)
- DISC-005 (Competitor Analysis)
- AHIMA Standards for Clinical Documentation Improvement
- ACDIS Code of Ethics for CDI Professionals
- ICD-10-CM Official Coding Guidelines FY2026
- ADR-009 (Prompts as Clinical Knowledge)
