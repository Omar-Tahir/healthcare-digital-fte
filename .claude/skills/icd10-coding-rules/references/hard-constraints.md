# ICD-10 Hard Constraints — Detailed Reference

These 5 rules are Constitution Article II.3 hard constraints.
Violations raise `CodingGuidelineViolationError` — a hard stop.

---

## Rule 1: Excludes 1 — Never Code Together

**Definition (ICD-10-CM Official Guidelines I.A.12.a):**
"When an Excludes1 note appears under a code, it is not to
be used at the same time as the code above the note. An
Excludes1 is used when two conditions cannot occur together,
such as a congenital form versus an acquired form of the same
condition."

**Example pairs:**
- E10.x (Type 1 diabetes) EXCLUDES 1 E11.x (Type 2 diabetes)
  A patient cannot have both Type 1 and Type 2 diabetes.
- J44.x (COPD) EXCLUDES 1 J43.x (Emphysema) when J44
  includes emphysema component.

**Detection:** The rules engine maintains a lookup table of
all Excludes 1 pairs from the ICD-10-CM Tabular List. Every
suggestion set is checked pairwise. O(n^2) but n <= 25 codes
so <1ms.

**Consequence of violation:** Claim denial (automatic edit
rejection by clearinghouse). Repeated violations trigger
payer audit. Systematic Excludes 1 violations = False Claims
Act exposure.

**What the AI gets wrong without this guidance:**
- Suggesting both E10.x and E11.x when note mentions "diabetes"
  and "insulin" (insulin use != Type 1)
- Missing Excludes 1 pairs that are at category level, not
  code level (the exclusion applies to all codes under the
  excluded category)

**Edge cases:**
- If both conditions truly documented, query the physician
  to clarify which applies
- Excludes 2 is different: "Not included here" — both CAN
  be coded together if documented

---

## Rule 2: Outpatient Uncertain Diagnosis

**Definition (Section IV.H):**
"Do not code diagnoses documented as 'probable,' 'suspected,'
'questionable,' 'rule out,' or 'working diagnosis' or other
similar terms indicating uncertainty."

**Complete trigger word list:**
probable, suspected, likely, questionable, possible, rule out,
still to be ruled out, working diagnosis, concern for,
appears to be, consistent with, compatible with, indicative of,
suggestive of, comparable with

**What to code instead:** The presenting sign or symptom.

**Examples:**
- "Possible pneumonia" in outpatient -> code R05.9 (Cough)
  or R06.02 (Shortness of breath), NOT J18.9
- "Probable DVT" in outpatient -> code R60.0 (Localized
  edema), NOT I82.40
- "Rule out PE" in ER (outpatient) -> code R06.02 (Dyspnea)
  or R07.9 (Chest pain), NOT I26.99

**Inpatient exception (Section II.H):** Inpatient uncertain
diagnoses ARE coded as if confirmed. "Probable pneumonia" in
inpatient -> code J18.9.

**"Ruled out" is different:** If a condition has been "ruled
out" at discharge, do NOT code it in ANY setting. "Ruled out"
means eliminated, not uncertain.

**Critical dependency:** This rule depends entirely on
encounter class. OBSENC (observation status) = OUTPATIENT
rules, even though patient is physically in the hospital.

**What the AI gets wrong without this guidance:**
- Applying inpatient rules to observation patients
- Treating "consistent with" as confirmed
- Confusing "rule out" (uncertain) with "ruled out" (excluded)

---

## Rule 3: Mandatory Sequencing (Code First / Use Additional)

**Definition (Section I.A.13):** When a code has a "Code First"
instruction, the underlying condition must be listed before it.
When a code has "Use Additional Code," the specified code must
follow.

**Top 5 mandatory pairings:**
1. H36 (Retinal disorder in diseases elsewhere) -> Code First
   E08-E13 (diabetes). Diabetes must precede retinopathy.
2. G63 (Polyneuropathy in diseases elsewhere) -> Code First
   underlying disease. E11.42 must precede G63.
3. N08 (Glomerular disorder in diseases elsewhere) -> Code
   First underlying disease.
4. M14.6x (Neuropathic arthropathy in diseases elsewhere) ->
   Code First underlying disease.
5. J17 (Pneumonia in diseases elsewhere) -> Code First
   underlying disease.

**Manifestation codes can NEVER be principal diagnosis.**
If the title contains "in diseases classified elsewhere,"
it is a manifestation code.

**"Code Also" is different:** Sequencing is discretionary.
Both codes are required but either can be first.

**What the AI gets wrong without this guidance:**
- Suggesting a manifestation code without the underlying
  condition code
- Placing manifestation code before etiology code
- Missing "Use Additional" requirements on combination codes
  (e.g., E11.22 requires N18.x for CKD stage)

---

## Rule 4: Combination Codes — When Mandatory

**Definition (Section I.B.9):** When a combination code exists
that classifies two related conditions, use the combination
code — do not code the components separately.

**Top 5 mandatory combination codes:**
1. Type 2 DM + CKD -> E11.22 (T2DM with diabetic CKD),
   NOT E11.9 + N18.x separately. Causal relationship assumed
   per guideline I.C.4.a.6.
2. Type 2 DM + peripheral neuropathy -> E11.42, NOT
   E11.9 + G63.
3. Hypertension + heart failure -> I11.0 (Hypertensive
   heart disease with HF), NOT I10 + I50.x. Causal
   relationship assumed per guideline I.C.9.a.1.
4. Hypertension + CKD -> I12.x, NOT I10 + N18.x.
   Causal relationship assumed per guideline I.C.9.a.2.
5. Hypertension + heart disease + CKD -> I13.x when
   all three present. Requires additional N18.x for stage.

**What the AI gets wrong without this guidance:**
- Suggesting I10 (HTN) + I50.x (HF) separately instead of
  I11.0 — CMS assumes causal relationship by guideline
- Suggesting E11.9 (DM unspecified) alongside a complication
  code instead of using the combination code
- Missing the required N18.x stage code with E11.22 or I12.x

---

## Rule 5: POA Indicator Accuracy

**POA indicator definitions:**
- **Y** — Present at time of inpatient admission order
- **N** — Developed after admission order
- **U** — Documentation insufficient to determine
- **W** — Provider clinically unable to determine
- **Blank** — Exempt from POA reporting

**Critical distinction: U vs W.**
- U = documentation problem (more info could resolve it)
- W = clinical judgment (unknowable even with complete docs)

**HAC penalty:** Incorrect N assignment on a Hospital-Acquired
Condition (14 categories including pressure ulcers, CAUTI,
falls, surgical site infections) can trigger Medicare payment
reduction.

**ER conditions are POA = Y.** Conditions developing in the ED
before the inpatient admission order are considered present on
admission.

**Temporal reasoning required:** The AI must determine whether
a condition existed before vs after the admission order, using
timestamps from labs, vitals, and clinical documentation.

**What the AI gets wrong without this guidance:**
- Marking ER-diagnosed conditions as POA = N
- Confusing U and W (U is fixable, W is not)
- Not checking temporal relationship between condition onset
  and admission order timestamp
