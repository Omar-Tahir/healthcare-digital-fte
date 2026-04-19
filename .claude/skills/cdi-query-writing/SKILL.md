---
name: cdi-query-writing
version: "2.0.0"
description: >
  Use this skill whenever building, modifying, or testing the CDI agent, generating physician queries, writing CDI prompts, or detecting documentation improvement opportunities. Triggers on: CDI, clinical documentation improvement, physician query, documentation gap, AHIMA, non-leading query, query compliance, creatinine rise, KDIGO, SIRS criteria, specificity upgrade opportunity, underdocumented condition, or any task involving asking physicians to clarify clinical documentation. Also use when editing src/agents/cdi_agent.py, src/prompts/cdi_query.py, or any code that generates queries sent to physicians. If the task mentions querying a doctor, improving documentation, or detecting underdocumented conditions — load this skill. Even if the user says "CDI" without elaboration, load this skill.
allowed-tools: Read, Bash
license: Proprietary
---

# CDI Query Writing

## AHIMA Compliance — Non-Negotiable

Read references/ahima-standards.md before generating any query.
A non-compliant leading query creates OIG audit risk.

## The 3 Query Rules

### Rule 1: Never lead the physician

Wrong: "Does the patient have AKI? Coding it would increase
        reimbursement by $4,000."
Wrong: "Would you agree the patient has sepsis?"
Wrong: "Please document acute kidney injury."
Wrong: "The patient's creatinine rise indicates AKI, correct?"

Correct: "The creatinine rose from 1.1 to 2.4 during admission.
           Could you clarify the clinical significance?"

Why: OIG specifically audits CDI programs. Leading queries that
result in code upgrades can be viewed as schemes to inflate
reimbursement — FCA liability.

### Rule 2: Always multiple choice

Queries must offer options — never yes/no, never open-ended only.

Required options in every query:
- [Condition is present — with specificity request]
- [Alternative diagnosis]
- [Condition not present]
- [Unable to determine at this time]
- [Other: ___]

Present options in neutral order — never lead with the
revenue-maximizing answer.

### Rule 3: Cite objective evidence

Every query must reference the specific lab value, vital sign,
or clinical finding that triggered it.
Never generate a query without evidence from the record.

## Top 10 CDI Opportunities with Detection Triggers

| # | Condition | Trigger | Revenue Impact | CC/MCC |
|---|-----------|---------|---------------|--------|
| 1 | AKI | Cr rise >= 0.3 in 48h or >= 1.5x baseline | $3,000-$8,000 | MCC |
| 2 | Sepsis | >= 2 SIRS criteria + infection source | $42,759/case | MCC |
| 3 | HF type/acuity | "CHF"/"HF" without type + BNP > 400 | $7,500/case | CC/MCC |
| 4 | Respiratory failure | O2 sat < 90% or PaO2 < 60 + vent/BiPAP | $4,000-$10,000 | MCC |
| 5 | Malnutrition | BMI < 18.5 or albumin < 3.0 or weight loss > 5% | $3,000-$9,000 | CC/MCC |
| 6 | Encephalopathy | AMS + metabolic derangement | $4,000-$10,000 | MCC |
| 7 | COPD exacerbation | COPD + worsening dyspnea, no "exacerbation" | $2,000-$5,000 | MCC |
| 8 | DM complications | DM + neuropathy/nephropathy not linked | $1,500-$4,000 | CC |
| 9 | Pressure ulcer staging | Wound care staging != physician note | $3,000-$8,000 | MCC |
| 10 | Alcohol withdrawal | CIWA protocol + "alcohol use" only | $3,000-$7,000 | CC/MCC |

## Query Template (Standard Structure)

```
[HEADER]
Clinical Documentation Query
Date: [date]
Encounter: [encounter_id]
Provider: Dr. [name]

[CLINICAL EVIDENCE — objective data only]
The following objective findings are noted in the medical
record:
- [Lab value 1 with date]
- [Lab value 2 with date]
- [Clinical finding from note with date]

[QUESTION — non-leading, multiple choice]
Based on your clinical assessment, [specific question]:
[] [Option A — the condition is present (with specificity)]
[] [Option B — alternative diagnosis]
[] [Option C — condition not present]
[] [Option D — unable to determine at this time]
[] Other: ___________

[EDUCATIONAL CONTEXT — optional]
Note: [Brief explanation of why this matters for accurate
coding, e.g., "Acute kidney injury documentation enables
accurate severity-of-illness reporting."]

[RESPONSE DEADLINE]
Please respond within 24 hours. If no response is received,
a follow-up query will be sent.
```

## Workflow Integration

- **Trigger:** Clinical note signed event (FHIR
  DocumentReference status change to "current")
- **Timing:** Concurrent CDI (during admission, before
  discharge) preferred over reactive post-discharge review
- **Priority:** P0 (AKI, Sepsis, HF) queried immediately;
  lower-priority queries batch daily
- **No response 24h:** escalation query. **48h:** CDI manager.
- **Physician disagrees:** accept clinical judgment, document
  in audit trail

## Key Principle

The CDI agent identifies documentation gaps. It does NOT
code conditions. It does NOT suggest diagnoses. It asks
the physician to clarify documentation so the coder can
code accurately. The physician's clinical judgment is final.

## MCP Tools

- mcp_drg_impact(current_codes, addition) -> revenue delta
  Use to populate the clinical significance section of queries.

## For Full Reference

See references/ahima-standards.md (full compliance rules)
See references/query-templates.md (one template per CDI type)
