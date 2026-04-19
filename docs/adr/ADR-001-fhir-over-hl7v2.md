# ADR-001: FHIR R4 Over HL7v2 for EHR Integration

**Status:** ACCEPTED
**Date:** 2026-03-30
**Decision makers:** Engineering team
**Constitution references:** Article III (Technical Law)

---

## Context

The system must integrate with hospital EHR systems (Epic,
Cerner/Oracle Health) to retrieve clinical notes, lab results,
vital signs, medications, problem lists, and encounter data.
Two integration standards exist in US healthcare:

- **HL7v2:** Legacy message-based protocol (1987+). Dominant
  in hospital interfaces. Requires dedicated interface engines
  (Mirth Connect, Rhapsody). Push-based (ADT feeds, ORU messages).
- **FHIR R4:** Modern RESTful API standard (2019+). Mandated
  by 21st Century Cures Act for patient access. Pull-based
  (on-demand queries). Supported by Epic (2018+) and Cerner.

We must choose one or both.

---

## Decision

**Use FHIR R4 REST API exclusively. No HL7v2 interfaces.**

Specifically:
1. All clinical data retrieval uses FHIR R4 REST endpoints
2. Authentication uses SMART on FHIR (OAuth 2.0)
3. Resources used: DocumentReference, Observation, Encounter,
   Condition, MedicationRequest, Patient (demographics only
   via token, never stored)
4. Coding output is delivered through EHR encoder UI integration,
   NOT via FHIR Claim write (which is not supported by major EHRs)
5. Vendor-specific deviations (Epic extensions, search parameter
   limitations) are handled by an abstraction layer

---

## Alternatives Considered

### Alternative 1: HL7v2 Message Interfaces

Use traditional HL7v2 ADT/ORU feeds for real-time data.

**Rejected because:**
- Requires dedicated interface engines (Mirth, Rhapsody) —
  additional infrastructure cost and maintenance
- Push-based model means we receive ALL messages, not just
  what we need — higher data volume, PHI exposure
- No standard authentication — each hospital has custom
  VPN/firewall requirements
- HL7v2 message parsing is fragile (Z-segments, custom
  fields vary by hospital)
- 21st Century Cures Act mandates FHIR — HL7v2 is legacy

### Alternative 2: Direct Database Access

Connect directly to Epic Clarity/Caboodle or Cerner Millennium
database.

**Rejected because:**
- Vendor lock-in — each EHR has different database schema
- Compliance risk — direct DB access may violate vendor
  terms and hospital security policies
- No standard API — custom SQL per hospital
- Cannot scale across multiple health systems

### Alternative 3: FHIR + HL7v2 Hybrid

Use FHIR for on-demand queries, HL7v2 for real-time events.

**Rejected because:**
- Doubles integration complexity and maintenance burden
- FHIR Subscription (R5) provides event-driven capability
  that replaces HL7v2 ADT feeds
- Phase 1 does not require real-time ADT feeds — CDI
  triggers on note-signed events available via FHIR

---

## Consequences

### Positive

1. **Single integration standard** — one client library,
   one auth flow, one data model across all EHR vendors
2. **RESTful simplicity** — standard HTTP, JSON, OAuth 2.0
3. **Regulatory alignment** — 21st Century Cures Act mandates
   FHIR, ensuring continued vendor support
4. **SMART on FHIR auth** — standardized OAuth 2.0 with
   clinical scopes
5. **Future-proof** — FHIR adoption is growing; HL7v2 is
   declining

### Negative

1. **Epic FHIR deviations** — 5-minute token expiration,
   search parameter limitations, rate limits 60-120 req/min,
   custom extensions (per DISC-003)
2. **No FHIR Claim write** — coding output cannot be written
   back via FHIR; must integrate with EHR encoder UI
   (per DISC-003 Section D)
3. **App Orchard approval** — Epic requires 3-6 month
   approval process for FHIR apps (per DISC-003)
4. **FHIR data gaps** — not all clinical data is available
   via FHIR (some requires custom Epic APIs or MyChart)

---

## References

- DISC-003 (FHIR R4 Implementation Edge Cases)
- Constitution Article III (Technical Law)
- 21st Century Cures Act (Public Law 114-255)
- HL7 FHIR R4 Specification (hl7.org/fhir/R4)
