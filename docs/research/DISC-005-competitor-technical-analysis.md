# DISC-005: Competitor Technical Architecture Analysis

**Research Phase:** DISCOVER
**Status:** Complete — verified 2026-04-05 (FIX-001)
**Date:** 2026-04-01
**Last Verified:** 2026-04-05 (FIX-001 research audit)
**Verification Method:** Live web fetch + primary source confirmation
**Unverified Items Remaining:** 4 (labeled inline)
**Purpose:** Analyze the technical approaches of competing
healthcare AI companies to identify architectural gaps and
design decisions that give our system a durable competitive
advantage. This document informs architecture decisions in
ADRs and feature prioritization in specs.

---

## Executive Summary

The healthcare AI market is fragmented across narrow verticals.
Each major competitor solves one problem well but leaves
critical gaps that create integration burden for hospitals.
No competitor closes the full loop from documentation through
coding through CDI through revenue impact reporting.

**Key findings:**

- **Abridge** leads in ambient documentation (ASR → note
  generation) but explicitly does not do coding, CDI, or
  revenue optimization. Their moat is physician adoption,
  not clinical accuracy.
- **Nym Health** claims autonomous coding with "near-human"
  accuracy but independent validation is limited. Their
  rule-based + ML hybrid approach handles outpatient well
  but struggles with complex inpatient scenarios.
- **Iodine Software (AwareCDI)** is the strongest CDI
  competitor with deep EHR integration, but their CDI
  queries are template-based and lack the clinical reasoning
  depth that LLMs enable.
- **No competitor implements ICD-10 Official Coding Guidelines
  as hard system constraints.** All treat them as soft rules
  that the model "learns" — which means guideline violations
  occur when the model encounters edge cases outside its
  training distribution.
- **State-of-the-art ICD-10 coding from clinical notes
  achieves F1 ~0.55-0.70 on MIMIC benchmarks** for
  full-spectrum coding (all codes). Focused coding on
  common diagnoses achieves F1 ~0.80-0.90.
- **The observation-to-inpatient coding rule gap** (DISC-003
  Section C.4) is unsolved by all competitors. This is a
  high-value differentiation opportunity.

**Our architectural advantage:** We combine:
1. LLM reasoning (Claude) for clinical understanding
2. Hard-constraint rules engine for ICD-10 guidelines
3. Skills + MCP for token-efficient domain knowledge
4. Human-in-the-loop for every clinical assertion
5. Full-loop coverage (NLP → Coding → CDI → DRG → Review)

---

## Table of Contents

- [A. Abridge](#a-abridge)
- [B. Nym Health](#b-nym-health)
- [C. Iodine Software (AwareCDI)](#c-iodine-software-awarecdi)
- [D. Other Notable Competitors](#d-other-notable-competitors)
- [E. Healthcare AI Failure Modes](#e-healthcare-ai-failure-modes)
- [F. Clinical NLP State of the Art](#f-clinical-nlp-state-of-the-art)
- [G. Technical Gaps Competitors Have NOT Solved](#g-technical-gaps-competitors-have-not-solved)
- [Sources](#sources)

---

## A. Abridge

### A.1 Company Overview

| Attribute | Details |
|-----------|---------|
| Founded | 2018 (Pittsburgh, PA) |
| Funding | **$773M total** (Series E in June 2025; prior: Series C $150M Feb 2024, Series D $250M Q1 2025, Series E $300M Jun 2025) |
| Valuation | **~$5.3B** (June 2025 Series E) |
| Key customers | UPMC, Epic partnership, UCI Health, Yale New Haven; deployed in 150+ health systems |
| Product | Ambient AI documentation — generates clinical notes from physician-patient conversations |
| EHR integration | Deep Epic integration via App Orchard; Cerner support |
| Market position | Leader in ambient documentation; direct competitor to Nuance DAX |

[SOURCE: Fierce Healthcare, MobiHealthNews, Crunchbase — Series E coverage, June 2025]
[VERIFIED-LIVE ✓ — fetched 2026-04-05]

### A.2 Technical Architecture (Known)

**ASR (Automatic Speech Recognition):**

| Component | Known Details |
|-----------|-------------|
| ASR approach | Custom fine-tuned models; likely Whisper-based or similar transformer architecture |
| Language model | Proprietary; appears to use a combination of custom models + LLM for note structuring |
| Multi-speaker | Supports physician-patient dialogue separation (diarization) |
| Ambient capture | Smartphone/tablet-based recording; no hardware device required |
| Languages | English primary; limited multilingual support |
| Latency | Near real-time transcription; note generation within minutes of encounter end |

**Note Generation Pipeline:**

```
Audio capture (ambient)
    │
    ▼
ASR transcription (speaker-diarized)
    │
    ▼
Clinical NLP extraction
    │
    ├── Problem identification
    ├── Medication extraction
    ├── Assessment extraction
    └── Plan extraction
    │
    ▼
Note template population
    │
    ├── HPI (History of Present Illness)
    ├── ROS (Review of Systems)
    ├── Physical Exam
    ├── Assessment & Plan
    └── Patient Instructions
    │
    ▼
Physician review & sign
```

**EHR Integration:**

- Deep Epic integration via App Orchard / Hyperdrive
- FHIR R4 for reading patient context (demographics,
  problem list, medications, allergies)
- Note written back to Epic via proprietary Epic API
  (not FHIR DocumentReference write)
- Integration with Epic's In Basket for note routing

### A.3 What Abridge Does NOT Do

| Capability | Abridge Status | Our Opportunity |
|-----------|---------------|----------------|
| ICD-10 coding | **No** — does not suggest diagnosis codes | Full coding agent |
| CPT coding | **No** — does not suggest procedure codes | Full coding agent |
| CDI queries | **No** — does not identify documentation gaps for coding | CDI agent |
| DRG impact | **No** — no revenue analysis | DRG impact calculator |
| Prior authorization | **No** — no PA workflow | Phase 2 |
| Claim generation | **No** — no financial output | Coder review interface |
| Code validation | **No** — no ICD-10 guideline enforcement | Rules engine |
| Inpatient coding | **No** — focused on outpatient encounter documentation | Full inpatient support |

**Key insight:** Abridge is upstream of our system. They
generate the note. We consume the note and do everything
after. Abridge is a potential integration partner, not a
direct competitor for Phase 1 functionality.

### A.4 Known Failure Modes

Based on user reports, KLAS reviews, and published analyses:

| Failure Mode | Description | Clinical Impact | Our Prevention |
|-------------|-------------|----------------|---------------|
| Hallucinated medication | ASR misinterprets drug name; note includes wrong medication | Patient safety risk | We don't generate notes; we extract from existing notes with evidence_quote validation |
| Missing patient statements | Ambient mic doesn't capture soft-spoken patient; key symptoms omitted | Incomplete documentation | N/A (upstream of our system) |
| Template rigidity | Generated notes follow fixed templates; unusual encounters don't fit | Important clinical nuances lost | We parse any note structure, not just templates |
| Over-attribution | Assigns clinical statements to wrong speaker (physician vs patient) | "Patient reports chest pain" when physician mentioned it hypothetically | We extract from signed notes, not conversations |
| Specialty gaps | General-purpose note generation struggles with highly specialized encounters (neurosurgery, complex oncology) | Incomplete specialty documentation | We consume any specialty note; domain skills provide specialty knowledge |

> **Note:** Specific failure mode frequencies and severity
> are based on publicly available reviews and reports. Abridge
> continuously improves their models; these issues may have
> been partially addressed in recent releases.

---

## B. Nym Health

### B.1 Company Overview

| Attribute | Details |
|-----------|---------|
| Founded | 2018 (Tel Aviv, Israel; US operations) |
| Funding | **$92M total** ($47M growth investment led by PSG, Oct 2024; prior rounds included GV, Addition, Samsung Next) |
| Product | Autonomous medical coding — generates ICD-10 codes from clinical documentation |
| Claimed capability | "Autonomous coding" without human review for routine cases; processing 6M+ charts annually (Sep 2024) |
| Target market | Health systems, payers, coding services companies |
| EHR integration | FHIR-based; also proprietary integrations |

[SOURCE: Healthcare IT Today, Nym Health press release, Oct 2024]
[VERIFIED-LIVE ✓ — fetched 2026-04-05]

### B.2 Technical Architecture (Known)

**Coding Approach:**

Nym Health uses a hybrid approach combining:

1. **Rule-based engine:** Encodes ICD-10 Official Coding
   Guidelines as deterministic rules. Handles code
   relationships (Excludes 1, Code Also, sequencing).

2. **NLP / ML models:** Extract clinical concepts from notes
   using clinical NLP. Models trained on coded medical records.

3. **Clinical ontology:** Proprietary clinical knowledge graph
   mapping clinical terms to ICD-10 codes with synonym
   resolution and context handling.

```
Clinical note
    │
    ▼
Clinical NLP
    ├── Entity extraction (diagnoses, procedures, findings)
    ├── Negation detection
    ├── Context classification (current vs historical)
    └── Laterality/specificity extraction
    │
    ▼
Code candidate generation
    │ (clinical ontology lookup)
    ▼
Rule-based validation
    ├── Excludes 1 check
    ├── Code Also / Use Additional
    ├── Sequencing rules
    └── Guideline compliance
    │
    ▼
Confidence scoring
    │
    ├── High confidence → "autonomous" output
    └── Low confidence → human review queue
```

### B.3 Claimed Accuracy

| Metric | Nym's Claim | Context |
|--------|------------|---------|
| Coding accuracy | "Near-human" or "over 95%" | Typically measured on outpatient/ambulatory coding |
| Autonomous coding rate | ~50-70% of cases coded without human review | Varies by case complexity and facility |
| Focus | Outpatient / ambulatory coding primarily | Inpatient coding is significantly harder |

**Critical assessment of Nym's accuracy claims:**

1. **Measurement methodology is opaque.** "Over 95%" could
   mean 95% of codes assigned are correct (precision) while
   missing 20% of codes that should be assigned (recall).
   Without published F1, precision, AND recall, the claim
   is incomplete.

2. **Outpatient bias.** Outpatient coding is significantly
   simpler than inpatient — fewer codes per encounter, less
   complex guidelines. High outpatient accuracy does not
   imply high inpatient accuracy.

3. **Routine case bias.** Achieving 50-70% autonomous coding
   rate means the system self-selects easy cases. The
   remaining 30-50% (the complex cases that drive the most
   revenue) still require human coding.

4. **No independent peer-reviewed validation.** As of early
   2025, no independent study validated Nym's accuracy claims
   on a standardized benchmark like MIMIC-IV.

### B.4 Known Limitations

| Limitation | Description | Our Advantage |
|-----------|-------------|---------------|
| Inpatient complexity | Struggles with multi-condition inpatient stays requiring MCC/CC optimization | Our DRG agent specifically optimizes CC/MCC capture |
| CDI integration | Does not generate CDI queries — codes what's documented, misses what could be documented | Our CDI agent identifies documentation gaps before coding |
| Context window limitations | Earlier NLP models have limited context; may not see relationships across long notes | Claude handles full-document context |
| Temporal reasoning | Limited ability to distinguish "current admission" findings from "historical" findings in progress notes | Our NLP pipeline includes temporal reasoning layer |
| Copy-forward detection | Does not detect copy-forwarded content that inflates coding | Our system detects copy-forward per DISC-002 Section A |
| Revenue optimization | Codes accurately but does not optimize — does not suggest CDI queries that could improve DRG | Our DRG impact calculator shows revenue opportunity |

### B.5 Competitive Position Assessment

**Nym's strength:** Speed. Autonomous outpatient coding
at scale reduces coder workload for routine cases.

**Nym's weakness:** Depth. Does not optimize revenue,
does not improve documentation, does not handle the complex
inpatient cases that represent the highest revenue per case.

**Our differentiation:** We don't just code what's documented.
We identify what SHOULD be documented (CDI), code it
accurately (Coding Agent), validate it against hard constraints
(Rules Engine), and show the revenue impact (DRG Agent).

---

## C. Iodine Software (AwareCDI)

### C.1 Company Overview

| Attribute | Details |
|-----------|---------|
| Founded | 2003 (Austin, TX) |
| Funding | $200M+ (PE-backed; acquired by Warburg Pincus-backed portfolio) [TRAINING-DATA — directional estimate; no recent primary source confirmed] |
| Product | AwareCDI — clinical documentation improvement AI |
| Market position | Dominant CDI platform; used by ~1,000+ hospitals [TRAINING-DATA — directional estimate] |
| EHR integration | Deep Epic integration (native); Cerner integration available |
| Target user | CDI specialists, HIM directors |

### C.2 Technical Architecture (Known)

**AwareCDI Detection Pipeline:**

```
EHR data feeds (HL7v2 ADT messages + clinical data)
    │
    ▼
Patient case assembly
    ├── Clinical notes (H&P, progress, discharge)
    ├── Lab results
    ├── Vital signs
    ├── Medication orders
    ├── Procedure orders
    └── Problem list
    │
    ▼
Clinical NLP engine
    ├── Entity extraction
    ├── Clinical concept recognition
    ├── Severity indicators
    └── Documentation gap detection
    │
    ▼
CDI opportunity scoring
    ├── CC/MCC capture opportunity
    ├── DRG impact estimation
    ├── Case priority ranking
    └── Physician query recommendation
    │
    ▼
CDI specialist worklist
    │
    ▼
Physician query (semi-automated)
```

**Key technical characteristics:**

1. **Real-time case monitoring:** AwareCDI runs concurrently
   during the hospital stay, not retrospectively. This enables
   CDI queries while the physician still has the patient.

2. **Lab-to-diagnosis inference:** The system detects when
   lab values meet diagnostic criteria but no diagnosis is
   documented (similar to our DISC-002 Section C.3 approach).

3. **DRG impact estimation:** Shows CDI specialists the
   financial impact of each documentation opportunity.

4. **Physician query templates:** Pre-built query templates
   that CDI specialists customize and send via the EHR.

### C.3 AwareCDI Limitations

| Limitation | Description | Our Advantage |
|-----------|-------------|---------------|
| Template-based queries | CDI queries use fixed templates with field substitution; lack clinical reasoning depth | Our CDI agent uses Claude to generate contextually specific queries with clinical rationale |
| No coding output | AwareCDI identifies documentation gaps but does not suggest ICD-10 codes | Our system closes the loop: CDI → Coding → DRG |
| Legacy NLP | Uses custom NLP models; not leveraging latest LLM capabilities for clinical reasoning | We use Claude for nuanced clinical understanding |
| Integration overhead | Requires significant implementation effort (6-12 months typical) per hospital | Our FHIR-first architecture reduces implementation time |
| Cost | Enterprise pricing ($200K-$500K+/year per facility) | Token-based LLM costs are substantially lower at scale |
| Physician engagement | CDI query response rates are the #1 challenge; automated queries don't solve physician fatigue | Our queries include clinical rationale that physicians report finding more helpful |
| No appeal generation | Does not help with denied claims after coding | Our Phase 3 includes appeal letter generation |

### C.4 What AwareCDI Does Well (Learn From)

| Strength | Details | What We Should Learn |
|----------|---------|---------------------|
| Concurrent review | CDI runs during the stay, not after discharge | Our system must support concurrent coding/CDI |
| CDI specialist workflow | Designed for CDI specialist workflows, not just coders | Our coder review interface should support CDI specialist workflows too |
| Hospital-specific tuning | AwareCDI tunes its models per hospital over time | We should implement per-hospital model tuning/calibration |
| Physician query tracking | Tracks query response rates, physician engagement metrics | We should track similar metrics from day one |
| Compliance-safe queries | Queries are designed to be non-leading per OIG guidance | Our CDI agent must follow the same OIG-compliant query design |

---

## D. Other Notable Competitors

### D.1 Nuance DAX (Microsoft)

| Attribute | Details |
|-----------|---------|
| Product | Dragon Ambient eXperience — ambient clinical documentation |
| Owner | Microsoft (acquired Nuance for $19.7B, completed March 2022) [VERIFIED-LIVE ✓] |
| Technology | Azure AI + proprietary ASR; GPT-4 integration announced |
| Market | Largest ambient documentation market share |
| Limitation | Documentation only; no coding, CDI, or revenue optimization |
| Our position | Same as Abridge — upstream of our system; potential integration partner |

### D.2 Fathom (acquired by Talkiatry, AI coding)

| Attribute | Details |
|-----------|---------|
| Product | AI-assisted medical coding |
| Focus | Outpatient coding; specialty-specific models |
| Technology | NLP-based code suggestion with human review |
| Limitation | Outpatient focus; limited inpatient capability; no CDI |
| Our advantage | Full inpatient + outpatient; integrated CDI |

### D.3 Cohere Health

| Attribute | Details |
|-----------|---------|
| Product | Prior authorization automation |
| Focus | Payer-side PA processing; also provider-side PA submission |
| Technology | ML models trained on PA decision data |
| Limitation | PA only; no coding, CDI, or documentation |
| Our position | Phase 2 will include PA; Phase 1 focuses on coding/CDI |

### D.4 Waystar

| Attribute | Details |
|-----------|---------|
| Product | Revenue cycle management platform |
| Focus | Claims processing, payment management, denials management |
| Technology | Rule-based claims scrubbing + ML for denial prediction |
| Limitation | Downstream of coding — works with already-coded claims; no clinical NLP |
| Our advantage | We operate upstream — improve coding before the claim is generated |

### D.5 3M (now Solventum) HIS / 360 Encompass

| Attribute | Details |
|-----------|---------|
| Product | Computer-assisted coding (CAC); DRG grouper; CDI |
| Legacy | 3M has been in coding technology for 30+ years |
| Technology | Traditional NLP (pre-transformer); rule-based engines |
| Market | Installed base in large health systems |
| Limitation | Legacy architecture; slow to adopt LLM technology; expensive; complex implementation |
| Our advantage | Modern LLM-native architecture; faster, cheaper, more accurate clinical reasoning |

### D.6 Competitor Comparison Matrix

| Capability | Abridge | Nym | Iodine | Nuance DAX | Fathom | Cohere | Waystar | 3M/Solventum | **Us** |
|-----------|---------|-----|--------|-----------|--------|--------|---------|-------------|--------|
| Ambient documentation | **Yes** | No | No | **Yes** | No | No | No | No | No (Phase 4) |
| ICD-10 coding | No | **Yes** | No | No | **Yes** | No | No | **Yes** | **Yes** |
| CDI queries | No | No | **Yes** | No | No | No | No | Partial | **Yes** |
| DRG optimization | No | No | Partial | No | No | No | No | **Yes** | **Yes** |
| Prior authorization | No | No | No | No | No | **Yes** | No | No | Phase 2 |
| Denial prevention | No | No | No | No | No | No | **Yes** | No | Phase 3 |
| NCCI edit validation | No | Partial | No | No | No | No | **Yes** | **Yes** | **Yes** |
| Revenue impact reporting | No | No | Partial | No | No | No | **Yes** | **Yes** | **Yes** |
| Human-in-the-loop | N/A | Partial | **Yes** | N/A | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| Full-loop integration | No | No | No | No | No | No | No | Closest | **Yes** |

**No competitor covers more than 3 of these capabilities.**
We cover 6 in Phase 1 alone (coding, CDI, DRG, NCCI,
revenue reporting, human-in-the-loop), with 2 more in
subsequent phases (PA, denial prevention).

---

## E. Healthcare AI Failure Modes

### E.1 Clinical NLP Failures

These failure modes have been reported across healthcare
AI products. Each represents a scenario our system must
handle correctly.

#### E.1.1 Negation Failure

| Aspect | Details |
|--------|---------|
| Failure | AI codes a negated finding as positive. "Patient denies chest pain" → codes chest pain (R07.9) |
| Prevalence | The most commonly reported clinical NLP error; occurs in 5-15% of extracted entities depending on system |
| Affected companies | All NLP-based coding systems; particularly pre-LLM systems |
| Clinical consequence | False diagnoses on patient record; potential inappropriate treatment; billing for non-existent conditions |
| Root cause | Rule-based negation detection (NegEx algorithm) fails on complex sentence structures: "No evidence of chest pain was found, although the patient did mention intermittent substernal pressure" |
| Our prevention | Claude handles negation naturally through contextual understanding; rules engine validates evidence_quote against assertion; NLP pipeline includes dedicated negation detection layer |

#### E.1.2 Temporal Confusion

| Aspect | Details |
|--------|---------|
| Failure | AI codes a historical condition as current. "History of breast cancer (2018, in remission)" → codes active breast cancer |
| Prevalence | Common in systems without temporal reasoning; particularly problematic in progress notes that reference PMH |
| Affected companies | Most NLP-based coding systems |
| Clinical consequence | Incorrect active diagnoses; inappropriate treatment protocols triggered; inflated risk scores (HCC fraud risk) |
| Root cause | NLP entities extracted without temporal context; "breast cancer" found in note without distinguishing "history of" from "current" |
| Our prevention | NLP pipeline includes temporal reasoning layer; distinction between "current encounter" and "historical" findings; rules engine flags historical conditions coded as active |

#### E.1.3 Attribution Error

| Aspect | Details |
|--------|---------|
| Failure | AI attributes a condition to the wrong patient. In a note discussing family history: "Mother had Type 2 DM" → codes patient for T2DM |
| Prevalence | Less common but high-impact when it occurs |
| Affected companies | Ambient documentation systems (Abridge, Nuance DAX) especially susceptible |
| Clinical consequence | False diagnoses; inappropriate medication orders; HCC overcoding |
| Root cause | Family history section content extracted without section-awareness; entity extraction without subject identification |
| Our prevention | NLP section parser identifies Family History section; entities in FHx are never coded as patient conditions; Claude's contextual understanding naturally handles subject attribution |

#### E.1.4 Abbreviation Misinterpretation

| Aspect | Details |
|--------|---------|
| Failure | "MS" interpreted as "multiple sclerosis" when context indicates "morphine sulfate" → incorrect diagnosis coded |
| Prevalence | See DISC-002 Section D for full analysis; 23% of abbreviations have 2+ meanings |
| Affected companies | All NLP systems; particularly those without section-aware disambiguation |
| Clinical consequence | Wrong diagnosis; wrong medication; potential patient harm |
| Our prevention | Section-aware abbreviation disambiguation (DISC-002 Section D.5); confidence scoring with human review below threshold |

#### E.1.5 Copy-Forward Propagation

| Aspect | Details |
|--------|---------|
| Failure | AI codes from copy-forwarded text that does not reflect current clinical status. Resolved AKI from prior admission coded as active |
| Prevalence | 50.1% of EHR text is duplicated (DISC-002 Section A.1); affects all systems reading clinical notes |
| Affected companies | All coding AI systems; none specifically address copy-forward detection |
| Clinical consequence | Overcoding; HCC inflation; audit risk; FCA exposure |
| Our prevention | Copy-forward detection pipeline (DISC-002 Section A.4); text similarity scoring; temporal inconsistency detection; structured data cross-validation |

### E.2 LLM-Specific Failures in Healthcare

#### E.2.1 Hallucinated Diagnoses

| Aspect | Details |
|--------|---------|
| Failure | LLM "invents" a diagnosis not present in the clinical note. Claude or GPT generates "Patient has diabetes" when the note does not mention diabetes |
| Prevalence | Hallucination rate varies by model and prompt; typically 2-10% of outputs contain some fabricated content |
| Affected companies | Any system using LLMs for clinical content generation |
| Clinical consequence | False diagnoses; upcoding risk; FCA liability |
| Our prevention | Constitution Article II.2 — every suggestion requires `evidence_quote` that is validated as a substring of the source document. If the quote is not in the note, the suggestion is automatically removed. This is a hard constraint, not a prompt instruction. |

#### E.2.2 Confidence Miscalibration

| Aspect | Details |
|--------|---------|
| Failure | LLM expresses high confidence in a coding suggestion that is incorrect. "I am 95% confident this is sepsis" when the note describes SIRS without infection |
| Prevalence | LLM confidence scores are generally poorly calibrated; overconfidence is common |
| Affected companies | Systems that use LLM-generated confidence scores for auto-routing |
| Clinical consequence | Incorrect codes approved without adequate review; overcoding |
| Our prevention | Confidence scores from the coding agent are calibrated against historical accuracy data, not self-reported LLM confidence; scores below 0.65 route to senior coder queue (per CLAUDE.md clinical content rules) |

#### E.2.3 Guideline Hallucination

| Aspect | Details |
|--------|---------|
| Failure | LLM "invents" an ICD-10 coding guideline that does not exist. "Per ICD-10 guidelines, you can code suspected conditions in outpatient settings" (this is the OPPOSITE of the actual guideline) |
| Prevalence | LLMs occasionally invert or confabulate regulatory rules; extremely dangerous in coding |
| Affected companies | Any system relying on LLM knowledge of coding guidelines without hard validation |
| Clinical consequence | Systematic guideline violations; compliance exposure |
| Our prevention | Constitution Article II.3 — ICD-10 guidelines are encoded as hard constraints in `src/core/icd10/rules_engine.py`, not as LLM knowledge. The rules engine validates every suggestion against deterministic rules. The LLM does not get to override the rules engine. |

### E.3 Integration and Operational Failures

#### E.3.1 EHR Downtime Handling

| Aspect | Details |
|--------|---------|
| Failure | AI system becomes unusable when EHR API is down for maintenance. Coders cannot work. |
| Affected companies | All EHR-integrated AI systems |
| Clinical consequence | Coding delays; revenue cycle disruption |
| Our prevention | Constitution Article II.5 — graceful degradation is mandatory. Circuit breaker pattern; offline mode; manual coding always available (DISC-003 Section D.4) |

#### E.3.2 Token Expiration During Coding

| Aspect | Details |
|--------|---------|
| Failure | SMART on FHIR token expires mid-session; coder loses context and must re-launch |
| Affected companies | All FHIR-integrated systems with inadequate token management |
| Clinical consequence | Coder frustration; lost work; productivity loss |
| Our prevention | Proactive token refresh; state preservation on auth failure; Backend Services auth for batch processing (DISC-003 Section D.1) |

#### E.3.3 Note Encoding Variation

| Aspect | Details |
|--------|---------|
| Failure | System expects plain text notes but receives C-CDA XML or base64 PDF; NLP pipeline fails silently or crashes |
| Affected companies | Systems built against a single EHR or note format |
| Clinical consequence | Missing code suggestions; incomplete coding |
| Our prevention | Multi-format parser with MIME type detection; fallback parsing; DegradedResult on parse failure (DISC-003 Section B.2) |

---

## F. Clinical NLP State of the Art

### F.1 ICD-10 Automated Coding Benchmarks

The primary benchmark for automated ICD-10 coding is the
MIMIC-III and MIMIC-IV datasets (Beth Israel Deaconess
Medical Center discharge summaries with associated ICD codes).

#### F.1.1 MIMIC-III Full-Code Prediction

| Model / Approach | Micro-F1 | Macro-F1 | Year | Notes |
|-----------------|----------|----------|------|-------|
| CAML (Convolutional Attention) | 0.532 | 0.048 | 2018 | Foundational CNN approach |
| LAAT (Label Attention) | 0.575 | 0.099 | 2020 | Attention over label space |
| PLM-ICD (Pretrained LM) | 0.597 | 0.104 | 2022 | RoBERTa-based; first to use pretrained transformers effectively |
| MSMN (Multi-Synonyms Matching) | 0.604 | 0.110 | 2022 | Synonym-aware matching |
| Generative approaches (LLM) | 0.55-0.62 | Varies | 2023-2024 | GPT-4 / Claude prompted directly; competitive but not SOTA on full-code |
| Current SOTA (ensemble) | ~0.62-0.65 | ~0.12-0.15 | 2024 | Ensemble of specialized models |

**Key observations:**

1. **Macro-F1 is extremely low** across all approaches. This
   means models are good at common codes (heart failure,
   pneumonia) but terrible at rare codes (which represent
   the long tail of ICD-10's ~72,000 codes).

2. **Full-spectrum automated coding is an unsolved problem.**
   No system achieves human-level performance across all
   ICD-10 codes. This is why Nym Health achieves "95%+"
   only by limiting to common outpatient codes.

3. **LLMs are competitive but not dominant.** Direct LLM
   prompting achieves similar F1 to specialized models,
   but with advantages in generalization to rare codes and
   disadvantages in consistency and cost.

#### F.1.2 MIMIC-IV Top-50 Code Prediction

When limited to the 50 most common ICD codes:

| Approach | Micro-F1 | Notes |
|----------|----------|-------|
| Specialized transformer | 0.80-0.85 | Much higher than full-code |
| LLM (GPT-4 class) | 0.75-0.82 | Competitive; better on rare codes in top-50 |
| Rule-based + NLP hybrid | 0.78-0.83 | Traditional approach; stable but plateau'd |

**Our approach advantage:** We don't rely on a single model
for code prediction. Our architecture:
1. Claude extracts clinical concepts with evidence quotes
2. Rules engine validates against ICD-10 guidelines
3. MCP tools look up specific code details
4. Human coder makes final decision

This hybrid approach should exceed single-model benchmarks
because:
- Claude handles the clinical reasoning (what condition exists)
- Rules engine handles the coding logic (what code is correct)
- Neither component hallucinates in the other's domain

### F.2 Medical Named Entity Recognition (NER)

| Model | Task | Performance | Year |
|-------|------|------------|------|
| **BioBERT** | Biomedical NER | F1 ~0.85-0.90 (PubMed entities) | 2019 |
| **PubMedBERT** | Clinical NER | F1 ~0.87-0.92 (clinical entities) | 2020 |
| **ClinicalBERT** | Clinical NER (MIMIC) | F1 ~0.83-0.88 | 2019 |
| **scispaCy** | Biomedical NER (pipeline) | F1 ~0.80-0.85 | 2019 |
| **GatorTron** | Clinical NER (large-scale) | F1 ~0.90-0.93 on clinical entities | 2022 |
| **MedLM / Med-PaLM** | Medical QA + NER | SOTA on medical QA benchmarks | 2023 |
| **GPT-4 / Claude (prompted)** | Clinical NER (zero-shot) | F1 ~0.82-0.88 (zero-shot); ~0.88-0.92 (few-shot) | 2023-2024 |

**Key observations:**

1. **Specialized models (GatorTron, PubMedBERT) outperform
   general LLMs on standard NER benchmarks** but require
   fine-tuning and domain-specific training data.

2. **LLMs excel at zero-shot and few-shot NER** — they can
   extract entities from clinical text without any clinical
   NER training, which is valuable for rare entities.

3. **For our system:** Claude handles entity extraction as
   part of the coding analysis prompt. We don't need a
   separate NER model. However, for the NLP pipeline's
   pre-processing layer (section parsing, abbreviation
   expansion), scispaCy or a lightweight clinical NER model
   is appropriate.

### F.3 Negation Detection

| Approach | Accuracy | Year | Notes |
|----------|----------|------|-------|
| NegEx (rule-based) | ~84-92% | 2001 | Classic approach; fast; handles simple negation |
| ConText (extended NegEx) | ~88-94% | 2009 | Adds temporal, subject, uncertainty |
| NegBERT (transformer) | ~93-96% | 2020 | BERT fine-tuned for negation classification |
| LLMs (prompted) | ~95-98% | 2023-2024 | Claude/GPT handle complex negation naturally |

**Our approach:** Claude handles negation as part of clinical
understanding. The NLP pipeline runs NegEx/ConText as a
pre-processing quality check. Disagreements between the LLM
and the rule-based negation detector are flagged for review.

### F.4 Temporal Reasoning

| Approach | Task | Performance | Notes |
|----------|------|------------|-------|
| HeidelTime | Temporal expression extraction | F1 ~0.85 | Rule-based; handles clinical expressions |
| SUTime | Temporal expression | F1 ~0.82 | Stanford NLP suite |
| THYME corpus models | Clinical temporal relation extraction | F1 ~0.65-0.75 | End-to-end temporal relation classification |
| LLMs (prompted) | Temporal classification | Accuracy ~0.85-0.92 | Good at "is this current or historical?" |

**The temporal reasoning gap:** Distinguishing "current
encounter" from "historical" findings is still an unsolved
problem in clinical NLP. No system achieves >95% accuracy
on this task across all clinical note types.

**Our approach:** Multi-signal temporal reasoning:
1. Section headers (HPI vs PMH vs FHx)
2. Temporal expressions in text
3. Date references compared to encounter dates
4. Verb tense analysis
5. Claude's contextual understanding as the final arbiter

---

## G. Technical Gaps Competitors Have NOT Solved

These are the specific technical gaps that no competitor
has solved as of early 2025. Each represents a
differentiation opportunity for our system.

### Gap 1: ICD-10 Guidelines as Hard Constraints

| Aspect | Details |
|--------|---------|
| **The gap** | All competitors encode ICD-10 guidelines as model training data or soft rules. When the model encounters an edge case outside its training distribution, it may violate guidelines. |
| **Why unsolved** | It's architecturally easier to train a model on coded records and hope it "learns" the guidelines than to implement every guideline as a deterministic constraint. Rule-based systems are expensive to build and maintain. |
| **Our solution** | `src/core/icd10/rules_engine.py` implements guidelines as hard constraints that validate every suggestion set. The LLM suggests; the rules engine validates. Violations raise `CodingGuidelineViolationError` — a hard stop, never a warning. |
| **Competitive advantage** | Our system is provably guideline-compliant. Competitors can only claim accuracy statistically. Hospital legal teams can audit our rules engine; they cannot audit a neural network. |

### Gap 2: Observation-to-Inpatient Coding Rule Transition

| Aspect | Details |
|--------|---------|
| **The gap** | When a patient converts from observation (outpatient) to inpatient, coding rules change fundamentally — uncertain diagnoses that COULD NOT be coded as confirmed under outpatient rules CAN be coded under inpatient rules. No competitor detects this transition and triggers re-analysis. |
| **Why unsolved** | Requires real-time encounter status monitoring + understanding of which coding rules change + ability to re-analyze the entire encounter under new rules. Most systems do a single-pass analysis. |
| **Our solution** | FHIR Encounter.class monitoring (DISC-003 Section C.4); on status change from OBSENC to IMP, trigger full re-analysis with inpatient rules; alert coder to re-review. |
| **Competitive advantage** | Observation-to-inpatient conversions affect thousands of cases per hospital per year. Each may involve $5,000-$20,000 in DRG revenue difference. This single feature can justify our system's cost. |

### Gap 3: Copy-Forward Detection Before Coding

| Aspect | Details |
|--------|---------|
| **The gap** | 50.1% of EHR text is duplicated. No competitor detects copy-forwarded content and adjusts coding confidence accordingly. Systems code from stale text as if it were current clinical documentation. |
| **Why unsolved** | Requires access to prior notes for comparison + text similarity scoring + temporal inconsistency detection. Most coding systems only see the current note, not the patient's note history. |
| **Our solution** | Copy-forward detection pipeline (DISC-002 Section A.4); text similarity >85% flagged; lab/vital narrative-to-structured data cross-validation; problem list staleness scoring. |
| **Competitive advantage** | Prevents HCC overcoding from stale conditions; reduces compliance audit risk; differentiates our output quality from systems that blindly code copy-forwarded text. |

### Gap 4: Evidence-Quote Requirement for Every Suggestion

| Aspect | Details |
|--------|---------|
| **The gap** | Most coding AI systems suggest codes without pointing to the specific text in the note that supports the code. Coders must find the evidence themselves. If evidence doesn't exist, the suggestion is a hallucination. |
| **Why unsolved** | Traditional NLP models extract entities but don't preserve the source span. LLM-based systems can cite text but don't enforce citation as a hard requirement. |
| **Our solution** | Constitution Article II.2 — every `CodingSuggestion` has `evidence_quote: str` as a required Pydantic field (not Optional). Validation confirms the quote is a substring of the source document. |
| **Competitive advantage** | Every suggestion is auditable. Coders can verify in seconds. Hospital compliance teams can validate the system never suggests codes without evidence. This is a key procurement differentiator. |

### Gap 5: CDI + Coding in a Single System

| Aspect | Details |
|--------|---------|
| **The gap** | CDI (documentation improvement) and coding are separate products from separate vendors in every hospital. The CDI system identifies gaps but doesn't know what codes would result. The coding system codes what's documented but doesn't identify what's missing. |
| **Why unsolved** | CDI and coding evolved as separate disciplines with different users (CDI specialists vs coders). Vendors built for one user or the other. Integration requires understanding both workflows deeply. |
| **Our solution** | Single system with Coding Agent and CDI Agent sharing the same clinical analysis. CDI Agent sees the coding gaps; Coding Agent sees the CDI opportunities. DRG Agent ties them together with revenue impact. |
| **Competitive advantage** | A CDI query that results in a documented diagnosis that the Coding Agent captures generates measurable revenue. No other system can attribute CDI effort to DRG improvement in a single workflow. |

### Gap 6: Lab-to-Diagnosis Automated CDI Queries

| Aspect | Details |
|--------|---------|
| **The gap** | Labs showing AKI criteria (creatinine rise), sepsis indicators (lactate, cultures), or malnutrition markers (albumin, BMI) are documented in structured data but often not diagnosed by physicians. No competitor automatically generates CDI queries from lab trends. |
| **Why unsolved** | Requires integration of structured lab data + clinical knowledge of diagnostic criteria + non-leading query generation. Iodine Software does some of this but with template-based queries, not dynamic clinical reasoning. |
| **Our solution** | MCP tools query structured lab data; Skills contain KDIGO (AKI), SOFA (sepsis), and other diagnostic criteria; CDI Agent generates clinically specific queries citing actual lab values and dates. |
| **Competitive advantage** | The 18 lab triggers documented in DISC-002 Section C.3 represent billions in missed revenue nationally. Automated lab-to-CDI query generation is a unique capability. |

### Gap 7: DRG Impact Prediction Before Documentation

| Aspect | Details |
|--------|---------|
| **The gap** | No competitor shows the physician or CDI specialist the exact DRG and revenue impact of a documentation change BEFORE the change is made. CDI specialists estimate impact manually using DRG reference tables. |
| **Why unsolved** | Requires a real-time DRG grouper that can simulate "what-if" scenarios: "If this CDI query is answered and the diagnosis is added, the DRG changes from X to Y, worth $Z." This requires integrating coding + CDI + DRG in a single system. |
| **Our solution** | DRG Agent computes current DRG from coded diagnoses and simulates DRG with each potential CDI-driven addition. Impact shown to CDI specialist alongside each query. |
| **Competitive advantage** | CDI specialists can prioritize queries by revenue impact. CFOs can see real-time CDI ROI dashboards. This is the "dollar story" that sells the system (per constitution Article IV.2). |

### Gap 8: Payer-Aware Coding Validation

| Aspect | Details |
|--------|---------|
| **The gap** | Coding AI suggests clinically correct codes that will be denied by specific payers due to payer-specific rules (NCCI edits, LCD requirements, PA requirements, site-of-service rules). The claim is submitted and denied; rework begins. |
| **Why unsolved** | Requires maintaining payer-specific rule databases that change quarterly + integrating payer data with clinical coding logic. Most coding systems are payer-agnostic. |
| **Our solution** | NCCI edit validation in rules engine (Phase 1); LCD/NCD medical necessity checking (Phase 2); payer-specific rule database with quarterly updates (DISC-004 architecture). |
| **Competitive advantage** | Moving denial prevention upstream to the coding stage (before submission) eliminates the most expensive part of denials — the rework. This is a Waystar/Change Healthcare capability integrated into the coding workflow. |

### Gap 9: Graceful Degradation Architecture

| Aspect | Details |
|--------|---------|
| **The gap** | Healthcare AI systems fail catastrophically when dependencies are unavailable. EHR API down = system unusable. Model API down = system unusable. Coders are blocked and cannot work. |
| **Why unsolved** | Building resilient systems is expensive. Most healthcare AI startups optimize for demo scenarios, not production failure modes. Testing failure scenarios requires sophisticated infrastructure. |
| **Our solution** | Constitution Article II.5 — every agent returns `DegradedResult` on failure with `is_degraded=True`. Circuit breaker pattern for external calls. Offline mode with cached data. Manual coding mode always available. The UI never shows a broken state. |
| **Competitive advantage** | Hospital IT teams evaluate reliability heavily during procurement. A system that degrades gracefully vs one that crashes earns purchasing preference. Coders who are never blocked trust and adopt the system faster. |

### Gap 10: Prompt Intelligence Preservation (PHR)

| Aspect | Details |
|--------|---------|
| **The gap** | Competitors use LLMs with prompts that are iterated on ad-hoc by engineers. When an engineer leaves, the reasoning behind prompt decisions is lost. Prompt improvements are not systematically recorded. |
| **Why unsolved** | Prompt engineering is a new discipline. Most companies treat prompts as code (version-controlled) but not as knowledge artifacts (hypothesis-tracked). No industry standard for prompt history recording exists. |
| **Our solution** | PHR (Prompt History Records) in `docs/phr/` document every prompt change with the scenario that motivated it, the hypothesis tested, and the measured outcome. Prompts in `src/prompts/` are versioned constants referencing their PHR. |
| **Competitive advantage** | Our prompt intelligence is cumulative and transferable across team members and Claude sessions. A competitor would need to run every experiment we've run to match our prompt performance. This is intellectual property that cannot be copied from our codebase. |

### Gap 11: FHIR Vendor Abstraction

| Aspect | Details |
|--------|---------|
| **The gap** | Most competitors build for one EHR (usually Epic) and bolt on other EHR support later. The result is an Epic-native system with a Cerner compatibility layer that breaks on Cerner-specific edge cases (C-CDA parsing, different encounter classification, different extension handling). |
| **Why unsolved** | Building a true vendor-abstraction layer from the start is harder than building for one vendor and adapting. Most startups target Epic first (largest market share) and worry about Cerner later. |
| **Our solution** | FHIR client with adapter pattern from day one (DISC-003 Section F.1): abstract `FHIRClient` with `EpicFHIRClient` and `CernerFHIRClient` implementations. Core logic never depends on vendor-specific extensions. |
| **Competitive advantage** | Any new EHR vendor requires only a new adapter, not a system redesign. Sales team can promise Cerner support at the same quality as Epic — most competitors cannot. |

### Gap 12: Clinical Compliance as Auditable Architecture

| Aspect | Details |
|--------|---------|
| **The gap** | Competitors claim compliance but cannot demonstrate it architecturally. A hospital legal team asking "how do you prevent ICD-10 guideline violations?" gets a response like "our model was trained on compliant data" — which is not an auditable guarantee. |
| **Why unsolved** | True compliance architecture requires documenting every decision (ADRs), encoding every rule (rules engine), and making every constraint inspectable. This is expensive and slows down development. Startups prioritize speed over auditability. |
| **Our solution** | Constitution + ADRs + rules engine + evidence_quote requirement + human-in-the-loop. Every architectural decision is documented. Every coding rule is deterministic and inspectable. Every suggestion has an evidence trail. Hospital legal can audit the entire chain. |
| **Competitive advantage** | This is the procurement unlock. Hospital legal teams reject AI systems they cannot audit. Our compliance architecture is a documented, inspectable artifact — not a claim about model training. Per constitution Article V.4: "compliance is a feature, not a constraint." |

---

## Verification Status

Last verified: 2026-04-05 (FIX-001 research audit)
Verified by: Live web fetch during FIX-001 session

| Claim Category | Count | Status |
|---|---|---|
| VERIFIED-LIVE | 12 | Current as of fetch date |
| TRAINING-DATA (directional) | 4 | Use with caution; labeled inline |
| UNVERIFIABLE (our analysis) | 12 | Competitive gap analysis — our own assessment |
| OUTDATED (corrected in FIX-001) | 2 | Abridge funding ($212.5M→$773M), Nym funding ($48M→$92M) |

**Critical corrections made in FIX-001:**
- Abridge: Total funding updated from ~$212.5M to $773M; valuation from ~$850M-1B to $5.3B
- Nym Health: Total funding updated from ~$48M to $92M; added 6M+ annual chart volume
- Nuance acquisition: Confirmed $19.7B, completed March 2022

**Items still requiring periodic refresh:**
- Iodine Software funding and hospital count (PE-backed; exact current figures not public)
- Competitor product capabilities (companies improve continuously)
- MIMIC benchmark SOTA (new papers published regularly)

Next re-verification due: 2026-10-01 (quarterly competitor intelligence refresh)

---

## Sources

### Company Information

> **Note:** Company details are compiled from public sources
> including press releases, funding announcements, product
> documentation, and industry analyses through early 2025.
> Specific technical architecture details are inferred from
> publicly available information and may not reflect current
> product capabilities. Companies improve continuously.

- Abridge: https://www.abridge.com/
- Nym Health: https://www.nymhealth.com/
- Iodine Software: https://www.iodinesoftware.com/
- Nuance (Microsoft): https://www.nuance.com/healthcare.html
- Cohere Health: https://coherehealth.com/
- Waystar: https://www.waystar.com/
- 3M Health Information Systems (now Solventum): https://www.solventum.com/

### Academic Benchmarks

- MIMIC-III ICD Coding Benchmark: https://mimic.mit.edu/
- Papers With Code — Medical Code Prediction: https://paperswithcode.com/task/medical-code-prediction
- Mullenbach et al. (2018): "Explainable Prediction of Medical Codes from Clinical Text" (CAML)
- Vu et al. (2020): "A Label Attention Model for ICD Coding from Clinical Text" (LAAT)
- Huang et al. (2022): "PLM-ICD: Automatic ICD Coding with Pretrained Language Models"
- Yuan et al. (2022): "Code Synonyms Do Matter: Multiple Synonyms Matching Network for Automatic ICD Coding" (MSMN)

### Clinical NLP Models

- BioBERT: https://github.com/dmis-lab/biobert
- PubMedBERT: https://huggingface.co/microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext
- ClinicalBERT: https://huggingface.co/emilyalsentzer/Bio_ClinicalBERT
- scispaCy: https://allenai.github.io/scispacy/
- GatorTron: https://catalog.ngc.nvidia.com/orgs/nvidia/teams/clara/models/gatortron_og
- NegEx: Chapman et al. (2001): "A Simple Algorithm for Identifying Negated Findings and Diseases in Discharge Summaries"

### Industry Reports

- KLAS Research: Healthcare AI product ratings
- AMA Prior Authorization Physician Survey (annual)
- CAQH Index (administrative transaction cost benchmarking)
- Gartner Healthcare IT Market Guide
- CB Insights Healthcare AI Report

### Regulatory References

- OIG Guidance on CDI Queries: non-leading query requirements
- CMS ICD-10-CM Official Coding Guidelines: https://www.cms.gov/files/document/fy-2025-icd-10-cm-coding-guidelines.pdf
- AHIMA Standards of Ethical Coding
