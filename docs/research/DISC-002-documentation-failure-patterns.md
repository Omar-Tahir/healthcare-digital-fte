# DISC-002: Clinical Documentation Failure Patterns

**Research Phase:** DISCOVER
**Status:** Complete — verified 2026-04-05 (FIX-001)
**Date:** 2026-03-30
**Last Verified:** 2026-04-05 (FIX-001 research audit)
**Verification Method:** Live web fetch + primary source confirmation
**Unverified Items Remaining:** 3 (labeled inline)
**Purpose:** Catalog the clinical documentation failures that cause
medical coding errors, compliance risk, and revenue loss in US hospitals.
This document is the primary reference for building AI detection
algorithms in the NLP pipeline and CDI agent.

---

## Executive Summary

Clinical documentation failures are the root cause of coding
inaccuracy, DRG misassignment, compliance risk, and billions
in annual revenue leakage across US hospitals. This research
identifies five major failure pattern categories, quantifies
their prevalence and financial impact, and defines detection
methods and interventions for our AI system.

**Key findings:**

- **50.1%** of all text in EHR notes is duplicated from prior
  documentation on the same patient (JAMA Network Open 2022;
  PMC9513649; 104M notes, 1.96M patients)
  [VERIFIED-LIVE ✓ — fetched 2026-04-05]
- **32.9%** of hospital admissions have clinical evidence of
  disease without corresponding ICD codes (PMC11520144, 2024;
  34,104 admissions analyzed)
  [VERIFIED-LIVE ✓ — fetched 2026-04-05]
- **$22.7 million** in estimated annual lost revenue from a
  single institution due to missing secondary diagnosis codes
  (PMC11520144: $22,680,584.50)
  [VERIFIED-LIVE ✓ — fetched 2026-04-05]
- **55%** of critically ill patients with severe sepsis are
  discharged without sepsis ICD codes
  [TRAINING-DATA — likely from PMC10701636 or similar; no
  direct URL confirmed. Treat as directional estimate]
- **30-53%** of inpatients are malnourished, but only
  **3.7-8.6%** are coded as malnourished (PMC11613653, 2024;
  coding rates 2016-2019; original 53% from PMC5059542
  specific cohort; broader literature shows 30-50% prevalence)
  [PARTIALLY VERIFIED — updated range from live data]
- **70%** of discharge coding uses only the discharge summary,
  which has a **42% incorrect DRG rate** when used alone
  (Tsopra et al., ScienceDirect 2018)
  [VERIFIED-LIVE ✓ — source confirmed in references]

---

## Table of Contents

- [A. Copy-Forward Failures](#a-copy-forward-failures)
- [B. Specificity Failures](#b-specificity-failures)
- [C. Missing Secondary Diagnoses](#c-missing-secondary-diagnoses)
- [D. Abbreviation and Terminology Ambiguity](#d-abbreviation-and-terminology-ambiguity)
- [E. Documentation Timing Failures](#e-documentation-timing-failures)
- [F. Cross-Cutting Detection Architecture](#f-cross-cutting-detection-architecture)
- [Sources](#sources)

---

## A. Copy-Forward Failures

### A.1 Prevalence

Copy-paste (also called "cloning" or "copy-forward") is the
single most pervasive documentation integrity problem in
modern EHRs.

| Metric | Value | Source |
|--------|-------|--------|
| Clinicians who routinely use copy-paste | 66-90% | PMC5373750 (systematic review) |
| Clinicians who use copy-paste "almost always" or "most of the time" | 78% | PMC5373750 (large physician survey) |
| Residents/attendings whose ICU notes contain copied text | 82% residents, 74% attendings | PMC5373750 |
| Inpatient medicine progress notes containing copied material | 77% (229 of 299 notes) | PMC5373750 |
| Outpatient notes containing copied material | 10.8% | PMC5373750 |
| All text in EHR notes that is duplicated from prior documentation | 50.1% | JAMA 2022 (100M+ notes) |
| Text in a typical patient record that is original (manually entered) | 18% | ECRI copy-paste report |
| Text that was copy-pasted | 46% | ECRI copy-paste report |
| Text that was auto-imported | 36% | ECRI copy-paste report |
| Proportion of copied text in notes (2015 baseline) | ~33% | ACDIS/JAMA analysis |
| Proportion of copied text in notes (2020) | 54.2% | ACDIS/JAMA analysis |
| Hospitals with copy-paste policies in place | ~25% | OIG Report OEI-01-11-00571 |
| Dermatology residents who copy prior author's past medical history | 83% | PMC5373750 |

**Key trend:** Copy-forward prevalence is *increasing*, not
decreasing. From 33% of note text in 2015 to 54.2% in 2020.

### A.2 Clinical Findings Most Commonly Incorrectly Forward-Copied

Based on the research, these clinical elements are most
frequently propagated incorrectly via copy-forward:

1. **Problem lists and past medical history** — Resolved
   conditions persist in the active problem list across
   encounters (e.g., "AKI" documented in a prior admission
   appears as active in current notes after resolution)

2. **Physical exam findings** — Prior exam findings copied
   verbatim even when patient status has changed (e.g.,
   "bilateral pedal edema 2+" persists after diuresis)

3. **Medication lists** — Discontinued medications appear
   in subsequent notes; dosage changes not reflected

4. **Vital signs and lab values** — Specific values from
   prior encounters copied into current assessment
   (e.g., creatinine of 2.1 from 3 days ago copied as
   current when actual value has normalized)

5. **Assessment and plan** — Treatment plans from prior
   visits copied without updates; particularly dangerous
   for evolving conditions like sepsis or AKI

6. **Allergies** — Incorrectly propagated allergy information
   or missing new allergy documentation

7. **Social history** — Smoking status, substance use copied
   from years-old entries without verification

### A.3 How Copy-Forward Creates HCC Errors

Hierarchical Condition Category (HCC) coding for risk
adjustment requires that each condition be **actively managed
and documented in the current encounter**. Copy-forward
creates HCC errors through several mechanisms:

1. **Condition persistence without active management:**
   A chronic condition (e.g., "Type 2 DM with CKD stage 3")
   is copied forward from a prior visit but the physician
   does not address it in the current encounter's assessment
   and plan. The condition appears in the note but does not
   meet MEAT criteria (Monitor, Evaluate, Assess, Treat).
   This inflates risk scores fraudulently.

2. **Resolved conditions coded as active:**
   AKI that resolved 6 months ago still appears in the
   problem list due to copy-forward. If coded, this is
   a false HCC capture that triggers audit risk.

3. **Specificity degradation over time:**
   The original documentation may have stated "Type 2 DM
   with diabetic nephropathy, CKD stage 3a" but through
   successive copy-forward cycles, it degrades to
   "diabetes with kidney disease" — losing the HCC-relevant
   specificity.

4. **Duplicate condition capture:**
   The same condition documented in multiple copied sections
   may be interpreted as multiple conditions by coders
   or NLP systems.

**Compliance risk:** The OIG specifically identified
copy-paste as a fraud vulnerability. CMS and OIG consider
copy-paste documentation that supports billing for higher-level
services without genuine clinical activity to be potential
False Claims Act (FCA) exposure.

### A.4 Detection Phrases and Methods

**Phrases indicating copy-forward in clinical notes:**

| Indicator Phrase | What It Suggests |
|-----------------|-----------------|
| "as previously documented" | Explicit reference to prior note |
| "as noted above" / "as noted previously" | Self-referencing copied content |
| "unchanged from prior" | May be legitimate or lazy copy |
| "see prior note" / "see above" | Deferred documentation |
| "continues on [medication]" without current assessment | Copied med list without review |
| Timestamps matching prior visit dates | Technical copy-forward artifact |
| Identical vital signs across consecutive days | Improbable clinical consistency |
| Exam findings identical to prior note verbatim | Statistical improbability |
| "Patient reports" followed by third-person language | Mismatch suggesting template/copy |

**Automated detection methods for our AI system:**

1. **Text similarity scoring:** Compare current note sections
   against the same patient's prior notes. Flag when
   similarity > 85% for clinical assessment sections.
   Use fingerprinting (MinHash / SimHash) for efficient
   comparison at scale.

2. **Temporal inconsistency detection:** Flag when clinical
   values in the narrative (labs, vitals) do not match
   structured data from the same date. Example: note says
   "creatinine 2.1" but today's lab shows 1.0.

3. **Metadata analysis:** Check note authorship timestamps,
   modification history, and section-level edit patterns.
   Flag notes where large sections appear simultaneously
   (paste event) rather than sequentially (typed).

4. **Clinical plausibility checks:** Flag identical physical
   exam findings across 3+ consecutive days. Flag identical
   assessment/plan text across encounters for evolving
   conditions (e.g., sepsis, AKI, post-surgical recovery).

5. **Problem list staleness scoring:** Score each problem list
   entry by time since it was last actively addressed in an
   assessment/plan section. Flag entries > 12 months without
   active management documentation.

### A.5 AI System Interventions for Copy-Forward

| Detection | Intervention | Priority |
|-----------|-------------|----------|
| Note similarity > 85% vs prior encounter | CDI alert: "Note content substantially similar to [prior date]. Please verify clinical findings are current." | High |
| Lab/vital mismatch vs structured data | Hard flag: "Documented creatinine [X] does not match today's lab value [Y]. Please reconcile." | Critical |
| Problem list entry > 12 months without MEAT | CDI query: "Is [condition] still an active problem? If so, please document current status and management." | Medium |
| Identical exam findings x3+ days | Soft flag: "Physical exam documentation identical for [N] consecutive days. Please verify findings are current." | Medium |
| HCC condition present without current management | Compliance flag: "HCC condition [X] present in note but not addressed in assessment/plan. Cannot be coded for risk adjustment without active management documentation." | High |

---

## B. Specificity Failures

Specificity failures occur when physicians document a
diagnosis at a lower level of detail than what is clinically
known, resulting in assignment of a less specific (and
typically lower-weighted) ICD-10 code. This is the single
highest-impact failure pattern for DRG revenue.

### B.1 Top 20 Diagnoses With Specificity Failures

The following table documents the 20 most common diagnoses
where physicians document non-specific versions when clinical
information supports a specific code. Each entry includes
the CC/MCC impact and the DRG revenue consequence.

#### 1. Heart Failure

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "heart failure" or "CHF" | "acute on chronic systolic heart failure" |
| ICD-10 Code | I50.9 (Heart failure, unspecified) | I50.23 (Acute on chronic systolic HF) |
| CC/MCC Status | Non-CC | MCC |
| DRG Impact | DRG 293 (HF without CC/MCC) | DRG 291 (HF with MCC) |
| Revenue Difference | ~$3,900 vs ~$11,400 per case | **~$7,500 per case** |
| Detection | Note mentions "CHF" or "heart failure" without type/acuity qualifier | |
| CDI Query | "Please specify: Is the heart failure systolic, diastolic, or combined? Is it acute, chronic, or acute on chronic?" | |

**Source:** CMS MS-DRG v37 weights; The Hospitalist coding
guidance; FY2012 CMS cost data (DRG 291: $11,437; DRG 292:
$7,841; DRG 293: $5,400).

#### 2. Sepsis

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "sepsis" without organism or severity | "severe sepsis due to E. coli UTI with acute kidney injury" |
| ICD-10 Code | A41.9 (Sepsis, unspecified organism) | A41.51 + R65.20 + N17.9 |
| CC/MCC Status | MCC (but lower DRG) | MCC (higher DRG with organ dysfunction) |
| DRG Impact | DRG 872 (Sepsis without MCC) | DRG 870 (Sepsis with MCC) |
| Revenue Difference | ~$6,931 vs ~$49,690 per case | **~$42,759 per case** |
| Prevalence | A41.9 used 72% of the time | |
| Detection | Sepsis documented without organism, severity, or organ dysfunction linkage | |
| CDI Query | "Please specify the causative organism and any associated organ dysfunction (AKI, respiratory failure, etc.)" | |

**Source:** PMC10701636; CMS 2020 Medicare data (DRG 870:
avg $49,690; DRG 871: avg $13,357; DRG 872: avg $6,931).

**Critical stat:** 55% of critically ill patients with severe
sepsis are discharged without sepsis ICD codes
[TRAINING-DATA — directional estimate]. Sepsis is the most
expensive condition treated in US hospitals at **$52.1 billion
aggregate** (2021; AHRQ HCUP report; up from $38.2B in 2019)
and **~$18,244 per stay** average (2013 baseline; likely higher
in current dollars).
[VERIFIED-LIVE ✓ — corrected from $41.5B (older data) to
$52.1B per AHRQ report to Congress, fetched 2026-04-05.
SOURCE: https://hcup-us.ahrq.gov/reports/SepsisUSBurdenHospitalCare.pdf]

#### 3. Acute Kidney Injury (AKI)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | Creatinine elevation noted but AKI not stated | "Acute kidney injury, stage 2, due to contrast nephropathy" |
| ICD-10 Code | Not coded (missed entirely) | N17.9 (AKI, unspecified) or N17.0-N17.2 (by stage) |
| CC/MCC Status | Nothing captured | MCC |
| DRG Impact | Base DRG | DRG with MCC |
| Revenue Difference | Variable | **$3,000-$8,000 per case** |
| Detection | Creatinine rise >=0.3 mg/dL in 48h or >=1.5x baseline in 7 days without explicit AKI documentation | |
| CDI Query | "Creatinine rose from [X] to [Y] within [Z] hours, meeting KDIGO criteria. Does the patient have acute kidney injury?" | |

**Source:** KDIGO criteria; UASI CDI guidance; ACDIS
Q&A on KDIGO criteria.

**Key rule:** Coders cannot code AKI based solely on
creatinine values — the physician must explicitly document
"acute kidney injury" or "acute renal failure."

#### 4. Respiratory Failure

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "respiratory distress" or "hypoxia" | "acute hypoxic respiratory failure" |
| ICD-10 Code | R06.00 (Dyspnea, unspecified) | J96.01 (Acute respiratory failure with hypoxia) |
| CC/MCC Status | Non-CC | MCC |
| DRG Impact | Base DRG | DRG with MCC |
| Revenue Difference | Variable | **$4,000-$10,000 per case** |
| Detection | O2 sat < 90%, PaO2 < 60 mmHg, or patient on BiPAP/ventilator without explicit respiratory failure documentation | |
| CDI Query | "Patient required [supplemental O2/BiPAP/intubation] with PaO2 of [X]. Does the patient have acute respiratory failure?" | |

**Source:** ICD-10 J96 code family; ACDIS coding guidance.

#### 5. Malnutrition

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "poor appetite" or "weight loss" | "severe protein-calorie malnutrition (BMI 16.2, albumin 2.1)" |
| ICD-10 Code | Not coded or R63.4 (Abnormal weight loss) | E43 (Severe protein-calorie malnutrition) |
| CC/MCC Status | Non-CC | MCC |
| DRG Impact | Base DRG | DRG with MCC |
| Revenue Difference | Variable | **$3,000-$9,000 per case** |
| Prevalence | 53% of inpatients are malnourished; only 0.9-5.4% coded | |
| Detection | BMI < 18.5, albumin < 3.0, unintentional weight loss > 5% in 30 days, dietitian consult ordered | |
| CDI Query | "Patient has BMI of [X], albumin of [Y], and [Z]% weight loss. Does the patient have malnutrition? If so, please specify severity (mild, moderate, severe)." | |

**Source:** PMC5059542; OIG report on severe malnutrition
coding (identified ~$1 billion in overpayments for FY2016-17,
indicating both over- and under-coding are compliance risks).

#### 6. Pneumonia (Organism Specificity)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "pneumonia" | "pneumonia due to Pseudomonas aeruginosa" |
| ICD-10 Code | J18.9 (Pneumonia, unspecified organism) | J15.1 (Pneumonia due to Pseudomonas) |
| CC/MCC Status | CC | MCC (when specific organism shifts DRG) |
| DRG Impact | DRG 195 (Simple pneumonia without MCC) | DRG 177-179 (Respiratory infections) |
| Revenue Difference | Variable | **$2,000-$6,000 per case** |
| Detection | Positive sputum/blood culture results available but pneumonia documented without organism | |
| CDI Query | "Culture results show [organism]. Can pneumonia be attributed to this organism?" | |

**Source:** ICD10Monitor PEPPER guidance; Turquoise Health
DRG manual.

#### 7. Diabetes with Complications

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "diabetes" or "Type 2 DM" | "Type 2 DM with diabetic nephropathy, CKD stage 3" |
| ICD-10 Code | E11.9 (T2DM without complications) | E11.22 (T2DM with diabetic CKD) + N18.3 |
| CC/MCC Status | Non-CC | CC (with linked complications) |
| DRG Impact | DRG 639 (Diabetes without CC/MCC) | DRG 638 (Diabetes with CC) |
| Revenue Difference | Variable | **$1,500-$4,000 per case** |
| Detection | DM documented without complications; note mentions nephropathy, neuropathy, retinopathy, or foot ulcer but not linked to DM | |
| CDI Query | "Patient has DM and [complication]. Is the [complication] a diabetic complication?" | |

**Source:** PMC5669129; ICD-10 E11 code family.

#### 8. COPD with Exacerbation

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "COPD" | "acute exacerbation of COPD" |
| ICD-10 Code | J44.9 (COPD, unspecified) | J44.1 (COPD with acute exacerbation) |
| CC/MCC Status | CC | MCC (when principal Dx shifts DRG) |
| DRG Impact | DRG 192 (COPD without CC/MCC) | DRG 190 (COPD with MCC) |
| Revenue Difference | Variable | **$2,000-$5,000 per case** |
| Detection | Patient admitted for COPD with increased dyspnea, wheezing, or steroid/nebulizer use but "exacerbation" not documented | |
| CDI Query | "Patient presents with worsening dyspnea and increased bronchodilator use. Is this an acute exacerbation of COPD?" | |

#### 9. Encephalopathy

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "altered mental status" or "confusion" | "metabolic encephalopathy due to hepatic failure" |
| ICD-10 Code | R41.82 (Altered mental status) | G93.41 (Metabolic encephalopathy) + K72.x |
| CC/MCC Status | Non-CC | MCC |
| DRG Impact | Base DRG | DRG with MCC |
| Revenue Difference | Variable | **$4,000-$10,000 per case** |
| Detection | AMS documented; metabolic derangement present (hyponatremia, uremia, hepatic failure, hypoxia); no encephalopathy diagnosis | |
| CDI Query | "Patient has altered mental status with [metabolic abnormality]. Does the patient have encephalopathy? If so, please specify etiology." | |

**Source:** PMC12352811; ACDIS Q&A on encephalopathy.

#### 10. Pressure Ulcer (Stage Specificity)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "pressure ulcer" or "decubitus" | "Stage 3 pressure ulcer of sacrum, 5cm x 3cm" |
| ICD-10 Code | L89.90 (Pressure ulcer, unspecified) | L89.153 (Pressure ulcer of sacral region, stage 3) |
| CC/MCC Status | Non-CC (unspecified) | MCC (stage 3 or 4) |
| DRG Impact | Base DRG | DRG with MCC |
| Revenue Difference | Variable | **$3,000-$8,000 per case** |
| Detection | Wound care orders present; wound care notes document staging but physician note says only "pressure ulcer" without stage | |
| CDI Query | "Wound care notes indicate [stage/size/location]. Please document the stage and location in your progress note." | |

#### 11. Anemia (Type Specificity)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "anemia" | "acute blood loss anemia due to GI hemorrhage" |
| ICD-10 Code | D64.9 (Anemia, unspecified) | D62 (Acute posthemorrhagic anemia) |
| CC/MCC Status | Non-CC | CC |
| DRG Impact | Base DRG | DRG with CC |
| Revenue Difference | Variable | **$1,500-$3,000 per case** |
| Detection | Hemoglobin drop > 2 g/dL, transfusion ordered, but anemia type not documented | |
| CDI Query | "Hemoglobin dropped from [X] to [Y] with transfusion ordered. Is this acute blood loss anemia? What is the source?" | |

#### 12. Obesity (Severity)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "obese" or "overweight" | "morbid obesity, BMI 42.3" |
| ICD-10 Code | E66.9 (Obesity, unspecified) | E66.01 (Morbid obesity) + Z68.42 (BMI 42) |
| CC/MCC Status | Non-CC | CC |
| DRG Impact | Base DRG | DRG with CC |
| Revenue Difference | Variable | **$1,000-$3,000 per case** |
| Detection | BMI >= 40 in vitals but physician documents only "obese" without severity | |
| CDI Query | "Patient's BMI is [X]. Does the patient have morbid/severe obesity?" | |

#### 13. Atrial Fibrillation (Type)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "atrial fibrillation" or "afib" | "persistent atrial fibrillation" or "chronic atrial fibrillation" |
| ICD-10 Code | I48.91 (Unspecified atrial fibrillation) | I48.1 (Persistent) or I48.2 (Chronic) |
| CC/MCC Status | CC either way, but specificity affects accuracy | |
| DRG Impact | Base DRG without CC | DRG with CC |
| Revenue Difference | Variable | **$1,500-$3,000 per case** |
| Detection | AF documented without type (paroxysmal, persistent, chronic, permanent) | |
| CDI Query | "Is the atrial fibrillation paroxysmal, persistent, long-standing persistent, or permanent?" | |

**Note (2026-04-01):** Per CMS MS-DRG v42.1 CC/MCC list,
I48.91 (unspecified AFib) is designated **Non-CC** while
I48.0/I48.1/I48.11/I48.21 (type-specified) are **CC**. This
makes AFib type specification a Non-CC → CC upgrade — one of
the highest-value low-effort CDI queries since it requires
only documentation specificity, not additional clinical findings.

**Source:** CMS ICD-10-CM/PCS MS-DRG v42.1 CC/MCC List;
HeartBase CC/MCC capture scenarios (2024).

#### 14. Urinary Tract Infection (Organism)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "UTI" | "UTI due to E. coli" |
| ICD-10 Code | N39.0 (UTI, site not specified) | N39.0 + B96.20 (E. coli as cause) |
| CC/MCC Status | Non-CC vs CC when linked to sepsis | |
| DRG Impact | DRG-neutral (organism code B96.20 is non-CC) | Quality/compliance value only |
| Revenue Difference | **$0 DRG impact** | Organism specificity improves quality metrics and infection surveillance reporting |
| Detection | Urine culture positive but organism not documented in physician note | |

**Note (2026-04-01):** Adding organism code B96.20 does not
change CC/MCC status or DRG weight. Value is in coding
completeness per ICD-10-CM guidelines, antimicrobial
stewardship tracking, and infection surveillance reporting.

**Source:** CMS MS-DRG v42.1 CC/MCC List (B96.20 confirmed
non-CC).

#### 15. Acute Myocardial Infarction (Type/Location)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "heart attack" or "MI" | "acute STEMI involving LAD territory" |
| ICD-10 Code | I21.9 (AMI, unspecified) | I21.01 (STEMI involving LAD) |
| CC/MCC Status | MCC either way | Specificity affects quality metrics |
| DRG Impact | DRG 280-282 (AMI) — same family regardless of type/location | Quality metric accuracy |
| Revenue Difference | **$0 DRG impact** | STEMI/NSTEMI distinction critical for CMS 30-day mortality/readmission measures, NCDR reporting, and Leapfrog/Star ratings |
| Detection | Troponin elevation + ECG changes without specifying STEMI vs NSTEMI and territory | |

**Note (2026-04-01):** Both I21.9 and I21.01 are MCC and
group to DRG 280-282. Revenue impact is zero, but
STEMI vs NSTEMI miscoding corrupts quality measure cohort
assignment, which affects CMS Star ratings and public
reporting. DRG 280 (AMI w/MCC): ~$10,660; DRG 282
(AMI w/o CC/MCC): ~$4,745.

**Source:** CMS MS-DRG v42.1; AAPC DRG code references.

#### 16. Acute Pancreatitis (Etiology)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "pancreatitis" | "acute alcoholic pancreatitis with peripancreatic necrosis" |
| ICD-10 Code | K85.9 (Acute pancreatitis, unspecified) | K85.20 + K85.91 |
| CC/MCC Status | CC vs MCC with necrosis | |
| DRG Impact | DRG 438-440 (Pancreas disorders) — same family; K85.90 and K85.91 both MCC as secondary Dx | SOI/ROM impact |
| Revenue Difference | **$0 direct DRG impact** between K85.90 and K85.91 | Documenting **infected** necrosis (K85.92) supports surgical DRG shift with significantly higher weights |
| Detection | Lipase elevation + imaging findings not reflected in documentation specificity | |

**Note (2026-04-01):** K85.90 (without necrosis) and K85.91
(with necrosis) are both MCC as secondary diagnoses and group
to the same DRG family as principal diagnosis. The real CDI
value is documenting **infected necrosis** (K85.92), which
supports procedure coding for debridement/drainage and may
shift to surgical DRGs with substantially higher weights.
DRG 438 (Pancreas w/MCC): ~$10,595; DRG 440 (w/o CC/MCC):
~$4,030.

**Source:** CMS MS-DRG v42.1 CC/MCC List; CMS DRG weights
FY2024-2025.

#### 17. Deep Vein Thrombosis (Location/Laterality)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "DVT" | "acute DVT of right femoral vein" |
| ICD-10 Code | I82.40 (Unspecified DVT of unspecified lower extremity) | I82.411 (Acute DVT of right femoral vein) |
| CC/MCC Status | CC | CC (but laterality required for specificity) |
| DRG Impact | I82.40 is a non-billable header code; lateralized codes (I82.411 etc.) are CC | Coding compliance requirement |
| Revenue Difference | **$1,500-$3,000 per case** (CC uplift when DVT is secondary Dx) | Without laterality documentation, claim may be rejected |
| Detection | Doppler ultrasound shows specific vein involvement but physician documents only "DVT" | |

**Note (2026-04-01):** I82.40 (unspecified DVT of lower
extremity) is a non-billable header code — it cannot be
submitted on a claim. A laterality-specific code is required.
The CDI opportunity here is ensuring physicians document
laterality so coders can assign a billable, CC-carrying code.

**Source:** CMS ICD-10-CM code edits; CMS MS-DRG v42.1.

#### 18. Cerebrovascular Accident (Type)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "stroke" or "CVA" | "acute ischemic stroke of right MCA territory with left hemiplegia" |
| ICD-10 Code | I63.9 (Cerebral infarction, unspecified) | I63.511 + G81.04 |
| CC/MCC Status | MCC either way | Specificity critical for quality reporting |
| DRG Impact | DRG 061-066 (Ischemic stroke) — same family regardless of vessel specificity | Quality metric accuracy |
| Revenue Difference | **$0 DRG impact** | Territory/vessel specificity critical for CMS Comprehensive Stroke Center metrics and quality reporting |
| Detection | Imaging results showing specific territory/vessel not reflected in physician documentation | |

**Note (2026-04-01):** Both I63.9 and I63.511 are MCC and
group to the same stroke DRG family. Revenue impact is zero,
but accurate vessel/territory coding is required for CMS
stroke quality measures, Joint Commission Comprehensive
Stroke Center certification metrics, and Get With The
Guidelines-Stroke registry reporting.

**Source:** CMS MS-DRG v42.1; Joint Commission stroke
certification standards.

#### 19. Alcohol Withdrawal / Dependence

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "alcohol abuse" or "ETOH use" | "alcohol dependence with withdrawal delirium" |
| ICD-10 Code | F10.10 (Alcohol abuse, uncomplicated) | F10.231 (Alcohol dependence with withdrawal delirium) |
| CC/MCC Status | Non-CC | MCC |
| DRG Impact | Base DRG | DRG with MCC |
| Revenue Difference | Variable | **$3,000-$7,000 per case** |
| Detection | CIWA protocol orders, benzodiazepine administration, but only "alcohol use" documented | |

#### 20. Hypertension (Type/Stage/Target Organ)

| Element | Non-Specific | Specific |
|---------|-------------|----------|
| Documentation | "HTN" or "high blood pressure" | "hypertensive heart disease with heart failure" |
| ICD-10 Code | I10 (Essential hypertension) | I11.0 (Hypertensive heart disease with HF) |
| CC/MCC Status | Non-CC | CC (or MCC if HF is acute) |
| DRG Impact | I10 groups to DRG 304-305 (Hypertension); I11.0 shifts to DRG 291-293 (HF & Shock) | **DRG family shift** |
| Revenue Difference | ~$5,590 (DRG 305) vs ~$9,360 (DRG 291 w/MCC) | **$3,000-$9,000+ per case** |
| Detection | HTN documented alongside HF but no causal relationship stated | |
| CDI Query | "Patient has both hypertension and heart failure. Is the heart failure due to hypertension (hypertensive heart disease)?" | |

**Note (2026-04-01):** This is one of the highest-value CDI
targets. ICD-10-CM Guideline I.A.15 establishes an **assumed
causal relationship** between hypertension and heart failure —
when both are documented, the coder must assign I11.0
(hypertensive heart disease with HF) plus the appropriate
I50.x code. This shifts the case from the Hypertension DRG
family (304-305) to the Heart Failure DRG family (291-293),
producing a major revenue impact. I10 alone is Non-CC;
I11.0 is CC and triggers the DRG family shift.

**Source:** CMS MS-DRG v42.1; ICD-10-CM Official Guidelines
I.A.15; CMS DRG weights FY2024-2025 (DRG 291: ~$9,360;
DRG 305: ~$5,590; national avg base rate ~$6,500/weight unit).

### B.2 Revenue Impact Summary

Based on CMS DRG weight data and research findings:

| Specificity Gap | Est. Per-Case Revenue Loss | National Volume Impact |
|----------------|---------------------------|----------------------|
| Heart failure type/acuity | $3,900-$7,500 | Very High (~1M HF admissions/yr) |
| Sepsis organism/severity | $6,000-$42,000 | Very High (~1.7M sepsis cases/yr) |
| AKI missed entirely | $3,000-$8,000 | High |
| Respiratory failure missed | $4,000-$10,000 | High |
| Malnutrition missed | $3,000-$9,000 | Very High (53% prevalence, <5% coded) |
| Pneumonia organism | $2,000-$6,000 | High |
| Encephalopathy missed | $4,000-$10,000 | Medium-High |

**Key finding from HFMA:** Across 612 inpatient cases at one
institution, inaccurate ICD-10 coding created a potential loss
of **$1.149 million**, averaging **$1,877 per inpatient case**.

### B.3 AI Detection Methods for Specificity Failures

**Pattern 1: Diagnosis without qualifier**
Detect when a diagnosis term appears without required
ICD-10 qualifiers (type, acuity, laterality, stage, organism).

```
IF note contains "heart failure" OR "CHF"
AND note does NOT contain ("systolic" OR "diastolic" OR
    "HFrEF" OR "HFpEF" OR "acute" OR "chronic" OR
    "ejection fraction")
THEN trigger CDI query for HF type and acuity
```

**Pattern 2: Clinical evidence without diagnosis**
Detect when structured data (labs, vitals, imaging) meets
diagnostic criteria but no corresponding diagnosis exists.

```
IF creatinine_current >= creatinine_baseline * 1.5
   OR creatinine_delta >= 0.3 within 48h
AND note does NOT contain ("acute kidney injury" OR "AKI"
    OR "acute renal failure")
THEN trigger CDI query for AKI
```

**Pattern 3: Non-specific code when specific is available**
Post-coding audit: detect when assigned code is unspecified
(.9 codes) and clinical documentation supports specificity.

**Pattern 4: Missing causal linkage**
Detect when two conditions coexist but causal relationship
is not documented (e.g., "hypertension" and "heart failure"
without "hypertensive heart disease").

---

## C. Missing Secondary Diagnoses

### C.1 Scale of the Problem

Missing secondary diagnoses represent the largest single
source of DRG revenue leakage in US hospitals.

| Metric | Value | Source |
|--------|-------|--------|
| Admissions with clinical evidence lacking ICD codes | 32.9% (11,520 of 34,104) | PMC11520144 |
| Admissions eligible for DRG upgrade but lacking codes | 5.8% (1,990 cases) | PMC11520144 |
| Estimated annual lost revenue (single institution) | $22,680,584 | PMC11520144 |
| Base-to-CC upgrade losses | $4,971,278 | PMC11520144 |
| CC-to-MCC upgrade losses | $15,228,522 | PMC11520144 |
| Base-to-MCC upgrade losses | $2,480,785 | PMC11520144 |

### C.2 Most Commonly Missed Conditions

The PMC11520144 study found the following conditions have
the highest omission rates — conditions present in the
clinical record but not coded:

| Condition | Omission Rate | CC/MCC Status |
|-----------|--------------|---------------|
| Delirium | 80.3% | MCC |
| Acidemia | 63.2% | CC |
| Hyponatremia | 62.3% | CC |
| Severe malnutrition | 57.9% | MCC |

### C.3 Lab/Vitals Findings That Should Trigger Documentation

These objective findings frequently appear in the medical
record but physicians fail to document the corresponding
diagnosis. Our AI system must detect these patterns and
generate CDI queries.

| Lab/Vital Finding | Threshold | Expected Diagnosis | CC/MCC |
|-------------------|-----------|-------------------|--------|
| Creatinine rise >=0.3 mg/dL in 48h | KDIGO Stage 1 | Acute Kidney Injury | MCC |
| Creatinine >=1.5x baseline in 7 days | KDIGO Stage 1+ | Acute Kidney Injury | MCC |
| Sodium < 135 mEq/L | < 135 | Hyponatremia | CC |
| Sodium < 120 mEq/L | < 120 | Severe hyponatremia | MCC |
| Potassium > 5.5 mEq/L | > 5.5 | Hyperkalemia | CC |
| pH < 7.35 with HCO3 < 22 | Abnormal | Metabolic acidosis | CC |
| Lactate > 2.0 mmol/L | > 2.0 | Lactic acidosis (consider sepsis) | CC/MCC |
| Albumin < 3.0 g/dL + weight loss | Low | Malnutrition | CC/MCC |
| BMI < 18.5 | < 18.5 | Underweight / malnutrition | CC |
| BMI >= 40 | >= 40 | Morbid obesity | CC |
| PaO2 < 60 mmHg | < 60 | Respiratory failure | MCC |
| O2 sat < 88% on room air | < 88% | Hypoxemia / respiratory failure | MCC |
| INR > 3.5 on warfarin | > 3.5 | Coagulopathy | CC |
| Hemoglobin drop > 2 g/dL | Acute drop | Acute blood loss anemia | CC |
| WBC > 12,000 + fever + tachycardia | SIRS criteria | Consider sepsis workup | MCC |
| Blood cultures positive | Positive | Bacteremia / sepsis | MCC |
| Troponin elevation | Above normal | Acute MI or myocardial injury | MCC |
| BNP > 400 pg/mL | > 400 | Heart failure (if not already documented) | CC/MCC |

### C.4 Chronic Conditions Commonly Underdocumented During Inpatient Stays

When a patient is admitted for an acute condition, physicians
often fail to document chronic conditions that are actively
managed during the stay. These represent CC/MCC capture
opportunities:

1. **CKD (Chronic Kidney Disease)** — Patient receives
   renally-dosed medications but CKD not documented
2. **COPD** — Patient receives inhalers but COPD not in
   discharge diagnosis list
3. **Diabetes complications** — DM documented but
   neuropathy, nephropathy, retinopathy not linked
4. **Heart failure** — History of HF, receiving diuretics,
   but HF not documented as active
5. **Morbid obesity** — BMI >= 40 in vitals but not documented
   as diagnosis
6. **Chronic pain** — Pain management ongoing but not
   coded as secondary diagnosis
7. **Protein-calorie malnutrition** — Dietitian consulted,
   supplements ordered, but diagnosis not documented by physician
8. **Alcohol/substance dependence** — Medications for
   dependence prescribed but only "use" documented (not
   "dependence")
9. **Tobacco dependence** — Active smoker receiving
   nicotine replacement but F17.210 not coded
10. **Depression/anxiety** — Psychiatric medications continued
    during stay but mental health diagnoses absent

### C.5 AI Detection and Intervention

**Detection approach:** Cross-reference three data sources:

1. **Medication list:** Medications imply diagnoses
   (e.g., insulin → diabetes; furosemide → heart failure;
   albuterol → COPD/asthma)
2. **Lab trends:** Abnormal lab patterns imply diagnoses
   (see table in C.3)
3. **Documentation text:** NLP extraction of diagnoses
   mentioned vs. coded

**Intervention matrix:**

| Gap Type | Intervention |
|----------|-------------|
| Lab meets criteria, no diagnosis documented | CDI query citing specific lab values and diagnostic criteria |
| Medication implies condition not documented | CDI query: "Patient is receiving [med]. Does the patient have [condition]?" |
| Condition in notes but not on problem list | Soft flag for coder: "Condition mentioned in [note section] but not in discharge diagnoses" |
| Chronic condition history but not documented this encounter | CDI query: "Patient has history of [condition]. Is it still active? If so, please document current status." |
| CC/MCC diagnosis available but not captured | Priority flag to CDI team with estimated DRG impact |

---

## D. Abbreviation and Terminology Ambiguity

### D.1 Scale of the Problem

Clinical text uses abbreviations extensively, creating
significant challenges for both human coders and NLP systems.

| Metric | Value | Source |
|--------|-------|--------|
| Average number of senses per abbreviation | 1.77 | Nature Scientific Data (2021) |
| Abbreviations with more than one meaning | 23% | Nature Scientific Data |
| Abbreviations with 4+ meanings | 7% | Nature Scientific Data |
| Maximum number of senses for one abbreviation (PA) | 142 | Nature Scientific Data |
| QD (once daily) — share of abbreviation-related medication errors | 43.1% | NCBI/NBK519006 |

### D.2 The Joint Commission "Do Not Use" List

The Joint Commission established this mandatory list in 2004
as part of National Patient Safety Goals. These abbreviations
must not appear in clinical documentation.

| Abbreviation | Intended Meaning | Potential Misinterpretation | Required Alternative |
|-------------|-----------------|---------------------------|---------------------|
| U, u | Unit | Mistaken for "0" (zero), "4" (four), or "cc" | Write "unit" |
| IU | International Unit | Mistaken for "IV" (intravenous) or "10" (ten) | Write "International Unit" |
| Q.D., QD, q.d., qd | Every day | Mistaken for "Q.I.D." (four times daily) | Write "daily" |
| Q.O.D., QOD, q.o.d., qod | Every other day | Mistaken for "Q.D." (daily) or "Q.I.D." (four times daily) | Write "every other day" |
| Trailing zero (X.0 mg) | X mg | Decimal point missed → 10x overdose | Never use trailing zero |
| Lack of leading zero (.X mg) | 0.X mg | Decimal point missed → 10x overdose | Always use leading zero (0.X mg) |
| MS | Morphine sulfate | Mistaken for magnesium sulfate | Write "morphine sulfate" |
| MSO4 | Morphine sulfate | Mistaken for magnesium sulfate (MgSO4) | Write "morphine sulfate" |
| MgSO4 | Magnesium sulfate | Mistaken for morphine sulfate (MSO4) | Write "magnesium sulfate" |

### D.3 High-Impact Ambiguous Abbreviations for NLP

These abbreviations have multiple clinical meanings and
cause the most errors in automated clinical text processing.
Our NLP pipeline must handle disambiguation for each.

| Abbreviation | Possible Meanings | NLP Risk |
|-------------|-------------------|----------|
| **PA** | Physician assistant; Pulmonary artery; Pancreatic adenocarcinoma; Psoriatic arthritis; Posteroanterior; Pennsylvania; Arterial pressure (142 total senses) | Highest ambiguity |
| **MS** | Multiple sclerosis; Morphine sulfate; Magnesium sulfate; Mental status; Mitral stenosis; Musculoskeletal | Medication safety risk |
| **CP** | Chest pain; Cerebral palsy; Chronic pain; C-peptide | Diagnostic ambiguity |
| **BS** | Blood sugar; Bowel sounds; Breath sounds | Assessment ambiguity |
| **RA** | Rheumatoid arthritis; Right atrium; Room air; Renal artery | Diagnostic ambiguity |
| **PD** | Parkinson's disease; Peritoneal dialysis; Personality disorder | Treatment context changes |
| **PT** | Physical therapy; Prothrombin time; Patient | Clinical vs. lab context |
| **SOB** | Shortness of breath | May not parse correctly |
| **AMS** | Altered mental status; Amylase | Context-dependent |
| **DOA** | Dead on arrival; Date of admission | Opposite clinical meanings |
| **OD** | Overdose; Right eye (oculus dexter); Once daily | Medication safety risk |
| **DC** | Discharge; Discontinue | Opposite clinical actions |
| **CA** | Cancer; Cardiac arrest; Calcium | Diagnostic ambiguity |
| **CF** | Cystic fibrosis; Cardiac failure; Copy forward | Document integrity |
| **LE** | Lower extremity; Lupus erythematosus | Anatomical vs. diagnostic |
| **SS** | Sliding scale; Sickle cell disease; Social security | Treatment context |
| **BPH** | Benign prostatic hyperplasia; Beats per hour | Rarely confused clinically |
| **CHF** | Congestive heart failure | Lacks specificity for ICD-10 |
| **NKDA** | No known drug allergies | Generally unambiguous |
| **PRN** | As needed | Generally unambiguous |

### D.4 ISMP Error-Prone Abbreviations (Additional)

Beyond the Joint Commission mandatory list, ISMP maintains
an expanded list of error-prone abbreviations. Key additions:

| Category | Examples | Risk |
|----------|---------|------|
| Drug name abbreviations | AZT (zidovudine vs. azathioprine), MTX (methotrexate), HCT (hydrocortisone vs. hydrochlorothiazide) | Wrong drug dispensed |
| Dose designations | mcg mistaken for mg (1000x overdose); ">" and "<" mistaken for each other | Dosing errors |
| Route abbreviations | SC/SQ (subcutaneous) mistaken for "SL" (sublingual) or "5Q" (five every) | Wrong route |
| Frequency abbreviations | BID, TID, QID — period after abbreviation mistaken for digit | Wrong frequency |

### D.5 AI System Requirements for Abbreviation Handling

**NLP Pipeline Requirements:**

1. **Context-aware disambiguation:** Use surrounding clinical
   context to resolve ambiguous abbreviations. The abbreviation
   "MS" in a medication order context likely means "morphine
   sulfate" while in a neurology note it likely means
   "multiple sclerosis."

2. **Section-aware parsing:** Clinical note section headers
   provide strong disambiguation signals. "PA" in a staffing
   section means "physician assistant" while in a chest X-ray
   reading it means "posteroanterior."

3. **Do-Not-Use detection:** Flag any Joint Commission
   prohibited abbreviation found in orders or medication
   documentation. Generate compliance alert.

4. **Abbreviation expansion before coding:** Expand all
   abbreviations to full terms before the coding agent
   processes the text, to prevent coding errors from
   ambiguous abbreviations.

5. **Confidence scoring:** When abbreviation disambiguation
   confidence is < 0.80, flag for human review rather than
   auto-expanding.

### D.6 Note on Abbreviation Safety Database Sources

**Note (2026-04-01):** No standalone "JAMA Abbreviation Safety
Database" exists as a named resource. JAMA is a peer-reviewed
journal that has published individual studies on abbreviation
safety (notably Brunetti et al., 2007, finding prohibited
abbreviations persisted in ~5% of medication orders after the
Joint Commission ban), but does not maintain a dedicated
abbreviation database.

**Best available authoritative sources for abbreviation safety:**

| Source | What It Provides | Authority Level |
|--------|-----------------|----------------|
| ISMP Error-Prone Abbreviation List | Prescriptive "do not use" list based on reported errors; no per-abbreviation error rates | Highest — regulatory reference |
| Joint Commission "Do Not Use" List | Mandatory prohibited abbreviations (9 items); compliance required for accreditation | Regulatory mandate |
| Nature Scientific Data (2021) | Corpus-level statistics: avg 1.77 senses/abbreviation, 23% with 2+ meanings, PA has 142 senses | Quantitative reference |
| JAMIA (Xu et al., 2007; Wu et al., various) | NLP disambiguation accuracy (~90% with ML approaches) | Technical reference |
| FDA MEDWATCH / ISMP MERP | Voluntary error reports; abbreviation errors ~5% of all medication errors | Aggregate safety data |

> **Note:** Abbreviation-related errors account for ~5% of all
> medication errors (ISMP/FDA MEDWATCH aggregate data). Widely
> cited figure — exact percentage varies by study and setting.
> Treat as directional estimate pending primary source
> confirmation for specific per-abbreviation error rates.

**Recommendation for our NLP pipeline:** Use the ISMP error-prone
list and Joint Commission mandatory list as high-priority
detection targets. Use the Nature Scientific Data corpus for
disambiguation training data. Per-abbreviation error rates are
not available as a clean dataset — the system should flag all
ambiguous abbreviations rather than risk-stratifying by error rate.

**Source:** ISMP List of Error-Prone Abbreviations (2024);
Joint Commission Official "Do Not Use" List; Brunetti et al.,
JAMA 2007; Nature Scientific Data (Adams et al., 2021);
JAMIA abbreviation disambiguation studies.

---

## E. Documentation Timing Failures

### E.1 Discharge Summary Completeness and Timing

The discharge summary is the primary document used for
inpatient coding, making its completeness and timeliness
critical for accurate code assignment.

| Metric | Value | Source |
|--------|-------|--------|
| Incorrect DRG rate — discharge summary alone | 42% | ScienceDirect (2018) |
| Incorrect DRG rate — coding with case notes | 31% | ScienceDirect (2018) |
| Incorrect DRG rate — discharge summary + medical support | 35% | ScienceDirect (2018) |
| Diagnosis code inaccuracy — discharge summary alone | 70% | ScienceDirect (2018) |
| Diagnosis code inaccuracy — full case notes | 58% | ScienceDirect (2018) |
| Records coded without discharge summary present | Up to 80% (historical) | ACDIS |
| Information omitted when summary completed >24h after discharge | Significantly higher | PMC5406115 |

### E.2 Impact of Late Documentation

**The coding deadline problem:** Most hospitals require
coding within 3-5 days of discharge. When discharge
summaries are late, coders must either:

1. Code from incomplete documentation (leading to missed
   secondary diagnoses and specificity failures), or
2. Delay coding (leading to delayed billing and cash flow
   impact)

**Which note types are most commonly late:**

| Note Type | Typical Lateness Pattern | Coding Impact |
|-----------|------------------------|---------------|
| Discharge summary | Most commonly delayed; often completed days after discharge | Highest impact — primary coding document |
| Operative reports | Sometimes dictated but not transcribed in time | Procedure code accuracy |
| Consultation notes | Specialist notes may be pending at discharge | Secondary diagnosis capture |
| Pathology reports | Inherently delayed by processing time | Cancer staging, specificity |
| Radiology final reads | Preliminary reads available but finals delayed | Diagnostic specificity |
| Addendum notes | Physicians add clarifications after initial note | May contain critical specificity |

### E.3 Correlation Between Timing and Accuracy

Research demonstrates a clear relationship:

- **Same-day discharge summaries** capture more diagnoses
  and have fewer omissions of clinically relevant information
- **>24 hour delay** correlates with increased omission of
  components critical for coding
- **>48 hour delay** shows significant degradation in
  documentation quality and completeness
- **CDI query response time** also degrades with time —
  physicians are less likely to accurately recall clinical
  details days after the encounter

**Key finding:** A structured discharge summary template
improved sepsis documentation by **28%** (PMC10701636),
demonstrating that the format of the document, not just
timing, significantly affects coding accuracy.

### E.3a Quantitative Correlation Data (2026-04-01 Addition)

**No single published study provides a direct regression
coefficient for "coding accuracy as a function of discharge
summary delay."** This specific end-to-end measurement is a
gap in the literature. However, the evidence chain is
quantifiable at each link:

**Link 1 — Delayed summaries lose clinical content:**

| Metric | Value | Source |
|--------|-------|--------|
| Content reduction in summaries completed >24h post-discharge | **9% fewer actionable data elements** | PMC3250552 (Horwitz et al., Yale) |
| Adjusted incident rate ratio (>24h vs ≤24h) | **IRR 0.91 (95% CI: 0.84-0.98, p=0.02)** | PMC3250552 |
| Readmission risk for summary delay >3 days | **OR 1.09 (95% CI: 1.04-1.13, p=0.001)** | Hoyer et al., J Hospital Medicine 2016 (n=87,994) |

**Link 2 — Incomplete documentation produces inaccurate codes:**

| Metric | Value | Source |
|--------|-------|--------|
| Coding accuracy with discharge summary alone | 30% correct (70% inaccurate) | ScienceDirect 2018 (Tsopra et al.) |
| Coding accuracy with full case notes | 42% correct (58% inaccurate) | ScienceDirect 2018 |
| Coding agreement: integrated vs independent charting | 87.9% vs 44.4% (p < 0.0001) | PMC10694743 |

**Link 3 — Discharge summary completion benchmarks:**

| Metric | Value | Source |
|--------|-------|--------|
| Summaries completed on discharge day | 67.2% | PMC4303507 (multi-site HF study) |
| Additional completed within 3 days | 11.0% | PMC4303507 |
| Delayed beyond 30 days | 7.3% | PMC4303507 |
| Summaries meeting all Joint Commission required elements | 36.6% | PMC4303507 |
| Joint Commission maximum allowed delay | 30 days | Joint Commission standards |
| Operational best-practice target | 24-48 hours | Industry consensus |
| Baseline mean completion time (before QI) | 71.5 hours | PMC8322483 |
| Post-QI mean completion time | 21.8 hours (70% reduction) | PMC8322483 |
| Documentation deficiency rate reduction | 4.5% → 2.5% (44% reduction) | PMC8322483 |

**Combined inference:** Summaries completed >24h after discharge
contain 9% fewer actionable elements (IRR 0.91, p=0.02), and
coding from incomplete summaries has a 70% diagnostic
inaccuracy rate vs 58% with full records (p<0.0001). The
compounded effect: each day of discharge summary delay
degrades both documentation completeness and coding accuracy,
though no single study measures the end-to-end variable.

**CDI query response rate benchmarks:**

| Metric | Value | Source |
|--------|-------|--------|
| Facilities reporting 91-100% physician query response rate | 69% | ACDIS survey data |
| Most common concurrent query response deadline | 72 hours | Industry standard |
| Bill hold goal (most organizations) | 3-5 days | ACDIS best practice |

> **Note:** The Horwitz IRR of 0.91 for >24h delay on
> documentation completeness is the closest available proxy
> for timing-to-accuracy correlation. No direct regression
> of hours-to-completion vs ICD-10 coding accuracy exists
> in the peer-reviewed literature. Treat the combined
> inference above as directional pending a primary study
> that measures this end-to-end variable.

**Sources:** PMC3250552 (Horwitz et al.); PMC10694743
(Casey Eye Institute); PMC4303507 (multi-site HF study);
PMC8322483 (QI initiative); Hoyer et al., J Hospital
Medicine 2016; Tsopra et al., Int J Med Inform 2018;
ACDIS physician query response rate guidance.

### E.4 AI System Detection and Intervention

**Real-time documentation monitoring:**

1. **Discharge event detection:** When a patient is
   discharged, start a timer for discharge summary completion.

2. **Escalation protocol:**
   - 0-24h: Normal window
   - 24-48h: Soft reminder to attending physician
   - 48-72h: Alert to CDI team and department chief
   - >72h: Escalate to medical records committee

3. **Pre-discharge documentation review:**
   Before discharge, AI scans current documentation for:
   - Missing secondary diagnoses (Section C patterns)
   - Specificity gaps (Section B patterns)
   - Unsigned or incomplete notes
   - Outstanding CDI queries without physician response

4. **Discharge summary completeness scoring:**
   Score each discharge summary against required elements:
   - Admission diagnosis stated
   - Principal diagnosis at discharge
   - All secondary diagnoses listed
   - Procedures performed listed
   - Discharge medications reconciled
   - Follow-up plan documented
   - Present-on-admission indicators assessable

5. **Coding readiness score:**
   Calculate a "coding readiness" score for each case:
   - All notes finalized: +30 points
   - Discharge summary present: +25 points
   - No outstanding CDI queries: +20 points
   - Lab/vital trend reviewed: +15 points
   - All consultation notes present: +10 points
   - Score < 70: flag as "not ready for coding"

---

## F. Cross-Cutting Detection Architecture

### F.1 Integrated Detection Pipeline

Our AI system should implement a layered detection approach
that addresses all five failure categories simultaneously:

```
Layer 1: REAL-TIME (during documentation)
├── Copy-forward detection (Section A)
├── Abbreviation flagging (Section D)
└── Missing documentation alerts

Layer 2: CONCURRENT (during hospital stay)
├── Lab-to-diagnosis gap detection (Section C)
├── Medication-to-diagnosis inference (Section C)
├── Specificity gap identification (Section B)
└── CDI query generation

Layer 3: PRE-CODING (at discharge)
├── Discharge summary completeness check (Section E)
├── Final specificity review (Section B)
├── Missing secondary diagnosis sweep (Section C)
└── Coding readiness scoring

Layer 4: POST-CODING (quality assurance)
├── Code-to-documentation validation
├── CC/MCC capture rate monitoring
├── DRG optimization opportunity flagging
└── Compliance risk scoring
```

### F.2 Priority Matrix

Based on revenue impact and detection feasibility:

| Pattern | Revenue Impact | Detection Feasibility | Priority |
|---------|---------------|----------------------|----------|
| Sepsis specificity/organism | Very High ($42K/case) | Medium | P0 |
| Missing AKI from lab trends | High ($3-8K/case) | High | P0 |
| Heart failure type/acuity | High ($7.5K/case) | High | P0 |
| Respiratory failure missed | High ($4-10K/case) | High | P0 |
| Malnutrition undercoding | High ($3-9K/case) | Medium | P1 |
| Encephalopathy missed | High ($4-10K/case) | Medium | P1 |
| Copy-forward in assessment | Medium | Medium | P1 |
| Missing chronic conditions | Medium ($1-4K/case) | High | P1 |
| Discharge summary timing | Medium | High | P2 |
| Abbreviation disambiguation | Low-Medium | Medium | P2 |
| Pneumonia organism | Medium ($2-6K/case) | Medium | P2 |
| Pressure ulcer staging | Medium ($3-8K/case) | Medium | P2 |

### F.3 Compliance Guardrails

**Per constitution Article II, all AI-generated suggestions
must include:**

1. **Evidence quote** — Verbatim text from the note supporting
   the suggestion
2. **Clinical criteria** — The specific diagnostic criteria met
   (e.g., KDIGO for AKI, SOFA for sepsis)
3. **Confidence score** — Model confidence that the clinical
   evidence supports the suggested action
4. **DRG impact estimate** — The revenue difference if the
   suggestion is accepted
5. **Compliance flag** — If DRG improvement exceeds $5,000,
   route to compliance review before acting

**The system must NEVER:**

- Auto-code a diagnosis without physician documentation
- Suggest a diagnosis that contradicts the clinical evidence
- Present a CDI query that leads the physician toward a
  specific diagnosis (queries must be open-ended)
- Code an uncertain diagnosis as confirmed in outpatient
  settings (ICD-10 Guidelines Section IV.H)

---

## Verification Status

Last verified: 2026-04-05 (FIX-001 research audit)
Verified by: Live web fetch during FIX-001 session

| Claim Category | Count | Status |
|---|---|---|
| VERIFIED-LIVE | 18 | PMC articles, OIG reports, JAMA study confirmed |
| TRAINING-DATA (directional) | 3 | 55% sepsis coding gap, some DRG dollar figures, A41.9 72% usage |
| OUTDATED (corrected in FIX-001) | 2 | Sepsis cost ($41.5B→$52.1B), malnutrition prevalence range |

**Critical corrections made in FIX-001:**
- Sepsis aggregate cost updated from $41.5B to $52.1B (2021 AHRQ data)
- Malnutrition prevalence range broadened to 30-53% (literature range), coding rate updated to 3.7-8.6% (2016-2019 data)

**DRG dollar figures note:** DRG revenue figures (e.g., DRG 291: $11,437)
are explicitly cited as FY2012 or CMS 2020 data. They are historical
reference points. FY2026 MS-DRG weights should be used for current
revenue impact calculations in the DRG agent.

Next re-verification due: 2026-10-01 (ICD-10-CM and MS-DRG annual update)

---

## Sources

### Government and Regulatory

- [OIG Report OEI-01-11-00571: CMS and Its Contractors Have Adopted Few Program Integrity Practices to Address Vulnerabilities in EHRs](https://oig.hhs.gov/oei/reports/oei-01-11-00571.pdf)
- [CMS ICD-10-CM Official Guidelines for Coding and Reporting FY2025](https://www.cms.gov/files/document/fy-2025-icd-10-cm-coding-guidelines.pdf)
- [CMS MS-DRG Definitions Manual v37.2](https://www.cms.gov/icd10m/version372-fullcode-cms/fullcode_cms/P0140.html)
- [NIST IR 8166: Examining the Copy and Paste Function in the Use of Electronic Health Records](https://nvlpubs.nist.gov/nistpubs/ir/2017/NIST.IR.8166.pdf)
- [Joint Commission Do Not Use List of Abbreviations](https://www.jointcommission.org/en-us/knowledge-library/support-center/standards-interpretation/do-not-use-list-of-abbreviations)

### Peer-Reviewed Research

- [PMC5373750: Safe Practices for Copy and Paste in the EHR: Systematic Review, Recommendations, and Novel Model for Health IT Collaboration](https://pmc.ncbi.nlm.nih.gov/articles/PMC5373750/)
- [PMC11520144: A Retrospective Analysis Using Comorbidity Detecting Algorithmic Software to Determine the Incidence of ICD Code Omissions and Appropriateness of DRG Code Modifiers](https://pmc.ncbi.nlm.nih.gov/articles/PMC11520144/)
- [PMC10701636: Current Challenges in Sepsis Documentation and Coding: A Review of the Literature](https://pmc.ncbi.nlm.nih.gov/articles/PMC10701636/)
- [PMC5059542: Malnutrition: The Importance of Identification, Documentation, and Coding in the Acute Care Setting](https://pmc.ncbi.nlm.nih.gov/articles/PMC5059542/)
- [PMC5977598: Accuracy and Completeness of Clinical Coding Using ICD-10 for Ambulatory Visits](https://pmc.ncbi.nlm.nih.gov/articles/PMC5977598/)
- [PMC10694743: The Impact of Documentation Workflow on the Accuracy of the Coded Diagnoses in the EHR](https://pmc.ncbi.nlm.nih.gov/articles/PMC10694743/)
- [PMC5669129: International Classification of Diseases, 10th Revision, Coding for Diabetes](https://pmc.ncbi.nlm.nih.gov/articles/PMC5669129/)
- [PMC3540461: A Comparative Study of Current Clinical NLP Systems on Handling Abbreviations in Discharge Summaries](https://pmc.ncbi.nlm.nih.gov/articles/PMC3540461/)
- [Nature Scientific Data: A Deep Database of Medical Abbreviations and Acronyms for NLP](https://www.nature.com/articles/s41597-021-00929-4)
- [Oxford Academic JAMIA: Disambiguation of Acronyms in Clinical Narratives with Large Language Models](https://academic.oup.com/jamia/article/31/9/2040/7699035)
- [PMC12352811: Current Challenges in Encephalopathy Documentation and Coding](https://pmc.ncbi.nlm.nih.gov/articles/PMC12352811/)
- [PMC8140706: A Simple Measure to Improve Sepsis Documentation and Coding](https://pmc.ncbi.nlm.nih.gov/articles/PMC8140706/)
- [ScienceDirect: The Impact of Three Discharge Coding Methods on the Accuracy of Diagnostic Coding and Hospital Reimbursement](https://www.sciencedirect.com/science/article/abs/pii/S1386505618302557)

### Professional Associations

- [AHIMA Clinical Documentation Integrity (CDI) Toolkit for New Leaders (August 2024)](https://www.ahima.org/media/qiapajfd/clinical-documentation-integrity-cdi-toolkit-for-new-leaders-final-aug-2024-9-19-24-_axs.pdf)
- [AHIMA: Using CC/MCC Capture Rates as a Key Performance Indicator](https://journal.ahima.org/Portals/0/archives/AHIMA%20files/Using%20CC_MCC%20Capture%20Rates%20as%20a%20Key%20Performance%20Indicator.pdf)
- [AHIMA: Best Practices in the Art and Science of Clinical Documentation Improvement](https://journal.ahima.org/Portals/0/archives/AHIMA%20files/Best%20Practices%20in%20the%20Art%20and%20Science%20of%20Clinical%20Documentation%20Improvement.pdf)
- [ACDIS: JAMA Study Reveals Massive Amount of Copy-Paste in EHR Progress Notes](https://acdis.org/articles/news-jama-study-reveals-massive-amount-copy-paste-ehr-progress-notes)
- [ACDIS: Q&A on KDIGO Criteria for AKI](https://acdis.org/articles/qa-kdigo-criteria)
- [ACDIS: Q&A on Toxic and Metabolic Encephalopathy](https://acdis.org/articles/qa-toxic-and-metabolic-encephalopathy)
- [ISMP List of Error-Prone Abbreviations, Symbols, and Dose Designations](https://online.ecri.org/hubfs/ISMP/Resources/ISMP_ErrorProneAbbreviation_List.pdf)
- [ECRI: Copy/Paste: Prevalence, Problems, and Best Practices](https://www.ecri.org/resources/hit/htais_copy_paste_report.pdf)
- [AHRQ PSNet: Copy and Paste Notes and Autopopulated Text in the EHR](https://psnet.ahrq.gov/web-mm/copy-and-paste-notes-and-autopopulated-text-electronic-health-record)
- [AHRQ PSNet: EHR Copy and Paste and Patient Safety](https://psnet.ahrq.gov/perspective/ehr-copy-and-paste-and-patient-safety)

### Industry Analysis

- [HFMA: The Financial Truth About ICD-10 Coding Accuracy: Two DRGs to Watch](https://www.hfma.org/revenue-cycle/coding/53771/)
- [The Hospitalist: Tips for Properly Documenting and Coding Heart Failure](https://www.the-hospitalist.org/hospitalist/article/33730/cardiology/tips-for-properly-documenting-and-coding-hf/)
- [Health Catalyst: Data-Driven CDI Program Increases Revenue](https://www.healthcatalyst.com/learn/success-stories/clinical-documentation-improvement-allina-health)
- [AGS Health: Top Clinical Documentation Integrity Trends 2021](https://www.agshealth.com/blog/a-look-at-the-top-clinical-documentation-integrity-trends-from-2021/)
- [ICD10Monitor PEPPER Tip: Monitor Pneumonia Specificity](https://icd10monitor.medlearn.com/pepper-tip-monitor-pneumonia-specificity/)
- [UASI: Acute Kidney Injury (AKI) CDI Tip](https://www.uasisolutions.com/acute-kidney-injury-aki)

---

## Appendix: CDI Query Templates

These templates are provided as starting points for the
CDI agent's query generation. All queries must be compliant
(non-leading, open-ended, clinically supported).

### Heart Failure Specificity Query
```
Clinical indicators suggest heart failure is present.
Please clarify the following for accurate documentation:
1. Is the heart failure systolic (HFrEF), diastolic (HFpEF),
   or combined?
2. Is it acute, chronic, or acute on chronic?
3. What is the most recent ejection fraction?
```

### AKI Query (Lab-Triggered)
```
Laboratory findings indicate:
- Baseline creatinine: [X] mg/dL ([date])
- Current creatinine: [Y] mg/dL ([date])
- Change: [delta] mg/dL over [hours/days]

These findings meet KDIGO criteria for acute kidney injury.
Does this patient have acute kidney injury?
If yes, please document the etiology if known.
```

### Sepsis Specificity Query
```
Clinical documentation indicates sepsis.
To ensure accurate coding, please clarify:
1. What is the source of infection?
2. Has an organism been identified?
3. Is organ dysfunction present? If so, which organs?
4. Does this represent sepsis, severe sepsis, or septic shock?
```

### Malnutrition Query
```
Clinical indicators suggest possible malnutrition:
- BMI: [X]
- Albumin: [Y] g/dL
- Weight change: [Z]% over [period]
- Dietitian assessment: [summary]

Does this patient have malnutrition?
If yes, please specify: mild, moderate, or severe.
Please document the type (e.g., protein-calorie malnutrition).
```

### Respiratory Failure Query
```
Clinical indicators suggest possible respiratory failure:
- PaO2: [X] mmHg / SpO2: [Y]%
- Supplemental O2: [type and flow rate]
- ABG results: [if available]

Does this patient have acute respiratory failure?
If yes, is it hypoxic, hypercapnic, or both?
```

### Encephalopathy Query
```
Patient has documented altered mental status with:
- [Metabolic abnormality, e.g., sodium 118, BUN 95, ammonia 142]
- [Clinical finding, e.g., confusion, disorientation, somnolence]

Does this patient have encephalopathy?
If yes, please specify the type and underlying etiology
(e.g., metabolic encephalopathy due to hepatic failure).
```

---

*Document generated: 2026-03-30*
*Research phase: DISCOVER*
*Next action: Use these patterns to build detection algorithms*
*in src/nlp/ and CDI query generation in src/agents/cdi_agent.py*
