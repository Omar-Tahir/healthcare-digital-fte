# DESIGN-009 — Epic End-to-End Coding Pipeline

**Status:** COMPLETE  
**Date:** 2026-04-27  
**Author:** Healthcare Digital FTE

---

## 1. Purpose

Bridge the gap between the Epic FHIR sandbox (VALIDATE-004) and the CodingAgent
(VALIDATE-005). A single `EpicCodingPipeline.run()` call:

1. Fetches a real encounter + clinical notes + labs from Epic FHIR
2. Runs each note through the full CodingAgent pipeline (NLP → LLM → ICD-10 rules)
3. Merges results across notes (dedup by code, keep highest-confidence)
4. Writes a draft Claim back to Epic FHIR (status always = "draft" — Article II.1)

This is the production-grade data flow for the first hospital pilot (VALIDATE-006).

---

## 2. Data Structures

### Input
```python
class PipelineRequest(BaseModel):
    patient_id: str       # Epic FHIR patient ID
    encounter_id: str     # Epic FHIR encounter ID
```

### Output
```python
class PipelineResult(BaseModel):
    patient_id: str
    encounter_id: str
    notes_analyzed: int
    suggestions: list[CodingSuggestion]   # merged, deduped, sorted by DRG impact
    cdi_opportunities: list[CDIOpportunity]
    draft_claim_id: str | None            # None if Epic rejected the Claim POST
    processing_time_ms: float
    is_degraded: bool                     # True if any step degraded
```

---

## 3. Logic

### 3.1 Pipeline Steps

```
run(patient_id, encounter_id):
  1. get_encounter(encounter_id)          → FHIREncounter | DegradedResult
     └─ on DegradedResult: return PipelineResult(is_degraded=True, suggestions=[])

  2. get_clinical_notes(patient_id, encounter_id)  → list[FHIRDocumentReference]
     └─ empty list: return PipelineResult(is_degraded=True, notes_analyzed=0)

  3. get_recent_labs(patient_id, encounter_id, LOINC_CDI_PANEL)
     └─ always continues — empty list acceptable

  4. for each note with note_text:
       analyze_note(note, encounter) → CodingAnalysisResult | DegradedResult
       └─ DegradedResult: mark is_degraded=True, skip note

  5. merge_suggestions(all_results)
     └─ dedup by ICD-10 code, keep highest confidence per code
     └─ sort descending by drg_revenue_delta
     └─ cap at 15 suggestions (same as CodingAgent._run_pipeline)

  6. write_draft_claim(encounter_id, merged_result)
     └─ DegradedResult: draft_claim_id=None, is_degraded=True (non-fatal)

  7. return PipelineResult
```

### 3.2 LOINC CDI Panel (labs fetched for every run)

| LOINC | Lab | CDI trigger |
|-------|-----|-------------|
| 2160-0 | Creatinine | AKI |
| 33914-3 | eGFR | CKD staging |
| 2345-7 | Glucose | DM |
| 6690-2 | WBC | Sepsis |
| 2823-3 | Potassium | Electrolyte disorder |

### 3.3 Merge Logic

```python
def merge_suggestions(results):
    best: dict[str, CodingSuggestion] = {}
    for result in results:
        for s in result.suggestions:
            if s.code not in best or s.confidence > best[s.code].confidence:
                best[s.code] = s
    return sorted(best.values(), key=lambda s: s.drg_revenue_delta, reverse=True)[:15]
```

---

## 4. Edge Cases

| Scenario | Handling |
|----------|----------|
| Encounter not found (404) | Return degraded PipelineResult immediately |
| No clinical notes | Return degraded PipelineResult with notes_analyzed=0 |
| Note has no text (PDF/image) | Skip note, continue with others |
| All notes degrade | Return degraded PipelineResult with suggestions=[] |
| Draft Claim POST rejected | draft_claim_id=None, is_degraded=True — pipeline still returns suggestions |
| Duplicate ICD-10 across notes | Keep highest-confidence instance |

---

## 5. Performance Requirements

- Total pipeline (1 encounter, ≤5 notes): < 60s
- Per-note analysis: < 30s (inherited from VALIDATE-005 SLA)
- FHIR round-trips: ≤4 (encounter + notes + labs + claim write)

---

## 6. Constitution Compliance

| Article | Enforcement |
|---------|-------------|
| II.1 (no autonomous claim) | `write_draft_claim` hardcodes `status="draft"` |
| II.2 (evidence citation) | Inherited from CodingAgent — each suggestion has evidence_quote |
| II.3 (ICD-10 as hard constraints) | Inherited from CodingAgent — rules engine applied |
| II.4 (no PHI in logs) | Only IDs and counts logged — never resource content |
| II.5 (DegradedResult, never raise) | All FHIR errors return DegradedResult; pipeline catches all exceptions |

---

## 7. Testing Strategy

| Test | Description |
|------|-------------|
| `test_epic_pipeline_run` | Full run against Epic sandbox; asserts suggestions returned |
| `test_epic_pipeline_degraded_on_bad_encounter` | Invalid encounter ID → degraded result |
| `test_epic_pipeline_draft_claim_written` | Claim resource POSTed to Epic with status=draft |
| `test_merge_deduplication` | Unit: same code across two results → highest confidence kept |
