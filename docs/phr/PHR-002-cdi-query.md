# PHR-002: CDI Physician Query Generator Prompt

**Status:** ACTIVE  
**Current version:** v1.0  
**Date created:** 2026-04-01  
**Implementation:** `src/prompts/cdi_query.py`  
**Spec reference:** `specs/04-prompt-engineering-architecture.md` Section 2.2  
**Model:** claude-sonnet-4-6  
**Constitution references:** Article II.2 (Source Citation),
Article II.6 (Conservative Defaults)  
**Compliance:** AHIMA Standards for CDI, ACDIS Code of Ethics

---

## Purpose

This prompt generates AHIMA-compliant, non-leading physician
queries from detected CDI opportunities. The query presents
objective clinical evidence and asks an open-ended question
that the physician can answer with "Yes", "No", or
"Clinically undetermined."

This prompt is the bridge between AI-detected documentation
gaps and physician action. Query quality directly determines
CDI response rates (target >80%) and acceptance rates
(target >70%).

---

## Design Decisions

### Why AHIMA compliance is enforced at the prompt level
The prompt itself contains the AHIMA compliance rules
(non-leading, no revenue language, multiple response options).
This is the first line of defense. The guardrail layer
(DESIGN-003) provides a second check, but catching leading
queries at generation time is more efficient than generating
and rejecting them.

### Why clinical rationale never mentions revenue
Per AHIMA Standards and ACDIS Code of Ethics, CDI queries
must be motivated by clinical accuracy, not revenue capture.
The prompt explicitly prohibits mentioning revenue, DRG,
reimbursement, or coding in the query. The clinical rationale
section explains why accurate documentation matters for
patient care — medication decisions, care continuity,
treatment planning.

### Why response options always include "No"
A query where "No" is not a reasonable answer is, by
definition, a leading query. The prompt requires every query
to include a "No" option that is accessible and not framed
as the "wrong" answer. This is tested by the compliance
flag `has_no_option`.

### Why tone is specified as "collegial"
Physicians are the clinical experts. CDI queries are requests
for clarification, not demands for documentation. An
adversarial tone reduces response rates. The prompt primes
the LLM as a peer CDI specialist, not an auditor.

---

## Prompt Components

- **System prompt:** `SYSTEM_PROMPT_CDI_QUERY_V1_0`
  (~900 tokens) — CDI specialist role, AHIMA rules,
  non-leading requirements, tone guidance
- **User prompt:** `USER_PROMPT_CDI_QUERY_V1_0`
  (~800 tokens avg with clinical evidence)
- **Output:** Structured JSON with query text, response
  options, clinical rationale, compliance flags (~600 tokens avg)

---

## Test Cases

### Test Case 1: AKI on CKD
- **Input:** Creatinine 1.8→3.2 in CKD stage 3 patient,
  nephrotoxics held, "worsening renal function" in note
- **Expected:** Non-leading query asking about superimposed
  AKI. Options include "progression of CKD" (No equivalent).
  Clinical rationale mentions nephrology follow-up.
- **Result:** PASS (v1.0)

### Test Case 2: Sepsis Undocumented
- **Input:** SIRS criteria met (3/4), pneumonia documented,
  lactate 3.2, IV antibiotics
- **Expected:** Non-leading query asking whether clinical
  presentation represents sepsis. Does NOT suggest "this
  is sepsis." Options include "infectious process without
  systemic sepsis."
- **Result:** PASS (v1.0)

### Test Case 3: Heart Failure Specificity
- **Input:** "Heart failure" documented, EF 30%, BNP 1840,
  IV furosemide
- **Expected:** Specificity query asking physician to clarify
  type and acuity. Options include specific types (acute
  systolic, acute on chronic) and "as documented is accurate."
- **Result:** PASS (v1.0)

---

## Version History

### v1.0 (ACTIVE)
- **Date:** 2026-04-01
- **Change:** Initial prompt design
- **Design basis:** DISC-002 (documentation gaps), DESIGN-002
  (CDI query templates), AHIMA Standards
- **Test results:** Pending clinical validation
- **Reviewer:** Engineering team
- **Decision:** DEPLOY as initial version

---

## Known Failure Modes

| Mode | Detection | Mitigation |
|---|---|---|
| Leading question | Compliance flag + AHIMA checklist | Regenerate |
| Revenue language leaked | Keyword scan | Hard reject + regenerate |
| Missing "No" option | Schema validation | Pydantic rejects |
| Query too long for mobile | Char count (max 1,500) | Truncation prompt |
| Clinical rationale mentions coding | Keyword scan | Hard reject |
