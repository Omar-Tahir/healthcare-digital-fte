# Epic FHIR R4 Deviations from Standard

These are real-world deviations from the FHIR R4 spec that
break AI systems in production. Source: DISC-003.

## 1. Token Expiration

Epic default: **5 minutes** (not the 60-minute OAuth standard).
Some hospitals configure shorter. Always check `expires_in`
from token response rather than assuming a duration.

## 2. Search Parameter Limitations

Not all FHIR search parameters are supported in Epic.
Test each search parameter in the target hospital's
production environment before relying on it.

Common unsupported parameters:
- _has (reverse chaining)
- _type on /everything endpoints
- Complex date ranges on some resources

## 3. Claim Resource

Epic provides ExplanationOfBenefit (read-only).
NO write support. NO create support for Claim resources.
Claims must go through the hospital's existing billing system.

## 4. Binary Content

Large documents (> 1MB) may timeout on Binary endpoint.
Use streaming/chunked retrieval for large PDFs or images.
Set a 30-second timeout and return DegradedResult on failure.

## 5. Patient Opt-Out

21st Century Cures Act allows patients to opt out.
Epic returns empty Bundle or 404 — NOT a standard error.
Do NOT log the opt-out as a system error.
Do NOT attempt alternative data retrieval paths.

## 6. Note Availability Timing

| Event | Typical Delay |
|-------|--------------|
| Note created | Not yet available via FHIR |
| Note signed by author | Available within 1-30 min |
| Note cosigned (resident) | Available after cosign (hours) |
| Amended notes | Variable — minutes to hours |

If no notes found for an active encounter: return
DegradedResult(reason="notes_not_yet_available"). Do NOT
retry aggressively — check again in 5 minutes.

## 7. App Orchard Approval

Epic requires 3-6 month approval process for FHIR apps:
- Sandbox testing on fhir.epic.com (synthetic data)
- Production approval per hospital
- Annual recertification
- **Sandbox != production** (clean data vs messy real data)

## 8. Encounter Status Transitions

Epic encounter status transitions are not always FHIR-
compliant. Common issues:
- Encounter may show "in-progress" after patient discharged
- Status updates may lag by hours
- Use discharge date rather than status for timing decisions
