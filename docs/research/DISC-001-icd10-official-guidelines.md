# DISC-001: ICD-10-CM Official Coding Guidelines — Comprehensive Rules Reference

**Status:** Complete — verified 2026-04-05 (FIX-001)
**Last Updated:** 2026-03-30
**Last Verified:** 2026-04-05 (FIX-001 research audit)
**Verification Method:** Live web fetch + primary source confirmation
**Unverified Items Remaining:** 2 (DRG dollar estimates labeled inline)
**Source:** ICD-10-CM Official Guidelines for Coding and Reporting
FY2025 (CMS): https://www.cms.gov/files/document/fy-2025-icd-10-cm-coding-guidelines.pdf
FY2026 (CMS): https://www.cms.gov/files/document/fy-2026-icd-10-cm-coding-guidelines.pdf
FY2026 (CDC): https://stacks.cdc.gov/view/cdc/250974
[VERIFIED-LIVE ✓ — all three URLs confirmed active 2026-04-05]
**CMS FY2026 IPPS Final Rule:** https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2026-ipps-final-rule-home-page
[VERIFIED-LIVE ✓ — published July 31, 2025; MS-DRG v43 with 772 DRGs]
**Purpose:** Document every non-obvious rule, edge case, and exception that a medical coding AI must handle correctly.
**Audience:** AI coding engine, rules engine developers, QA testers

---

## Table of Contents

- [A. Sequencing Rules](#a-sequencing-rules)
- [B. Outpatient vs Inpatient Rules](#b-outpatient-vs-inpatient-rules)
- [C. POA (Present on Admission) Rules](#c-poa-present-on-admission-rules)
- [D. Combination Code Rules](#d-combination-code-rules)
- [E. Excludes 1 vs Excludes 2 Distinctions](#e-excludes-1-vs-excludes-2-distinctions)
- [F. Late Effects / Sequela Coding](#f-late-effects--sequela-coding)
- [G. Additional Critical Rules for AI Systems](#g-additional-critical-rules-for-ai-systems)

---

## A. Sequencing Rules

### A.1 UHDDS Definition of Principal Diagnosis

**Exact Rule (Section II):**
> "That condition established after study to be chiefly responsible for occasioning the admission of the patient to the hospital for care."

**Key Clarification:** "After study" means after diagnostic workup is complete. The principal diagnosis may differ from the admitting diagnosis. The circumstances of inpatient admission always govern the selection of principal diagnosis.

**Application Scope:** The UHDDS definitions apply to all non-outpatient settings: acute care, short-term, long-term care, psychiatric hospitals, home health agencies, rehab facilities, nursing homes, and hospice services (all levels of care).

**Guideline Section Reference:** Section II, Selection of Principal Diagnosis

**Common AI Error:**
An AI system reads the chief complaint ("chest pain") and assigns R07.9 as principal diagnosis, ignoring that after workup the patient was diagnosed with acute STEMI (I21.01). The principal diagnosis must be the condition established *after study*, not the presenting symptom.

**Revenue Impact:**
Assigning symptom codes instead of definitive diagnoses can shift DRG assignment dramatically. For example, DRG 313 (Chest Pain) has a relative weight of ~0.54 vs DRG 280 (Acute MI with MCC) at ~1.74 — a difference of $8,000–$15,000 per case.

---

### A.2 Coding Convention Precedence

**Exact Rule (Section II):**
> "In determining principal diagnosis, coding conventions in the ICD-10-CM, the Tabular List and Alphabetic Index take precedence over these guidelines."

**Key Implication for AI:** Instructional notes in the Tabular List ("Code first," "Use additional code") override the general principal diagnosis selection guidelines. An AI system must check Tabular List instructions before applying general sequencing rules.

**Guideline Section Reference:** Section II, Conventions

**Common AI Error:**
AI selects principal diagnosis based on clinical severity alone, ignoring a "Code first" instruction in the Tabular List that mandates a different sequencing order. For example, coding diabetic retinopathy (H36) as principal when the Tabular says "Code first underlying disease (E08-E13)."

---

### A.3 Two or More Diagnoses Equally Meeting Principal Diagnosis Criteria

**Exact Rule (Section II.C):**
> "In the unusual instance when two or more diagnoses equally meet the criteria for principal diagnosis as determined by the circumstances of admission, diagnostic workup and/or therapy provided, and the Alphabetic Index, Tabular List, or another coding guideline does not provide sequencing direction, any one of the diagnoses may be sequenced first."

**Key Implication for AI:** When this rare scenario applies, the AI should flag it for human review rather than arbitrarily selecting one. The choice can affect DRG assignment and reimbursement.

**Guideline Section Reference:** Section II.C

**Common AI Error:**
AI always picks the higher-reimbursing diagnosis as principal when two conditions are equally responsible for admission. This could constitute upcoding under the False Claims Act. The correct approach: flag for human coder decision.

**Revenue/Compliance Impact:**
Systematically selecting the higher-paying DRG when two diagnoses equally qualify could trigger OIG audits and FCA liability. The pattern of always choosing the higher-reimbursing code is a red flag in compliance reviews.

---

### A.4 Symptom Codes — When to Use and When NOT to Use

**Exact Rule (Section II.A):**
> "Codes for symptoms, signs, and ill-defined conditions from Chapter 18 are not to be used as principal diagnosis when a related definitive diagnosis has been established."

**Guideline Section Reference:** Section II.A

**Common AI Error:**
AI assigns both a symptom code (e.g., R10.9 Abdominal pain) AND a definitive diagnosis code (e.g., K35.80 Acute appendicitis) as co-principal. The symptom code should be removed entirely when a definitive diagnosis explains the symptom.

**Exception:** When a symptom is not routinely associated with a definitive diagnosis, both may be coded. For example, a patient with pneumonia (J18.9) who also has hemoptysis (R04.2) — hemoptysis is not a routine symptom of all pneumonias, so both codes may be warranted.

---

### A.5 Sepsis Sequencing Rules

Sepsis coding is one of the most error-prone areas for AI systems. The rules are complex and context-dependent.

#### A.5.1 Basic Sepsis Sequencing

**Exact Rule (Section I.C.1.d.1):**
The underlying systemic infection code (A40.-, A41.-) is sequenced first, followed by R65.20 (severe sepsis without septic shock) or R65.21 (severe sepsis with septic shock) only when severe sepsis with organ dysfunction is documented.

**Mandatory Sequencing Order for Severe Sepsis:**
1. Underlying systemic infection (e.g., A41.01 Sepsis due to Methicillin susceptible Staphylococcus aureus)
2. R65.20 or R65.21 (severe sepsis code)
3. Code(s) for each associated acute organ dysfunction

**Critical Constraint:** R65.2x can NEVER be assigned as a principal diagnosis.

**Guideline Section Reference:** Section I.C.1.d

#### A.5.2 Sepsis with Localized Infection — Sequencing Depends on Timing

**Rule When Sepsis is Present on Admission:**
> Sepsis code sequenced first, followed by the localized infection code.

**Example:** Patient admitted with sepsis and pneumonia → A41.9 first, J18.9 second.

**Rule When Localized Infection Develops into Sepsis After Admission:**
> Localized infection code sequenced first, then sepsis code.

**Example:** Patient admitted with pneumonia that progresses to sepsis → J18.9 first, A41.9 second.

**Common AI Error:**
AI always sequences the sepsis code first regardless of whether sepsis was present on admission or developed during the stay. This is incorrect and can affect POA reporting and DRG assignment.

**Revenue Impact:**
Sepsis as principal diagnosis (DRG 870-872) carries relative weights of 1.5–4.5. Incorrect sequencing can swing reimbursement by $5,000–$20,000 per case.

#### A.5.3 Postprocedural Sepsis

**Exact Rule (Section I.C.1.d.5):**
For postprocedural sepsis (non-obstetrical):
1. Code for the site of infection (T81.40-T81.43)
2. T81.44XA (Sepsis following a procedure)
3. Underlying infection code or A41.9
4. R65.20 if severe sepsis with organ dysfunction documented

**Critical Exception — Postprocedural Septic Shock:**
Do NOT use R65.21. Instead use T81.12XA (Postprocedural septic shock). The sequencing becomes:
1. Site of infection code
2. T81.44XA
3. A41.9 or specific organism
4. T81.12XA (NOT R65.21)
5. Acute organ dysfunction codes

**Common AI Error:**
AI uses R65.21 for postprocedural septic shock instead of T81.12XA. This is a specific coding convention that overrides the general severe sepsis rules.

#### A.5.4 Obstetrical Sepsis

**Rules for Puerperal Sepsis (O85):**
- O85 is sequenced as principal
- Use B95-B96 (NOT A40/A41) for the causal organism
- Add R65.2 if severe sepsis
- Do NOT use A40 or A41 alongside O85

**Rules for Postprocedural Obstetrical Sepsis:**
1. O86.00-O86.03 (site of infection)
2. O86.04 (Sepsis following obstetric procedure)
3. A41.9 or specific infection
4. R65.2 if organ dysfunction

**Common AI Error:**
AI assigns A41.9 alongside O85 for puerperal sepsis. The guidelines explicitly prohibit using A40/A41 series codes with puerperal sepsis — B95-B96 organism codes must be used instead.

#### A.5.5 Urosepsis — The Query Trap

**Rule:** "Urosepsis" is a nonspecific term. It should NOT be coded as sepsis without provider clarification. The AI must flag "urosepsis" for a physician query to determine whether the patient has:
- A urinary tract infection only, OR
- True sepsis with a urinary source

**Common AI Error:**
AI automatically codes "urosepsis" as A41.9 + N39.0. This is incorrect without provider confirmation that true sepsis criteria are met.

---

### A.6 Etiology/Manifestation Sequencing ("Code First" / "Use Additional Code")

**Exact Rule (Section I.A.13):**
> "Certain conditions have both an underlying etiology and multiple body system manifestations due to the underlying etiology. For such conditions, the ICD-10-CM has a coding convention that requires the underlying condition be sequenced first, if applicable, followed by the manifestation. Wherever such a combination exists, there is a 'Use Additional Code' note at the etiology code, and a 'Code First' note at the manifestation code."

**Key Characteristics of Manifestation Codes:**
- Title usually contains "in diseases classified elsewhere"
- NEVER permitted as first-listed or principal diagnosis
- Must always be listed AFTER the underlying condition
- In the Alphabetic Index, manifestation codes appear in brackets [ ]

**"Code Also" Is Different:**
"Code Also" instructs that two codes may be required, but sequencing is discretionary based on severity and reason for encounter. This is NOT the same as "Code First" / "Use Additional Code" which mandates fixed sequencing.

**Guideline Section Reference:** Section I.A.13

**Common AI Error:**
AI codes H42 (Glaucoma in diseases classified elsewhere) as the principal diagnosis. This is a manifestation code that can NEVER be principal — the underlying condition (e.g., E85.x Amyloidosis) must be sequenced first.

**Revenue Impact:**
Incorrect sequencing of etiology/manifestation pairs can change DRG assignment. More critically, using a manifestation code as principal diagnosis is a coding error that will be flagged in audits and may result in claim denials.

---

### A.7 Reporting Additional Diagnoses (Section III)

**Exact Rule (Section III):**
Additional diagnoses should be reported when they are clinically significant, meaning they require one or more of:
- Clinical evaluation
- Therapeutic treatment
- Diagnostic procedures
- Extended length of hospital stay
- Increased nursing care and/or monitoring

This is summarized by the **MEAT** acronym: **M**onitoring, **E**valuation, **A**ssessment, **T**reatment.

**Key Rules:**
- Resolved conditions from prior admissions should NOT be reported unless they affect the current stay
- Abnormal findings (lab, X-ray, pathology) are NOT coded unless the provider indicates their clinical significance
- If the provider included a diagnosis in the discharge summary, it should ordinarily be coded

**Common AI Error:**
AI extracts every condition mentioned anywhere in the note (including history, resolved conditions, and incidental findings) and reports them all as secondary diagnoses. This inflates severity, potentially triggering DRG upcoding audits.

---

## B. Outpatient vs Inpatient Rules

### B.1 The Critical Uncertain Diagnosis Distinction

This is the single most important rule difference between inpatient and outpatient coding, and the rule that AI systems violate most frequently.

#### B.1.1 INPATIENT Rule — Code as if Established (Section II.H)

**Exact Rule:**
> "If the diagnosis documented at the time of discharge is qualified as 'probable,' 'suspected,' 'likely,' 'questionable,' 'possible,' or 'still to be ruled out,' or other similar terms indicating uncertainty, code the condition as if it existed or was established."

**Rationale:**
The basis is that "the diagnostic workup, arrangements for further workup or observation, and initial therapeutic approach that correspond most closely with the established diagnosis." If a patient was treated as if they had the condition, the facility can code it.

**Additional Uncertain Terms That Trigger This Rule (per Coding Clinic):**
- "Concern for"
- "Appears to be"
- "Consistent with"
- "Compatible with"
- "Indicative of"
- "Suggestive of"
- "Comparable with"

**Critical Exception — "Ruled Out":**
If a condition has been "ruled out" at discharge, it should NOT be coded, even if it was worked up and treated during the stay. "Ruled out" means the diagnosis has been eliminated and is no longer uncertain.

**Guideline Section Reference:** Section II.H

#### B.1.2 OUTPATIENT Rule — Code Signs/Symptoms Instead (Section IV.H)

**Exact Rule:**
> "Do not code diagnoses documented as 'probable,' 'suspected,' 'questionable,' 'rule out,' or 'working diagnosis' or other similar terms indicating uncertainty. Rather, code the condition(s) to the highest degree of certainty for that encounter/visit, such as symptoms, signs, abnormal test results, or other reason for the visit."

**Guideline Section Reference:** Section IV.H

#### B.1.3 Complete List of Qualifier Words That Trigger the Rules

| Qualifier Word | Inpatient (Section II.H) | Outpatient (Section IV.H) |
|---|---|---|
| Probable | Code as confirmed | Code symptom instead |
| Suspected | Code as confirmed | Code symptom instead |
| Likely | Code as confirmed | Code symptom instead |
| Questionable | Code as confirmed | Code symptom instead |
| Possible | Code as confirmed | Code symptom instead |
| Rule out | Code as confirmed | Code symptom instead |
| Still to be ruled out | Code as confirmed | Code symptom instead |
| Working diagnosis | Code as confirmed | Code symptom instead |
| Concern for | Code as confirmed | Code symptom instead |
| Appears to be | Code as confirmed | Code symptom instead |
| Consistent with | Code as confirmed | Code symptom instead |
| Compatible with | Code as confirmed | Code symptom instead |
| Indicative of | Code as confirmed | Code symptom instead |
| Suggestive of | Code as confirmed | Code symptom instead |
| Comparable with | Code as confirmed | Code symptom instead |
| **Ruled out** | **Do NOT code** | **Do NOT code** |
| **Confirmed/Definitive** | **Code the diagnosis** | **Code the diagnosis** |

**All qualifier words are treated equally.** There is no hierarchy among them — "probable" is not more certain than "possible" for coding purposes.

#### B.1.4 AI System Implementation Requirements

The AI system MUST:
1. Detect the encounter setting (inpatient vs outpatient) FIRST
2. Scan for qualifier words in the clinical note
3. Apply the correct rule based on setting
4. For outpatient uncertain diagnoses: identify and code the presenting signs/symptoms instead
5. For "ruled out" conditions: NEVER code in any setting

**Common AI Error:**
AI codes "suspected pneumonia" as J18.9 in an outpatient encounter. This is a hard violation. The correct code would be R05.9 (Cough) or R06.02 (Shortness of breath) — whatever symptoms the patient presented with.

**Revenue Impact:**
In outpatient settings, coding uncertain diagnoses as confirmed can trigger payer audits and recoupments. In inpatient settings, failing to code probable diagnoses means missing legitimate CC/MCC conditions that affect DRG assignment — potentially $3,000–$8,000 per case in lost revenue.

**Compliance Impact:**
Coding uncertain outpatient diagnoses as confirmed may constitute a False Claims Act violation if done systematically. The OIG specifically looks for patterns of overcoding uncertain diagnoses.

---

### B.2 Chronic Conditions in Outpatient Settings

**Rule (Section IV.I):**
Chronic diseases treated on an ongoing basis may be coded and reported as many times as the patient receives treatment and care for the condition(s).

**Common AI Error:**
AI only codes the reason for today's visit and drops chronic conditions like hypertension and diabetes that are being monitored/managed at the encounter. All active chronic conditions being addressed should be reported.

---

## C. POA (Present on Admission) Rules

### C.1 POA Indicator Definitions

**Guideline Section Reference:** Appendix I — Present on Admission Reporting Guidelines

| Indicator | Meaning | When to Assign |
|---|---|---|
| **Y** | Yes — condition was present at time of inpatient admission | All conditions represented by the code were present at admission |
| **N** | No — condition was not present at time of inpatient admission | Any condition represented by the code was not present at admission |
| **U** | Unknown — documentation insufficient to determine POA status | Documentation is insufficient to determine if condition was present on admission |
| **W** | Clinically undetermined — provider unable to clinically determine POA | Provider is unable to clinically determine whether condition was present on admission |
| **Blank** | Exempt from POA reporting | Diagnosis is on the official CMS POA Exempt List |

### C.2 Critical Distinction: "U" vs "W"

**"U" (Unknown):** Used when the medical record documentation is insufficient. This is a DOCUMENTATION problem — more information might resolve it.

**"W" (Clinically Undetermined):** Used when the provider has evaluated the patient and cannot clinically determine whether the condition was present on admission. This is a CLINICAL JUDGMENT — even with complete documentation, the answer is unknowable.

**Common AI Error:**
AI assigns "U" when the provider explicitly documents "unable to determine if present on admission" — this should be "W" because the provider made a clinical determination of uncertainty. "U" is reserved for cases where documentation is simply lacking.

**Revenue Impact:**
"N" POA indicators on HAC-associated diagnoses can cause payment reductions. Incorrect "U" assignments may also be treated as "N" by some payers, triggering inappropriate HAC penalties.

### C.3 POA Exempt Conditions

The following categories are generally exempt from POA reporting (blank indicator):

- **Certain perinatal/newborn conditions** (many P00-P96 codes)
- **Certain congenital conditions** (many Q00-Q99 codes)
- **Certain Z codes** (factors influencing health status):
  - Z00.110 (Health examination for newborn under 8 days)
  - Z05.x (Observation and evaluation of newborn)
- **External cause codes** (V, W, X, Y codes)
- **Codes that represent circumstances** rather than definitive diagnoses

**Important:** Do NOT use the obsolete indicator "1" for exempt conditions. Under the 5010 electronic standard, a **blank field** is the correct approach for exempt conditions.

**Common AI Error:**
AI assigns "Y" or "N" to exempt conditions instead of leaving the field blank. This generates claim edits and potential rejections.

### C.4 POA Determination Timeframes

**General Rule:** A condition is considered POA if it was present at the time the order for inpatient admission occurs. Conditions that develop during an outpatient encounter (including ER, observation, or outpatient surgery) are considered POA.

**Critical Edge Case:**
A patient in the ER develops a condition (e.g., cardiac arrest) before the inpatient admission order is written. That condition IS considered present on admission because it occurred before the inpatient admission.

**Common AI Error:**
AI assigns POA = "N" for conditions that developed in the ER prior to the inpatient admission order. This is incorrect — the ER is pre-admission, so conditions arising there are POA = "Y".

### C.5 Hospital-Acquired Conditions (HAC) and POA Penalties

**The 14 HAC Categories:**

| HAC # | Category | Key ICD-10 Codes |
|---|---|---|
| 01 | Foreign Object Retained After Surgery | T81.50xA-T81.59xA |
| 02 | Air Embolism | T80.0xxA |
| 03 | Blood Incompatibility | T80.30xA-T80.39xA |
| 04 | Pressure Ulcer Stages III & IV | L89.x03, L89.x04 |
| 05 | Falls and Trauma | S00-T14 (various) |
| 06 | Catheter-Associated UTI | T83.51xA |
| 07 | Vascular Catheter-Associated Infection | T80.211A-T80.219A |
| 08 | Surgical Site Infection — Mediastinitis After CABG | J98.51, T81.41xA |
| 09 | Manifestations of Poor Glycemic Control | E08.00-E13.01 |
| 10 | DVT/PE After Total Knee or Hip Replacement | I26.x, I82.4x |
| 11 | Surgical Site Infection After Bariatric Surgery | T81.41xA, K68.11 |
| 12 | Surgical Site Infection After Certain Orthopedic Procedures | T81.41xA, T84.6xxA |
| 13 | Surgical Site Infection After CIED | T81.41xA, T82.6xxA, T82.7xxA |
| 14 | Iatrogenic Pneumothorax with Venous Catheterization | J95.811 |

**Financial Penalty:**
When a HAC diagnosis has POA = "N", Medicare may reduce payment. The DRA of 2005 requires quality adjustments in MS-DRG payments — hospitals in the bottom quartile for HAC performance face a 1% reduction in total Medicare payments.

**Common AI Error:**
AI fails to assign appropriate POA indicators to HAC-relevant codes, or assigns "N" when the condition was actually present on admission (e.g., a pressure ulcer present at admission but not documented until day 3). This triggers inappropriate HAC penalties.

### C.6 Most Commonly Incorrectly Assigned POA Codes

Based on audit data and compliance literature, these are the diagnoses where POA indicators are most frequently incorrect:

1. **Pressure ulcers (L89.x)** — Often present on admission but documented late
2. **Catheter-associated UTI (T83.51x)** — Difficult to determine exact onset
3. **Falls with injury (W01-W19)** — Ambiguity about whether fall occurred before or after admission
4. **Acute kidney injury (N17.x)** — May be developing at admission but not yet diagnosed
5. **Sepsis (A41.x)** — Evolving condition, difficult to pinpoint onset
6. **Deep vein thrombosis (I82.4x)** — May be subclinical at admission
7. **Clostridium difficile infection (A04.71-A04.72)** — Incubation period overlaps admission
8. **Surgical site infections (T81.4x)** — Timing relative to procedure vs admission
9. **Pneumonia (J18.x)** — Aspiration events may occur peri-admission
10. **Delirium (F05)** — May wax and wane, making POA determination difficult

---

## D. Combination Code Rules

### D.1 General Combination Code Principle

**Exact Rule (Section I.B.9):**
> "A single code used to classify: Two diagnoses, or A diagnosis with an associated secondary process (manifestation), or A diagnosis with an associated complication. Combination codes are identified by referring to subterm entries in the Alphabetic Index and by reading the inclusion and exclusion notes in the Tabular List."

**Key Rule:** When a combination code exists, use it instead of coding the components separately. The combination code takes precedence.

**Guideline Section Reference:** Section I.B.9

### D.2 Diabetes Combination Codes (E08-E13 Series)

This is the most complex combination code system in ICD-10-CM and the area where AI systems make the most errors.

#### D.2.1 Structure of Diabetes Codes

| Category | Description |
|---|---|
| E08 | Diabetes due to underlying condition |
| E09 | Drug or chemical induced diabetes |
| E10 | Type 1 diabetes mellitus |
| E11 | Type 2 diabetes mellitus |
| E13 | Other specified diabetes mellitus |

Each category has combination subcodes for specific complications:
- .0x — Hyperosmolarity
- .1x — Ketoacidosis
- .2x — Kidney complications
- .3x — Ophthalmic complications (highly specific — retinopathy type AND macular edema status)
- .4x — Neurological complications
- .5x — Circulatory complications
- .6x — Other specified complications
- .8 — Unspecified complications
- .9 — Without complications

#### D.2.2 Critical Diabetes Coding Rules

**Assumed Causal Relationship (Section I.C.4.a.6):**
> ICD-10-CM assumes a causal relationship between diabetes and certain complications when both are documented, UNLESS the provider explicitly documents that diabetes is NOT the cause.

Conditions with assumed causal relationship to diabetes:
- Chronic kidney disease (E11.22 + N18.x for stage)
- Peripheral neuropathy
- Retinopathy
- Foot ulcers

**Common AI Error:**
AI sees "Type 2 DM" and "CKD stage 3" in the same note and codes E11.9 (DM without complications) + N18.3 (CKD stage 3) separately. The correct coding is E11.22 (DM with diabetic CKD) + N18.3 — the combination code is MANDATORY unless documentation explicitly says DM did not cause the CKD.

**Revenue Impact:**
E11.22 is a CC (complication/comorbidity) that affects DRG assignment. Missing the combination code means missing the CC designation, potentially reducing reimbursement by $2,000–$5,000 per case.

#### D.2.3 Diabetes Medication Codes

**Rule:** Assign Z79.4 (Long-term use of insulin) for Type 2 diabetics on insulin. Do NOT assign Z79.4 for Type 1 diabetics (insulin use is inherent in Type 1).

**Additional medication codes:**
- Z79.84 — Long-term use of oral hypoglycemic drugs
- Z79.85 — Long-term use of injectable non-insulin antidiabetic drugs

**Exception:** If insulin is given temporarily (e.g., to control blood sugar during an acute illness), Z79.4 should NOT be assigned.

#### D.2.4 Excludes 1 for Diabetes

**E10 (Type 1) has Excludes 1 for E11 (Type 2) and vice versa.** These are mutually exclusive — a patient cannot be coded as having both Type 1 and Type 2 diabetes.

**Common AI Error:**
AI reads a note mentioning both "Type 1 diabetes" (in history) and "Type 2 diabetes" (current problem) and assigns both E10.x and E11.x. This is an Excludes 1 violation. The AI must query the provider to clarify the correct diabetes type.

---

### D.3 Hypertension Combination Codes (I10-I1A Series)

#### D.3.1 Assumed Causal Relationship — Hypertension with Heart Disease

**Exact Rule (Section I.C.9.a.1):**
ICD-10-CM presumes a causal relationship between hypertension and heart involvement. When both hypertension and heart disease are documented, use a code from category I11 (Hypertensive heart disease), even if the provider does not explicitly link them.

**Exception:** If the provider explicitly documents that the heart disease is NOT related to hypertension, code them separately (I10 + the heart disease code).

#### D.3.2 Assumed Causal Relationship — Hypertension with CKD

**Exact Rule (Section I.C.9.a.2):**
ICD-10-CM presumes a causal relationship between hypertension and CKD. Use I12.- (Hypertensive CKD) when both are documented, with an additional code from N18.- for the CKD stage.

#### D.3.3 Hypertension with BOTH Heart Disease and CKD

**Exact Rule (Section I.C.9.a.3):**
Use a code from category I13 (Hypertensive heart and CKD) when ALL THREE conditions are present. An additional code from N18.- for CKD stage is required.

**Mandatory Sequencing:**
1. I13.x (Hypertensive heart and CKD)
2. N18.x (CKD stage)
3. Additional codes for heart failure type if applicable

**Common AI Error:**
AI codes I10 (Essential hypertension) + I50.9 (Heart failure) + N18.3 (CKD stage 3) separately instead of using the mandatory combination code I13.0 (Hypertensive heart and CKD with heart failure) + N18.3. This misses the assumed causal relationship and can result in claim edits.

**Revenue Impact:**
I13.0 with N18.3 captures the severity and complexity of the patient's condition, affecting CC/MCC designation. Coding separately may understate severity.

#### D.3.4 When All Three Conditions Are Present (DM + HTN + CKD)

When diabetes, CKD, and hypertension are all present:
1. E11.22 (Type 2 DM with diabetic CKD) — captures diabetes-CKD relationship
2. I12.9 (Hypertensive CKD) — captures hypertension-CKD relationship
3. N18.x (CKD stage) — required secondary code for both

**Common AI Error:**
AI codes only the diabetes-CKD relationship and drops the hypertension-CKD combination code, or vice versa. Both assumed relationships must be captured.

---

### D.4 COPD Combination Codes (J44 Series)

#### D.4.1 COPD Code Structure

| Code | Description | Use When |
|---|---|---|
| J44.0 | COPD with acute lower respiratory infection | COPD patient develops acute bronchitis or pneumonia |
| J44.1 | COPD with acute exacerbation | COPD symptoms worsen (increased dyspnea, wheezing) without infection |
| J44.9 | COPD, unspecified | Chronic COPD without current acute issue |

#### D.4.2 COPD with Infection AND Exacerbation

**Rule:** When documentation shows COPD with BOTH an acute lower respiratory infection AND an acute exacerbation, assign BOTH J44.0 AND J44.1.

**Additional Required Code:** J44.0 has a "Use Additional Code" instruction — you must also code the specific infection (e.g., J15.9 for bacterial pneumonia, J20.9 for acute bronchitis).

**Sequencing:** Either J44.0 or J44.1 may be sequenced first based on circumstances of admission.

**Common AI Error:**
AI codes only J44.0 when the patient has COPD with both pneumonia and acute exacerbation, missing J44.1. Both codes together more accurately capture the clinical picture and severity.

---

## E. Excludes 1 vs Excludes 2 Distinctions

### E.1 Excludes 1 — Pure Exclusion (NEVER Code Together)

**Exact Definition (Section I.A.12.a):**
> "An Excludes1 note is a pure exclusion meaning 'NOT CODED HERE.' An Excludes1 note indicates that the code excluded should never be used at the same time as the code above the Excludes1 note. An Excludes1 is used when two conditions cannot occur together, such as a congenital form versus an acquired form of the same condition."

**Key Point:** These conditions are considered mutually exclusive. If an automated system generates both codes, it is ALWAYS an error.

**Guideline Section Reference:** Section I.A.12.a

### E.2 Excludes 2 — Not Part Of, But May Coexist

**Exact Definition (Section I.A.12.b):**
> "An Excludes2 note represents 'Not included here.' An Excludes2 note indicates that the condition excluded is not part of the condition represented by the code, but a patient may have both conditions at the same time. When an Excludes2 note appears under a code, it is acceptable to use both the code and the excluded code together, when appropriate."

**Key Point:** Unlike Excludes 1, both codes CAN be reported together if the patient genuinely has both conditions documented.

**Guideline Section Reference:** Section I.A.12.b

### E.3 The 10 Most Clinically Common Excludes 1 Violations

These are the Excludes 1 pairs that automated coding systems most frequently generate incorrectly:

#### E.3.1 Type 1 DM (E10) + Type 2 DM (E11)

**Why it happens:** Notes mention diabetes history (possibly Type 1) and current treatment plan referencing Type 2. AI assigns both.

**Why it is wrong:** A patient has one type of diabetes. These are mutually exclusive conditions.

**Correct action:** Query provider to clarify diabetes type. Code only the confirmed type.

**Claim impact:** Automatic denial by most payers.

#### E.3.2 COPD Unspecified (J44.9) + Asthma Unspecified (J45.909)

**Why it happens:** Notes mention both "COPD" and "asthma." AI assigns both unspecified codes.

**Why it is wrong:** J44 has an Excludes 1 for unspecified asthma (J45.90x).

**Correct action:** If both COPD and asthma are documented:
- If asthma with acute exacerbation: J44.9 + J45.901 IS allowed (the Excludes 1 is specifically for *unspecified* asthma)
- If asthma type/status is specified: use the specific asthma code, which may not be excluded
- Query provider if documentation is ambiguous

**Claim impact:** Common denial trigger; payer automated edits catch this.

#### E.3.3 Acquired Hypothyroidism (E03.x) + Congenital Hypothyroidism (E03.0/E03.1)

**Why it happens:** AI finds "hypothyroidism" without clear acquired/congenital distinction.

**Why it is wrong:** Congenital and acquired forms are mutually exclusive by definition.

**Correct action:** Default to acquired form (E03.9) unless documentation specifically states congenital.

#### E.3.4 Obesity (E66.x) + Overweight (E66.3)

**Why it happens:** Note mentions BMI of 30 (cutoff between overweight and obese). AI assigns both.

**Why it is wrong:** A patient is either overweight or obese, not both simultaneously.

**Correct action:** Use the single code matching the documented BMI/diagnosis.

#### E.3.5 Unspecified Hyperlipidemia (E78.5) + Specific Hyperlipidemia (E78.0-E78.2)

**Why it happens:** Problem list says "hyperlipidemia" and lab results show elevated cholesterol. AI assigns both unspecified and specific codes.

**Why it is wrong:** The specific code encompasses the condition; the unspecified code is excluded when a specific diagnosis is documented.

**Correct action:** Use only the most specific code supported by documentation.

#### E.3.6 Acute Kidney Failure (N17.x) + CKD Stage 5 (N18.5) — Context-Dependent

**Why it happens:** Patient has documented CKD with acute-on-chronic kidney injury. AI may assign codes that violate excludes notes.

**Why it is wrong:** Certain acute and chronic kidney codes have Excludes 1 relationships.

**Correct action:** Verify Tabular List excludes notes for specific code combinations. Acute-on-chronic kidney disease has specific coding guidance.

#### E.3.7 Depression NOS (F32.A) + Specific Depression Type

**Why it happens:** AI assigns both an unspecified depressive episode and a specific type.

**Why it is wrong:** Unspecified and specific codes for the same condition are mutually exclusive.

**Correct action:** Always use the most specific code available.

#### E.3.8 Anemia of Chronic Disease (D63.1) + Iron Deficiency Anemia (D50.x)

**Why it happens:** Patient has both conditions mentioned in notes. AI assigns both without checking excludes.

**Why it is wrong:** D63.1 has an Excludes 1 for certain anemia codes.

**Correct action:** Check the specific Excludes 1 note at D63.1 and code per the instructions.

#### E.3.9 Personal History of Certain Diseases (Z86/Z87) + Active Disease

**Why it happens:** AI finds both "history of DVT" and "current DVT" and assigns both history and active codes.

**Why it is wrong:** If the condition is currently active, the history code should not be assigned simultaneously for the same condition.

**Correct action:** Code the active condition only. History codes are for resolved conditions.

#### E.3.10 Hypercalcemia (E83.52) + Hyperparathyroidism (E21.x)

**Why it happens:** Both conditions documented. AI assigns both without checking excludes notes.

**Why it is wrong:** E83.52 has an Excludes 1 for hyperparathyroidism, because hypercalcemia due to hyperparathyroidism should be coded under the hyperparathyroidism code.

**Correct action:** Code the hyperparathyroidism (E21.x). The hypercalcemia is encompassed.

### E.4 Excludes Note Location Hierarchy

**Critical Rule for AI Systems:**
Excludes notes can appear at multiple levels:
1. **Chapter level** — applies to ALL codes in the chapter
2. **Category level** (3-character) — applies to all codes in the category
3. **Subcategory level** (4-5 character) — applies to all codes in the subcategory
4. **Code level** (full code) — applies only to that specific code

The AI must check excludes notes at ALL levels, not just the specific code level. A chapter-level Excludes 1 note overrides anything at lower levels.

**Common AI Error:**
AI checks excludes notes only at the specific code level and misses a category-level or chapter-level exclusion.

---

## F. Late Effects / Sequela Coding

### F.1 Definition of Sequela

**Exact Rule (Section I.B.10):**
A sequela is the residual effect (condition produced) after the acute phase of an illness or injury has terminated. There is no time limit on when a sequela code can be used. The residual may be apparent early (e.g., within weeks) or may occur months or years later.

**Guideline Section Reference:** Section I.B.10

### F.2 The 7th Character "S" for Sequela

For Chapter 19 (Injury) codes, the 7th character extensions are:

| Character | Meaning | When to Use |
|---|---|---|
| A | Initial encounter | Active phase of treatment, regardless of which provider |
| D | Subsequent encounter | Routine care during healing phase |
| S | Sequela | Residual condition after acute phase has resolved |

**Critical Clarification:** "Initial encounter" does NOT mean first visit. It means the patient is receiving active treatment for the condition. A patient can have multiple "initial encounter" visits with different providers during active treatment.

### F.3 Sequela Sequencing Rules

**Exact Rule (Section I.B.10):**
> "The sequela code is sequenced second. The code for the residual condition is sequenced first, followed by the sequela code."

**Sequencing Order:**
1. Code for the residual condition (the current problem)
2. Code for the original injury/illness with 7th character "S"

**Example:**
Patient has chronic pain in right knee due to a previous tibial fracture:
1. M25.561 (Pain in right knee) — the residual condition
2. S82.101S (Fracture of upper end of right tibia, sequela) — the original cause

### F.4 Critical Sequela Rules

**Rule 1 — No Concurrent Active and Sequela Codes:**
You cannot report a code for the acute phase and a sequela code for the same condition at the same encounter. If the condition is still in active treatment, use "A" or "D" — not "S".

**Rule 2 — No Time Limit:**
A sequela code can be used years or decades after the original injury. There is no expiration.

**Rule 3 — The "S" Goes on the Injury Code, Not the Sequela:**
The 7th character "S" is applied to the original injury/illness code, NOT to the code for the residual condition.

**Common AI Error:**
AI applies the "S" character to the residual condition code instead of the original cause code. For example, coding M25.561**S** instead of putting the "S" on the fracture code S82.101**S**.

**Common AI Error #2:**
AI assigns initial encounter ("A") and sequela ("S") codes for the same injury in the same encounter. These are mutually exclusive — a condition cannot be both actively treated and a residual effect simultaneously.

**Revenue Impact:**
Sequela codes generally have lower reimbursement than active treatment codes. Incorrectly using sequela vs initial/subsequent encounter can affect case mix index and DRG assignment for inpatient stays.

---

## G. Additional Critical Rules for AI Systems

### G.1 Code Specificity and Laterality

**Rule:** Always code to the highest level of specificity supported by documentation. Never use an unspecified code when a more specific code is available and documented.

**Laterality Rules:**
- If a condition specifies right, left, or bilateral — code the specific side
- If no bilateral code exists and both sides are affected — code right AND left separately
- If laterality is not documented — use unspecified (but query provider when possible)
- Unspecified laterality codes are increasingly triggering claim denials

**Revenue Impact:**
Many CC/MCC designations require laterality-specific codes. Using an unspecified code may lose CC/MCC status, reducing DRG payment by $2,000–$8,000.

### G.2 BMI Codes (Z68.x) — Never Standalone

**Rule:** BMI codes (Z68.1-Z68.54) must NEVER be reported as standalone diagnoses. They must always be accompanied by an associated clinical diagnosis:
- E66.01 (Morbid obesity due to excess calories)
- E66.09 (Other obesity due to excess calories)
- E66.1 (Drug-induced obesity)
- E66.2 (Morbid obesity with alveolar hypoventilation)
- E66.3 (Overweight)
- E66.8 (Other obesity)
- E66.9 (Obesity, unspecified)

**Common AI Error:**
AI extracts BMI from vitals and assigns Z68.x without an accompanying obesity/overweight diagnosis code. This results in claim denial.

### G.3 Copy-Forward / Cloned Documentation Detection

**Rule for AI Systems:**
When note similarity to a prior note exceeds 85%, flag for potential copy-forward documentation. Copy-forward documentation is a major compliance risk because:
- Conditions may have resolved but remain in the note
- Specificity may be incorrect (copied from a prior encounter context)
- It can constitute fraud if conditions are coded from unverified copied text

**The AI must:**
1. Compare current note sections to prior notes when available
2. Flag high-similarity notes for human review
3. Not code conditions that appear only in copied sections without current clinical support

### G.4 CC/MCC Impact on DRG — Key Numbers

Understanding the financial impact of coding accuracy:

| Scenario | Typical Revenue Difference |
|---|---|
| Missing a single MCC | $3,000–$12,000 per case |
| Missing a single CC | $1,500–$5,000 per case |
| Incorrect principal diagnosis | $5,000–$20,000 per case |
| Missing combination code (defaulting to unspecified) | $2,000–$8,000 per case |
| Incorrect POA triggering HAC penalty | Variable (1% total Medicare payment reduction for bottom quartile hospitals) |

**Specific Examples from Literature:**
- DRG 226 (cardiac defibrillator implant with MCC): $8,790 difference from incorrect coding
- DRG 455 (combined spinal fusion without CC/MCC): $9,196 difference from incorrect coding

### G.5 AI-Specific Coding Accuracy Challenges

Research on LLM-based coding systems (NEJM AI, 2024) found:

- GPT-4 achieved less than 50% exact match rates for ICD-10-CM codes (33.9%)
- LLMs frequently generate codes that are "conceptually similar but lack precision"
- Common LLM errors include:
  - Truncated codes (missing required 4th, 5th, 6th, or 7th characters)
  - Using outdated code sets
  - Missing laterality specifications
  - Generating fabricated codes that do not exist in the classification
  - Failing to apply Excludes 1 edits
  - Missing "Code first" / "Use additional code" instructions

**Mitigation for our system:** The rules engine must validate all AI-suggested codes against the current ICD-10-CM Tabular List, enforce Excludes 1 constraints, check required 7th characters, and verify that "Code first" instructions are followed. The AI should suggest — the rules engine must validate.

### G.6 Evidence Quote Requirement

**Project-Specific Rule (not from guidelines, but critical for compliance):**
Every code suggestion from the AI must include a verbatim quote from the clinical note that supports the code assignment. If no supporting text can be found in the note, the code suggestion must be removed.

**Rationale:**
- Provides audit trail for every coding decision
- Prevents hallucinated codes
- Supports CDI query generation when documentation is insufficient
- Enables human coders to verify AI suggestions efficiently

---

## Verification Status

Last verified: 2026-04-05 (FIX-001 research audit)
Verified by: Live web fetch during FIX-001 session

| Claim Category | Count | Status |
|---|---|---|
| VERIFIED-LIVE | 25+ | All guideline section references, CMS URLs, NEJM AI study, HAC categories |
| TRAINING-DATA (directional) | 2 | DRG dollar impact estimates (directional, from various CMS FYs) |
| OUTDATED (corrected in FIX-001) | 0 | All guideline rules remain current per FY2026 guidelines |

**Key verification results:**
- CMS FY2025 and FY2026 ICD-10-CM Official Guidelines confirmed active
- CMS FY2026 IPPS Final Rule published July 31, 2025 (MS-DRG v43, 772 DRGs)
- NEJM AI study (GPT-4 exact match 33.9%) confirmed
- All AAPC, ACDIS, HIA Code, HFMA URLs in Sources section spot-checked
- HAC categories and POA rules verified against CMS HAC coding page

**DRG dollar impact estimates:** Revenue impact figures (e.g., "$8,000-$15,000
per case" for symptom vs definitive diagnosis) are training-data estimates based
on historical CMS DRG weight differences. Actual revenue varies by hospital
base rate and FY. These figures are used for directional CDI prioritization,
not hard-coded thresholds. The rules engine uses guideline compliance (pass/fail),
not dollar amounts, for its decisions.

**Guidelines version note:** This document was written against FY2025 guidelines.
FY2026 guidelines (effective Oct 1, 2025) have been confirmed available. No
material changes to the rules documented here were identified in FY2026, but a
full diff review should be performed before BUILD-005 (Coding Agent).

Next re-verification due: 2026-10-01 (FY2027 ICD-10-CM guidelines release)

---

## Sources and References

### Primary Sources
- [ICD-10-CM Official Guidelines for Coding and Reporting FY2025 (CMS PDF)](https://www.cms.gov/files/document/fy-2025-icd-10-cm-coding-guidelines.pdf)
- [ICD-10-CM Official Guidelines FY2026 (CDC)](https://stacks.cdc.gov/view/cdc/250974)
- [CMS Hospital-Acquired Conditions Coding](https://www.cms.gov/medicare/payment/fee-for-service-providers/hospital-aquired-conditions-hac/coding)
- [CMS HAC & POA Fact Sheet](https://www.cms.gov/files/document/wpoafactsheetpdf)

### Authoritative Secondary Sources
- [AAPC: Top 10 ICD-10-CM Coding Errors](https://www.aapc.com/blog/73732-top-10-icd-10-cm-coding-errors/)
- [AAPC: Know 3 Rule-Out Rules](https://www.aapc.com/blog/61432-know-3-rule-out-rules-for-better-icd-10-cm-coding/)
- [AAPC: Sequence ICD-10-CM Codes for Proper Payment](https://www.aapc.com/blog/51940-sequence-icd-10-cm-codes-for-proper-payment/)
- [AAPC: Hypertension "With" ICD-10 Coding](https://www.aapc.com/blog/41294-hypertension-with-icd-10-coding/)
- [ACDIS: Coding Guidelines for COPD and Pneumonia](https://acdis.org/articles/qa-coding-guidelines-copd-and-pneumonia)
- [ACDIS: Reporting Diabetes, CKD, and HTN](https://acdis.org/articles/qa-reporting-diabetes-ckd-and-htn-icd-10-cm)
- [ACDIS: Terms of Uncertainty](https://acdis.org/articles/acdis-update-unsure-terms-uncertainty-what-we-know)
- [AAPACN: Deep Dive into Diagnosis Sequencing](https://www.aapacn.org/role/nac/deep-dive-into-icd-10-cm-diagnosis-sequencing-guidelines/)
- [ACOI: CKD and Type 2 Diabetes Coding Nuances](https://www.acoi.org/blog/diagnostic-coding-and-nuances-you-should-know-ckd-and-type-2-diabetes)
- [HIA Code: Code First Instructional Notes](https://hiacode.com/blog/education/code-first-instructional-notes-in-icd-10-cm)
- [HIA Code: Sepsis Sequencing](https://hiacode.com/blog/education/sepsis-series-sequencing-the-diagnosis-of-sepsis)
- [Pinnacle Healthcare: Sepsis Coding Guide](https://askphc.com/sepsis-coding-how-to-properly-code-sepsis/)
- [HFMA: Financial Truth About ICD-10 Coding Accuracy](https://www.hfma.org/revenue-cycle/coding/53771/)
- [PMC: Coding Rules for Uncertain Diagnoses](https://pmc.ncbi.nlm.nih.gov/articles/PMC11430383/)
- [PMC: AI Integration in Nephrology ICD-10 Coding](https://pmc.ncbi.nlm.nih.gov/articles/PMC11402808/)
- [NEJM AI: Large Language Models Are Poor Medical Coders](https://ai.nejm.org/doi/full/10.1056/AIdbp2300040)
- [UASI: Coding Possible Diagnoses Inpatient vs Outpatient](https://www.uasisolutions.com/coding-possible-diagnoses-inpatient-vs-outpatient-rules-explained)
- [EmblemHealth: Sequela Diagnosis Codes](https://www.emblemhealth.com/providers/claims-corner/coding/use-of-sequela-diagnosis-codes)
- [EmblemHealth: Correct Laterality Policy](https://www.emblemhealth.com/providers/claims-corner/coding/correct-laterality-icd-10-cm-diagnosis-coding-policy)

---

*This document is core intellectual property for the Healthcare Digital FTE project. It encodes months of research into ICD-10-CM coding rules that the AI system must enforce. Every rule has been traced to its guideline section reference and validated against authoritative sources.*
