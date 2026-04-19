---
name: drg-optimization
version: "2.0.0"
description: >
  Use this skill whenever working on DRG calculation, revenue impact analysis, coding suggestion ranking, CFO-facing reports, or any component that computes or displays financial impact of coding changes. Triggers on: DRG, diagnosis related group, revenue impact, reimbursement, CC/MCC upgrade, DRG weight, DRG tier, base rate, case mix index, coding improvement value, CFO dashboard, revenue narrative, compliance review threshold, the $5000 guardrail (G-SOFT-003), or any dollar-amount calculation from coding changes. Also use when editing src/core/drg/, src/agents/drg_agent.py, src/prompts/drg_analysis.py, or any code that calculates or displays financial amounts. If the task involves money, revenue, or financial impact of coding — load this skill.
allowed-tools: Read, Bash
license: Proprietary
---

# DRG Optimization

## How DRG Assignment Works

MS-DRG = Medical Severity Diagnosis Related Group

CMS groups inpatient stays into ~760 MS-DRGs based on:
1. **Principal diagnosis** -> MDC + base DRG family
2. **Secondary diagnoses** -> CC/MCC status -> tier
3. **Procedures performed** -> surgical vs medical DRGs
4. **Patient age** -> affects some assignments
5. **Discharge status** -> death, transfer, AMA affect payment

### The Three-Way Split

Most DRG families have three tiers:

```
DRG Family: Heart Failure & Shock
  DRG 291 — with MCC     -> Weight ~1.76 -> ~$11,400
  DRG 292 — with CC      -> Weight ~1.21 -> ~$7,800
  DRG 293 — without CC/MCC -> Weight ~0.83 -> ~$5,400

Revenue difference: 291 vs 293 = ~$7,500 per case
```

One MCC upgrades the entire case — a single documented
MCC condition can add $3,000-$8,000 in reimbursement.

## MCP Tools — Use These, Do Not Embed Tables

- mcp_drg_grouper(codes) -> compute MS-DRG from a code set
- mcp_drg_weight(drg_number) -> relative weight + payment
- mcp_drg_impact(current, addition) -> revenue delta

Do NOT embed full DRG weight tables in context.
Call mcp_drg_calculate() instead — saves ~5,000 tokens.

## Top 10 DRG Families (Revenue Impact Order)

| # | Family | DRG (MCC/CC/None) | Weights | Revenue Gap |
|---|--------|-------------------|---------|-------------|
| 1 | Sepsis | 870/871/872 | 4.47/1.80/0.93 | ~$42,759 |
| 2 | Heart Failure & Shock | 291/292/293 | 1.76/1.21/0.83 | ~$7,500 |
| 3 | GI Hemorrhage | 377/378/379 | 1.69/1.07/0.72 | ~$6,300 |
| 4 | Renal Failure | 682/683/684 | 1.63/1.01/0.72 | ~$5,900 |
| 5 | Simple Pneumonia | 193/194/195 | 1.49/0.97/0.69 | ~$5,200 |
| 6 | Cellulitis | 602/—/603 | 1.50/—/0.82 | ~$4,500 |
| 7 | COPD | 190/191/192 | 1.42/0.97/0.72 | ~$4,500 |
| 8 | Nutritional & Metabolic | 640/—/641 | 1.34/—/0.72 | ~$4,000 |
| 9 | Esophagitis & GI Misc | 391/—/392 | 1.39/—/0.77 | ~$4,000 |
| 10 | Hypertension | 304/—/305 | 1.11/—/0.61 | ~$3,200 |

Note: Linking HTN + HF shifts from DRG 304-305 to DRG 291-293
— additional ~$4,000-$7,000 via DRG family shift.

## CC/MCC Upgrade Checklist

When reviewing a note, check these conditions that are
commonly present but undocumented:

| # | Condition | Detection Method | CC/MCC |
|---|-----------|-----------------|--------|
| 1 | AKI | Creatinine rise >= 0.3 or >= 1.5x baseline | MCC |
| 2 | Malnutrition | BMI < 18.5, albumin < 3.0, weight loss | CC/MCC |
| 3 | Encephalopathy | AMS + metabolic derangement | MCC |
| 4 | Respiratory failure | O2 sat < 90%, PaO2 < 60, on vent/BiPAP | MCC |
| 5 | Morbid obesity | BMI >= 40 | CC |
| 6 | CKD stage | Documented DM + CKD not linked | CC |
| 7 | Hyponatremia | Sodium < 135 | CC |
| 8 | Coagulopathy | INR > 3.5 on warfarin | CC |
| 9 | Alcohol dependence | CIWA protocol + "alcohol use" only | CC/MCC |
| 10 | Pressure ulcer | Wound care staging vs physician note | MCC |

For each: if clinical evidence exists but physician has
not documented the diagnosis, generate a CDI query. Never
assume the diagnosis.

## Compliance Guardrail

If DRG improvement > $5,000 from a single code addition,
soft guardrail G-SOFT-003 triggers a compliance review flag.
Not a block — a flag that says "high-value change, ensure
documentation fully supports it."

## CFO-Facing Language

Never say: "The MCC capture rate improved DRG weight by 0.8"
Always say: "Documenting acute kidney injury generated
             $4,200 in additional reimbursement for this case"

The buyer is the CFO (Constitution Article IV.2). Report
in plain English, in revenue terms.

## For Full Reference

See references/drg-families.md (complete top 20 list)
See references/cc-mcc-lists.md (full CC and MCC code lists)
