# ADR-012: Research Verification Policy

## Status

ACCEPTED

## Date

2026-04-05

## Context

During the FIX-001 audit (2026-04-05), all five DISCOVER phase
research documents (DISC-001 through DISC-005) were systematically
reviewed for data provenance. The audit revealed a mix of:

1. **VERIFIED-LIVE** data — fetched from live URLs during research
   (e.g., CMS guidelines PDFs, PMC articles, FHIR specs)
2. **TRAINING-DATA** — plausible statistics from Claude's training
   data that were not fetched from a live source and lacked
   specific URLs (e.g., "65% of denied claims are never appealed")
3. **OUTDATED** data that was accurate when written but has since
   been superseded by newer publications

### Specific issues found in FIX-001

| Document | Issue | Risk |
|---|---|---|
| DISC-002 | Sepsis aggregate cost cited as $41.5B (actual 2021 data: $52.1B) | CDI revenue projections understated |
| DISC-004 | Denial rate cited as 15-20% (actual 2024 data: 11.8-15%) | Denial prevention ROI overstated |
| DISC-004 | AMA PA survey data from 2023 (2024 edition now available with different figures) | Stale data in competitive materials |
| DISC-005 | Abridge funding $212.5M (actual June 2025: $773M, $5.3B valuation) | Severely outdated competitive intelligence |
| DISC-005 | Nym Health funding $48M (actual Oct 2024: $92M) | Outdated competitive intelligence |
| DISC-003 | Epic market share ~38% (KLAS 2024: 42.3%) | Minor but worth correcting |

For a healthcare coding AI where accuracy directly affects hospital
revenue and regulatory compliance, unverified statistics create risk:

- **Rules engine risk:** If a threshold in code is based on an
  unverified statistic, it may be miscalibrated
- **Sales risk:** If competitive data is outdated, sales materials
  lose credibility with informed buyers
- **Compliance risk:** If regulatory citations are stale, the
  system may not reflect current CMS requirements

## Decision

All research claims that affect system behavior (coding rules,
CDI thresholds, DRG values, compliance requirements) must be:

1. **Fetched from a live primary source URL** during research
2. **Cited with exact URL + page/section reference** in the
   research document
3. **Marked with verification status** inline:
   - `[VERIFIED-LIVE ✓]` — confirmed from live URL
   - `[TRAINING-DATA — directional estimate]` — from training
     data, not live-verified
   - `[UNVERIFIABLE]` — cannot be confirmed (e.g., competitor
     internal metrics)
4. **Re-verified on a defined schedule** (see below)

### Training-data-sourced statistics

May be retained in research documents only if:

1. Clearly labeled `[TRAINING-DATA — directional estimate]`
2. **Not used as hard thresholds in code** (rules engine uses
   CMS guidelines, not statistics, for decisions)
3. Not used in compliance-critical logic
4. Accompanied by a note explaining what primary source would
   confirm or replace the estimate

### Verification headers

Every DISC document must include at the top:
- `Last Verified:` date
- `Verification Method:` (live_fetch, manual_review, etc.)
- `Unverified Items Remaining:` count

And at the bottom (before Sources):
- A `## Verification Status` section with a summary table

## Re-verification Schedule

| Data Type | Refresh Cycle | Trigger |
|---|---|---|
| CMS ICD-10-CM guidelines | Annual | October 1 (new FY effective) |
| CMS MS-DRG weights | Annual | October 1 (new FY effective) |
| CMS NCCI edits | Quarterly | January, April, July, October |
| AMA/CAQH/MGMA surveys | Annual | When new edition published |
| Competitor intelligence | Quarterly | Or upon major funding/product announcement |
| FHIR vendor behaviors | Quarterly | Aligned with Epic quarterly release |
| Payer PA lists/criteria | Quarterly | Per payer update cycles |

## Consequences

### Positive

- Research documents are trustworthy and auditable
- All coding rules are traceable to current CMS publications
- Annual re-verification aligns with CMS update schedule
- FCA defense: can demonstrate rules are based on current guidelines
- Sales team can cite research with confidence
- Constitution Article V.1 (Research Before Building) is strengthened

### Negative

- Research documents take longer to produce (live fetch required)
- Re-verification is an ongoing maintenance cost
- Some industry statistics cannot be live-verified and must be
  labeled as directional estimates

## Compliance

This ADR supports:
- Constitution Article II.3 (ICD-10 Guidelines as Hard Constraints)
  — ensures guidelines are current
- Constitution Article V.1 (Research Before Building) — ensures
  research is accurate
- Constitution Article V.4 (Compliance Is A Feature) — ensures
  all compliance claims are auditable

## References

- FIX-001 audit session (2026-04-05)
- CMS FY2026 ICD-10-CM Guidelines: https://www.cms.gov/files/document/fy-2026-icd-10-cm-coding-guidelines.pdf
- CMS FY2026 IPPS Final Rule: https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/fy-2026-ipps-final-rule-home-page
