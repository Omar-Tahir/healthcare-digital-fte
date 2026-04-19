# Skill: DRG Optimization

**Domain:** MS-DRG assignment and revenue impact calculation  
**Source research:** DISC-002, DESIGN-001  
**Used by:** DRG agent, coding agent, PROMPT-003  
**Read before:** Any work on `src/core/drg/grouper.py`,
`src/agents/drg_agent.py`

---

## Section 1 — How DRG Assignment Works

### MS-DRG = Medical Severity Diagnosis Related Group

CMS groups inpatient stays into ~760 MS-DRGs based on:
1. **Principal diagnosis** — determines the MDC (Major
   Diagnostic Category) and base DRG family
2. **Secondary diagnoses** — CC/MCC status determines
   which tier within the DRG family
3. **Procedures performed** — surgical DRGs vs medical DRGs
4. **Patient age** — affects some DRG assignments
5. **Discharge status** — death, transfer, AMA affect payment

### The Three-Way Split

Most DRG families have three tiers:

```
DRG Family: Heart Failure & Shock
├── DRG 291 — with MCC     → Weight ~1.76  → ~$11,400
├── DRG 292 — with CC      → Weight ~1.21  → ~$7,800
└── DRG 293 — without CC/MCC → Weight ~0.83 → ~$5,400

Revenue difference: 291 vs 293 = ~$7,500 per case
```

**How it works:**
- Patient admitted with principal diagnosis I50.9 (HF)
- If NO secondary diagnoses are CC or MCC → DRG 293
- If ANY secondary diagnosis is CC → DRG 292
- If ANY secondary diagnosis is MCC → DRG 291

**One MCC upgrades the entire case.** A single documented
MCC condition can add $3,000-$8,000 in reimbursement.

---

## Section 2 — Top 10 DRG Families With Revenue Impact

### 1. Sepsis (DRG 870-872)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 870 | Sepsis with MV >96 hours | ~4.47 | ~$49,690 |
| 871 | Sepsis without MV >96 hours, with MCC | ~1.80 | ~$13,357 |
| 872 | Sepsis without MV >96 hours, without MCC | ~0.93 | ~$6,931 |

**Revenue gap:** 870 vs 872 = ~$42,759. Key: document
organism, severity, organ dysfunction, ventilator hours.

### 2. Heart Failure & Shock (DRG 291-293)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 291 | Heart failure & shock with MCC | ~1.76 | ~$11,400 |
| 292 | With CC | ~1.21 | ~$7,800 |
| 293 | Without CC/MCC | ~0.83 | ~$5,400 |

**Revenue gap:** 291 vs 293 = ~$7,500. Key: specify HF type
(systolic/diastolic) and acuity (acute/chronic/acute-on-chronic).

### 3. COPD (DRG 190-192)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 190 | COPD with MCC | ~1.42 | ~$9,200 |
| 191 | With CC | ~0.97 | ~$6,300 |
| 192 | Without CC/MCC | ~0.72 | ~$4,700 |

**Revenue gap:** 190 vs 192 = ~$4,500. Key: document
"acute exacerbation" and any associated conditions.

### 4. Renal Failure (DRG 682-684)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 682 | Renal failure with MCC | ~1.63 | ~$10,600 |
| 683 | With CC | ~1.01 | ~$6,600 |
| 684 | Without CC/MCC | ~0.72 | ~$4,700 |

**Revenue gap:** 682 vs 684 = ~$5,900. Key: document
AKI stage, etiology, and link to other conditions.

### 5. Simple Pneumonia (DRG 193-195)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 193 | Simple pneumonia with MCC | ~1.49 | ~$9,700 |
| 194 | With CC | ~0.97 | ~$6,300 |
| 195 | Without CC/MCC | ~0.69 | ~$4,500 |

**Revenue gap:** 193 vs 195 = ~$5,200. Key: document
organism specificity and any secondary MCC conditions.

### 6. GI Hemorrhage (DRG 377-379)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 377 | GI hemorrhage with MCC | ~1.69 | ~$11,000 |
| 378 | With CC | ~1.07 | ~$7,000 |
| 379 | Without CC/MCC | ~0.72 | ~$4,700 |

**Revenue gap:** 377 vs 379 = ~$6,300.

### 7. Esophagitis & GI Misc (DRG 391-392)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 391 | With MCC | ~1.39 | ~$9,000 |
| 392 | Without MCC | ~0.77 | ~$5,000 |

**Revenue gap:** ~$4,000.

### 8. Cellulitis (DRG 602-603)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 602 | Cellulitis with MCC | ~1.50 | ~$9,800 |
| 603 | Without MCC | ~0.82 | ~$5,300 |

**Revenue gap:** ~$4,500.

### 9. Nutritional & Metabolic Disorders (DRG 640-641)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 640 | With MCC | ~1.34 | ~$8,700 |
| 641 | Without MCC | ~0.72 | ~$4,700 |

**Revenue gap:** ~$4,000. Key: document malnutrition severity.

### 10. Hypertension (DRG 304-305)

| DRG | Description | Weight | Avg Payment |
|-----|------------|--------|-------------|
| 304 | With MCC | ~1.11 | ~$7,200 |
| 305 | Without MCC | ~0.61 | ~$4,000 |

**Revenue gap:** ~$3,200. But: linking HTN + HF shifts
from DRG 304-305 family to DRG 291-293 family (HF & Shock)
— additional ~$4,000-$7,000 via DRG family shift.

---

## Section 3 — CC and MCC Upgrade Checklist

When reviewing a note, check these 10 conditions that are
commonly present but undocumented (from DISC-002 Section C):

| # | Condition | Detection Method | CC/MCC |
|---|-----------|-----------------|--------|
| 1 | AKI | Creatinine rise ≥0.3 or ≥1.5x baseline | MCC |
| 2 | Malnutrition | BMI <18.5, albumin <3.0, weight loss | CC/MCC |
| 3 | Encephalopathy | AMS + metabolic derangement | MCC |
| 4 | Respiratory failure | O2 sat <90%, PaO2 <60, on vent/BiPAP | MCC |
| 5 | Morbid obesity | BMI ≥40 | CC |
| 6 | CKD stage | Documented DM + CKD not linked | CC |
| 7 | Hyponatremia | Sodium <135 | CC |
| 8 | Coagulopathy | INR >3.5 on warfarin | CC |
| 9 | Alcohol dependence | CIWA protocol + "alcohol use" only | CC/MCC |
| 10 | Pressure ulcer | Wound care staging vs physician note | MCC |

**For each:** If clinical evidence exists but physician has
not documented the diagnosis, generate a CDI query (see
cdi-query-writing Skill). Never assume the diagnosis.

---

## Section 4 — DRG Calculation for AI Systems

### How to Calculate DRG Impact

```python
# Pseudocode for DRG impact calculation
current_codes = get_existing_codes(encounter)
current_drg = grouper.assign(current_codes)

proposed_codes = current_codes + [new_suggestion]
proposed_drg = grouper.assign(proposed_codes)

impact = DRGImpact(
    current_drg=current_drg.number,
    current_weight=current_drg.weight,
    current_payment=current_drg.weight * base_rate,
    proposed_drg=proposed_drg.number,
    proposed_weight=proposed_drg.weight,
    proposed_payment=proposed_drg.weight * base_rate,
    delta=proposed_drg.weight * base_rate - current_drg.weight * base_rate,
    upgrade_reason=f"Adding {new_code} ({cc_status})",
)
```

### When to Show DRG Impact

Always. Every coding suggestion in the coder review UI
includes its DRG impact. The coder needs this information to
prioritize review and understand the financial significance
of each suggestion.

### Compliance Guardrail

If DRG improvement > $5,000 from a single code addition,
soft guardrail G-SOFT-003 triggers a compliance review flag.
This is not a block — it is a flag that says "this is a
high-value change, ensure documentation fully supports it."

### CFO Reporting Language

DRG impact is reported in plain English for CFO dashboards:

```
"Adding acute kidney injury (N17.9) to this encounter
upgrades the DRG from 293 (Heart Failure without CC/MCC)
to 291 (Heart Failure with MCC), increasing expected
reimbursement by approximately $7,500."
```

Never report in medical jargon. The buyer is the CFO
(Constitution Article IV.2).

---

## MCP Tool Usage

- `mcp_drg_grouper(codes)` — compute MS-DRG from a code set
- `mcp_drg_weight(drg_number)` — get relative weight and
  payment estimate for a DRG
- Use MCP tools for real-time DRG calculations. Use this Skill
  for understanding DRG logic and interpreting results.
