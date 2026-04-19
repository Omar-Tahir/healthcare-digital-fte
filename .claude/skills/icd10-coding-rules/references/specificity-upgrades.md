# Top 20 Specificity Upgrades — Revenue Impact Reference

Source: DISC-002 research. Ordered by revenue impact.

Each row shows: non-specific documentation -> specific
documentation, code change, revenue impact, and what triggers
the CDI query.

---

| # | Non-Specific -> Specific | Code Change | Revenue Impact | CDI Trigger |
|---|------------------------|-------------|---------------|-------------|
| 1 | "Sepsis" -> "Severe sepsis due to E.coli with AKI" | A41.9 -> A41.51+R65.20+N17.9 | $42,759/case | Organism + organ dysfunction in labs |
| 2 | "HTN" + "CHF" separate -> hypertensive heart disease | I10+I50.9 -> I11.0+I50.x | $3,000-$9,000 | HTN and HF both documented separately |
| 3 | "Heart failure" -> "Acute on chronic systolic HF" | I50.9 -> I50.23 | $7,500/case | HF without type + acuity; BNP available |
| 4 | "Respiratory distress" -> "Acute respiratory failure" | R06.00 -> J96.01 | $4,000-$10,000 | O2 sat / vent status supports RF |
| 5 | "Confusion" -> "Metabolic encephalopathy" | R41.82 -> G93.41 | $4,000-$10,000 | AMS + metabolic derangement present |
| 6 | "Poor appetite" -> "Severe protein-calorie malnutrition" | R63.4 -> E43 | $3,000-$9,000 | BMI <18.5 + albumin <3.0 |
| 7 | Creatinine rise, AKI not stated -> AKI documented | Not coded -> N17.9 | $3,000-$8,000 | Cr rise >= 0.3 in 48h or >= 1.5x baseline |
| 8 | "Alcohol use" -> "Alcohol dependence with withdrawal" | F10.10 -> F10.231 | $3,000-$7,000 | CIWA protocol ordered |
| 9 | "Pneumonia" -> "Pneumonia due to Pseudomonas" | J18.9 -> J15.1 | $2,000-$6,000 | Culture results available |
| 10 | "COPD" -> "Acute exacerbation of COPD" | J44.9 -> J44.1 | $2,000-$5,000 | Symptom worsening + treatment escalation |
| 11 | "Pressure ulcer" -> "Stage 3 pressure ulcer of sacrum" | L89.90 -> L89.153 | $3,000-$8,000 | Wound care staging documented |
| 12 | "Diabetes" -> "T2DM with diabetic CKD" | E11.9 -> E11.22+N18.x | $1,500-$4,000 | DM + CKD both documented separately |
| 13 | "DVT" -> "Acute DVT of right femoral vein" | I82.40 -> I82.411 | $1,500-$3,000 | Laterality in imaging report |
| 14 | "Atrial fibrillation" -> "Persistent atrial fibrillation" | I48.91 -> I48.1 | $1,500-$3,000 | AFib type in cardiology notes |
| 15 | "Anemia" -> "Acute blood loss anemia" | D64.9 -> D62 | $1,500-$3,000 | Hgb drop + transfusion documented |
| 16 | "Obese" -> "Morbid obesity, BMI 42" | E66.9 -> E66.01+Z68.42 | $1,000-$3,000 | BMI >= 40 documented |
| 17 | "Stroke" -> "Acute ischemic stroke, right MCA" | I63.9 -> I63.511 | $0 DRG | Quality metric — no DRG change |
| 18 | "Heart attack" -> "Acute STEMI, LAD territory" | I21.9 -> I21.01 | $0 DRG | Quality metric — no DRG change |
| 19 | "Pancreatitis" -> "Acute alcoholic pancreatitis" | K85.9 -> K85.20 | $0 DRG | SOI/ROM only |
| 20 | "UTI" -> "UTI due to E. coli" | N39.0 -> N39.0+B96.20 | $0 DRG | Surveillance only |
