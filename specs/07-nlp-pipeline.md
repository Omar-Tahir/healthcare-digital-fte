# DESIGN-007: NLP Pipeline Specification

**Status:** COMPLETE
**Date:** 2026-04-03
**Author:** Claude (AI Engineering Partner)
**Research inputs:** DISC-001, DISC-002 (documentation failure patterns)
**Constitution references:**
  - Article I.1 (Spec-Driven Development)
  - Article II.2 (Evidence citation — entity positions enable evidence_quote)
  - Article II.4 (No PHI in logs — note text never logged)
  - Article II.5 (Graceful degradation — any component failure returns degraded result)
  - Article II.6 (Conservative defaults — skip uncertain entities)
**Implementation target:** `src/nlp/`

---

## Purpose

The NLP pipeline transforms a raw clinical note (free-text string) into
a structured list of `ClinicalEntity` objects. Each entity carries:
- The verbatim text span (enabling `evidence_quote` validation per Article II.2)
- Character offsets (start_char, end_char) for retrieval from source
- Section context (ASSESSMENT, HISTORY, PLAN, etc.)
- Negation status (is_negated=True → condition documented as absent)
- Temporal status (HISTORICAL → past condition, FAMILY → family history)

The coding agent uses entities as inputs. Without accurate negation and
temporal classification, the coding agent would suggest codes for
conditions the patient does not currently have — a patient safety event.

**Approach: Rule-Based (Not ML)**

Design decision: All NLP components use deterministic rule-based
approaches rather than ML models. See ADR-006.

Rationale:
1. Deterministic behavior = reproducible test outcomes
2. No GPU dependency, no model deployment infrastructure
3. Clinically-specific patterns outperform general NLP models
   on structured documentation patterns
4. Failures are debuggable without ML expertise

---

## 1. Component Architecture

```
ClinicalNote (str)
       │
       ▼
┌─────────────────────┐
│  SectionParser      │  → dict[NoteSection, str]
│  src/nlp/section_parser.py   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  ClinicalNER        │  → list[ClinicalEntity] (text, type, offsets, section)
│  src/nlp/ner.py     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  NegationDetector   │  → annotates each entity with is_negated, negation_cue
│  src/nlp/negation.py│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  TemporalClassifier │  → annotates each entity with temporal_status, temporal_cue
│  src/nlp/temporal.py│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  NLPPipeline        │  → NLPResult
│  src/nlp/pipeline.py│
└─────────────────────┘
```

Each component is independently testable. The pipeline orchestrates them
with graceful degradation at each step.

---

## 2. SectionParser

### 2.1 Responsibility

Split a free-text clinical note into named sections. Returns a dict
mapping NoteSection enum to the text of that section.

### 2.2 Section Headers (Pattern Library)

The parser matches section headers case-insensitively using regex.

| NoteSection | Header patterns |
|-------------|----------------|
| SUBJECTIVE | Chief Complaint, HPI, History of Present Illness, Subjective, CC |
| OBJECTIVE | Physical Exam, Vitals, Labs, Objective, Exam, PE |
| ASSESSMENT | Assessment, Impression, Diagnosis, A/P (assessment part), A: |
| PLAN | Plan, Treatment, Orders, P: |
| HISTORY | Past Medical History, PMH, Social History, Family History, Medical History, Past History |
| UNKNOWN | (fallback for unrecognized text) |

### 2.3 Parsing Algorithm

1. Compile regex for all known section headers
2. Find all header positions in the note (case-insensitive)
3. Sort matches by start position
4. Extract text between consecutive headers
5. Map each block to the closest matching NoteSection
6. Assign any pre-header text (before first header) to UNKNOWN
7. If no headers found: return entire note under UNKNOWN

### 2.4 Constraints

- Section text must NOT be empty (skip empty sections)
- If a section appears multiple times, concatenate its text
- Maximum section size: 10,000 characters (truncate and log warning)
- Never log section content (II.4)

---

## 3. ClinicalNER (Named Entity Recognition)

### 3.1 Responsibility

Extract clinical entities (diseases, findings, lab values, procedures,
anatomy) from section text. Returns entities with character offsets
into the section text.

### 3.2 Entity Detection Strategy

**Pattern layers (applied in order):**

1. **Lab Value Pattern** — regex for numeric values with clinical units
   Examples: "creatinine 3.2 mg/dL", "hemoglobin 8.5", "WBC 14.5"
   Entity type: LAB_VALUE

2. **Vital Sign Pattern** — regex for vital sign numeric patterns
   Examples: "BP 142/88", "HR 112", "O2 sat 89%", "temp 38.9"
   Entity type: FINDING

3. **Procedure Pattern** — keyword matching against procedure dictionary
   Examples: "intubation", "central line", "thoracentesis", "dialysis"
   Entity type: PROCEDURE

4. **Disease/Diagnosis Pattern** — keyword matching against disease dictionary
   Priority clinical entities from DISC-002 high-revenue conditions:
   - Sepsis, septic shock, bacteremia
   - Acute kidney injury, AKI, renal failure
   - Heart failure, CHF, cardiomyopathy
   - Respiratory failure, ARDS
   - Encephalopathy, delirium
   - Malnutrition, cachexia
   - Pneumonia (with organism patterns)
   - COPD exacerbation
   - DVT, pulmonary embolism
   - Atrial fibrillation, flutter
   - Diabetes (with complication patterns)
   - Pressure ulcer, decubitus
   Entity type: DISEASE

5. **Anatomy Pattern** — body part keywords for laterality context
   Examples: "right femoral", "left MCA", "bilateral"
   Entity type: ANATOMY

### 3.3 Entity Extraction Algorithm

For each pattern layer:
1. Apply regex/keyword scan to section text
2. Record match.start(), match.end(), match.group()
3. Avoid overlapping matches (later layers skip positions already matched)
4. Create ClinicalEntity with:
   - text = verbatim matched string
   - start_char / end_char = offsets in section text
   - source_section = the NoteSection being scanned
   - confidence = pattern-type specific (lab patterns = 0.95, disease keywords = 0.80)
   - is_negated = False (to be filled by NegationDetector)
   - temporal_status = CURRENT (to be filled by TemporalClassifier)

### 3.4 Constraints

- Minimum entity text length: 3 characters (skip noise matches)
- No duplicate entities at same offset (dedup by (start_char, end_char, source_section))
- Never log entity text (II.4) — only log entity_type and count
- If entity dict lookup fails: return empty list, log warning (graceful)

---

## 4. NegationDetector

### 4.1 Responsibility

Given an entity and its surrounding section text, determine whether the
entity is negated (documented as absent). Returns NegationResult with
is_negated: bool and negation_cue: str | None.

### 4.2 NegEx Algorithm (Simplified)

Based on NegEx (Chapman et al., 2001). Rule-based negation detection
using pre-negation and post-negation trigger phrases.

**Pre-negation triggers** (appear BEFORE the entity):
"no", "no evidence of", "no sign of", "without", "denies", "denied",
"negative for", "free of", "absent", "rules out", "ruled out",
"not", "never", "nor", "neither", "cannot", "can't"

**Post-negation triggers** (appear AFTER the entity):
"ruled out", "was ruled out", "not confirmed", "not found",
"not detected", "not present", "was negative"

**Termination tokens** (stop looking for negation context):
"but", "however", "although", "except", "despite", "though",
",", ";", "."

### 4.3 Negation Algorithm

1. Find the entity span in the section text
2. Extract pre-context: up to 6 tokens before entity start
3. Extract post-context: up to 6 tokens after entity end
4. Stop pre-context at any termination token (right-to-left scan)
5. Stop post-context at any termination token (left-to-right scan)
6. If any pre-negation trigger in pre-context: is_negated=True
7. If any post-negation trigger in post-context: is_negated=True
8. Record the matched cue phrase as negation_cue

### 4.4 Constraints

- Context window: 6 tokens max (narrow scope to avoid false positives)
- False positive risk: "patient denies [X] but reports [Y]" — termination
  token "but" must stop the search after [X]
- Never log entity text (II.4)

---

## 5. TemporalClassifier

### 5.1 Responsibility

Given an entity and its surrounding section text, determine whether the
entity refers to a current, historical, or family history condition.
Returns TemporalResult with temporal_status: TemporalStatus and
temporal_cue: str | None.

### 5.2 Temporal Pattern Library

**HISTORICAL triggers** (pre or post entity):
Pre: "history of", "h/o", "prior", "previous", "past", "hx of",
     "pmh:", "old", "known", "chronic" (when in HISTORY section),
     "remote history", "formerly", "in the past"
Post: "in the past", "previously"

**FAMILY triggers** (pre entity):
"family history of", "fh:", "father with", "mother with",
"sibling with", "parent with", "family hx"

**CURRENT triggers** (override historical if present):
"current", "active", "acute", "new onset", "presenting with",
"now with", "today", "recently", "this admission"

### 5.3 Classification Algorithm

1. Find entity span in section text
2. Extract pre-context (up to 8 tokens before entity)
3. Extract post-context (up to 4 tokens after entity)
4. Check FAMILY triggers in pre-context → FAMILY (highest priority)
5. Check HISTORICAL triggers in pre-context or post-context → HISTORICAL
6. Check section-based default:
   - HISTORY section → default to HISTORICAL (if no CURRENT trigger)
7. Check CURRENT trigger → override to CURRENT
8. Default: CURRENT (conservative — better to catch and filter than miss)

### 5.4 Constraints

- FAMILY > HISTORICAL > CURRENT in priority order
- Section context informs default (HISTORY section → historical)
- Never log entity text (II.4)

---

## 6. NLPPipeline (Orchestrator)

### 6.1 Responsibility

Orchestrate section_parser → NER → negation → temporal for a full note.
Return `NLPResult`. Graceful degradation at each step.

### 6.2 Pipeline Steps

```python
def analyze(note_text: str) -> NLPResult:
    # Step 1: Parse sections
    sections = self._parser.parse(note_text)
    # Step 2: Extract entities per section
    all_entities = ner.extract(text, section) for each section
    # Step 3: Apply negation to each entity
    enriched = negation.check(entity, section_text) for each entity
    # Step 4: Apply temporal to each entity
    final = temporal.classify(entity, section_text) for each entity
    # Return NLPResult
```

### 6.3 Degradation Behavior

| Failure point | Behavior |
|--------------|---------|
| SectionParser fails | Treat entire note as UNKNOWN section, is_degraded=True |
| NER fails on a section | Skip that section's entities, is_degraded=True |
| NegationDetector fails | Leave is_negated=False (conservative), is_degraded=True |
| TemporalClassifier fails | Leave temporal_status=CURRENT (conservative), is_degraded=True |

### 6.4 Logging (HIPAA-compliant)

```python
log.info("nlp_pipeline_complete",
         entity_count=len(final_entities),
         section_count=len(sections),
         negated_count=...,
         historical_count=...,
         family_count=...,
         is_degraded=is_degraded,
         elapsed_ms=elapsed_ms)
```

NEVER log: note text, entity text, section content, evidence quotes.

---

## 7. Acceptance Criteria

| Test | Expected behavior |
|------|-----------------|
| Note with SOAP headers | Sections correctly identified |
| Note with no headers | Entire note as UNKNOWN section |
| "No evidence of sepsis" | Sepsis entity is_negated=True |
| "History of diabetes" | Diabetes entity temporal_status=HISTORICAL |
| "Family history of CAD" | CAD entity temporal_status=FAMILY |
| "Acute kidney injury" | AKI entity extracted, is_negated=False, CURRENT |
| SectionParser raises | Pipeline returns is_degraded=True with empty entities |
| NER raises | Pipeline returns is_degraded=True |
| Note with "creatinine 3.2" | LAB_VALUE entity extracted |
| Empty note | NLPResult with empty entities, no exception |

---

## 8. File Map

```
src/nlp/
├── __init__.py
├── section_parser.py    ← SectionParser class
├── ner.py               ← ClinicalNER class
├── negation.py          ← NegationDetector class
├── temporal.py          ← TemporalClassifier class
└── pipeline.py          ← NLPPipeline class

tests/unit/
└── test_nlp_pipeline.py ← All NLP unit tests
```

---

## 9. What This Spec Does NOT Cover

- ML-based NER (Phase 2+ enhancement)
- De-identification (MIMIC data is already de-identified)
- Coreference resolution ("it", "the condition" referring to prior entity)
- Negation scope beyond 6 tokens (acceptable tradeoff for Phase 1)
- Cross-sentence negation (treated as separate scope)
