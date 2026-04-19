# Research Index — Healthcare Digital FTE
# Read when: referencing statistics, understanding domain decisions
# Full files: docs/research/DISC-00N-*.md
# Verification policy: ADR-012 — all stats must cite primary source

## DISC-001 — ICD-10 Official Guidelines
- Source: CMS ICD-10-CM Official Guidelines for Coding and Reporting FY2024
- Key rules encoded:
  - Outpatient uncertain dx (possible/probable/suspected/rule out) → code sign/symptom (Sec. IV.H)
  - Inpatient uncertain dx → may code as confirmed (Sec. II.H)
  - Excludes 1 = true mutual exclusivity; Excludes 2 = not coded together but may coexist
  - Code Also / Use Additional = mandatory paired codes
- Implemented in: src/core/icd10/rules_engine.py, data_loader.py

## DISC-002 — Documentation Failure Patterns
- Source: AHIMA CDI practice brief + case studies
- Key findings:
  - 41% of diagnoses lack ICD-10 specificity for optimal reimbursement
  - $3,000–$12,000/admission left on table from imprecise documentation
  - Top failure patterns: HF without systolic/diastolic spec, sepsis without organ failure,
    AKI without stage (KDIGO), malnutrition without severity, pneumonia without organism
- Used to build: tests/fixtures/known_cases/cases.py (20 hand-labeled cases)
- CDI triggers implemented in: src/agents/cdi_agent.py (KDIGO thresholds)

## DISC-003 — FHIR Implementation Edge Cases
- Source: HL7 FHIR R4 spec + Epic/Cerner implementation guides
- Key findings:
  - SMART on FHIR JWT assertion required for EHR integration (not basic auth)
  - DocumentReference vs DiagnosticReport for clinical notes (use DocumentReference)
  - Observation.category for lab results: "laboratory" value set
  - Claim resource: status=draft enforced until human approval
- Implemented in: src/core/fhir/ (client.py, auth.py, resources.py)

## DISC-004 — Payer Denial Patterns
- Source: MGMA denial management survey + CMS denial data
- Key findings:
  - 23% of claims denied; majority preventable
  - Top denial reasons: missing/incorrect codes, lack of medical necessity docs, auth issues
  - Coding-related denials ~40% of total denials
  - Specificity upgrades reduce denial rate significantly for HF, sepsis, AKI
- Deferred to Phase 2: payer-specific pre-submission validation
- Skill: .claude/skills/payer-denial-patterns/

## DISC-005 — Competitor Technical Analysis
- Source: Public documentation, patent filings, job postings, product pages
- Key gap confirmed: no competitor closes the full loop (note → coding → CDI → revenue)
  - Abridge/Nuance DAX: ambient documentation only
  - Nym Health/Fathom: coding only
  - Iodine Software: CDI only
  - Cohere Health: prior auth only
  - Waystar: claims processing only
- Our moat: encoded clinical knowledge (Skills) + PHR-documented prompts + compliance arch
- Note: ADR-012 requires stats to cite primary source; treat competitor analysis as directional
