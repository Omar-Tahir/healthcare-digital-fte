# Skill: Payer Denial Patterns

**Domain:** Insurance claim denial prevention  
**Source research:** DISC-004  
**Used by:** Coding agent (Phase 1 denial prevention),
Prior Auth agent (Phase 2), Appeal agent (Phase 3)  
**Read before:** Any work on denial prevention, payer rules,
or prior authorization

---

## Section 1 — The 8 Denial Categories

Source: DISC-004 research, Change Healthcare Denials Index.

### 1. Prior Authorization Denials (~23% of all denials)

**Primary cause:** Service performed without required PA, or
PA expired/mismatched.

**Prevention:** Check payer PA requirements before scheduling.
Verify PA number matches CPT code on claim. Alert if PA
expiring within 30 days.

**AI automation potential:** HIGH — PA requirement lists are
deterministic and published by payers.

### 2. Medical Necessity Denials (~19% of all denials)

**Primary cause:** Documentation does not support clinical
need for the service under LCD/NCD criteria.

**Prevention:** Ensure diagnosis codes meet LCD-approved
indications for the procedure. Flag insufficient
documentation before claim submission.

**AI automation potential:** HIGH — LCD criteria are published
and can be encoded as rules.

### 3. Coding Error Denials (~15% of all denials)

**Primary cause:** NCCI edit violations, unbundling, modifier
misuse, diagnosis-procedure mismatch.

**Prevention:** Rules engine checks NCCI edits, MUE limits,
and diagnosis-procedure linkage before submission.

**AI automation potential:** VERY HIGH — NCCI edits are
deterministic CMS-published tables updated quarterly.

### 4. Timely Filing Denials (~12% of all denials)

**Primary cause:** Claim submitted after payer filing
deadline. 100% preventable operational failure.

**Prevention:** Track filing deadlines per payer. Alert when
approaching deadline. Auto-escalate at 75% of deadline.

**AI automation potential:** VERY HIGH — deadlines are
deterministic per payer.

### 5. Duplicate Claim Denials (~10% of all denials)

**Primary cause:** Same claim submitted twice, often due to
system errors or rebilling without proper adjustment.

**Prevention:** Claim deduplication check before submission.
Track claim status to avoid rebilling active claims.

**AI automation potential:** HIGH.

### 6. Patient Eligibility Denials (~8% of all denials)

**Primary cause:** Patient not covered on date of service,
wrong insurance information, coordination of benefits issues.

**Prevention:** Real-time eligibility verification before
service. Flag coverage gaps.

**AI automation potential:** MEDIUM — requires real-time payer
connectivity.

### 7. Missing Information Denials (~7% of all denials)

**Primary cause:** Incomplete claim data (missing modifier,
missing referring provider, missing POS code).

**Prevention:** Claim completeness validation before
submission. Check all required fields populated.

**AI automation potential:** VERY HIGH — field validation
is deterministic.

### 8. Contractual/Bundling Denials (~6% of all denials)

**Primary cause:** Service bundled into another service per
payer contract. Payer-specific bundling rules beyond NCCI.

**Prevention:** Maintain payer-specific bundling rules.
Alert when code pair is bundled per specific payer contract.

**AI automation potential:** MEDIUM — payer-specific rules
require per-contract configuration.

---

## Section 2 — Medical Necessity Documentation

### CMS LCD Requirements

Local Coverage Determinations (LCDs) define which diagnosis
codes support medical necessity for specific procedures.
A procedure may be clinically indicated but denied if the
documented diagnosis doesn't appear on the LCD's covered
ICD-10 code list.

**AI system requirement:** Check the LCD for the relevant
MAC jurisdiction. A procedure covered in Florida (First Coast)
may have different criteria in California (Noridian).

### Top 10 Procedures Requiring Specific Diagnosis Support

| # | Procedure | Required Documentation |
|---|-----------|----------------------|
| 1 | Inpatient admission | Two-midnight rule rationale; expected LOS ≥2 midnights |
| 2 | MRI spine | Radiculopathy or neurological deficit; failed 4-6 weeks conservative care |
| 3 | Total knee replacement | Failed conservative treatment (PT, injections, NSAIDs); bone-on-bone imaging |
| 4 | Spinal fusion | 6+ months failed conservative care; MRI findings; neurological deficit |
| 5 | Cardiac catheterization | Abnormal stress test OR acute coronary syndrome presentation |
| 6 | Bariatric surgery | BMI ≥40 (or ≥35 with comorbidities); 3-6 month supervised diet; psych eval |
| 7 | Sleep study | ESS ≥10 or documented witnessed apneas; BMI documentation |
| 8 | Home health services | Face-to-face encounter; homebound status; skilled nursing need |
| 9 | CT abdomen/pelvis | GI symptoms documented; prior imaging if non-emergent |
| 10 | Genetic testing | Personal/family history; genetic counseling documentation |

### How Documentation Quality Affects Denials

**Strong documentation that survives review:**
- Specific symptoms with onset, duration, severity
- Failed prior treatments with dates and outcomes
- Objective test results supporting clinical decision
- Clear rationale connecting diagnosis to procedure

**Weak documentation that triggers denials:**
- "Back pain" without neurological findings (for MRI)
- "Admit for observation" without clinical rationale
- Procedure ordered without documented prior workup
- Generic diagnosis codes (.9 unspecified) for procedures
  requiring specific indications

---

## Section 3 — Prior Auth Quick Reference

Phase 2 feature, but useful context for coding agent now.

### Top 20 CPT Codes Requiring Prior Auth

| # | CPT | Description | Payers Requiring PA |
|---|-----|-------------|-------------------|
| 1 | 72141-72159 | MRI Spine | All major commercial |
| 2 | 27447 | Total knee replacement | All |
| 3 | 27130 | Total hip replacement | All |
| 4 | 22551-22612 | Spinal fusion | All |
| 5 | 70551-70553 | MRI Brain | UHC, Aetna, Cigna, Anthem |
| 6 | 74176-74178 | CT Abdomen/Pelvis (non-emergent) | Most commercial |
| 7 | 71250-71275 | CT Chest (non-emergent) | Most commercial |
| 8 | 43239 | EGD with biopsy | Some |
| 9 | 43644-43645 | Bariatric surgery | All |
| 10 | 29881 | Knee arthroscopy | Most |
| 11 | 47562-47564 | Lap cholecystectomy | Some |
| 12 | J0135 | Adalimumab (Humira) | All |
| 13 | J9271 | Pembrolizumab (Keytruda) | Most |
| 14 | J2323 | Natalizumab (Tysabri) | All |
| 15 | E0601 | CPAP device | Medicare + most commercial |
| 16 | K0823-K0886 | Power wheelchair | Medicare + most commercial |
| 17 | J1745 | Infliximab (Remicade) | All |
| 18 | J3490 | GLP-1 agonists (various) | All |
| 19 | 93451-93462 | Cardiac catheterization (elective) | Most |
| 20 | 77078 | Bone density (DEXA) | Some — frequency limits |

**Exemptions:** Emergency procedures generally exempt.
Inpatient orders exempt at most payers. Cancer staging
follow-up often exempt.

### How Documentation Affects PA Approval

86% of PA denials are eventually overturned on appeal (AMA
2023), indicating initial denials are often due to
documentation gaps rather than clinical inappropriateness.

**The CDI agent can help PA approval** by ensuring
documentation includes the clinical criteria payers require
BEFORE the PA request is submitted.

---

## Section 4 — Timely Filing Deadlines

### By Payer Type

| Payer | Filing Deadline | Appeal Deadline |
|-------|----------------|----------------|
| Medicare | 365 days from DOS | 120 days from determination |
| Medicaid | 90-365 days (varies by state) | Varies |
| UnitedHealthcare | 90-180 days | 180 days |
| Aetna | 90-180 days | 180 days |
| Cigna | 90-365 days | 365 days |
| Anthem/BCBS | 90-180 days (varies by state plan) | 180 days |
| Humana | 180 days | 180 days |
| Tricare | 365 days | 90 days |

**Shortest deadline:** New York Medicaid = 90 days.

### Alert Thresholds

| Threshold | Alert Level | Action |
|-----------|------------|--------|
| 75% of deadline | Warning | Flag in coder worklist |
| 90% of deadline | Urgent | Escalate to billing manager |
| 95% of deadline | Critical | Auto-escalate to director |
| 100% of deadline | Too late | Log as timely filing miss |

**Timely filing denials are 100% preventable.** They are
pure operational failures that our system should eliminate
entirely through automated deadline tracking.

---

## MCP Tool Usage

- No MCP tools specific to denial patterns in Phase 1
- Phase 2 will add: `mcp_pa_check(cpt, payer)` — check if
  prior auth required for a CPT code by specific payer
- Phase 3 will add: `mcp_denial_predict(claim)` — predict
  denial probability for a claim before submission
