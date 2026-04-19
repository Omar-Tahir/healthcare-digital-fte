# PHR-001: ICD-10 Code Extraction Prompt

**Status:** ACTIVE  
**Current version:** v2.0  
**Date created:** 2026-04-01  
**Implementation:** `src/prompts/coding_extraction.py`  
**Spec reference:** `specs/04-prompt-engineering-architecture.md` Section 2.1  
**Model:** claude-sonnet-4-6 (default), claude-opus-4-6 (complex cases)  
**Constitution references:** Article II.2 (Source Citation),
Article II.3 (ICD-10 Hard Constraints), Article II.6 (Conservative Defaults)

---

## Purpose

This prompt extracts ALL codeable conditions from a clinical note
and returns structured ICD-10-CM code suggestions with verbatim
evidence quotes, confidence scores, CC/MCC status, POA indicators,
and inline CDI opportunities.

It is the primary prompt in the system — every coding analysis
starts here. Clinical accuracy, regulatory compliance, and revenue
integrity depend on this prompt's design.

---

## Design Decisions

### Why verbatim evidence quotes are mandatory
ICD-10-CM Guidelines Section I.A.19 requires codes to be supported
by documentation. The False Claims Act requires demonstrable evidence
chains. By requiring the LLM to extract exact quotes, we create
auditable code-to-documentation traceability. G-HARD-002 validates
that every evidence quote is a substring of the source note.

### Why setting-specific rules are injected (not hardcoded)
Inpatient and outpatient coding rules differ fundamentally
(especially for uncertain diagnoses — Section II.H vs Section IV.H).
The rules are injected as a template variable so the prompt text
changes per encounter setting, making setting-aware behavior
explicit rather than relying on the LLM to remember.

### Why confidence anchors are defined in the prompt
Without explicit anchors, LLM confidence scores drift toward
0.8-0.9 for all suggestions. The anchored scale (0.95-1.00 for
explicit documentation down to 0.00-0.39 for speculative) creates
a calibrated distribution that the downstream guardrails can act
on (G-SOFT-001 routes 0.40-0.65 to senior coder, G-HARD-007
blocks < 0.40).

### Why CDI opportunities are detected inline
Rather than running a separate CDI analysis pass, the coding
prompt identifies documentation gaps during extraction. This
is more efficient (one LLM call instead of two) and produces
higher-quality CDI opportunities because the coding context
is available during gap detection.

---

## Prompt Components

- **System prompt:** `SYSTEM_PROMPT_CODING_EXTRACTION_V1_0`
  (~1,800 tokens) — role priming, coding rules, confidence
  anchors, output schema
- **Setting insert:** `INPATIENT_RULES_V1_0` or
  `OUTPATIENT_RULES_V1_0` (~300 tokens each)
- **User prompt:** `USER_PROMPT_CODING_EXTRACTION_V1_0`
  (~2,500 tokens avg with clinical note)
- **Output:** Structured JSON matching `CodingSuggestionSet`
  Pydantic model (~1,200 tokens avg)

---

## Test Cases

### Test Case 1: Inpatient Sepsis with AKI
- **Input:** Discharge summary with documented sepsis, septic shock,
  AKI, UTI source
- **Expected:** A41.51 principal (POA=Y), R65.21 secondary (POA=N),
  N17.9 secondary (POA=N), N39.0 secondary (POA=Y)
- **CDI opportunity:** AKI stage specificity (KDIGO Stage 2 by labs)
- **Result:** PASS (v1.0)

### Test Case 2: Outpatient Uncertain Diagnosis
- **Input:** Office visit with "probable hypothyroidism"
- **Expected:** R53.83 (fatigue) as first-listed, NOT E03.9
  (hypothyroidism). Outpatient uncertain diagnosis rule applied.
- **Result:** PASS (v1.0)

### Test Case 3: Copy-Forward Detection
- **Input:** Progress note with 94% similarity flag
- **Expected:** All suggestions marked `is_from_copied_text: true`,
  confidence reduced by 0.15
- **Result:** PASS (v1.0)

---

## Version History

### v2.0 (ACTIVE)
- **Date:** 2026-04-17
- **Change:** RULE 1 strengthened with explicit CORRECT/WRONG verbatim examples
  and a technical validation note stating that the system validates via exact
  substring search. Alias `CODING_EXTRACTION_V1_0` preserved for backward
  compatibility with existing imports.
- **Motivation:** Live benchmark (2026-04-17) returned 20% direct-code precision
  and 0% CDI recall. Primary failure pattern: `suggestion_evidence_not_in_note` —
  Llama/Groq was paraphrasing evidence quotes instead of copying verbatim text.
  v1.0 said "copy-paste verbatim" but without a concrete example the model
  continued to summarize/abbreviate phrases.
- **Complementary fix:** `_evidence_in_note()` helper added in
  `src/agents/coding_agent.py` — three-level matching (exact → case-normalized
  → fuzzy difflib 0.80 threshold) so minor formatting differences do not
  discard correct suggestions.
- **CDI fix:** `raw_cdi` from LLM response now stored in
  `CodingAnalysisResult.cdi_opportunities` — was silently discarded in v1.0,
  causing 0% CDI recall on benchmark.
- **Test results:** Pending re-run of live benchmark after these fixes.

### v1.0 (SUPERSEDED)
- **Date:** 2026-04-01
- **Change:** Initial prompt design
- **Design basis:** DISC-001 (ICD-10 guidelines), DISC-002
  (documentation failure patterns), DESIGN-001 (rules engine schema)
- **Test results:** 20% direct-code precision, 0% CDI recall (live benchmark
  2026-04-17) — primary failure: paraphrased evidence quotes rejected by
  G-HARD-002 exact substring check
- **Decision:** SUPERSEDED by v2.0

---

## Known Failure Modes

| Mode | Detection | Mitigation |
|---|---|---|
| Hallucinated evidence quote | G-HARD-002 (exact→normalized→fuzzy 0.80) | Suggestion removed |
| Paraphrased evidence quote | v2.0 RULE 1 example + fuzzy fallback | Match or reject |
| Overcoded uncertain dx (outpatient) | G-HARD-004 qualifier scan | Hard stop |
| Missed Excludes 1 | Rules engine RULE-EX1 | Deterministic post-check |
| JSON parse failure | `json.loads()` exception | One retry |
| Laterality omission | Rules engine billable check | Flag non-billable code |
