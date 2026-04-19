# CC/MCC Reference — Conditions and DRG Tier Implications

## Definitions

**CC** (Complication/Comorbidity): secondary diagnosis that
increases resource consumption. Upgrades base DRG one tier.

**MCC** (Major CC): secondary diagnosis that significantly
increases resource consumption. Upgrades DRG two tiers.

One MCC upgrades the entire case. A single documented MCC
condition can add $3,000-$8,000 in reimbursement.

---

## Top 10 CC Conditions (frequently underdocumented)

1. **E11.22** — T2DM with diabetic CKD
2. **I48.0/I48.1** — Paroxysmal/persistent AFib
3. **D62** — Acute posthemorrhagic anemia
4. **E66.01** — Morbid obesity (BMI >= 40)
5. **J44.1** — COPD with acute exacerbation
6. **I82.4x** — DVT of lower extremity
7. **E87.1** — Hyponatremia
8. **N18.3/N18.4** — CKD stage 3/4
9. **F10.20** — Alcohol dependence, uncomplicated
10. **G47.33** — Obstructive sleep apnea

---

## Top 10 MCC Conditions (highest revenue impact)

1. **A41.x + R65.20** — Sepsis with severe sepsis
2. **N17.x** — Acute kidney injury
3. **J96.0x** — Acute respiratory failure
4. **G93.41** — Metabolic encephalopathy
5. **E43** — Severe protein-calorie malnutrition
6. **L89.x03/x04** — Pressure ulcer stage 3/4
7. **F10.231** — Alcohol dependence with withdrawal delirium
8. **I50.21/I50.23** — Acute systolic/acute-on-chronic systolic HF
9. **J44.0** — COPD with acute lower respiratory infection
10. **E08.10-E13.10** — Diabetes with ketoacidosis

---

## DRG Tier Implications

Most DRG families have three tiers:

```
DRG Family: Heart Failure & Shock
  DRG 291 — with MCC     -> Weight ~1.76 -> ~$11,400
  DRG 292 — with CC      -> Weight ~1.21 -> ~$7,800
  DRG 293 — without CC/MCC -> Weight ~0.83 -> ~$5,400

Revenue difference: 291 vs 293 = ~$7,500 per case
```

How it works:
- Patient admitted with principal diagnosis
- If NO secondary diagnoses are CC or MCC -> lowest tier DRG
- If ANY secondary diagnosis is CC -> middle tier
- If ANY secondary diagnosis is MCC -> highest tier

---

## Detecting CC/MCC Upgrade Opportunities

1. Check if note mentions a condition without CC/MCC-qualifying
   specificity (e.g., "heart failure" without type/acuity)
2. Check labs for thresholds that imply undiagnosed MCC conditions
   (creatinine rise -> AKI, lactate -> sepsis, low albumin -> malnutrition)
3. Check medications that imply undocumented conditions
   (insulin -> diabetes; CIWA protocol -> alcohol withdrawal)
4. If CC/MCC upgrade available: generate CDI query
5. Never assume the diagnosis — query the physician
