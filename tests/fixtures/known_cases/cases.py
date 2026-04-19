"""
20 Hand-Labeled Specificity Upgrade Test Cases

Each case extracted from DISC-002 §B.1: Top 20 Diagnoses With
Specificity Failures. Notes are synthetic (no PHI) but clinically
realistic — they contain the documentation patterns that a physician
would write, including the evidence clues that support the specific code.

For each case:
  - note_text: synthetic discharge summary with specificity clues
  - nonspecific_code: what a naive/incomplete coding would produce
  - specific_code: what the coding agent should suggest (or CDI query toward)
  - expect_cdi_query: whether a CDI query should be generated
  - cdi_query_keyword: keyword expected in the CDI query text
  - drg_revenue_range: (low, high) expected revenue impact

Constitution: Article II.4 — synthetic notes only, no PHI.
Source: docs/research/DISC-002-documentation-failure-patterns.md §B.1
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnownCase:
    """A single hand-labeled specificity upgrade test case."""

    case_id: str
    title: str
    note_text: str
    nonspecific_code: str
    specific_code: str
    expect_cdi_query: bool
    cdi_query_keyword: str
    drg_revenue_low: int
    drg_revenue_high: int


# ─── Case 1: Heart Failure ────────────────────────────────────────────────────

CASE_01_HEART_FAILURE = KnownCase(
    case_id="DISC002-01",
    title="Heart Failure — type and acuity upgrade",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Decompensated heart failure

HISTORY OF PRESENT ILLNESS:
72-year-old female with known chronic systolic heart failure (last echo
showed EF 25%) presents with 3-day history of worsening dyspnea on
exertion, orthopnea, and bilateral lower extremity edema. She reports
increasing her pillow use from 2 to 4. Patient was adherent to home
medications including carvedilol, lisinopril, and furosemide.

PHYSICAL EXAM:
JVD to 12 cm. Bilateral crackles at lung bases. 3+ bilateral pedal
edema. S3 gallop present.

LABS:
BNP: 2,450 pg/mL (markedly elevated)
Creatinine: 1.4 (baseline 1.1)
Sodium: 131

HOSPITAL COURSE:
Patient was treated with IV furosemide for decompensated heart failure.
This represents an acute exacerbation of her chronic systolic heart
failure. Echo confirmed EF of 22%, consistent with systolic dysfunction.
She diuresed 4 liters and symptoms improved significantly.

DISCHARGE CONDITION: Stable, improved.
DISCHARGE MEDICATIONS: Carvedilol 25mg BID, lisinopril 10mg daily,
furosemide 80mg daily (increased from 40mg).
""".strip(),
    nonspecific_code="I50.9",
    specific_code="I50.23",
    expect_cdi_query=False,  # Note already says "acute exacerbation of chronic systolic"
    cdi_query_keyword="systolic",
    drg_revenue_low=3900,
    drg_revenue_high=7500,
)


# ─── Case 2: Sepsis ──────────────────────────────────────────────────────────

CASE_02_SEPSIS = KnownCase(
    case_id="DISC002-02",
    title="Sepsis — organism and severity upgrade",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Sepsis

HISTORY OF PRESENT ILLNESS:
68-year-old male presents with fever 102.4F, rigors, and dysuria for
2 days. Foley catheter in place for urinary retention. Vitals: HR 118,
BP 84/52 (MAP 63), RR 24, SpO2 94% on room air. Lactate 4.2 mmol/L.

LABS:
WBC: 22,400 with 15% bands
Blood cultures: 2 of 2 bottles positive for Escherichia coli
Urine culture: >100,000 CFU E. coli
Creatinine: 3.1 (baseline 1.0) — consistent with acute kidney injury
Lactate: 4.2 mmol/L (repeat 2.8)

HOSPITAL COURSE:
Patient met criteria for sepsis with organ dysfunction — septic shock
requiring vasopressor support for 36 hours. Source identified as E. coli
urinary tract infection. Treated with IV piperacillin-tazobactam per
sensitivity. AKI developed with creatinine peaking at 3.4, now trending
down to 1.8 at discharge. Required ICU admission for hemodynamic monitoring.

DISCHARGE CONDITION: Stable, improving. Completing 14-day antibiotic course.
""".strip(),
    nonspecific_code="A41.9",
    specific_code="A41.51",  # Sepsis due to E. coli
    expect_cdi_query=False,  # Note already documents organism and severity
    cdi_query_keyword="organism",
    drg_revenue_low=6000,
    drg_revenue_high=42759,
)


# ─── Case 3: Acute Kidney Injury ─────────────────────────────────────────────

CASE_03_AKI = KnownCase(
    case_id="DISC002-03",
    title="AKI — missed diagnosis from creatinine elevation",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Congestive heart failure exacerbation

HISTORY OF PRESENT ILLNESS:
74-year-old male admitted for heart failure exacerbation with volume
overload. Known EF 30%.

LABS ON ADMISSION:
Creatinine: 2.8 mg/dL (baseline from 3 months ago: 1.0 mg/dL)
BUN: 48
Potassium: 5.2
BNP: 3,200

HOSPITAL COURSE:
Aggressive IV diuresis with furosemide drip. Patient's creatinine rose
from baseline of 1.0 to peak of 2.8 on admission, representing a rise
of 1.8 mg/dL. We held ACE inhibitor due to renal function decline.
Creatinine trended down to 1.6 by discharge. Renal function expected
to continue improving.

Volume status improved with 6L net negative. Transitioned to oral
furosemide. Weight on discharge 4kg below admission weight.

DISCHARGE CONDITION: Stable, improved.
""".strip(),
    nonspecific_code="I50.9",  # Only HF coded, AKI missed
    specific_code="N17.9",    # AKI — creatinine 1.0→2.8 meets KDIGO
    expect_cdi_query=True,    # Note never says "acute kidney injury"
    cdi_query_keyword="acute kidney injury",
    drg_revenue_low=3000,
    drg_revenue_high=8000,
)


# ─── Case 4: Respiratory Failure ─────────────────────────────────────────────

CASE_04_RESPIRATORY_FAILURE = KnownCase(
    case_id="DISC002-04",
    title="Respiratory Failure — missed from hypoxia and O2 requirement",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Community-acquired pneumonia

HISTORY OF PRESENT ILLNESS:
81-year-old female presents with 4-day history of productive cough,
fever, and progressive shortness of breath.

VITALS ON ADMISSION:
Temp 101.8F, HR 110, BP 108/62, RR 28, SpO2 82% on room air.
Required 6L nasal cannula to maintain SpO2 > 92%. Escalated to
high-flow nasal cannula at 40L/min, FiO2 60%.

ABG on admission: pH 7.44, PaCO2 32, PaO2 54 on room air.

LABS:
WBC 18,200, Procalcitonin 3.8
Chest X-ray: Right lower lobe consolidation

HOSPITAL COURSE:
Patient required supplemental oxygen via high-flow nasal cannula
for respiratory distress with documented hypoxia. PaO2 of 54 mmHg
on room air. Treated with IV ceftriaxone and azithromycin. Gradually
weaned oxygen support over 5 days. Able to maintain SpO2 93% on
2L nasal cannula at discharge.

DISCHARGE CONDITION: Improved, continuing oral antibiotics.
""".strip(),
    nonspecific_code="R06.00",  # Dyspnea coded, resp failure missed
    specific_code="J96.01",    # Acute respiratory failure with hypoxia
    expect_cdi_query=True,     # Note says "respiratory distress" but not "respiratory failure"
    cdi_query_keyword="respiratory failure",
    drg_revenue_low=4000,
    drg_revenue_high=10000,
)


# ─── Case 5: Malnutrition ────────────────────────────────────────────────────

CASE_05_MALNUTRITION = KnownCase(
    case_id="DISC002-05",
    title="Malnutrition — missed despite low BMI and albumin",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Hip fracture, right

HISTORY OF PRESENT ILLNESS:
78-year-old female presents after fall at home with right hip pain.
X-ray confirms right intertrochanteric hip fracture.

VITALS AND MEASUREMENTS:
Height: 5'4" Weight: 98 lbs (BMI 16.8)
Patient appears cachectic with temporal wasting.

LABS:
Albumin: 2.0 g/dL (low)
Prealbumin: 8 mg/dL (low)
Total protein: 4.8 g/dL (low)

HOSPITAL COURSE:
Right hip hemiarthroplasty performed. Post-operatively, patient had
poor appetite and was eating less than 25% of meals. Dietitian
consulted — recommended oral supplements and caloric fortification.
Patient lost additional 3 lbs during hospitalization.

Wound healing noted to be slow. Physical therapy initiated.

DISCHARGE CONDITION: Stable, transferred to skilled nursing facility.
""".strip(),
    nonspecific_code="R63.4",  # Weight loss coded, malnutrition missed
    specific_code="E43",       # Severe protein-calorie malnutrition
    expect_cdi_query=True,     # Note has evidence but no malnutrition diagnosis
    cdi_query_keyword="malnutrition",
    drg_revenue_low=3000,
    drg_revenue_high=9000,
)


# ─── Case 6: Pneumonia Organism ───────────────────────────────────────────────

CASE_06_PNEUMONIA_ORGANISM = KnownCase(
    case_id="DISC002-06",
    title="Pneumonia — organism specificity from culture results",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Pneumonia

HISTORY OF PRESENT ILLNESS:
66-year-old male with COPD presents with productive cough with
purulent sputum, fever 101.2F, and dyspnea for 3 days.

LABS AND IMAGING:
WBC: 16,800
Sputum culture: Heavy growth Pseudomonas aeruginosa
Blood cultures: No growth
Chest CT: Left lower lobe consolidation with air bronchograms

HOSPITAL COURSE:
Patient admitted for pneumonia. Sputum culture grew Pseudomonas
aeruginosa. Treated with IV cefepime and ciprofloxacin per
sensitivity results. Clinical improvement noted by day 3.
Transitioned to oral ciprofloxacin for discharge.

DISCHARGE CONDITION: Improved. Follow-up chest X-ray in 6 weeks.
""".strip(),
    nonspecific_code="J18.9",  # Pneumonia, unspecified organism
    specific_code="J15.1",     # Pneumonia due to Pseudomonas
    expect_cdi_query=False,    # Note documents organism
    cdi_query_keyword="organism",
    drg_revenue_low=2000,
    drg_revenue_high=6000,
)


# ─── Case 7: Diabetes with Complications ─────────────────────────────────────

CASE_07_DIABETES_COMPLICATIONS = KnownCase(
    case_id="DISC002-07",
    title="Diabetes — complications linkage upgrade",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Type 2 diabetes mellitus

HISTORY OF PRESENT ILLNESS:
62-year-old male with type 2 diabetes mellitus presents for
medication adjustment. HbA1c 9.2%.

PAST MEDICAL HISTORY:
- Type 2 diabetes mellitus, on insulin
- Chronic kidney disease stage 3 (GFR 42)
- Diabetic retinopathy — last eye exam 6 months ago
- Peripheral neuropathy with numbness in feet bilaterally

LABS:
HbA1c: 9.2%
Creatinine: 1.8, GFR 42
Urine albumin/creatinine ratio: 380 mg/g (elevated)

ASSESSMENT AND PLAN:
1. Type 2 DM — poorly controlled. Adjusting insulin regimen.
2. CKD stage 3 — likely related to longstanding diabetes. Continue
   monitoring renal function.
3. Continue annual ophthalmology follow-up for retinopathy.
4. Gabapentin for peripheral neuropathy symptoms.

DISCHARGE CONDITION: Stable.
""".strip(),
    nonspecific_code="E11.9",   # T2DM without complications
    specific_code="E11.22",     # T2DM with diabetic chronic kidney disease
    expect_cdi_query=False,     # Note says "CKD ... likely related to longstanding diabetes"
    cdi_query_keyword="diabetic",
    drg_revenue_low=1500,
    drg_revenue_high=4000,
)


# ─── Case 8: COPD with Exacerbation ──────────────────────────────────────────

CASE_08_COPD_EXACERBATION = KnownCase(
    case_id="DISC002-08",
    title="COPD — exacerbation upgrade",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: COPD

HISTORY OF PRESENT ILLNESS:
70-year-old male with history of COPD presents with 3-day history
of increased shortness of breath, increased sputum production
(now purulent), and worsening wheezing. Baseline home O2 at 2L,
currently requiring 4L to maintain SpO2 > 90%.

HOSPITAL COURSE:
Patient treated with systemic corticosteroids (prednisone 40mg daily),
scheduled nebulizer treatments with albuterol and ipratropium every
4 hours, and azithromycin for acute exacerbation of COPD. Symptoms
improved significantly. Oxygen requirement decreased to baseline 2L.

DISCHARGE CONDITION: Improved, stable.
""".strip(),
    nonspecific_code="J44.9",  # COPD unspecified
    specific_code="J44.1",     # COPD with acute exacerbation
    expect_cdi_query=False,    # Note says "acute exacerbation of COPD"
    cdi_query_keyword="exacerbation",
    drg_revenue_low=2000,
    drg_revenue_high=5000,
)


# ─── Case 9: Encephalopathy ──────────────────────────────────────────────────

CASE_09_ENCEPHALOPATHY = KnownCase(
    case_id="DISC002-09",
    title="Encephalopathy — missed metabolic encephalopathy",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Altered mental status

HISTORY OF PRESENT ILLNESS:
73-year-old male with history of liver cirrhosis presents with
progressive confusion over 48 hours. Family reports increasing
somnolence and disorientation. No recent medication changes.

LABS:
Ammonia: 142 mcmol/L (markedly elevated, normal <35)
Sodium: 128 (hyponatremia)
INR: 2.1
Albumin: 2.4
CT Head: No acute intracranial pathology

HOSPITAL COURSE:
Patient found to have significantly elevated ammonia level of 142.
Started on lactulose and rifaximin for hepatic encephalopathy
management. Mental status gradually cleared over 72 hours.
Ammonia trended down to 48 at discharge.

DISCHARGE CONDITION: Returned to baseline mental status.
""".strip(),
    nonspecific_code="R41.82",  # Altered mental status
    specific_code="G93.41",    # Metabolic encephalopathy
    expect_cdi_query=True,     # Note says "altered mental status" as Dx, not encephalopathy
    cdi_query_keyword="encephalopathy",
    drg_revenue_low=4000,
    drg_revenue_high=10000,
)


# ─── Case 10: Pressure Ulcer ─────────────────────────────────────────────────

CASE_10_PRESSURE_ULCER = KnownCase(
    case_id="DISC002-10",
    title="Pressure Ulcer — stage specificity from wound care notes",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Pressure ulcer

HISTORY OF PRESENT ILLNESS:
82-year-old bedbound male admitted from nursing facility with
worsening sacral wound.

WOUND CARE ASSESSMENT:
Sacral pressure ulcer, 6cm x 4cm x 2cm deep, with exposed
subcutaneous tissue. Full-thickness skin loss. No exposed bone,
tendon, or muscle visible. Wound base with granulation tissue
and 20% slough. This is consistent with a stage 3 pressure injury.

HOSPITAL COURSE:
Wound care team managing with negative pressure wound therapy.
Nutrition optimized with dietitian consultation. Pressure redistribution
mattress in place. Wound showing early granulation after 7 days.

DISCHARGE CONDITION: Stable, wound improving. Continued wound care
at skilled nursing facility.
""".strip(),
    nonspecific_code="L89.90",   # Pressure ulcer, unspecified
    specific_code="L89.153",     # Pressure ulcer sacral, stage 3
    expect_cdi_query=False,      # Note documents stage and location
    cdi_query_keyword="stage",
    drg_revenue_low=3000,
    drg_revenue_high=8000,
)


# ─── Case 11: Anemia ─────────────────────────────────────────────────────────

CASE_11_ANEMIA = KnownCase(
    case_id="DISC002-11",
    title="Anemia — acute blood loss anemia from GI bleed",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Upper GI bleeding

HISTORY OF PRESENT ILLNESS:
59-year-old male presents with melena and hematemesis for 1 day.

LABS:
Hemoglobin on admission: 6.8 g/dL (known baseline 13.2 from 2 weeks ago)
Hemoglobin dropped to nadir of 5.9 g/dL
Transfused 4 units packed red blood cells

HOSPITAL COURSE:
EGD revealed bleeding duodenal ulcer which was clipped. Patient
required 4 units pRBC transfusion for anemia secondary to acute
gastrointestinal hemorrhage. Hemoglobin stabilized at 9.2 after
transfusion. Started on PPI therapy.

DISCHARGE CONDITION: Stable. Hemoglobin 9.2 at discharge.
""".strip(),
    nonspecific_code="D64.9",  # Anemia, unspecified
    specific_code="D62",       # Acute posthemorrhagic anemia
    expect_cdi_query=False,    # Note documents acute blood loss and GI source
    cdi_query_keyword="blood loss",
    drg_revenue_low=1500,
    drg_revenue_high=3000,
)


# ─── Case 12: Obesity ────────────────────────────────────────────────────────

CASE_12_OBESITY = KnownCase(
    case_id="DISC002-12",
    title="Obesity — morbid obesity from BMI",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Elective total knee arthroplasty

HISTORY OF PRESENT ILLNESS:
55-year-old male admitted for right total knee arthroplasty for
severe osteoarthritis.

VITALS:
Height: 5'10" Weight: 295 lbs. BMI: 42.3
Noted to be obese.

PAST MEDICAL HISTORY:
- Osteoarthritis bilateral knees
- Obese
- Obstructive sleep apnea on CPAP
- Type 2 DM

HOSPITAL COURSE:
Uncomplicated right TKA performed. Patient's elevated BMI of 42.3
presents increased surgical risk. Required bariatric bed and equipment.
Physical therapy initiated POD 1. Discharged to home with home PT.

DISCHARGE CONDITION: Stable.
""".strip(),
    nonspecific_code="E66.9",   # Obesity, unspecified
    specific_code="E66.01",     # Morbid obesity
    expect_cdi_query=True,      # Note says "obese" but not "morbid obesity"
    cdi_query_keyword="morbid",
    drg_revenue_low=1000,
    drg_revenue_high=3000,
)


# ─── Case 13: Atrial Fibrillation ────────────────────────────────────────────

CASE_13_AFIB = KnownCase(
    case_id="DISC002-13",
    title="Atrial Fibrillation — type specification",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Atrial fibrillation with rapid ventricular response

HISTORY OF PRESENT ILLNESS:
71-year-old female presents with palpitations and heart rate 142.
History of atrial fibrillation diagnosed 3 years ago. She reports
multiple prior episodes requiring cardioversion. Despite antiarrhythmic
therapy, she has been in afib for most of the past 2 years per
Holter monitoring and cardiology records. Currently on warfarin and
amiodarone.

HOSPITAL COURSE:
Rate controlled with IV diltiazem, then transitioned to oral metoprolol.
Her atrial fibrillation has been persistent — she has been in continuous
afib for over a year per cardiology notes. Anticoagulation continued.

DISCHARGE CONDITION: Rate controlled, stable.
""".strip(),
    nonspecific_code="I48.91",  # Unspecified atrial fibrillation
    specific_code="I48.1",      # Persistent atrial fibrillation
    expect_cdi_query=False,     # Note documents persistent pattern
    cdi_query_keyword="persistent",
    drg_revenue_low=1500,
    drg_revenue_high=3000,
)


# ─── Case 14: UTI Organism ───────────────────────────────────────────────────

CASE_14_UTI_ORGANISM = KnownCase(
    case_id="DISC002-14",
    title="UTI — organism specificity (quality, not DRG impact)",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Urinary tract infection

HISTORY OF PRESENT ILLNESS:
82-year-old female presents with dysuria, frequency, and low-grade
fever of 100.1F.

LABS:
Urinalysis: positive leukocyte esterase, positive nitrites, >100 WBC
Urine culture: >100,000 CFU Escherichia coli, sensitive to
ciprofloxacin and TMP-SMX

HOSPITAL COURSE:
UTI treated with IV ceftriaxone, transitioned to oral TMP-SMX based
on culture sensitivities. Symptoms resolved within 48 hours.

DISCHARGE CONDITION: Improved.
""".strip(),
    nonspecific_code="N39.0",   # UTI site not specified
    specific_code="N39.0",      # Same — organism code B96.20 is additional
    expect_cdi_query=False,     # Organism documented, just needs additional code
    cdi_query_keyword="organism",
    drg_revenue_low=0,
    drg_revenue_high=0,  # Quality impact only
)


# ─── Case 15: AMI Type ───────────────────────────────────────────────────────

CASE_15_AMI = KnownCase(
    case_id="DISC002-15",
    title="AMI — STEMI territory specificity (quality impact)",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Acute myocardial infarction

HISTORY OF PRESENT ILLNESS:
58-year-old male presents with crushing substernal chest pain x2 hours.

DIAGNOSTICS:
ECG: ST elevation in V1-V4, reciprocal changes in inferior leads,
consistent with anterior STEMI.
Troponin I: 28.4 ng/mL (markedly elevated)

HOSPITAL COURSE:
Emergent cardiac catheterization revealed 100% occlusion of proximal
LAD (left anterior descending). Drug-eluting stent placed with TIMI 3
flow restored. Patient started on dual antiplatelet therapy.

Peak troponin 52.1. Echo showed EF 40% with anterior wall hypokinesis.

DISCHARGE CONDITION: Stable, EF 40%.
""".strip(),
    nonspecific_code="I21.9",   # AMI unspecified
    specific_code="I21.01",     # STEMI involving LAD
    expect_cdi_query=False,     # Note documents STEMI and LAD
    cdi_query_keyword="STEMI",
    drg_revenue_low=0,
    drg_revenue_high=0,  # Quality metric impact only
)


# ─── Case 16: Acute Pancreatitis ─────────────────────────────────────────────

CASE_16_PANCREATITIS = KnownCase(
    case_id="DISC002-16",
    title="Pancreatitis — etiology specificity",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Acute pancreatitis

HISTORY OF PRESENT ILLNESS:
45-year-old male presents with severe epigastric pain radiating to back.
Reports heavy alcohol use (12-15 beers daily for 20 years).

LABS:
Lipase: 4,200 U/L (markedly elevated)
Amylase: 890
AST: 42, ALT: 38 (normal — argues against biliary etiology)
Triglycerides: 180 (normal)

CT Abdomen: Edematous pancreas with peripancreatic fat stranding and
small peripancreatic fluid collection. No evidence of necrosis.

HOSPITAL COURSE:
Managed with aggressive IV fluids, NPO, pain management. Etiology
determined to be alcohol-related given significant alcohol use history
and normal biliary labs. Lipase trended down. Diet advanced day 3.
Patient counseled on alcohol cessation.

DISCHARGE CONDITION: Improved, tolerating regular diet.
""".strip(),
    nonspecific_code="K85.9",   # Acute pancreatitis, unspecified
    specific_code="K85.20",     # Alcohol-induced acute pancreatitis without necrosis
    expect_cdi_query=False,     # Note documents alcoholic etiology
    cdi_query_keyword="alcohol",
    drg_revenue_low=0,
    drg_revenue_high=0,
)


# ─── Case 17: DVT ────────────────────────────────────────────────────────────

CASE_17_DVT = KnownCase(
    case_id="DISC002-17",
    title="DVT — location and laterality upgrade",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Deep vein thrombosis

HISTORY OF PRESENT ILLNESS:
63-year-old female presents with left leg swelling and pain x3 days.
Risk factors: recent 10-hour flight, oral contraceptive use.

DIAGNOSTICS:
Venous duplex ultrasound: Acute deep vein thrombosis of the left
femoral vein extending to the left popliteal vein. No thrombus in
the right lower extremity.

HOSPITAL COURSE:
Started on heparin drip, transitioned to apixaban. Compression
stockings applied. Left lower extremity elevated.

DISCHARGE CONDITION: Stable, on apixaban 5mg BID for 3 months.
""".strip(),
    nonspecific_code="I82.40",   # DVT unspecified lower extremity
    specific_code="I82.412",     # Acute DVT of left femoral vein
    expect_cdi_query=False,      # Note documents laterality and location
    cdi_query_keyword="laterality",
    drg_revenue_low=1500,
    drg_revenue_high=3000,
)


# ─── Case 18: Stroke ─────────────────────────────────────────────────────────

CASE_18_STROKE = KnownCase(
    case_id="DISC002-18",
    title="Stroke — vessel territory specificity (quality impact)",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Acute ischemic stroke

HISTORY OF PRESENT ILLNESS:
76-year-old male presents with sudden onset left-sided weakness and
facial droop. Last seen normal 2 hours ago.

DIAGNOSTICS:
CT Head: No hemorrhage
CT Angiography: Occlusion of right middle cerebral artery (MCA)
MRI Brain: Acute infarct in right MCA distribution

HOSPITAL COURSE:
tPA administered within the 4.5-hour window. Transferred to
neuro-ICU for monitoring. Left hemiplegia persistent. Speech intact.
NIH Stroke Scale: 14 on admission, 8 at discharge.

DISCHARGE CONDITION: Transferred to inpatient rehab for left hemiplegia.
""".strip(),
    nonspecific_code="I63.9",    # Cerebral infarction unspecified
    specific_code="I63.511",     # Cerebral infarction due to unspecified occlusion of right MCA
    expect_cdi_query=False,      # Note documents MCA territory
    cdi_query_keyword="MCA",
    drg_revenue_low=0,
    drg_revenue_high=0,  # Quality impact only
)


# ─── Case 19: Alcohol Withdrawal ─────────────────────────────────────────────

CASE_19_ALCOHOL_WITHDRAWAL = KnownCase(
    case_id="DISC002-19",
    title="Alcohol withdrawal — dependence with withdrawal delirium",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Alcohol use

HISTORY OF PRESENT ILLNESS:
52-year-old male presents 48 hours after last drink with tremors,
agitation, visual hallucinations (seeing bugs on the walls), and
tachycardia to 130. CIWA score 28 on admission.

PAST MEDICAL HISTORY: Chronic alcohol use (1 pint vodka daily x 15 years),
2 prior ICU admissions for withdrawal seizures.

HOSPITAL COURSE:
Patient placed on CIWA protocol. Required IV lorazepam 2mg every
2 hours for the first 24 hours. Developed withdrawal delirium on
hospital day 2 with worsening hallucinations, disorientation, and
combativeness. Transferred to ICU. Managed with IV diazepam drip.
Delirium resolved by day 4. Transitioned to symptom-triggered
benzodiazepine protocol. Social work consulted for alcohol rehabilitation.

DISCHARGE CONDITION: Stable, transferred to inpatient rehab program.
""".strip(),
    nonspecific_code="F10.10",   # Alcohol abuse, uncomplicated
    specific_code="F10.231",     # Alcohol dependence with withdrawal delirium
    expect_cdi_query=False,      # Note documents withdrawal delirium
    cdi_query_keyword="dependence",
    drg_revenue_low=3000,
    drg_revenue_high=7000,
)


# ─── Case 20: Hypertensive Heart Disease ─────────────────────────────────────

CASE_20_HYPERTENSIVE_HD = KnownCase(
    case_id="DISC002-20",
    title="Hypertension — causal linkage to heart failure (DRG shift)",
    note_text="""
DISCHARGE SUMMARY

PRINCIPAL DIAGNOSIS: Hypertension

HISTORY OF PRESENT ILLNESS:
69-year-old female with longstanding hypertension presents with
dyspnea on exertion and bilateral lower extremity edema. Blood
pressure 182/96 on admission.

PAST MEDICAL HISTORY:
- Hypertension x 20 years, poorly controlled
- Heart failure (EF 45%, diagnosed 2 years ago)
- Type 2 diabetes mellitus
- Hyperlipidemia

ECHO (this admission):
Concentric left ventricular hypertrophy with EF 42%. Grade 2
diastolic dysfunction. Moderate mitral regurgitation.

HOSPITAL COURSE:
Blood pressure managed with IV labetalol, then transitioned to
oral amlodipine and lisinopril. Heart failure management with
IV furosemide for volume overload. Patient's long history of
hypertension with progressive cardiac remodeling (LVH on echo)
and heart failure is consistent with hypertensive heart disease.

DISCHARGE CONDITION: Stable, BP controlled at 138/82.
""".strip(),
    nonspecific_code="I10",      # Essential hypertension only
    specific_code="I11.0",       # Hypertensive heart disease with HF
    expect_cdi_query=False,      # Note documents HTN + HF causal link
    cdi_query_keyword="hypertensive heart disease",
    drg_revenue_low=3000,
    drg_revenue_high=9000,
)


# ─── All cases list ──────────────────────────────────────────────────────────

ALL_CASES: list[KnownCase] = [
    CASE_01_HEART_FAILURE,
    CASE_02_SEPSIS,
    CASE_03_AKI,
    CASE_04_RESPIRATORY_FAILURE,
    CASE_05_MALNUTRITION,
    CASE_06_PNEUMONIA_ORGANISM,
    CASE_07_DIABETES_COMPLICATIONS,
    CASE_08_COPD_EXACERBATION,
    CASE_09_ENCEPHALOPATHY,
    CASE_10_PRESSURE_ULCER,
    CASE_11_ANEMIA,
    CASE_12_OBESITY,
    CASE_13_AFIB,
    CASE_14_UTI_ORGANISM,
    CASE_15_AMI,
    CASE_16_PANCREATITIS,
    CASE_17_DVT,
    CASE_18_STROKE,
    CASE_19_ALCOHOL_WITHDRAWAL,
    CASE_20_HYPERTENSIVE_HD,
]

# Revenue-impact cases (excluding quality-only cases)
REVENUE_IMPACT_CASES: list[KnownCase] = [
    c for c in ALL_CASES if c.drg_revenue_high > 0
]

# Cases where CDI query is expected
CDI_QUERY_CASES: list[KnownCase] = [
    c for c in ALL_CASES if c.expect_cdi_query
]

# Cases where specific code should be directly suggested (no CDI needed)
DIRECT_CODE_CASES: list[KnownCase] = [
    c for c in ALL_CASES if not c.expect_cdi_query
]
