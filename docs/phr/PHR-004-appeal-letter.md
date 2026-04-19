# PHR-004: Appeal Letter Generator Prompt

**Status:** ACTIVE  
**Current version:** v1.0  
**Date created:** 2026-04-01  
**Implementation:** `src/prompts/appeal_letter.py`  
**Spec reference:** `specs/04-prompt-engineering-architecture.md` Section 2.4  
**Model:** claude-opus-4-6 (complex clinical reasoning)  
**Constitution references:** Article II.2 (Source Citation),
Article IV.1 (Revenue North Star)

---

## Purpose

This prompt generates medical necessity appeal letters for
denied insurance claims. It builds a clinical argument from
patient documentation, cites applicable clinical guidelines,
and formats the letter for the specific payer's requirements.

Appeal letters require the highest-quality clinical reasoning
in the system — they must persuade a medical director that
the clinical evidence supports the contested service. This
is why PROMPT-004 uses claude-opus-4-6 instead of
claude-sonnet-4-6.

---

## Design Decisions

### Why claude-opus-4-6 for appeals
Appeal letters require multi-step clinical reasoning: analyzing
denial rationale, building counter-arguments from patient data,
citing relevant guidelines, and writing persuasive clinical prose.
This is the most complex reasoning task in the system. Sonnet
produces adequate appeal letters; Opus produces letters with
significantly stronger clinical argumentation and more precise
guideline citations. At 5% denial rate with selective appeals,
the volume is low enough that Opus pricing is acceptable.

### Why PHI placeholder tokens
The prompt generates a letter template with [PATIENT_NAME],
[DOB], [MRN] placeholders. The application fills these from
FHIR data at render time. This ensures PHI never appears in
LLM API calls or prompt logs. Per G-HARD-005, no PHI in
any log or API request.

### Why payer-specific format matters
Medicare, Medicaid, and commercial payers have different appeal
requirements. Medicare appeals cite NCDs/LCDs and CMS Manual
sections. Commercial appeals cite plan coverage policies. The
prompt receives `payer_type` as input and adapts the format.

### Why appeal strength assessment is included
The output includes an honest assessment of overturn probability,
strongest arguments, and weaknesses. This helps the HIM team
prioritize which appeals to pursue and what additional
documentation to gather. Per DISC-004, 65% of denials are never
appealed despite 40-70% overturn rates — better triage increases
appeal ROI.

---

## Prompt Components

- **System prompt:** `SYSTEM_PROMPT_APPEAL_LETTER_V1_0`
  (~1,200 tokens) — HIM professional role, appeal structure,
  evidence requirements, PHI rules
- **User prompt:** `USER_PROMPT_APPEAL_LETTER_V1_0`
  (~3,000 tokens avg with clinical notes)
- **Output:** Full appeal letter with references and strength
  assessment (~2,500 tokens avg)

---

## Test Cases

### Test Case 1: Medical Necessity Denial (Medicare)
- **Input:** Septic shock with ICU admission denied as
  "observation recommended"
- **Expected:** Letter citing Surviving Sepsis Campaign
  guidelines, CMS inpatient criteria, clinical severity
  indicators. Strength: HIGH.
- **Result:** PASS (v1.0)

### Test Case 2: Prior Authorization Missing
- **Input:** Elective procedure denied for missing PA
- **Expected:** Letter documenting clinical urgency that
  warranted proceeding without PA, citing clinical guidelines
  for the procedure. Strength: MEDIUM (PA denials harder to
  overturn).
- **Result:** PASS (v1.0)

### Test Case 3: Coding Disagreement
- **Input:** Payer downcoded DRG, disagreeing with MCC
  assignment
- **Expected:** Letter citing ICD-10-CM guidelines supporting
  the code assignment, with verbatim documentation evidence.
  Strength: HIGH (if documentation is clear).
- **Result:** PASS (v1.0)

---

## Version History

### v1.0 (ACTIVE)
- **Date:** 2026-04-01
- **Change:** Initial prompt design
- **Design basis:** DISC-004 (payer denial patterns),
  DISC-002 (documentation evidence), clinical appeal
  best practices
- **Test results:** Pending production validation
- **Reviewer:** Engineering team
- **Decision:** DEPLOY as initial version

---

## Known Failure Modes

| Mode | Detection | Mitigation |
|---|---|---|
| PHI leakage | Regex scan for names, DOB, SSN | G-HARD-005 + hard reject |
| Fabricated guideline | Reference validation | Manual review flag |
| Wrong payer format | Payer type validation | Setting-specific instructions |
| Adversarial tone | Tone keyword scan | Regenerate |
| Uncited clinical assertions | Assertion vs citation count | Flag for review |
