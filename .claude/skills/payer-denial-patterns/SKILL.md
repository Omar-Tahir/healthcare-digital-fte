---
name: payer-denial-patterns
version: "2.0.0"
description: >
  Use this skill whenever working on denial prevention, pre-submission claim validation, prior authorization checks, coding agent denial risk assessment, appeal letter generation, or any component that predicts or prevents insurance claim denials. Triggers on: denial, prior auth, PA, medical necessity, LCD, NCD, NCCI edit, timely filing, claim rejection, payer rules, unbundling, modifier, appeal, eligibility verification, filing deadline, documentation requirements for procedures, or any reference to insurance payer behavior. Also use when editing code related to claim submission, payer interaction, denial prediction, or appeal generation. If the task involves insurance, payers, claims, preventing rejections, or understanding why claims get denied — load this skill.
allowed-tools: Read
license: Proprietary
---

# Payer Denial Patterns

## The 8 Denial Categories

Source: DISC-004, Change Healthcare Denials Index.

| # | Category | % of Denials | AI Automation Potential |
|---|----------|-------------|----------------------|
| 1 | Prior Authorization | ~23% | HIGH |
| 2 | Medical Necessity | ~19% | HIGH |
| 3 | Coding Errors | ~15% | VERY HIGH |
| 4 | Timely Filing | ~12% | VERY HIGH |
| 5 | Duplicate Claims | ~10% | HIGH |
| 6 | Patient Eligibility | ~8% | MEDIUM |
| 7 | Missing Information | ~7% | VERY HIGH |
| 8 | Contractual/Bundling | ~6% | MEDIUM |

## Prevention by Category

### 1. Prior Authorization (~23%)

Cause: Service performed without required PA, or PA
expired/mismatched.
Prevention: Check PA requirements before scheduling. Verify
PA number matches CPT on claim. Alert if PA expiring < 30 days.

### 2. Medical Necessity (~19%)

Cause: Documentation does not support clinical need under
LCD/NCD criteria.
Prevention: Ensure diagnosis codes meet LCD-approved
indications. Flag insufficient documentation pre-submission.
Note: LCD criteria vary by MAC jurisdiction.

### 3. Coding Errors (~15%)

Cause: NCCI edit violations, unbundling, modifier misuse,
diagnosis-procedure mismatch.
Prevention: Rules engine checks NCCI edits, MUE limits,
and diagnosis-procedure linkage before submission.

### 4. Timely Filing (~12%)

Cause: Claim submitted after payer filing deadline.
100% preventable operational failure.
Prevention: Track deadlines per payer. Auto-escalate at 75%.

### 5. Duplicate Claims (~10%)

Cause: Same claim submitted twice.
Prevention: Deduplication check before submission.

### 6. Patient Eligibility (~8%)

Cause: Patient not covered on DOS, wrong insurance info.
Prevention: Real-time eligibility verification before service.

### 7. Missing Information (~7%)

Cause: Incomplete claim data (missing modifier, referring
provider, POS code).
Prevention: Field completeness validation before submission.

### 8. Contractual/Bundling (~6%)

Cause: Service bundled per payer contract (beyond NCCI).
Prevention: Maintain payer-specific bundling rules.

## Medical Necessity Documentation

### Top 10 Procedures Requiring Specific Diagnosis Support

| # | Procedure | Required Documentation |
|---|-----------|----------------------|
| 1 | Inpatient admission | Two-midnight rule rationale |
| 2 | MRI spine | Radiculopathy + failed 4-6 weeks conservative care |
| 3 | Total knee replacement | Failed conservative treatment; bone-on-bone imaging |
| 4 | Spinal fusion | 6+ months failed conservative care; MRI + neuro deficit |
| 5 | Cardiac catheterization | Abnormal stress test OR acute coronary syndrome |
| 6 | Bariatric surgery | BMI >= 40 (or >= 35 with comorbidities); supervised diet; psych eval |
| 7 | Sleep study | ESS >= 10 or witnessed apneas; BMI documented |
| 8 | Home health services | Face-to-face encounter; homebound status; skilled need |
| 9 | CT abdomen/pelvis | GI symptoms documented; prior imaging if non-emergent |
| 10 | Genetic testing | Personal/family history; genetic counseling |

### Strong vs Weak Documentation

**Strong (survives review):**
- Specific symptoms with onset, duration, severity
- Failed prior treatments with dates and outcomes
- Objective test results supporting clinical decision
- Clear rationale connecting diagnosis to procedure

**Weak (triggers denials):**
- "Back pain" without neurological findings (for MRI)
- "Admit for observation" without clinical rationale
- Procedure ordered without documented prior workup
- Generic .9 unspecified codes for procedures needing specifics

## Timely Filing Deadlines

| Payer | Filing Deadline | Appeal Deadline |
|-------|----------------|----------------|
| Medicare | 365 days from DOS | 120 days |
| Medicaid | 90-365 days (varies by state) | Varies |
| UnitedHealthcare | 90-180 days | 180 days |
| Aetna | 90-180 days | 180 days |
| Cigna | 90-365 days | 365 days |
| Anthem/BCBS | 90-180 days (varies) | 180 days |
| Humana | 180 days | 180 days |
| Tricare | 365 days | 90 days |

Alert thresholds: 75% = warning, 90% = urgent,
95% = critical, 100% = too late.

Timely filing denials are 100% preventable. Our system
should eliminate them entirely through automated tracking.

## Appeal Statistics

86% of PA denials are eventually overturned on appeal
(AMA 2023), indicating initial denials are often due to
documentation gaps rather than clinical inappropriateness.

## For Full Reference

See references/payer-specific-rules.md (per-payer details)
See references/prior-auth-cpt-list.md (PA-required CPT codes)
