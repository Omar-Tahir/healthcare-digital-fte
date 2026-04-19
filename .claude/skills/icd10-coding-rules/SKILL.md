---
name: icd10-coding-rules
version: "2.0.0"
description: >
  Use this skill whenever working on the coding agent, rules engine, CDI agent, DRG calculator, or ANY component that suggests, validates, sequences, or filters ICD-10 codes. Triggers on: ICD-10, ICD10, diagnosis code, coding guideline, Excludes 1, uncertain diagnosis, outpatient vs inpatient coding, POA indicator, combination code, Code First, Use Additional, manifestation code, specificity upgrade, CC/MCC status, or any reference to CMS coding rules. Also use when editing src/core/icd10/, src/agents/coding_agent.py, src/agents/cdi_agent.py, src/prompts/coding_extraction.py, tests/clinical/, or any file that imports from src.core.icd10. If the task involves clinical coding in ANY way, load this skill — even if the user does not explicitly mention ICD-10.
allowed-tools: Read, Bash
license: Proprietary
---

# ICD-10 Coding Rules

## Read First

Read references/hard-constraints.md for the 5 rules that
can never be violated (Article II.3 of constitution).

Read references/specificity-upgrades.md for the top 20
revenue-impact specificity upgrades from DISC-002.

Read references/cc-mcc-reference.md for CC/MCC conditions
and DRG tier implications.

## Quick Reference — The 5 Hard Constraints

### Rule 1: Excludes 1 — Never code together

Two codes with an Excludes 1 relationship cannot appear
in the same claim. Ever.
Check: call mcp_excludes1_check(code_a, code_b) before
suggesting any pair.
Violation consequence: claim denial + FCA exposure.

### Rule 2: Outpatient uncertain diagnosis

Qualifier words: possible, probable, suspected, rule out,
working diagnosis, questionable, likely, concern for,
appears to be, consistent with, compatible with, indicative of,
suggestive of, comparable with, still to be ruled out.

Outpatient + any qualifier = code the SIGN or SYMPTOM only.
Never code the uncertain diagnosis as confirmed.
Inpatient = may code as confirmed (Section II.H).

"Ruled out" = eliminated — do NOT code in ANY setting.

OBS status (OBSENC) = OUTPATIENT rules.

### Rule 3: Mandatory sequencing (Code First / Use Additional)

Code First / Use Additional instructions are mandatory.
E11.22 (DM with CKD) requires N18.x — cannot code alone.
Use mcp_sequencing_rules(code) to check requirements.

Manifestation codes can NEVER be principal diagnosis.

### Rule 4: Combination codes — use them

When a combination code exists for two conditions,
use the combination code. Do not code components separately.

Examples: E11.22 (T2DM with CKD), I11.0 (HTN with HF),
I12.x (HTN with CKD).

### Rule 5: POA indicator accuracy

Y = present at admission. N = developed after admission.
U = documentation insufficient. W = clinically undetermined.

ER conditions are POA = Y. Incorrect N on HAC conditions
triggers Medicare payment reduction.

## Inpatient vs Outpatient Rules Summary

| Rule | Inpatient | Outpatient |
|------|-----------|------------|
| Uncertain diagnosis | Code as confirmed | Code symptom instead |
| Principal diagnosis | Condition chiefly responsible for admission | First-listed = reason for visit |
| POA indicators | Required | Not applicable |
| Chronic conditions | Code if actively managed | Code if addressed |
| "Ruled out" | Do NOT code | Do NOT code |

Encounter class mapping:
- IMP (inpatient) -> INPATIENT rules
- AMB (ambulatory) -> OUTPATIENT rules
- EMER (emergency) -> OUTPATIENT rules
- OBSENC (observation) -> OUTPATIENT rules (critical!)

## MCP Tools Available

- mcp_icd10_lookup(code) -> code description, Excludes 1 pairs,
  Code First instructions, CC/MCC status, billability
- mcp_icd10_search(term) -> find codes matching a clinical term
- mcp_excludes1_check(code_a, code_b) -> relationship check
- mcp_sequencing_rules(code) -> mandatory pairings

## For Full Reference Tables

See references/hard-constraints.md (detailed rule explanations)
See references/specificity-upgrades.md (top 20 upgrades)
See references/cc-mcc-reference.md (CC/MCC conditions)
