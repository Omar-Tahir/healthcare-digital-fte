# DESIGN-002: CDI Intelligence Layer Specification

**Status:** COMPLETE  
**Date:** 2026-04-01  
**Author:** Claude (AI Engineering Partner)  
**Research inputs:** DISC-001 (ICD-10 Official Guidelines), DISC-002 (Documentation Failure Patterns)  
**Constitution references:** Article II.2 (Source Citation), Article II.3 (ICD-10 Hard Constraints), Article II.6 (Conservative Defaults), Article IV.1 (Revenue North Star)  
**Implementation target:** `src/agents/cdi_agent.py`, `src/prompts/cdi_query.py`  
**Depends on:** DESIGN-001 (Coding Rules Engine — provides DRG impact calculation)

---

## Purpose

The CDI Intelligence Layer detects documentation gaps in
physician notes and generates compliant physician queries
BEFORE coding happens. This is the component that closes the
loop between clinical documentation and accurate revenue capture.

No competitor integrates CDI intelligence with their coding AI.
Iodine Software (AwareCDI) is the closest competitor, but their
queries are template-based and lack the clinical reasoning depth
that LLM-enabled analysis provides (DISC-005).

The CDI layer does NOT code. It does NOT suggest diagnoses.
It identifies where documentation is insufficient for accurate
coding and asks the physician to clarify — using non-leading,
AHIMA-compliant queries grounded in objective clinical evidence.

---

## 1. CDI Opportunity Categories

### Category A: Severity Upgrades (Highest Revenue Impact)

These are conditions where clinical evidence strongly suggests
a diagnosis that would carry CC/MCC status, but the physician
has not explicitly documented it. Without physician documentation,
the coder cannot code the condition.

#### CDI-SEV-001: Acute Kidney Injury (AKI) Not Documented

- **Category:** Severity upgrade — missing MCC diagnosis
- **Clinical trigger:** Creatinine rise meeting KDIGO criteria without explicit AKI documentation in the physician note
- **Lab corroboration:**
  - Creatinine rise >= 0.3 mg/dL within 48 hours (KDIGO Stage 1), OR
  - Creatinine >= 1.5x baseline within 7 days (KDIGO Stage 1+), OR
  - Urine output < 0.5 mL/kg/h for >= 6 hours (if available)
- **Note indicators that should be ABSENT to trigger:**
  - "acute kidney injury," "AKI," "acute renal failure," "ARF," "acute renal insufficiency"
- **Revenue impact:** N17.x is MCC. Missing AKI = $3,000-$8,000 per case in DRG revenue loss (DISC-002 B.1.3)
- **ICD-10 target codes:** N17.0 (AKI with tubular necrosis), N17.1 (AKI with acute cortical necrosis), N17.2 (AKI with medullary necrosis), N17.9 (AKI, unspecified)
- **Key rule:** Coders cannot code AKI from lab values alone — physician must explicitly document the diagnosis (DISC-002 B.1.3)
- **Omission rate:** Not separately tracked, but AKI is among the most commonly missed secondary diagnoses
- **Priority:** P0

#### CDI-SEV-002: Sepsis Not Documented When SIRS + Infection Present

- **Category:** Severity upgrade — missing MCC diagnosis
- **Clinical trigger:** Patient meets SIRS criteria AND has a documented or suspected infection, but "sepsis" is not explicitly documented
- **Lab/vitals corroboration (SIRS criteria — need >= 2):**
  - Temperature > 38.3°C (101°F) or < 36.0°C (96.8°F)
  - Heart rate > 90 bpm
  - Respiratory rate > 20 or PaCO2 < 32 mmHg
  - WBC > 12,000 or < 4,000 or > 10% bands
- **Additional severity indicators:**
  - Lactate > 2.0 mmol/L (suggests tissue hypoperfusion)
  - Positive blood cultures
  - Vasopressor requirement (suggests septic shock)
  - Organ dysfunction (creatinine rise, bilirubin rise, platelet drop, altered mental status)
- **Note indicators that should be ABSENT to trigger:**
  - "sepsis," "septic," "severe sepsis," "septic shock," "SIRS"
- **Revenue impact:** Sepsis with MCC (DRG 870) = $49,690 avg. Sepsis without MCC (DRG 872) = $6,931 avg. Sepsis not coded at all = base DRG only. Potential impact: $6,000-$42,759 per case (DISC-002 B.1.2)
- **Critical statistic:** 55% of critically ill patients with severe sepsis are discharged without sepsis ICD codes (DISC-002 B.1.2)
- **Omission rate:** 55% (PMC10701636)
- **Priority:** P0

#### CDI-SEV-003: Malnutrition Not Documented

- **Category:** Severity upgrade — missing CC/MCC diagnosis
- **Clinical trigger:** Objective nutritional indicators present without malnutrition diagnosis documented
- **Lab/vitals corroboration (any combination):**
  - BMI < 18.5 (underweight)
  - Albumin < 3.0 g/dL
  - Prealbumin < 15 mg/dL
  - Unintentional weight loss > 5% in 30 days or > 10% in 6 months
  - Dietitian consult ordered or completed
  - Nutritional supplements ordered (Ensure, tube feeds, TPN)
- **Note indicators that should be ABSENT to trigger:**
  - "malnutrition," "malnourished," "protein-calorie malnutrition," "PCM," "cachexia," "kwashiorkor," "marasmus"
- **Revenue impact:** E43 (Severe protein-calorie malnutrition) is MCC. E44.0/E44.1 (Moderate/Mild protein-calorie malnutrition) is CC. Impact: $3,000-$9,000 per case (DISC-002 B.1.5)
- **Critical statistic:** 53% of inpatients are malnourished, but only 0.9-5.4% are coded (DISC-002 B.1.5)
- **Compliance note:** OIG identified ~$1 billion in malnutrition coding overpayments for FY2016-17. Malnutrition CDI must be clinically grounded and cannot lead the physician.
- **Omission rate:** 57.9% (PMC11520144)
- **Priority:** P1

#### CDI-SEV-004: Encephalopathy Not Documented

- **Category:** Severity upgrade — missing MCC diagnosis
- **Clinical trigger:** Altered mental status documented with concurrent metabolic derangement, but "encephalopathy" not documented
- **Lab/vitals corroboration:**
  - Sodium < 120 mEq/L (hyponatremic encephalopathy)
  - BUN > 60 mg/dL (uremic encephalopathy)
  - Ammonia > 60 mcg/dL (hepatic encephalopathy)
  - PaO2 < 60 mmHg (hypoxic encephalopathy)
  - Blood glucose < 50 mg/dL (hypoglycemic encephalopathy)
  - Toxic substance levels elevated (toxic encephalopathy)
- **Note indicators that trigger detection (present):**
  - "altered mental status," "AMS," "confusion," "disorientation," "somnolence," "obtunded," "delirium," "agitation"
- **Note indicators that should be ABSENT to trigger:**
  - "encephalopathy," "metabolic encephalopathy," "hepatic encephalopathy," "toxic encephalopathy," "hypoxic encephalopathy"
- **Revenue impact:** G93.41 (Metabolic encephalopathy) is MCC. Impact: $4,000-$10,000 per case (DISC-002 B.1.9)
- **Omission rate:** 80.3% for delirium (PMC11520144) — encephalopathy likely higher
- **Priority:** P1

#### CDI-SEV-005: Respiratory Failure Not Documented

- **Category:** Severity upgrade — missing MCC diagnosis
- **Clinical trigger:** Objective evidence of respiratory failure (hypoxemia, hypercapnia, mechanical ventilation) without explicit respiratory failure diagnosis
- **Lab/vitals corroboration:**
  - PaO2 < 60 mmHg on ABG
  - SpO2 < 88% on room air (or requiring supplemental O2 to maintain > 88%)
  - PaCO2 > 50 mmHg with pH < 7.35 (hypercapnic respiratory failure)
  - Patient on BiPAP, CPAP (non-sleep), or mechanical ventilation
  - FiO2 > 40% requirement
- **Note indicators that should be ABSENT to trigger:**
  - "respiratory failure," "acute respiratory failure," "chronic respiratory failure," "acute on chronic respiratory failure," "ventilatory failure"
- **Note indicators PRESENT that are NOT sufficient for coding (trigger CDI):**
  - "hypoxia," "hypoxemia," "respiratory distress," "dyspnea," "shortness of breath" — these are symptoms, not diagnoses of respiratory failure
- **Revenue impact:** J96.0x (Acute respiratory failure) is MCC. Impact: $4,000-$10,000 per case (DISC-002 B.1.4)
- **Priority:** P0

#### CDI-SEV-006: Acute on Chronic Condition Not Documented

- **Category:** Severity upgrade — MCC capture from acuity specification
- **Clinical trigger:** Patient has a documented chronic condition with clinical evidence of acute exacerbation, but "acute on chronic" not explicitly stated
- **Applies to:**
  - Heart failure: chronic HF documented + acute decompensation evidence (increased BNP, pulmonary edema, diuretic escalation) → query for "acute on chronic"
  - Kidney disease: CKD documented + creatinine rise meeting KDIGO criteria → query for "acute on chronic kidney disease"
  - Respiratory failure: chronic respiratory failure documented + acute worsening → query for "acute on chronic"
  - COPD: chronic COPD documented + increased dyspnea/wheezing/steroid use → query for "acute exacerbation"
- **Revenue impact:** "Acute on chronic" codes are typically MCC while "chronic" alone is CC. Upgrade potential: $3,000-$8,000 per case
- **Priority:** P0

---

### Category B: Specificity Upgrades

These are conditions documented at a non-specific level when
clinical information supports a more specific diagnosis.
Specificity upgrades often shift codes from Non-CC to CC or
from CC to MCC.

#### CDI-SPEC-001: Heart Failure Type and Acuity

- **Category:** Specificity upgrade — Non-CC to MCC potential
- **Clinical trigger:** Note contains "heart failure," "CHF," or "HF" without specifying type (systolic/diastolic/combined) AND/OR acuity (acute/chronic/acute on chronic)
- **Lab/vitals corroboration:**
  - BNP > 400 pg/mL or NT-proBNP > 900 pg/mL (suggests active HF)
  - Echocardiogram with EF documented (supports systolic vs diastolic distinction)
  - Diuretic dose changes (suggests active management)
  - Pulmonary edema on CXR (suggests acute component)
- **Detection logic:**
  ```
  IF note_contains("heart failure" OR "CHF" OR "HF" OR "congestive heart failure")
  AND NOT note_contains("systolic" OR "diastolic" OR "HFrEF" OR "HFpEF"
      OR "reduced ejection fraction" OR "preserved ejection fraction"
      OR "combined systolic and diastolic")
  THEN flag CDI-SPEC-001-TYPE

  IF note_contains("heart failure")
  AND NOT note_contains("acute" OR "chronic" OR "acute on chronic"
      OR "decompensated" OR "exacerbation")
  THEN flag CDI-SPEC-001-ACUITY
  ```
- **Revenue impact:** I50.9 (unspecified) = Non-CC. I50.23 (acute on chronic systolic) = MCC. Delta: $7,500 per case (DISC-002 B.1.1). Highest-volume specificity gap.
- **Priority:** P0

#### CDI-SPEC-002: Diabetes Type and Complication Linkage

- **Category:** Specificity upgrade — Non-CC to CC potential
- **Clinical trigger:** Diabetes documented without type specification OR with complications present but not linked to diabetes
- **Lab/vitals corroboration:**
  - HbA1c value (supports diabetes presence and control level)
  - Creatinine / GFR (supports CKD linkage)
  - Monofilament exam results (supports neuropathy)
  - Retinal exam results (supports retinopathy)
  - Foot exam findings (supports foot complication)
- **Detection logic:**
  ```
  # Type specification gap
  IF note_contains("diabetes" OR "DM" OR "diabetic")
  AND NOT note_contains("type 1" OR "type 2" OR "T1DM" OR "T2DM"
      OR "type I" OR "type II" OR "insulin-dependent" OR "IDDM"
      OR "NIDDM" OR "juvenile" OR "adult-onset")
  THEN flag CDI-SPEC-002-TYPE

  # Complication linkage gap
  IF note_contains("diabetes") AND note_contains(
      "CKD" OR "chronic kidney disease" OR "neuropathy"
      OR "retinopathy" OR "foot ulcer" OR "nephropathy")
  AND NOT note_contains("diabetic CKD" OR "diabetic nephropathy"
      OR "diabetic neuropathy" OR "diabetic retinopathy"
      OR "diabetic foot" OR "due to diabetes"
      OR "secondary to diabetes")
  THEN flag CDI-SPEC-002-LINK
  ```
- **Revenue impact:** E11.9 (without complications) = Non-CC. E11.22 (with diabetic CKD) = CC. Delta: $1,500-$4,000 per case (DISC-002 B.1.7). ICD-10-CM assumes causal relationship per Section I.C.4.a.6.
- **Priority:** P0

#### CDI-SPEC-003: Pneumonia Organism Specificity

- **Category:** Specificity upgrade — CC to MCC potential
- **Clinical trigger:** Pneumonia documented without specifying causative organism when culture results are available
- **Lab corroboration:**
  - Positive sputum culture with identified organism
  - Positive blood culture in context of pneumonia
  - Positive respiratory viral panel
  - BAL culture results
- **Detection logic:**
  ```
  IF note_contains("pneumonia")
  AND NOT note_contains(organism_name for organism_name
      in COMMON_RESPIRATORY_ORGANISMS)
  AND lab_results_contain(positive_respiratory_culture)
  THEN flag CDI-SPEC-003
  WITH organism = culture_result.organism
  ```
- **Revenue impact:** J18.9 (unspecified organism) = CC. Specific organism codes may shift DRG family. Delta: $2,000-$6,000 per case (DISC-002 B.1.6)
- **Priority:** P2

#### CDI-SPEC-004: Anemia Type Specification

- **Category:** Specificity upgrade — Non-CC to CC potential
- **Clinical trigger:** "Anemia" documented without type when clinical data supports a specific type
- **Lab corroboration:**
  - Hemoglobin drop > 2 g/dL (acute blood loss anemia — D62)
  - Transfusion ordered/administered (supports acute blood loss)
  - Low iron / low ferritin / high TIBC (iron deficiency — D50.x)
  - Low B12 or folate (megaloblastic — D51.x, D52.x)
  - Elevated reticulocyte count (hemolytic — D55-D59)
  - Chronic disease context + low EPO (anemia of chronic disease — D63.x)
- **Detection logic:**
  ```
  IF note_contains("anemia") AND code_assigned IN [D64.9]
  AND (hemoglobin_drop > 2.0 OR transfusion_ordered)
  THEN flag CDI-SPEC-004-ACUTE_BLOOD_LOSS
  WITH evidence = [hgb_trend, transfusion_order]

  IF note_contains("anemia") AND code_assigned IN [D64.9]
  AND (ferritin < 30 OR iron < 60 OR TIBC > 400)
  THEN flag CDI-SPEC-004-IRON_DEFICIENCY
  ```
- **Revenue impact:** D64.9 (unspecified) = Non-CC. D62 (acute blood loss) = CC. Delta: $1,500-$3,000 per case (DISC-002 B.1.11)
- **Priority:** P2

#### CDI-SPEC-005: Renal Failure Acute vs Chronic and Stage

- **Category:** Specificity upgrade — stage determines CC/MCC status
- **Clinical trigger:** "Renal failure" or "kidney disease" documented without acute/chronic distinction or staging
- **Lab corroboration:**
  - GFR value (determines CKD stage: G1 >= 90, G2 60-89, G3a 45-59, G3b 30-44, G4 15-29, G5 < 15)
  - Creatinine trend (rising = acute component; stable elevated = chronic)
  - Prior creatinine baseline (determines if current level represents change)
  - Dialysis orders (CKD Stage 5 or AKI requiring RRT)
- **Detection logic:**
  ```
  IF note_contains("renal failure" OR "kidney disease" OR "renal insufficiency")
  AND NOT note_contains("acute" OR "chronic" OR "stage"
      OR "ESRD" OR "end stage" OR "CKD" OR "AKI")
  THEN flag CDI-SPEC-005-TYPE

  IF note_contains("CKD" OR "chronic kidney disease")
  AND NOT note_contains("stage" OR "G1" OR "G2" OR "G3"
      OR "G4" OR "G5" OR "ESRD")
  AND gfr_value IS available
  THEN flag CDI-SPEC-005-STAGE
  WITH suggested_stage = gfr_to_ckd_stage(gfr_value)
  ```
- **Revenue impact:** N18.9 (CKD unspecified) vs N18.3 (CKD stage 3) — CC status varies by stage. AKI (N17.x) is MCC. Delta: $1,500-$8,000 per case depending on whether AKI is captured
- **Priority:** P0

---

### Category C: Causality Documentation

These are situations where two conditions coexist but the
causal relationship ("due to," "secondary to") is not
documented. ICD-10-CM mandates combination codes for certain
assumed causal relationships, but other relationships require
explicit physician documentation.

#### CDI-CAUSE-001: Infection to Sepsis Causality

- **Category:** Causality documentation — organism and source linkage
- **Clinical trigger:** Sepsis documented but source infection and/or causative organism not specified
- **Evidence required:**
  - Culture results identifying organism
  - Known infection site (UTI, pneumonia, wound, line infection)
  - Clinical documentation linking infection to systemic response
- **Detection logic:**
  ```
  IF note_contains("sepsis" OR "septic")
  AND NOT note_contains("due to" OR "secondary to" OR "caused by"
      OR "from" OR "source")
  AND culture_results.positive == True
  THEN flag CDI-CAUSE-001
  WITH organism = culture_results.organism
  WITH suspected_source = infer_source_from_culture_type(culture)
  ```
- **Revenue impact:** A41.9 (unspecified organism) groups differently than A41.51 (Gram-negative sepsis due to E. coli). Organism specification with organ dysfunction can shift DRG 872 ($6,931) to DRG 870 ($49,690). (DISC-002 B.1.2)
- **Query purpose:** Establish source, organism, and organ dysfunction linkage for complete sepsis coding
- **Priority:** P0

#### CDI-CAUSE-002: Diabetes to Complication Causality

- **Category:** Causality documentation — assumed causal relationship verification
- **Clinical trigger:** Patient has diabetes and a complication that ICD-10-CM presumes is caused by diabetes, but documentation does not explicitly link them OR documentation suggests the complication is NOT caused by diabetes
- **Conditions with assumed causal relationship (per Section I.C.4.a.6):**
  - Chronic kidney disease
  - Peripheral neuropathy
  - Retinopathy
  - Foot ulcers
- **Detection logic:**
  ```
  # Positive case: both present, linkage assumed per guidelines
  IF note_contains(diabetes_terms)
  AND note_contains(complication_terms)
  AND complication IN ASSUMED_CAUSAL_COMPLICATIONS
  THEN:
      IF note_contains("not due to diabetes" OR "not diabetic"
          OR "not related to diabetes" OR "unrelated to DM"):
          # Provider explicitly denied causal relationship
          # Do NOT code as diabetic complication
          LOG: "Provider denied causal relationship"
      ELSE:
          # ICD-10-CM assumes causal relationship
          # Ensure combination code will be used
          VALIDATE: combination_code_will_be_assigned

  # Negative case: complication present but unclear if diabetes-related
  IF note_contains(complication_terms)
  AND NOT complication IN ASSUMED_CAUSAL_COMPLICATIONS
  AND note_contains(diabetes_terms)
  THEN flag CDI-CAUSE-002
  # Query: "Is [complication] a diabetic complication?"
  ```
- **Revenue impact:** E11.22 (DM with diabetic CKD) = CC. E11.9 (DM without complications) = Non-CC. Delta: $1,500-$4,000 (DISC-002 B.1.7)
- **Priority:** P0

#### CDI-CAUSE-003: Procedure to Complication Causality

- **Category:** Causality documentation — postprocedural complication linkage
- **Clinical trigger:** Patient developed a complication after a procedure, but the documentation does not establish the causal relationship
- **Common postprocedural complications:**
  - Postprocedural hemorrhage (wound, GI, other)
  - Surgical site infection
  - Postprocedural respiratory failure
  - Postprocedural sepsis/septic shock
  - Postprocedural AKI (contrast nephropathy, hemodynamic)
  - Postprocedural DVT/PE
- **Detection logic:**
  ```
  IF procedure_performed_within(days=14)
  AND new_diagnosis_after_procedure IN COMPLICATION_CODES
  AND NOT note_contains("postprocedural" OR "post-operative"
      OR "complication of" OR "following procedure"
      OR "due to surgery" OR "iatrogenic")
  THEN flag CDI-CAUSE-003
  WITH procedure = procedure_name
  WITH complication = new_diagnosis
  WITH timing = days_since_procedure
  ```
- **Revenue impact:** Postprocedural complication codes (T81.x, T82.x, etc.) carry CC/MCC status and affect DRG assignment. T81.12XA (postprocedural septic shock) has specific coding rules per DISC-001 A.5.3. Impact varies: $3,000-$15,000 per case
- **Priority:** P1

#### CDI-CAUSE-004: "Due To" / "Secondary To" Language Needed

- **Category:** Causality documentation — general causal linkage
- **Clinical trigger:** Two conditions coexist where causal language would change coding, but the physician has not documented the relationship
- **Common patterns requiring causal language:**
  - Hypertension + heart failure → "hypertensive heart disease" triggers I11.0 combination code
  - Hypertension + CKD → "hypertensive CKD" triggers I12.x combination code
  - Infection + organ failure → "sepsis with organ dysfunction" triggers severity coding
  - Alcohol + liver disease → "alcoholic liver disease" vs "liver disease" changes code family
  - Aspiration + pneumonia → "aspiration pneumonia" (J69.0) vs "pneumonia" (J18.9)
- **Detection logic:**
  ```
  FOR each (condition_a, condition_b) in CAUSAL_PAIR_TABLE:
      IF note_contains(condition_a) AND note_contains(condition_b)
      AND NOT note_contains(CAUSAL_LANGUAGE_MARKERS)
      AND combination_code_exists(condition_a, condition_b)
      THEN flag CDI-CAUSE-004
      WITH pair = (condition_a, condition_b)
      WITH combination_code = lookup_combination(pair)

  CAUSAL_LANGUAGE_MARKERS = [
      "due to", "secondary to", "caused by", "resulting from",
      "as a result of", "attributable to", "related to",
      "associated with", "complication of", "hypertensive"
  ]
  ```
- **Revenue impact:** Causal linkage creates combination codes with higher CC/MCC status. Hypertension + HF: I10 (Non-CC) → I11.0 (CC) = $3,000-$9,000 per case (DISC-002 B.1.20)
- **Priority:** P0

---

### Category D: POA Determination Support

These are situations where the documentation does not clearly
establish when a condition began relative to the inpatient
admission, making POA indicator assignment uncertain.

#### CDI-POA-001: Conditions Needing Onset Documentation

- **Category:** POA determination — onset timing unclear
- **Clinical trigger:** A diagnosis is present in the record but there is insufficient documentation to determine whether it was present at the time of the inpatient admission order
- **Conditions most commonly requiring onset clarification:**
  - Pressure ulcers (documented day 3 but may have been present at admission — skin assessment incomplete or missing)
  - Catheter-associated UTI (catheter placed day 1, culture positive day 4 — incubation period ambiguous)
  - Acute kidney injury (creatinine trending up — was the rise pre- or post-admission?)
  - Sepsis (evolving condition — were SIRS criteria met before or after admission?)
  - DVT (may be subclinical at admission — diagnosed on ultrasound day 5)
  - Falls with injury (did the fall occur before or after admission?)
  - Clostridium difficile infection (incubation period overlaps admission)
- **Detection logic:**
  ```
  IF diagnosis.poa_indicator IN ["U", "W"]
  OR diagnosis IN HIGH_POA_AMBIGUITY_CODES
  AND NOT note_contains(TEMPORAL_MARKERS + diagnosis_terms)
  THEN flag CDI-POA-001
  WITH diagnosis = code
  WITH question = "When did [condition] first manifest?"

  TEMPORAL_MARKERS = [
      "on admission", "at presentation", "presented with",
      "prior to admission", "developed during", "hospital-acquired",
      "day [N] of admission", "onset", "first noted"
  ]
  ```
- **Revenue impact:** Incorrect POA on HAC-associated codes triggers CMS payment reductions. Bottom-quartile HAC hospitals face 1% total Medicare payment reduction.
- **Priority:** P1

#### CDI-POA-002: HAC-Prone Conditions Requiring Explicit Documentation

- **Category:** POA determination — HAC risk mitigation
- **Clinical trigger:** A HAC-associated diagnosis code (14 CMS HAC categories) is being assigned without clear POA documentation
- **The 5 most frequently mis-assigned HAC codes (DISC-001 C.6):**
  1. Pressure ulcers (L89.x) — often present on admission but documented late
  2. Catheter-associated UTI (T83.51x) — difficult onset determination
  3. Falls with injury (W01-W19) — pre- vs post-admission ambiguity
  4. AKI (N17.x) — evolving condition
  5. Sepsis (A41.x) — developing vs present at admission
- **Detection logic:**
  ```
  IF diagnosis.code IN HAC_RELEVANT_CODES
  AND diagnosis.poa_indicator NOT IN ["Y", "N"]
  THEN flag CDI-POA-002-MISSING_POA

  IF diagnosis.code IN HAC_RELEVANT_CODES
  AND diagnosis.poa_indicator == "N"
  AND skin_assessment_on_admission IS None  # (for pressure ulcers)
  THEN flag CDI-POA-002-VERIFY_N
  # Query: "Was [condition] present on admission? Documentation
  # needed for accurate POA indicator assignment."
  ```
- **Revenue impact:** HAC penalty: 1% total Medicare payment reduction for bottom-quartile hospitals. Individual case adjustment for HAC diagnoses with POA=N. Per DISC-001 C.5.
- **Priority:** P1

---

## 2. Detection Algorithm

### 2.1 Data Model (Input)

```python
class CDIAnalysisInput(BaseModel):
    """Complete data required for CDI opportunity detection."""

    encounter_id: str
    encounter_setting: Literal["inpatient", "outpatient"]
    admission_date: datetime
    current_date: datetime

    # NLP-extracted entities from physician note
    note_entities: NoteEntities
    # Structured lab results from FHIR Observation
    lab_results: list[LabResult]
    # Vital signs from FHIR Observation
    vitals: list[VitalSign]
    # Medication list from FHIR MedicationRequest
    medications: list[Medication]
    # Problem list from FHIR Condition
    problem_list: list[ProblemListEntry]
    # Prior notes for copy-forward detection
    prior_notes: list[PriorNote] | None = None


class NoteEntities(BaseModel):
    """Entities extracted by the NLP pipeline."""

    diagnoses: list[ExtractedDiagnosis]
    symptoms: list[ExtractedSymptom]
    procedures: list[ExtractedProcedure]
    medications_mentioned: list[str]
    qualifier_words: list[QualifierWord]
    negated_entities: list[str]
    note_sections: dict[str, str]  # section_name → text


class LabResult(BaseModel):
    """Single lab result from FHIR Observation."""

    code: str  # LOINC code
    name: str  # Display name
    value: float
    unit: str
    reference_low: float | None = None
    reference_high: float | None = None
    timestamp: datetime
    is_critical: bool = False


class CDIOpportunity(BaseModel):
    """A single CDI opportunity detected by the algorithm."""

    opportunity_id: str  # e.g., "CDI-SEV-001"
    category: Literal["severity", "specificity", "causality", "poa"]
    subcategory: str  # e.g., "AKI not documented"
    priority: Literal["P0", "P1", "P2"]

    # Evidence supporting this opportunity
    clinical_indicators: list[ClinicalIndicator]
    lab_evidence: list[LabEvidence]
    medication_evidence: list[str]

    # Revenue context
    current_cc_status: str  # "non_cc", "cc", "mcc"
    potential_cc_status: str
    estimated_revenue_impact: str  # e.g., "$3,000-$8,000"
    requires_compliance_review: bool  # True if impact > $5,000

    # Query generation
    query_template_id: str  # Maps to physician query template
    query_variables: dict[str, str]  # Template variable values

    confidence: float = Field(ge=0.0, le=1.0)
```

### 2.2 Detection Pseudocode for Each Category

#### CDI-SEV-001: AKI Detection

```
FUNCTION detect_aki(input: CDIAnalysisInput) -> CDIOpportunity | None:

    # Step 1: Check if AKI is already documented
    AKI_TERMS = ["acute kidney injury", "AKI", "acute renal failure",
                 "ARF", "acute renal insufficiency", "acute tubular necrosis"]
    IF any(term IN input.note_entities.diagnoses for term in AKI_TERMS):
        RETURN None  # Already documented — no CDI opportunity

    # Step 2: Get creatinine values
    creatinine_results = filter(input.lab_results, code="2160-0")  # LOINC for serum creatinine
    IF len(creatinine_results) < 2:
        RETURN None  # Need trend data

    # Step 3: Determine baseline creatinine
    # Baseline = lowest creatinine in prior 7-365 days, or admission value
    baseline_cr = get_baseline_creatinine(creatinine_results, input.admission_date)
    current_cr = get_most_recent(creatinine_results)

    # Step 4: Apply KDIGO criteria
    delta_48h = get_max_rise_within_hours(creatinine_results, hours=48)
    ratio_7d = current_cr.value / baseline_cr.value IF baseline_cr.value > 0 ELSE 0

    kdigo_stage = None
    IF delta_48h >= 0.3:
        kdigo_stage = 1
    IF ratio_7d >= 1.5 AND ratio_7d < 2.0:
        kdigo_stage = max(kdigo_stage or 0, 1)
    IF ratio_7d >= 2.0 AND ratio_7d < 3.0:
        kdigo_stage = 2
    IF ratio_7d >= 3.0 OR current_cr.value >= 4.0:
        kdigo_stage = 3

    IF kdigo_stage IS None:
        RETURN None  # Does not meet KDIGO criteria

    # Step 5: Check if creatinine rise is acknowledged in note
    IF note_contains("creatinine" AND ("elevated" OR "rising" OR "increased")):
        # Physician noted the creatinine change but did not diagnosis AKI
        # This strengthens the CDI opportunity
        confidence = 0.90
    ELSE:
        confidence = 0.80

    # Step 6: Check for medications that imply AKI awareness
    nephrotoxic_held = any(med.status == "held" AND med.name IN NEPHROTOXIC_MEDS
                          for med in input.medications)
    IF nephrotoxic_held:
        confidence = min(confidence + 0.05, 0.95)

    RETURN CDIOpportunity(
        opportunity_id="CDI-SEV-001",
        category="severity",
        subcategory=f"AKI KDIGO Stage {kdigo_stage} not documented",
        priority="P0",
        clinical_indicators=[
            ClinicalIndicator(type="lab_trend",
                description=f"Creatinine: {baseline_cr.value} → {current_cr.value} mg/dL"),
            ClinicalIndicator(type="criteria_met",
                description=f"KDIGO Stage {kdigo_stage} criteria met"),
        ],
        lab_evidence=[
            LabEvidence(name="Baseline creatinine", value=baseline_cr.value,
                date=baseline_cr.timestamp),
            LabEvidence(name="Current creatinine", value=current_cr.value,
                date=current_cr.timestamp),
            LabEvidence(name="48h delta", value=delta_48h),
        ],
        medication_evidence=[med.name for med in input.medications
                            if med.name IN RENAL_DOSE_ADJUSTED],
        current_cc_status="not_coded",
        potential_cc_status="mcc",
        estimated_revenue_impact="$3,000-$8,000",
        requires_compliance_review=False,
        query_template_id="QUERY-SEV-001",
        query_variables={
            "baseline_cr": str(baseline_cr.value),
            "baseline_date": baseline_cr.timestamp.strftime("%m/%d"),
            "current_cr": str(current_cr.value),
            "current_date": current_cr.timestamp.strftime("%m/%d"),
            "delta": str(delta_48h),
            "kdigo_stage": str(kdigo_stage),
        },
        confidence=confidence,
    )
```

#### CDI-SEV-002: Sepsis Detection

```
FUNCTION detect_sepsis(input: CDIAnalysisInput) -> CDIOpportunity | None:

    SEPSIS_TERMS = ["sepsis", "septic", "severe sepsis", "septic shock",
                    "bacteremia", "SIRS with infection"]
    IF any(term IN input.note_entities.diagnoses for term in SEPSIS_TERMS):
        # Sepsis already documented — check for specificity opportunity
        RETURN detect_sepsis_specificity(input)  # → CDI-CAUSE-001

    # Step 1: Check SIRS criteria (need >= 2)
    sirs_count = 0
    sirs_evidence = []
    temp = get_latest_vital(input.vitals, "temperature")
    hr = get_latest_vital(input.vitals, "heart_rate")
    rr = get_latest_vital(input.vitals, "respiratory_rate")
    wbc = get_latest_lab(input.lab_results, code="6690-2")  # WBC

    IF temp AND (temp.value > 38.3 OR temp.value < 36.0):
        sirs_count += 1
        sirs_evidence.append(f"Temp: {temp.value}°C")
    IF hr AND hr.value > 90:
        sirs_count += 1
        sirs_evidence.append(f"HR: {hr.value} bpm")
    IF rr AND rr.value > 20:
        sirs_count += 1
        sirs_evidence.append(f"RR: {rr.value}")
    IF wbc AND (wbc.value > 12000 OR wbc.value < 4000):
        sirs_count += 1
        sirs_evidence.append(f"WBC: {wbc.value}")

    IF sirs_count < 2:
        RETURN None  # Does not meet SIRS criteria

    # Step 2: Check for documented infection
    infection_documented = any(
        term IN input.note_entities.diagnoses
        for term in INFECTION_TERMS  # UTI, pneumonia, cellulitis, etc.
    )
    positive_cultures = any(
        lab.name CONTAINS "culture" AND lab.value_text == "positive"
        for lab in input.lab_results
    )

    IF NOT infection_documented AND NOT positive_cultures:
        RETURN None  # SIRS without infection evidence — not sepsis

    # Step 3: Check lactate (severity indicator)
    lactate = get_latest_lab(input.lab_results, code="2524-7")
    has_organ_dysfunction = False
    organ_dysfunction_list = []

    IF lactate AND lactate.value > 2.0:
        organ_dysfunction_list.append(f"Lactate: {lactate.value} mmol/L")
        has_organ_dysfunction = True

    # Check for organ dysfunction markers
    cr_rise = check_creatinine_rise(input.lab_results)
    IF cr_rise:
        organ_dysfunction_list.append("Creatinine rise (renal)")
        has_organ_dysfunction = True

    plt = get_latest_lab(input.lab_results, code="777-3")  # Platelets
    IF plt AND plt.value < 100000:
        organ_dysfunction_list.append(f"Platelets: {plt.value}")
        has_organ_dysfunction = True

    bili = get_latest_lab(input.lab_results, code="1975-2")  # Total bilirubin
    IF bili AND bili.value > 2.0:
        organ_dysfunction_list.append(f"Bilirubin: {bili.value}")
        has_organ_dysfunction = True

    # Step 4: Check for vasopressors (septic shock indicator)
    on_vasopressors = any(
        med.name IN VASOPRESSOR_MEDS for med in input.medications
    )

    severity = "sepsis"
    IF has_organ_dysfunction:
        severity = "severe sepsis"
    IF on_vasopressors:
        severity = "septic shock"

    RETURN CDIOpportunity(
        opportunity_id="CDI-SEV-002",
        category="severity",
        subcategory=f"{severity} not documented (SIRS + infection present)",
        priority="P0",
        clinical_indicators=[
            ClinicalIndicator(type="criteria_met",
                description=f"SIRS criteria met ({sirs_count}/4): {', '.join(sirs_evidence)}"),
            ClinicalIndicator(type="infection",
                description=f"Infection evidence: {infection_source}"),
        ] + ([ClinicalIndicator(type="organ_dysfunction",
                description=f"Organ dysfunction: {', '.join(organ_dysfunction_list)}")]
             IF has_organ_dysfunction ELSE []),
        lab_evidence=[...],  # SIRS labs + lactate + cultures
        current_cc_status="not_coded",
        potential_cc_status="mcc",
        estimated_revenue_impact="$6,000-$42,759" IF has_organ_dysfunction ELSE "$6,000-$13,000",
        requires_compliance_review=True,  # Sepsis always > $5,000
        query_template_id="QUERY-SEV-002",
        query_variables={
            "sirs_criteria": ", ".join(sirs_evidence),
            "infection_source": infection_source,
            "organ_dysfunction": ", ".join(organ_dysfunction_list) or "None identified",
            "lactate": str(lactate.value) if lactate else "Not available",
            "cultures": culture_summary,
        },
        confidence=0.85 IF positive_cultures ELSE 0.70,
    )
```

#### CDI-SEV-003: Malnutrition Detection

```
FUNCTION detect_malnutrition(input: CDIAnalysisInput) -> CDIOpportunity | None:

    MALNUTRITION_TERMS = ["malnutrition", "malnourished", "protein-calorie malnutrition",
                          "PCM", "cachexia", "kwashiorkor", "marasmus",
                          "severe malnutrition", "moderate malnutrition"]
    IF any(term IN input.note_entities.diagnoses for term in MALNUTRITION_TERMS):
        RETURN None  # Already documented

    # Collect nutritional indicators
    indicators = []
    score = 0  # Need >= 2 indicators to flag

    bmi = get_latest_vital(input.vitals, "bmi")
    IF bmi AND bmi.value < 18.5:
        indicators.append(f"BMI: {bmi.value}")
        score += 2  # Strong indicator

    albumin = get_latest_lab(input.lab_results, code="1751-7")
    IF albumin AND albumin.value < 3.0:
        indicators.append(f"Albumin: {albumin.value} g/dL")
        score += 1
    IF albumin AND albumin.value < 2.5:
        score += 1  # Additional weight for severe hypoalbuminemia

    prealbumin = get_latest_lab(input.lab_results, code="14338-7")
    IF prealbumin AND prealbumin.value < 15:
        indicators.append(f"Prealbumin: {prealbumin.value} mg/dL")
        score += 1

    # Weight loss detection
    weight_trend = get_weight_trend(input.vitals, days=30)
    IF weight_trend AND weight_trend.percent_loss > 5:
        indicators.append(f"Weight loss: {weight_trend.percent_loss:.1f}% in {weight_trend.days} days")
        score += 2

    # Medication/order indicators
    dietitian_consult = any("dietitian" IN order.description OR "nutrition" IN order.description
                           for order in input.note_entities.procedures)
    IF dietitian_consult:
        indicators.append("Dietitian consult ordered")
        score += 1

    nutritional_supplements = any(med.name IN NUTRITIONAL_SUPPLEMENT_MEDS
                                  for med in input.medications)
    IF nutritional_supplements:
        indicators.append("Nutritional supplements ordered")
        score += 1

    IF score < 2:
        RETURN None  # Insufficient evidence

    # Determine likely severity
    severity = "mild"
    IF (bmi AND bmi.value < 16) OR (albumin AND albumin.value < 2.5) \
       OR (weight_trend AND weight_trend.percent_loss > 10):
        severity = "severe"
    ELIF (bmi AND bmi.value < 17) OR (albumin AND albumin.value < 2.8) \
         OR (weight_trend AND weight_trend.percent_loss > 7):
        severity = "moderate"

    RETURN CDIOpportunity(
        opportunity_id="CDI-SEV-003",
        category="severity",
        subcategory=f"Malnutrition (likely {severity}) not documented",
        priority="P1",
        clinical_indicators=[ClinicalIndicator(type="nutritional", description=ind)
                            for ind in indicators],
        lab_evidence=[...],
        current_cc_status="not_coded",
        potential_cc_status="mcc" IF severity == "severe" ELSE "cc",
        estimated_revenue_impact="$3,000-$9,000",
        requires_compliance_review=severity == "severe",
        query_template_id="QUERY-SEV-003",
        query_variables={
            "bmi": str(bmi.value) if bmi else "Not recorded",
            "albumin": str(albumin.value) if albumin else "Not available",
            "weight_loss": f"{weight_trend.percent_loss:.1f}%" if weight_trend else "Not measured",
            "indicators": "; ".join(indicators),
        },
        confidence=min(0.60 + (score * 0.08), 0.92),
    )
```

#### CDI-SEV-004: Encephalopathy Detection

```
FUNCTION detect_encephalopathy(input: CDIAnalysisInput) -> CDIOpportunity | None:

    ENCEPHALOPATHY_TERMS = ["encephalopathy", "metabolic encephalopathy",
                            "hepatic encephalopathy", "toxic encephalopathy",
                            "hypoxic encephalopathy", "uremic encephalopathy",
                            "hyponatremic encephalopathy"]
    IF any(term IN input.note_entities.diagnoses for term in ENCEPHALOPATHY_TERMS):
        RETURN None

    # Step 1: Check for altered mental status
    AMS_TERMS = ["altered mental status", "AMS", "confusion", "disorientation",
                 "somnolence", "obtunded", "delirium", "agitation", "lethargy",
                 "unresponsive", "GCS < 15"]
    ams_documented = any(term IN input.note_entities.symptoms for term in AMS_TERMS)
    IF NOT ams_documented:
        RETURN None

    # Step 2: Check for metabolic derangement
    metabolic_causes = []

    sodium = get_latest_lab(input.lab_results, code="2951-2")
    IF sodium AND sodium.value < 120:
        metabolic_causes.append(("hyponatremic", f"Sodium: {sodium.value} mEq/L"))

    bun = get_latest_lab(input.lab_results, code="3094-0")
    IF bun AND bun.value > 60:
        metabolic_causes.append(("uremic", f"BUN: {bun.value} mg/dL"))

    ammonia = get_latest_lab(input.lab_results, code="1925-7")
    IF ammonia AND ammonia.value > 60:
        metabolic_causes.append(("hepatic", f"Ammonia: {ammonia.value} mcg/dL"))

    pao2 = get_latest_lab(input.lab_results, code="2703-7")
    IF pao2 AND pao2.value < 60:
        metabolic_causes.append(("hypoxic", f"PaO2: {pao2.value} mmHg"))

    glucose = get_latest_lab(input.lab_results, code="2345-7")
    IF glucose AND glucose.value < 50:
        metabolic_causes.append(("hypoglycemic", f"Glucose: {glucose.value} mg/dL"))

    IF len(metabolic_causes) == 0:
        RETURN None  # AMS without identified metabolic cause

    primary_etiology = metabolic_causes[0][0]

    RETURN CDIOpportunity(
        opportunity_id="CDI-SEV-004",
        category="severity",
        subcategory=f"{primary_etiology} encephalopathy not documented",
        priority="P1",
        clinical_indicators=[
            ClinicalIndicator(type="symptom", description="Altered mental status documented"),
            ClinicalIndicator(type="metabolic",
                description=f"Metabolic derangement: {metabolic_causes[0][1]}"),
        ],
        lab_evidence=[...],
        current_cc_status="non_cc",  # R41.82 (AMS) is Non-CC
        potential_cc_status="mcc",    # G93.41 (Metabolic encephalopathy) is MCC
        estimated_revenue_impact="$4,000-$10,000",
        requires_compliance_review=True,
        query_template_id="QUERY-SEV-004",
        query_variables={
            "ams_description": ams_term_found,
            "metabolic_abnormality": metabolic_causes[0][1],
            "etiology_type": primary_etiology,
            "all_derangements": "; ".join([c[1] for c in metabolic_causes]),
        },
        confidence=0.80,
    )
```

#### CDI-SEV-005: Respiratory Failure Detection

```
FUNCTION detect_respiratory_failure(input: CDIAnalysisInput) -> CDIOpportunity | None:

    RF_TERMS = ["respiratory failure", "acute respiratory failure",
                "chronic respiratory failure", "acute on chronic respiratory failure",
                "ventilatory failure"]
    IF any(term IN input.note_entities.diagnoses for term in RF_TERMS):
        RETURN None

    # Step 1: Check objective respiratory indicators
    indicators = []
    rf_type = None

    pao2 = get_latest_lab(input.lab_results, code="2703-7")
    spo2 = get_latest_vital(input.vitals, "spo2")
    paco2 = get_latest_lab(input.lab_results, code="2019-8")
    ph = get_latest_lab(input.lab_results, code="2744-1")

    IF pao2 AND pao2.value < 60:
        indicators.append(f"PaO2: {pao2.value} mmHg (< 60)")
        rf_type = "hypoxic"
    IF spo2 AND spo2.value < 88:
        indicators.append(f"SpO2: {spo2.value}% (< 88%)")
        rf_type = rf_type or "hypoxic"
    IF paco2 AND paco2.value > 50 AND ph AND ph.value < 7.35:
        indicators.append(f"PaCO2: {paco2.value} mmHg with pH {ph.value}")
        rf_type = "hypercapnic" IF rf_type IS None ELSE "mixed"

    # Step 2: Check respiratory support
    on_ventilator = any(med.name IN VENTILATOR_SETTINGS for med in input.medications)
    on_bipap = any("BiPAP" IN order.description OR "NIPPV" IN order.description
                   for order in input.note_entities.procedures)
    high_flow_o2 = get_latest_vital(input.vitals, "fio2")

    IF on_ventilator:
        indicators.append("On mechanical ventilation")
    IF on_bipap:
        indicators.append("On BiPAP/NIPPV")
    IF high_flow_o2 AND high_flow_o2.value > 0.40:
        indicators.append(f"FiO2: {high_flow_o2.value * 100:.0f}% (> 40%)")

    IF len(indicators) == 0:
        RETURN None

    # Step 3: Check that symptoms are documented (not RF diagnosis)
    symptom_only = any(term IN input.note_entities.symptoms
                       for term in ["hypoxia", "hypoxemia", "respiratory distress",
                                    "dyspnea", "shortness of breath"])

    RETURN CDIOpportunity(
        opportunity_id="CDI-SEV-005",
        category="severity",
        subcategory=f"Acute {rf_type or ''} respiratory failure not documented",
        priority="P0",
        clinical_indicators=[ClinicalIndicator(type="respiratory", description=ind)
                            for ind in indicators],
        lab_evidence=[...],
        current_cc_status="non_cc" IF symptom_only ELSE "not_coded",
        potential_cc_status="mcc",
        estimated_revenue_impact="$4,000-$10,000",
        requires_compliance_review=True,
        query_template_id="QUERY-SEV-005",
        query_variables={
            "pao2": str(pao2.value) if pao2 else "Not available",
            "spo2": str(spo2.value) if spo2 else "Not available",
            "fio2": f"{high_flow_o2.value * 100:.0f}%" if high_flow_o2 else "Not recorded",
            "support_type": "mechanical ventilation" if on_ventilator
                           else "BiPAP" if on_bipap else "supplemental O2",
            "rf_type": rf_type or "unspecified",
        },
        confidence=0.85 IF on_ventilator ELSE 0.75,
    )
```

### 2.3 CDI Opportunity Prioritization

```python
class CDIPrioritizer:
    """Ranks CDI opportunities by clinical validity and revenue impact."""

    PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

    def prioritize(
        self,
        opportunities: list[CDIOpportunity],
    ) -> list[CDIOpportunity]:
        """Sort opportunities by priority, then confidence, then revenue."""

        return sorted(opportunities, key=lambda o: (
            self.PRIORITY_ORDER[o.priority],   # P0 first
            -o.confidence,                      # Higher confidence first
            -self._revenue_midpoint(o),         # Higher revenue first
        ))

    def _revenue_midpoint(self, o: CDIOpportunity) -> float:
        """Extract midpoint from revenue range string."""
        # Parse "$3,000-$8,000" → 5500.0
        ...

    def filter_low_confidence(
        self,
        opportunities: list[CDIOpportunity],
        threshold: float = 0.65,
    ) -> list[CDIOpportunity]:
        """Remove opportunities below confidence threshold.

        Per CLAUDE.md: confidence < 0.65 routes to senior queue.
        CDI opportunities below this threshold are too uncertain
        to generate a physician query.
        """
        return [o for o in opportunities if o.confidence >= threshold]
```

---

## 3. Physician Query Templates

### 3.1 Template Compliance Framework

All physician queries comply with:

1. **AHIMA Standards for CDI (2016 updated):** Queries must be
   clinically relevant, non-leading, and supported by objective
   clinical indicators from the patient's record.

2. **ACDIS Code of Ethics:** CDI queries must not suggest a
   specific diagnosis. They must present clinical evidence and
   ask the physician to make a clinical determination.

3. **OIG Compliance Guidance:** Queries must not be designed
   to "lead" physicians toward higher-reimbursing diagnoses.
   The clinical question must be genuine — the answer must be
   clinically uncertain based on the documentation.

**Compliance test for every query template:**
- Does the query present objective clinical data? YES required.
- Does the query suggest a specific diagnosis? NO required.
- Does the query offer multiple clinically valid options? YES required.
- Could the physician reasonably answer "No" or "Clinically undetermined"? YES required.
- Does the query include revenue/DRG information? NO required.

### 3.2 Query Template Structure

```python
class PhysicianQuery(BaseModel):
    """AHIMA-compliant physician query generated by CDI agent."""

    query_id: str = Field(description="Unique query identifier.")
    encounter_id: str
    opportunity_id: str  # Links to CDIOpportunity
    template_id: str  # e.g., "QUERY-SEV-001"

    # Header
    query_type: Literal["clinical_clarification", "specificity",
                        "causality", "poa_determination"]
    addressed_to: str  # Attending physician name
    generated_at: datetime
    response_deadline: datetime  # 24 hours from generation

    # Body
    clinical_indicators: str  # Formatted clinical evidence
    clinical_question: str  # The non-leading question
    response_options: list[QueryResponseOption]

    # Educational component
    clinical_rationale: str  # Why this matters clinically (not financially)

    # Compliance metadata
    is_compliant: bool = True
    compliance_review_notes: str = ""


class QueryResponseOption(BaseModel):
    """A single response option for a physician query."""

    option_id: str
    label: str  # e.g., "Yes — acute kidney injury is present"
    requires_free_text: bool = False
    follow_up_needed: bool = False
```

### 3.3 Query Templates by Category

#### QUERY-SEV-001: AKI Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

Laboratory findings indicate a change in renal function:
  - Baseline creatinine: {baseline_cr} mg/dL ({baseline_date})
  - Current creatinine: {current_cr} mg/dL ({current_date})
  - Change: {delta} mg/dL within 48 hours
  - These values meet KDIGO Stage {kdigo_stage} criteria

CLINICAL QUESTION:

Based on the clinical picture, does this patient have
acute kidney injury?

RESPONSE OPTIONS:

  [ ] Yes — acute kidney injury is present
      If yes, please document:
      - Etiology (if known): _______________
      - Stage (if assessable): _____________

  [ ] No — creatinine change is not clinically significant
      or represents a different process
      Please clarify: _______________

  [ ] Clinically undetermined at this time

  [ ] Other: _______________

CLINICAL NOTE:

Accurate documentation of acute kidney injury, when present,
ensures appropriate clinical communication across the care
team, supports medication dosing decisions, and facilitates
continuity of care at discharge.

─────────────────────────────────────────
This query was generated based on objective laboratory data.
CDI Department | Response within 24 hours appreciated.
```

**Compliance notes:**
- Query presents objective lab data, not a diagnosis suggestion
- "Does this patient have acute kidney injury?" is open-ended
- "No" is a valid and accessible response option
- "Clinically undetermined" is offered per AHIMA guidance
- Clinical rationale focuses on patient care, not revenue
- No mention of DRG, CC/MCC, or financial impact

#### QUERY-SEV-002: Sepsis Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

The following clinical findings have been identified:

Systemic inflammatory response indicators:
  {sirs_criteria}

Infection evidence:
  {infection_source}

Additional findings:
  {organ_dysfunction}
  Lactate: {lactate} mmol/L

CLINICAL QUESTION:

Based on the clinical presentation and your assessment,
does this patient meet criteria for sepsis?

RESPONSE OPTIONS:

  [ ] Yes — sepsis is present
      If yes, please clarify:
      - Source of infection: _______________
      - Causative organism (if known): _______________
      - Is organ dysfunction present? _______________
      - Severity: [ ] Sepsis  [ ] Severe sepsis  [ ] Septic shock

  [ ] No — SIRS criteria are present but do not represent
      sepsis in this clinical context
      Please clarify: _______________

  [ ] Clinically undetermined at this time

  [ ] Other: _______________

CLINICAL NOTE:

Early and accurate recognition of sepsis is associated with
improved patient outcomes. Clear documentation of sepsis
severity and source supports antimicrobial stewardship and
care team communication.

─────────────────────────────────────────
This query was generated based on objective clinical data.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-SEV-003: Malnutrition Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

Nutritional assessment findings:
  - BMI: {bmi}
  - Albumin: {albumin} g/dL
  - Weight change: {weight_loss} over recent period
  - Additional indicators: {indicators}

CLINICAL QUESTION:

Based on your clinical assessment, does this patient have
malnutrition?

RESPONSE OPTIONS:

  [ ] Yes — malnutrition is present
      If yes, please specify:
      - Severity: [ ] Mild  [ ] Moderate  [ ] Severe
      - Type (if applicable): _______________
        (e.g., protein-calorie malnutrition)

  [ ] No — nutritional indicators do not represent
      clinical malnutrition in this patient
      Please clarify: _______________

  [ ] Clinically undetermined — further nutritional
      assessment needed

  [ ] Other: _______________

CLINICAL NOTE:

Malnutrition is associated with increased infection risk,
impaired wound healing, longer hospital stays, and higher
readmission rates. Accurate documentation supports
appropriate nutritional care planning and discharge
nutrition services.

─────────────────────────────────────────
This query was generated based on objective clinical data.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-SEV-004: Encephalopathy Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

Mental status findings:
  - Documented: {ams_description}

Concurrent metabolic findings:
  - {all_derangements}

CLINICAL QUESTION:

In the setting of altered mental status with the above
metabolic findings, does this patient have encephalopathy?

RESPONSE OPTIONS:

  [ ] Yes — encephalopathy is present
      If yes, please specify:
      - Type: [ ] Metabolic  [ ] Toxic  [ ] Hepatic
              [ ] Hypoxic  [ ] Uremic  [ ] Other: ____
      - Underlying etiology: _______________

  [ ] No — altered mental status has a different etiology
      Please clarify: _______________

  [ ] Clinically undetermined at this time

  [ ] Other: _______________

CLINICAL NOTE:

Accurate characterization of altered mental status supports
appropriate neurological monitoring, identifies reversible
causes, and guides treatment decisions.

─────────────────────────────────────────
This query was generated based on objective clinical data.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-SEV-005: Respiratory Failure Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

Respiratory assessment findings:
  - PaO2: {pao2} mmHg
  - SpO2: {spo2}%
  - Current respiratory support: {support_type}
  - FiO2: {fio2}

CLINICAL QUESTION:

Based on the clinical presentation and respiratory support
requirements, does this patient have acute respiratory
failure?

RESPONSE OPTIONS:

  [ ] Yes — acute respiratory failure is present
      If yes, please specify:
      - Type: [ ] Hypoxic (Type 1)  [ ] Hypercapnic (Type 2)
              [ ] Mixed  [ ] Acute on chronic
      - Etiology (if known): _______________

  [ ] No — respiratory findings do not represent
      respiratory failure in this clinical context
      Please clarify: _______________

  [ ] Clinically undetermined at this time

  [ ] Other: _______________

CLINICAL NOTE:

Documentation of respiratory failure type and acuity
supports ventilator management decisions, weaning
protocols, and appropriate post-discharge respiratory
care planning.

─────────────────────────────────────────
This query was generated based on objective clinical data.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-SPEC-001: Heart Failure Specificity Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

Heart failure is documented in the clinical record.
The following additional clinical data is available:
  - Most recent ejection fraction: {ef_value}
  - BNP: {bnp_value} pg/mL
  - Current diuretic regimen: {diuretics}
  - Chest imaging: {cxr_findings}

CLINICAL QUESTION:

To support accurate clinical communication, please
clarify the following about the patient's heart failure:

1. Type:
   [ ] Systolic (HFrEF)
   [ ] Diastolic (HFpEF)
   [ ] Combined systolic and diastolic
   [ ] Unable to determine at this time

2. Acuity:
   [ ] Acute
   [ ] Chronic
   [ ] Acute on chronic (acute decompensation of
       chronic heart failure)
   [ ] Unable to determine at this time

CLINICAL NOTE:

Specificity of heart failure type and acuity supports
appropriate guideline-directed medical therapy selection,
device eligibility assessment, and prognostic counseling.

─────────────────────────────────────────
This query was generated based on available clinical data.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-CAUSE-001: Sepsis Source/Organism Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

Sepsis is documented. The following additional data
is available:

  Culture results: {cultures}
  Identified organism: {organism}
  Suspected infection source: {suspected_source}

CLINICAL QUESTION:

To support complete clinical documentation of the
sepsis episode:

1. Source of infection:
   [ ] Urinary tract  [ ] Respiratory  [ ] Skin/soft tissue
   [ ] Bloodstream (primary)  [ ] Intra-abdominal
   [ ] Surgical site  [ ] Line-related
   [ ] Other: _______________
   [ ] Unknown source

2. Can the documented organism ({organism}) be identified
   as the causative agent?
   [ ] Yes  [ ] No  [ ] Undetermined

3. Is organ dysfunction present?
   [ ] Yes — Organs affected: _______________
   [ ] No

CLINICAL NOTE:

Source identification and organism documentation support
antimicrobial stewardship, infection control surveillance,
and continuity of care at discharge and follow-up.

─────────────────────────────────────────
This query was generated based on objective clinical data.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-CAUSE-004: Causal Relationship Query (General)

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

The patient's record documents:
  - {condition_a}
  - {condition_b}

CLINICAL QUESTION:

Is there a causal relationship between {condition_a}
and {condition_b}?

RESPONSE OPTIONS:

  [ ] Yes — {condition_b} is due to / caused by {condition_a}
  [ ] Yes — {condition_a} is due to / caused by {condition_b}
  [ ] No — these are independent conditions
  [ ] Clinically undetermined

CLINICAL NOTE:

Clarifying the relationship between coexisting conditions
supports accurate clinical communication, treatment
prioritization, and care team coordination.

─────────────────────────────────────────
This query was generated based on clinical documentation.
CDI Department | Response within 24 hours appreciated.
```

#### QUERY-POA-001: POA Determination Query

```
CLINICAL CLARIFICATION QUERY
Patient: [encounter_id]
Attending: [physician_name]
Date: [current_date]
Response requested by: [deadline_24h]

─────────────────────────────────────────

CLINICAL INDICATORS:

The following condition has been identified in the
clinical record:
  - Diagnosis: {diagnosis}
  - First documented: {first_documented_date}
  - Admission date: {admission_date}

CLINICAL QUESTION:

Was {diagnosis} present at the time of inpatient
admission?

RESPONSE OPTIONS:

  [ ] Yes — condition was present at admission
  [ ] No — condition developed after admission
  [ ] Clinically unable to determine
  [ ] Documentation is insufficient to make a
      determination

CLINICAL NOTE:

Accurate documentation of condition onset relative to
admission supports quality reporting and patient safety
monitoring.

─────────────────────────────────────────
This query was generated for documentation clarification.
CDI Department | Response within 24 hours appreciated.
```

---

## 4. CDI Workflow Integration

### 4.1 Trigger Events

```
CDI analysis is triggered by the following events:

EVENT 1: Note Signed (PRIMARY TRIGGER)
─────────────────────────────────────
When: Attending physician signs a progress note, H&P,
      consultation note, or operative report
Source: EHR event subscription (FHIR Subscription on
        DocumentReference with status=current)
Latency target: CDI analysis begins < 5 minutes after
                note signing event

EVENT 2: Lab Result Critical (SECONDARY TRIGGER)
─────────────────────────────────────
When: A critical or significantly abnormal lab result
      posts to the patient's chart
Source: FHIR Subscription on Observation with
        interpretation=critical
Examples: Creatinine doubling, lactate > 4.0, blood
          culture positive
Action: Re-run CDI detection against most recent note
        with new lab data

EVENT 3: Discharge Pending (FINAL SWEEP)
─────────────────────────────────────
When: Discharge order is placed or discharge date set
Source: EHR discharge workflow event
Action: Final comprehensive CDI sweep across all notes,
        labs, and medications for the entire encounter
Latency target: CDI sweep completes < 30 minutes after
                discharge event
Purpose: Catch any missed opportunities before coding
         begins
```

### 4.2 Query Delivery

```
DELIVERY CHANNEL HIERARCHY:

1. EHR Inbox (PRIMARY)
   - Query appears as a structured message in the
     physician's EHR inbox
   - Integrated with existing CDI query workflow
   - Physician responds within the EHR
   - Response captured as structured data

2. Mobile Push Notification (SECONDARY)
   - If EHR supports mobile integration
   - Notification that a CDI query awaits response
   - Links to EHR inbox for response

3. CDI Specialist Delivery (FALLBACK)
   - If electronic delivery fails or is unavailable
   - CDI specialist delivers query in person or via
     secure message
   - CDI specialist enters response into the system

QUERY ROUTING:

- Addressed to: ATTENDING PHYSICIAN of record
- CC: CDI specialist assigned to the unit/service
- NOT sent to: Residents, fellows, NPs, PAs
  (unless they are the attending of record)
- Rationale: Only the attending can make documentation
  changes that coders rely on for code assignment
```

### 4.3 Response Handling

```
RESPONSE WORKFLOW:

Physician Responds → Response Captured → Action Taken

RESPONSE: "Yes — [condition] is present"
ACTION:
  1. CDI opportunity status = RESOLVED_POSITIVE
  2. Physician's documentation update is recorded
  3. CDI agent notifies coding agent that a new
     condition has been documented
  4. Coding agent re-runs code suggestion pipeline
     with updated documentation
  5. Rules engine validates new suggestion set
  6. Updated suggestions appear in coder review UI
  7. DRG impact is recalculated and displayed

RESPONSE: "No — [condition] is not present"
ACTION:
  1. CDI opportunity status = RESOLVED_NEGATIVE
  2. No coding change occurs
  3. Opportunity logged for quality tracking
     (was this a false positive?)
  4. If confidence was high (> 0.85) and physician
     said "No," flag for CDI specialist review
     (the AI may be wrong, or the physician may need
     education)

RESPONSE: "Clinically undetermined"
ACTION:
  1. CDI opportunity status = DEFERRED
  2. No coding change occurs
  3. Schedule follow-up query in 24-48 hours
     if patient is still admitted
  4. At discharge: final determination needed

NO RESPONSE within 24 hours:
ACTION:
  1. CDI opportunity status = PENDING_ESCALATION
  2. Proceed to escalation path (Section 4.4)
```

### 4.4 Escalation Path

```
ESCALATION TIMELINE:

T+0h:    CDI query generated and delivered to attending
T+24h:   First reminder sent to attending
         CDI specialist notified of non-response
T+48h:   Second reminder to attending
         CDI specialist attempts verbal contact
         Department chief notified (if policy permits)
T+72h:   CDI query status = EXPIRED
         CDI specialist documents non-response
         Case coded WITHOUT the CDI opportunity
         Non-response logged for physician scorecard

POST-DISCHARGE NON-RESPONSE:
  If patient discharged and attending has not responded:
  - CDI specialist has 5 business days to obtain
    response per standard bill-hold period
  - If response obtained: addendum to discharge summary,
    coding updated
  - If no response: code from existing documentation only
  - Per constitution Article II.6: when uncertain,
    code conservatively

NEVER:
  - Auto-code a condition based on CDI query alone
  - Extend bill-hold beyond facility policy waiting
    for a CDI response
  - Contact the physician more than 3 times about
    one query
```

### 4.5 Workflow Diagram

```
     PHYSICIAN SIGNS NOTE
              │
              ▼
     ┌────────────────┐
     │  NLP Pipeline   │ ← Extracts entities, symptoms,
     │  processes note  │   negations, qualifiers
     └───────┬────────┘
              │
              ▼
     ┌────────────────┐    ┌─────────────────┐
     │  CDI Agent      │◄───│ FHIR Data       │
     │  Detection      │    │ (labs, vitals,   │
     │  Algorithm      │    │  meds, problems) │
     └───────┬────────┘    └─────────────────┘
              │
              ▼
     ┌────────────────┐
     │  CDI Opps       │ ← Prioritized list of
     │  Prioritized    │   documentation gaps
     └───────┬────────┘
              │
              ▼
     ┌────────────────┐
     │  Query          │ ← Generates AHIMA-compliant
     │  Generator      │   physician queries
     └───────┬────────┘
              │
              ├──────────────────┐
              ▼                  ▼
     ┌────────────┐     ┌─────────────┐
     │ EHR Inbox  │     │ CDI         │
     │ (physician)│     │ Dashboard   │
     └─────┬──────┘     │ (CDI team)  │
           │            └──────┬──────┘
           ▼                   │
     ┌────────────┐            │
     │ Physician  │            │
     │ Responds   │◄───────────┘ (if no response,
     └─────┬──────┘               CDI follows up)
           │
           ▼
     ┌────────────────┐
     │  Response       │
     │  Handler        │
     └───────┬────────┘
              │
              ├─── YES ──► Coding Agent re-runs
              │            with updated documentation
              │
              ├─── NO ───► Log false positive,
              │            no coding change
              │
              └─── UNDETERMINED ─► Schedule follow-up
```

---

## 5. Compliance Requirements

### 5.1 AHIMA Standards for CDI Compliance

Every query template was designed against these AHIMA principles:

| AHIMA Principle | How Our Templates Comply |
|----------------|-------------------------|
| **Non-leading queries** | All queries ask "Does the patient have [condition]?" — never "The patient has [condition], please confirm." Response options always include "No" and "Clinically undetermined." |
| **Clinically supported** | Every query cites specific objective clinical data (lab values, vital signs, imaging findings) from the patient's record. No query is generated without corroborating clinical evidence. |
| **Open-ended options** | All queries offer free-text "Other" option. Yes/No options include space for physician to clarify. |
| **Educational value** | Each query includes a "Clinical Note" section explaining why the clarification matters for patient care — never for revenue. |
| **Physician autonomy** | The physician's response is final. The system never overrides a physician's clinical determination. If the physician says "No," the condition is not coded. |
| **Audit trail** | Every query, response, and resulting coding action is logged (without PHI) for compliance audit. |

### 5.2 ACDIS Code of Ethics Compliance

| ACDIS Ethical Principle | Our Implementation |
|------------------------|-------------------|
| CDI professionals shall not engage in upcoding | The system never suggests a specific code to the physician. It identifies documentation gaps and asks clinical questions. Coding happens only after physician documentation, through the separate coding agent validated by the rules engine. |
| CDI queries shall be non-leading | Templates verified against ACDIS non-leading query checklist. "Does the patient have X?" not "The patient appears to have X, agree?" |
| CDI programs shall not be incentivized by revenue alone | Query prioritization uses clinical validity (confidence score based on clinical criteria like KDIGO, SIRS) as the primary sort, not revenue impact. Revenue impact is used only for tiebreaking among clinically equivalent opportunities. |
| Respect physician clinical judgment | "Clinically undetermined" is always a valid response. The system does not re-query the same question if the physician answered it. Escalation is for non-response only, not for "wrong" answers. |

### 5.3 OIG Compliance Guidance

| OIG Concern | Our Safeguard |
|-------------|--------------|
| CDI programs that systematically drive upcoding | All queries are generated from objective clinical evidence. Queries with revenue impact > $5,000 are routed to compliance review per constitution Article II.6. Query generation rates, acceptance rates, and DRG impact are monitored for statistical anomalies. |
| Physicians pressured to change documentation | Physicians can respond "No" or "Clinically undetermined." Maximum 3 contacts per query (1 initial + 2 reminders). No penalty for non-response beyond scorecard tracking. |
| CDI queries that lead to unsupported diagnoses | Every accepted CDI response feeds into the coding agent, which validates against the rules engine (DESIGN-001). Even if a physician documents a condition, the rules engine validates that the code is clinically supported by evidence in the note. |
| Pattern analysis showing systematic DRG manipulation | Monthly compliance reports track: query volume by category, acceptance rate by physician, DRG shift patterns, and comparison to national benchmarks. Outlier physicians (> 95% acceptance rate) are flagged for compliance review. |

### 5.4 Query Template Compliance Verification

Every query template in this spec was verified against this checklist:

```
COMPLIANCE VERIFICATION CHECKLIST

Template ID: [QUERY-XXX-NNN]

[ ] Query presents objective clinical data from the patient record
[ ] Query does NOT suggest a specific diagnosis
[ ] Query does NOT mention DRG, CC/MCC, revenue, or reimbursement
[ ] Query offers "No" as a valid response option
[ ] Query offers "Clinically undetermined" as a valid response option
[ ] Query includes free-text "Other" option
[ ] Query educational component focuses on patient care, not billing
[ ] Query does not use the phrases: "would you agree," "as you know,"
    "clearly shows," "obviously," "confirms"
[ ] Query response deadline is 24 hours (not shorter to pressure response)
[ ] Query addressed to attending physician only (not residents)

Verified by: [CDI compliance review]
Date: [verification date]
```

---

## 6. Metrics and Performance Targets

### 6.1 Operational Metrics

| Metric | Target | Measurement Method | Rationale |
|--------|--------|-------------------|-----------|
| **CDI query response rate** | > 80% | Responses received / queries sent within 72h | Industry benchmark: 69% of facilities report 91-100% response rates (ACDIS survey). Our target of 80% is conservative for initial deployment. |
| **First-pass query acceptance rate** | > 70% | "Yes" responses / total responses | High acceptance indicates accurate detection. > 85% may indicate leading queries (compliance concern). |
| **False positive CDI rate** | < 15% | "No" responses / total responses | CDI opportunities where physician confirmed condition is NOT present. Calibrate detection thresholds to minimize. |
| **Revenue impact per resolved query** | Track and report | Sum of DRG deltas for accepted queries / number of accepted queries | Key metric for CFO reporting. Do NOT use as a target that drives query generation (compliance risk). |
| **Time from note signed to CDI query generated** | < 2 hours | Timestamp(query_generated) - Timestamp(note_signed) | Proactive CDI value depends on speed. Concurrent CDI (during stay) is more effective than retrospective CDI (after discharge). |
| **CDI query turnaround time** | < 24 hours median | Timestamp(response) - Timestamp(query_sent) | Faster responses mean coding can proceed without bill-hold delays. |
| **Coding delay due to pending CDI** | < 4 hours additional | Coding completion time with CDI vs without | CDI should accelerate, not delay, the coding process. |

### 6.2 Quality Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Detection sensitivity** | > 85% for P0 categories | Validated against MIMIC-IV annotated cases where conditions are present in clinical data but not in discharge codes |
| **Detection specificity** | > 85% for all categories | 1 - (false positive rate). Validated against cases where conditions are correctly absent from documentation. |
| **Query compliance score** | 100% | Monthly audit of random query sample against compliance checklist (Section 5.4). Zero tolerance for non-compliant queries. |
| **Physician satisfaction score** | > 3.5 / 5.0 | Quarterly physician survey on query relevance and usefulness. |
| **CC/MCC capture rate improvement** | > 5% improvement from baseline | Pre/post comparison of CC/MCC capture rate per case. National benchmark: well-performing CDI programs achieve 5-15% improvement. |

### 6.3 System Performance

| Metric | Target | Notes |
|--------|--------|-------|
| CDI analysis latency (full pipeline) | < 30 seconds | NLP extraction + FHIR data retrieval + detection algorithm + query generation |
| NLP entity extraction | < 10 seconds per note | Pre-CDI step; shared with coding agent |
| FHIR data retrieval (labs + vitals + meds) | < 5 seconds | Parallel queries via FHIR client |
| Detection algorithm (all categories) | < 5 seconds | All detection functions run in parallel |
| Query template rendering | < 1 second | Template population with patient-specific data |
| Concurrent CDI analyses supported | 100 | Matches coder concurrency target from DESIGN-001 |

### 6.4 Compliance Monitoring Dashboard

```
MONTHLY COMPLIANCE REPORT

Section 1: Query Volume
  - Total queries generated: [N]
  - By category: Severity [N], Specificity [N], Causality [N], POA [N]
  - By priority: P0 [N], P1 [N], P2 [N]
  - Trend vs prior month: [+/-N%]

Section 2: Response Rates
  - Overall response rate: [N%] (target > 80%)
  - Yes rate: [N%] (flag if > 85% — possible leading queries)
  - No rate: [N%] (this is the false positive rate)
  - Clinically undetermined rate: [N%]
  - Non-response rate: [N%]

Section 3: Revenue Impact
  - Total DRG impact from accepted CDI queries: [$N]
  - Average revenue impact per accepted query: [$N]
  - Queries routed to compliance review (> $5K): [N]
  - Compliance review outcomes: [approved N, modified N, rejected N]

Section 4: Physician Patterns
  - Physicians with > 95% acceptance rate: [flag for review]
  - Physicians with < 30% response rate: [flag for outreach]
  - Query volume per physician: [distribution]

Section 5: Detection Quality
  - False positive rate by category: [N% per category]
  - Categories exceeding 15% FP threshold: [list]
  - Detection threshold adjustments needed: [recommendations]
```

---

## 7. Integration with Coding Agent and Rules Engine

### 7.1 Data Flow

```
CDI Agent (this spec)
    │
    │  CDI opportunity detected
    │  Physician query generated
    │  Physician responds "Yes"
    │
    ▼
Physician updates documentation
    │
    │  Updated note signed
    │
    ▼
NLP Pipeline re-processes note
    │
    │  New entities extracted
    │
    ▼
Coding Agent generates updated suggestions
    │
    │  Includes new condition from CDI resolution
    │
    ▼
Rules Engine (DESIGN-001) validates suggestions
    │
    │  Checks sequencing, Excludes, combinations, POA
    │
    ▼
Coder Review Interface
    │
    │  Coder sees: original suggestions + CDI-added suggestions
    │  CDI-added suggestions are flagged with source
    │  DRG impact shows before/after CDI
    │
    ▼
Human coder approves/modifies/rejects
```

### 7.2 Constitution Compliance

| Constitution Article | How CDI Layer Complies |
|---------------------|----------------------|
| II.1 — No autonomous claims | CDI queries feed into coding suggestions that require human coder approval. CDI never auto-codes. |
| II.2 — Source citation | Every CDI opportunity includes specific clinical indicators and lab evidence from the patient record. |
| II.3 — ICD-10 hard constraints | CDI-resolved codes pass through the rules engine before reaching the coder. The rules engine is the final compliance gate. |
| II.4 — HIPAA | CDI queries contain clinical indicators but no PHI in logs. Encounter IDs only in audit trail. Query content (which contains clinical data) is transmitted only within the EHR system under existing BAA. |
| II.5 — Graceful degradation | If CDI detection fails, coding proceeds without CDI suggestions. CDI enhances but never blocks the coding workflow. |
| II.6 — Conservative defaults | When uncertain between querying and coding, CDI always queries. DRG improvements > $5,000 routed to compliance review. |

---

*This specification is the authoritative reference for the CDI
Intelligence Layer. No implementation code may deviate from
these detection algorithms, query templates, or compliance
requirements without an ADR explaining why.*
