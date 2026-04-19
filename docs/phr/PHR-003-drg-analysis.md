# PHR-003: DRG Impact Narrative Prompt

**Status:** ACTIVE  
**Current version:** v1.0  
**Date created:** 2026-04-01  
**Implementation:** `src/prompts/drg_analysis.py`  
**Spec reference:** `specs/04-prompt-engineering-architecture.md` Section 2.3  
**Model:** claude-sonnet-4-6  
**Constitution references:** Article IV.1 (Revenue North Star)

---

## Purpose

This prompt generates plain-English revenue impact narratives
from DRG impact data. The audience is HIM directors and CFOs
who understand business but not medical coding terminology.

The narrative translates "MS-DRG 872 → MS-DRG 871 via N17.9 MCC
capture" into "When the physician confirmed the presence of acute
kidney injury, the documentation now fully reflects the clinical
complexity of this sepsis case, resulting in a $5,988 difference."

---

## Design Decisions

### Why plain English, not coding terminology
The DRG narrative is for executives who make budget decisions.
If they cannot understand the impact, they cannot fund the
CDI program. ICD codes appear only in technical footnotes.

### Why compliance framing is mandatory
Every narrative must frame documentation improvements as
clinical accuracy, never as upcoding. The compliance note
explicitly states that revenue impact reflects documentation
accuracy. This protects against OIG audit findings of
revenue-motivated documentation practices.

### Why dollar amounts must match input data
The prompt receives pre-calculated DRG data from the rules
engine (DESIGN-001). The LLM does not calculate dollar amounts
— it formats them. This prevents arithmetic errors in
financial outputs.

---

## Prompt Components

- **System prompt:** `SYSTEM_PROMPT_DRG_NARRATIVE_V1_0`
  (~500 tokens)
- **User prompt:** `USER_PROMPT_DRG_NARRATIVE_V1_0`
  (~400 tokens with DRG data)
- **Output:** Executive summary, before/after, compliance
  note (~500 tokens)

---

## Test Cases

### Test Case 1: Sepsis MCC Capture
- **Input:** DRG 872→871 via AKI documentation, $5,988 impact
- **Expected:** Plain-English summary explaining AKI documentation
  improved severity classification. Compliance note states
  no documentation was suggested for revenue purposes.
- **Result:** PASS (v1.0)

### Test Case 2: Heart Failure Specificity
- **Input:** DRG 293→291 via HFrEF specificity, $3,200 impact
- **Expected:** Narrative explaining heart failure type
  clarification changed complexity level.
- **Result:** PASS (v1.0)

### Test Case 3: High-Impact Case ($5K+ triggers compliance review)
- **Input:** DRG change with $8,500 impact
- **Expected:** `requires_compliance_review: true` in output.
  Narrative does not change in tone despite high impact.
- **Result:** PASS (v1.0)

---

## Version History

### v1.0 (ACTIVE)
- **Date:** 2026-04-01
- **Change:** Initial prompt design
- **Design basis:** DESIGN-001 (DRG impact model),
  Constitution Article IV.1 (Revenue North Star)
- **Test results:** Pending production validation
- **Reviewer:** Engineering team
- **Decision:** DEPLOY as initial version

---

## Known Failure Modes

| Mode | Detection | Mitigation |
|---|---|---|
| Upcoding language | Keyword scan | Regenerate |
| Fabricated dollar amounts | Math validation vs input | Arithmetic check |
| Technical jargon in summary | Reading level check | Simplification retry |
| Missing compliance note | Schema validation | Pydantic rejects |
