# Skill: ICD-10 Coding Rules

**Domain:** ICD-10-CM Official Coding Guidelines  
**Source research:** DISC-001, DISC-002  
**Used by:** Rules engine (DESIGN-001), Guardrails (DESIGN-003),
Coding agent  
**Read before:** Any work on `src/core/icd10/`, `src/agents/coding_agent.py`

---

## Section 1 — The Five Rules That Cannot Be Broken

These are Constitution Article II.3 hard constraints. The rules
engine enforces them deterministically. Violations raise
`CodingGuidelineViolationError` — a hard stop, not a warning.

### Rule 1: Excludes 1 — Never Code Together

**Definition (ICD-10-CM Official Guidelines I.A.12.a):**
"When an Excludes1 note appears under a code, it is not to
be used at the same time as the code above the note. An
Excludes1 is used when two conditions cannot occur together,
such as a congenital form versus an acquired form of the same
condition."

**Example pair:**
- E10.x (Type 1 diabetes) EXCLUDES 1 E11.x (Type 2 diabetes)
- A patient cannot have both Type 1 and Type 2 diabetes
- If both appear in documentation, query the physician

**Detection:** The rules engine maintains a lookup table of
all Excludes 1 pairs from the ICD-10-CM Tabular List. Every
suggestion set is checked pairwise. O(n²) but n ≤ 25 codes
so <1ms.

**Consequence of violation:** Claim denial (automatic edit
rejection by clearinghouse). Repeated violations trigger
payer audit. Systematic Excludes 1 violations = False Claims
Act exposure.

### Rule 2: Outpatient Uncertain Diagnosis

**Definition (Section IV.H):**
"Do not code diagnoses documented as 'probable,' 'suspected,'
'questionable,' 'rule out,' or 'working diagnosis' or other
similar terms indicating uncertainty. Rather, code the
condition(s) to the highest degree of certainty for that
encounter/visit, such as symptoms, signs, abnormal test
results, or other reason for the visit."

**Trigger words (complete list):**
probable, suspected, likely, questionable, possible, rule out,
still to be ruled out, working diagnosis, concern for,
appears to be, consistent with, compatible with, indicative of,
suggestive of, comparable with

**What to code instead:** The presenting sign or symptom.

**Example:**
- "Possible pneumonia" in outpatient → code R05.9 (Cough)
  or R06.02 (Shortness of breath), NOT J18.9
- "Probable DVT" in outpatient → code R60.0 (Localized
  edema), NOT I82.40

**Inpatient exception (Section II.H):** Inpatient uncertain
diagnoses ARE coded as if confirmed. "Probable pneumonia" in
inpatient → code J18.9.

**"Ruled out" is different:** If a condition has been "ruled
out" at discharge, do NOT code it in ANY setting. "Ruled out"
means eliminated, not uncertain.

**Critical:** This rule depends entirely on encounter class.
OBSENC (observation status) = OUTPATIENT rules, even though
patient is physically in the hospital.

### Rule 3: Mandatory Sequencing (Code First / Use Additional)

**Definition (Section I.A.13):** When a code has a "Code First"
instruction, the underlying condition must be listed before it.
When a code has "Use Additional Code," the specified code must
follow.

**Top 5 examples:**
1. H36 (Retinal disorder in diseases elsewhere) → Code First
   E08-E13 (diabetes). Diabetes must precede retinopathy.
2. G63 (Polyneuropathy in diseases elsewhere) → Code First
   underlying disease. E11.42 must precede G63.
3. N08 (Glomerular disorder in diseases elsewhere) → Code
   First underlying disease.
4. M14.6x (Neuropathic arthropathy in diseases elsewhere) →
   Code First underlying disease.
5. J17 (Pneumonia in diseases elsewhere) → Code First
   underlying disease.

**Manifestation codes can NEVER be principal diagnosis.**
If the title contains "in diseases classified elsewhere,"
it is a manifestation code.

**"Code Also" is different:** Sequencing is discretionary.
Both codes are required but either can be first based on
the circumstances of the encounter.

### Rule 4: Combination Codes — When Mandatory

**Definition (Section I.B.9):** When a combination code exists
that classifies two related conditions, use the combination
code — do not code the components separately.

**Top 5 examples:**
1. Type 2 DM + CKD → Use E11.22 (T2DM with diabetic CKD),
   NOT E11.9 + N18.x separately. Causal relationship is
   assumed per guideline I.C.4.a.6.
2. Type 2 DM + peripheral neuropathy → Use E11.42, NOT
   E11.9 + G63. Causal relationship assumed.
3. Hypertension + heart failure → Use I11.0 (Hypertensive
   heart disease with HF), NOT I10 + I50.x. Causal
   relationship assumed per guideline I.C.9.a.1.
4. Hypertension + CKD → Use I12.x, NOT I10 + N18.x.
   Causal relationship assumed per guideline I.C.9.a.2.
5. Hypertension + heart disease + CKD → Use I13.x when
   all three present. Requires additional N18.x for stage.

**Detection:** Before suggesting component codes separately,
check if a combination code exists. MCP tool
`mcp_icd10_lookup` returns `requires_additional` and
`code_also` fields.

### Rule 5: POA Indicator Accuracy

**POA indicator definitions:**
- **Y** — Present at time of inpatient admission order
- **N** — Developed after admission order
- **U** — Documentation insufficient to determine
- **W** — Provider clinically unable to determine
- **Blank** — Exempt from POA reporting (external cause codes,
  certain perinatal/congenital codes)

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

---

## Section 2 — Top 20 Specificity Upgrades

Ordered by revenue impact. Source: DISC-002 research.

| # | Non-Specific → Specific | Code Change | Revenue Impact | CDI Query? |
|---|------------------------|-------------|---------------|------------|
| 1 | "Sepsis" → "Severe sepsis due to E.coli with AKI" | A41.9 → A41.51+R65.20+N17.9 | $42,759/case | Yes — organism + organ dysfunction |
| 2 | "HTN" + "CHF" separate → hypertensive heart disease | I10+I50.9 → I11.0+I50.x | $3,000-$9,000 | Yes — causal link |
| 3 | "Heart failure" → "Acute on chronic systolic HF" | I50.9 → I50.23 | $7,500/case | Yes — type + acuity |
| 4 | "Respiratory distress" → "Acute respiratory failure" | R06.00 → J96.01 | $4,000-$10,000 | Yes — O2/vent status |
| 5 | "Confusion" → "Metabolic encephalopathy" | R41.82 → G93.41 | $4,000-$10,000 | Yes — etiology |
| 6 | "Poor appetite" → "Severe protein-calorie malnutrition" | R63.4 → E43 | $3,000-$9,000 | Yes — BMI + albumin |
| 7 | Creatinine rise, AKI not stated → AKI documented | Not coded → N17.9 | $3,000-$8,000 | Yes — KDIGO criteria |
| 8 | "Alcohol use" → "Alcohol dependence with withdrawal" | F10.10 → F10.231 | $3,000-$7,000 | Yes — CIWA protocol |
| 9 | "Pneumonia" → "Pneumonia due to Pseudomonas" | J18.9 → J15.1 | $2,000-$6,000 | Yes — culture results |
| 10 | "COPD" → "Acute exacerbation of COPD" | J44.9 → J44.1 | $2,000-$5,000 | Yes — symptom worsening |
| 11 | "Pressure ulcer" → "Stage 3 pressure ulcer of sacrum" | L89.90 → L89.153 | $3,000-$8,000 | Yes — wound care staging |
| 12 | "Diabetes" → "T2DM with diabetic CKD" | E11.9 → E11.22+N18.x | $1,500-$4,000 | Yes — complication link |
| 13 | "DVT" → "Acute DVT of right femoral vein" | I82.40 → I82.411 | $1,500-$3,000 | Yes — laterality |
| 14 | "Atrial fibrillation" → "Persistent atrial fibrillation" | I48.91 → I48.1 | $1,500-$3,000 | Yes — type |
| 15 | "Anemia" → "Acute blood loss anemia" | D64.9 → D62 | $1,500-$3,000 | Yes — Hgb drop + transfusion |
| 16 | "Obese" → "Morbid obesity, BMI 42" | E66.9 → E66.01+Z68.42 | $1,000-$3,000 | Yes — BMI documented |
| 17 | "Stroke" → "Acute ischemic stroke, right MCA" | I63.9 → I63.511 | $0 DRG | No — quality metric only |
| 18 | "Heart attack" → "Acute STEMI, LAD territory" | I21.9 → I21.01 | $0 DRG | No — quality metric only |
| 19 | "Pancreatitis" → "Acute alcoholic pancreatitis" | K85.9 → K85.20 | $0 DRG | No — SOI/ROM only |
| 20 | "UTI" → "UTI due to E. coli" | N39.0 → N39.0+B96.20 | $0 DRG | No — surveillance only |

---

## Section 3 — Inpatient vs Outpatient Rules Summary

| Rule | Inpatient | Outpatient |
|------|-----------|------------|
| Uncertain diagnosis | Code as confirmed | Code symptom instead |
| Principal diagnosis | Condition "after study" chiefly responsible for admission | First-listed = reason for visit |
| POA indicators | Required for all inpatient claims | Not applicable |
| Chronic conditions | Code if actively managed during stay | Code if addressed at encounter |
| "Ruled out" | Do NOT code (any setting) | Do NOT code (any setting) |

**Encounter class → coding setting:**
- IMP (inpatient) → INPATIENT rules
- AMB (ambulatory) → OUTPATIENT rules
- EMER (emergency) → OUTPATIENT rules
- OBSENC (observation) → OUTPATIENT rules (critical!)

**Observation-to-inpatient conversion:** When encounter class
changes from OBSENC to IMP, discard all previous coding
analysis and re-analyze under inpatient rules.

---

## Section 4 — CC and MCC Reference

**CC** (Complication/Comorbidity): secondary diagnosis that
increases resource consumption. Upgrades base DRG one tier.

**MCC** (Major CC): secondary diagnosis that significantly
increases resource consumption. Upgrades DRG two tiers.

### Top 10 CC Conditions (frequently underdocumented)

1. E11.22 — T2DM with diabetic CKD
2. I48.0/I48.1 — Paroxysmal/persistent AFib
3. D62 — Acute posthemorrhagic anemia
4. E66.01 — Morbid obesity (BMI ≥40)
5. J44.1 — COPD with acute exacerbation
6. I82.4x — DVT of lower extremity
7. E87.1 — Hyponatremia
8. N18.3/N18.4 — CKD stage 3/4
9. F10.20 — Alcohol dependence, uncomplicated
10. G47.33 — Obstructive sleep apnea

### Top 10 MCC Conditions (highest revenue impact)

1. A41.x + R65.20 — Sepsis with severe sepsis
2. N17.x — Acute kidney injury
3. J96.0x — Acute respiratory failure
4. G93.41 — Metabolic encephalopathy
5. E43 — Severe protein-calorie malnutrition
6. L89.x03/x04 — Pressure ulcer stage 3/4
7. F10.231 — Alcohol dependence with withdrawal delirium
8. I50.21/I50.23 — Acute systolic/acute-on-chronic systolic HF
9. J44.0 — COPD with acute lower respiratory infection
10. E08.10-E13.10 — Diabetes with ketoacidosis

### Detecting CC/MCC Upgrade Opportunities

```
1. Check if note mentions a condition without CC/MCC-qualifying
   specificity (e.g., "heart failure" without type/acuity)
2. Check labs for thresholds that imply undiagnosed MCC conditions
   (creatinine rise → AKI, lactate → sepsis, low albumin → malnutrition)
3. Check medications that imply undocumented conditions
   (insulin → diabetes; CIWA protocol → alcohol withdrawal)
4. If CC/MCC upgrade available: generate CDI query
5. Never assume the diagnosis — query the physician
```

---

## MCP Tool Usage

- `mcp_icd10_lookup(code)` — get Excludes 1 pairs, Code First
  instructions, CC/MCC status, billability for a specific code
- `mcp_icd10_search(term)` — find codes matching a clinical term
- Use MCP tools for specific code lookups. Use this Skill for
  rule logic and clinical reasoning patterns.
