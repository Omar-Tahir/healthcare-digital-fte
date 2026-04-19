# DESIGN-006: Coder Review UI Specification

**Status:** COMPLETE  
**Date:** 2026-04-02  
**Author:** Claude (AI Engineering Partner)  
**Research inputs:** DISC-002 (Documentation Failure Patterns),
DISC-004 (Payer Denial Patterns)  
**Constitution references:** Article II.1 (No Autonomous Claims),
Article II.4 (HIPAA), Article III.8 (FastAPI),
Article IV.3 (HIM Director as Champion)  
**Implementation target:** `src/api/routes/`, `src/api/templates/`  
**Depends on:** DESIGN-001 (Coding Rules Engine),
DESIGN-002 (CDI Intelligence Layer),
DESIGN-003 (Compliance Guardrails)  
**ADR references:** ADR-002 (No Autonomous Claims),
ADR-010 (HTMX for Coder UI)

---

## Purpose

The Coder Review UI is the human-in-the-loop interface where
credentialed coders review, modify, and approve AI-generated
coding suggestions before codes are entered into the EHR
encoder.

This interface is the enforcement point for Constitution
Article II.1 (No Autonomous Claims). Without it, the system
has no compliant output pathway. Every code suggestion the
system generates must pass through this interface and receive
explicit human approval before affecting any claim.

**Design principles:**
1. The coder is in control — AI assists, never dictates
2. Every approval is cryptographically bound to the exact
   code set reviewed
3. The interface works when AI is unavailable (manual mode)
4. Session security enforces HIPAA access controls
5. No React, no npm, no build step — HTMX + server-rendered
   HTML (ADR-010)

---

## 1. Pages and Routes

### 1.1 Worklist — GET /queue

**Purpose:** Display encounters pending coding review, sorted
by priority.

**Route definition:**
```python
@router.get("/queue")
async def worklist(
    request: Request,
    status: Literal["pending", "in_progress", "completed"] = "pending",
    sort_by: Literal["priority", "date", "drg_impact"] = "priority",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> HTMLResponse:
```

**Worklist columns:**

| Column | Source | Sortable |
|--------|--------|----------|
| Encounter ID | FHIR Encounter.id | Yes |
| Patient initials | Derived (first letter only — not PHI) | No |
| Encounter class | IMP / AMB / EMER / OBSENC | Yes |
| Admit date | Encounter.period.start | Yes |
| Note count | Count of DocumentReferences | No |
| AI status | pending / ready / degraded / error | Yes |
| DRG impact estimate | From DRG agent | Yes |
| Priority | Computed from DRG impact + age | Yes |
| Assigned coder | From session/assignment | Yes |

**Priority calculation:**
```
priority_score = (
    drg_impact_dollars * 0.6
    + days_since_admit * 100 * 0.3
    + (1 if has_cdi_queries else 0) * 500 * 0.1
)
```

Higher score = higher priority. CDI queries add urgency
because physician queries have response time expectations.

**Worklist behaviors:**
- Auto-refreshes every 60 seconds via HTMX polling
  (`hx-trigger="every 60s"`)
- Click encounter row → navigate to /review/{encounter_id}
- Status filter tabs: Pending | In Progress | Completed
- "Degraded" status shown when AI analysis incomplete
  (Constitution Article II.5 — manual mode available)

### 1.2 Coding Review — GET /review/{encounter_id}

**Purpose:** Three-panel coding review interface. This is where
the coder does their primary work.

**Route definition:**
```python
@router.get("/review/{encounter_id}")
async def coding_review(
    request: Request,
    encounter_id: str,
) -> HTMLResponse:
```

**Three-panel layout:**

```
┌────────────────────────────────────────────────────────────┐
│ Header: Encounter ID | Class | Admit Date | Coder Name    │
├───────────────┬──────────────────┬─────────────────────────┤
│               │                  │                         │
│  PANEL 1      │  PANEL 2         │  PANEL 3                │
│  Clinical     │  AI Suggestions  │  DRG Impact             │
│  Note         │                  │                         │
│               │  ┌────────────┐  │  Current DRG: XXX       │
│  [scrollable  │  │ Code 1     │  │  Weight: X.XX           │
│   note text   │  │ E11.22     │  │  Revenue: $XX,XXX       │
│   with        │  │ ☑ Accept   │  │                         │
│   evidence    │  │ ☐ Reject   │  │  Optimized DRG: YYY     │
│   highlights] │  │ Evidence:  │  │  Weight: Y.YY           │
│               │  │ "patient   │  │  Revenue: $YY,YYY       │
│               │  │  has type  │  │                         │
│               │  │  2 diab..."│  │  Delta: +$Z,ZZZ         │
│               │  └────────────┘  │                         │
│               │                  │  ─────────────────────  │
│               │  ┌────────────┐  │                         │
│               │  │ Code 2     │  │  CDI Queries:           │
│               │  │ I50.23     │  │  • AKI documentation    │
│               │  │ ☑ Accept   │  │  • Sepsis clarification │
│               │  │ ☐ Reject   │  │                         │
│               │  └────────────┘  │  Warnings:              │
│               │                  │  • DRG impact > $5,000  │
│               │  [+ Add Code]    │    (compliance review)  │
│               │                  │                         │
├───────────────┴──────────────────┴─────────────────────────┤
│ Footer: [Approve & Generate Token] [Save Draft] [Skip]     │
└────────────────────────────────────────────────────────────┘
```

**Panel 1 — Clinical Note:**
- Displays full clinical note text (from FHIR DocumentReference)
- Evidence quotes from AI suggestions are highlighted in the
  note text (yellow background)
- Clicking a suggestion in Panel 2 scrolls Panel 1 to the
  corresponding evidence quote
- If multiple notes exist, tabbed interface shows each note
- Amended notes shown with visual diff (additions in green)

**Panel 2 — AI Suggestions:**
- Each suggestion displayed as a card with:
  - ICD-10 code and description
  - Evidence quote (verbatim from note)
  - Confidence score (displayed as percentage)
  - CC/MCC status badge
  - Accept/Reject toggle
  - Reject reason dropdown (if rejected)
- Principal diagnosis marked with a distinct visual indicator
- Suggestions sorted: principal first, then by DRG impact
- "Add Code" button for manual code entry (coder types code)
- Suggestions with confidence < 0.65 shown with amber border
  (routed to senior coder queue per CLAUDE.md rules)
- Guardrail warnings displayed inline on affected suggestions

**Panel 3 — DRG Impact:**
- Current DRG (from existing codes) vs Optimized DRG (with
  AI suggestions accepted)
- Revenue delta in dollars
- CC/MCC contribution breakdown
- CDI queries section: pending physician queries with status
- Soft guardrail warnings displayed here
- If DRG improvement > $5,000: compliance review flag shown
  (G-SOFT-003)

**HTMX interactions:**
- Accept/reject toggles update via `hx-patch` without
  full page reload
- DRG impact recalculates when suggestions change
  (`hx-trigger="change"` on toggles)
- Evidence highlight scrolls via `hx-swap="none"` with
  JavaScript scroll trigger

### 1.3 Approve — POST /approve

**Purpose:** Generate human approval token for the reviewed
code set. This is the Constitution Article II.1 enforcement
point.

**Route definition:**
```python
@router.post("/approve")
async def approve_coding(
    request: Request,
    body: ApprovalRequest,
) -> ApprovalResponse:
```

**Request model:**
```python
class ApprovalRequest(BaseModel):
    encounter_id: str
    approved_codes: list[ApprovedCode]
    coder_id: str  # From authenticated session
    session_token: str  # CSRF protection

class ApprovedCode(BaseModel):
    code: str  # ICD-10-CM or CPT code
    is_principal: bool = False
    evidence_quote_hash: str  # SHA-256 of evidence quote
    poa_indicator: Literal["y", "n", "u", "w",
                            "exempt"] | None = None
```

**Response model:**
```python
class ApprovalResponse(BaseModel):
    success: bool
    human_approval_token: str | None = None
    token_expires_at: datetime | None = None
    encounter_id: str
    code_count: int
    error: str | None = None
```

**Approval flow:**

```
Step 1: Validate session
        - Coder must be authenticated
        - Session must not be expired
        - CSRF token must match

Step 2: Validate coder credentials
        - coder_id must have 'credentialed_coder' role
        - If not credentialed: reject with clear error

Step 3: Validate approved codes
        - At least one code must be approved
        - Exactly one code must be is_principal=True
        - All codes must pass ICD-10 rules engine validation
          (no Excludes 1 violations in approved set)
        - Evidence quote hashes must match stored quotes

Step 4: Generate human approval token
        - Compute code_set_hash = SHA-256 of sorted approved
          codes concatenated
        - Create token payload:
          {
              coder_id: str,
              encounter_id: str,
              code_set_hash: str,
              timestamp: ISO 8601,
              expires_at: timestamp + 15 minutes
          }
        - Sign with HMAC-SHA256 using server secret key
        - Token is single-use (stored in Redis/memory with
          used flag; consumed on first validation)

Step 5: Log approval to audit trail
        - Log: encounter_id, coder_id, code_count,
          timestamp, token_id (NOT the codes, NOT PHI)
        - Audit log is append-only

Step 6: Return token to UI
        - UI displays success confirmation
        - Token shown with expiration countdown
        - Coder enters codes into EHR encoder
```

**Token specification:**

| Property | Value | Rationale |
|----------|-------|-----------|
| Algorithm | HMAC-SHA256 | Fast, secure, no key distribution needed |
| Expiration | 15 minutes | Enough time to enter codes in EHR; short enough to prevent stale approvals |
| Single-use | Yes | Prevents replay — one token, one claim |
| Binding | code_set_hash | Prevents approving one set, submitting another |
| Role requirement | credentialed_coder | Only qualified humans can approve |
| Storage | Server-side (Redis or in-memory dict) | Track used/unused status |

### 1.4 Health Check — GET /health

**Purpose:** System health status for monitoring and load
balancer probes.

**Route definition:**
```python
@router.get("/health")
async def health_check() -> HealthResponse:
```

**Response model:**
```python
class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    components: dict[str, ComponentHealth]

class ComponentHealth(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    message: str | None = None
    last_check: datetime

# Components checked:
# - fhir_client: last successful FHIR call
# - llm_client: last successful Claude API call
# - rules_engine: ICD-10 data tables loaded
# - database: audit log writeable (if applicable)
```

**Behavior:**
- Always returns 200 with status body (never 500)
- Returns "degraded" if any non-critical component is down
- Returns "unhealthy" only if audit logging is unavailable
  (cannot operate without audit trail)
- No PHI in health check response

---

## 2. HIPAA Audit Log

Every user action in the coder review UI is logged to an
append-only audit trail. This audit log is the FCA defense
record — it proves that every code was human-reviewed.

### 2.1 Auditable Events

| Event | Fields Logged | NOT Logged |
|-------|--------------|------------|
| Coder opens review | encounter_id, coder_id, timestamp | Note text, patient info |
| Suggestion accepted | encounter_id, code, coder_id, timestamp | Evidence quote text |
| Suggestion rejected | encounter_id, code, coder_id, reject_reason, timestamp | Evidence quote text |
| Code manually added | encounter_id, code, coder_id, timestamp | Clinical rationale |
| Approval token generated | encounter_id, coder_id, token_id, code_count, timestamp | Code list, patient info |
| Session started | coder_id, timestamp, ip_hash | IP address (only hash) |
| Session ended | coder_id, timestamp, duration | — |

### 2.2 Audit Log Model

```python
class AuditLogEntry(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    coder_id: str
    encounter_id: str | None = None
    details: dict[str, str | int | float | bool] = Field(
        default_factory=dict,
    )

    @model_validator(mode="after")
    def validate_no_phi(self) -> "AuditLogEntry":
        """Ensure no PHI fields in details dict."""
        phi_fields = {
            "patient_name", "name", "first_name", "last_name",
            "date_of_birth", "dob", "ssn", "mrn", "address",
            "phone", "email", "note_text", "clinical_text",
            "evidence_quote",
        }
        violations = phi_fields & set(self.details.keys())
        if violations:
            raise ValueError(
                f"PHI fields in audit log: {violations}"
            )
        return self
```

---

## 3. Session Security

### 3.1 Authentication

The coder review UI integrates with the hospital's identity
provider via SMART on FHIR launch context or SAML/OIDC
federation.

**Session requirements:**

| Property | Value | Rationale |
|----------|-------|-----------|
| Session timeout | 30 minutes idle | HIPAA requires automatic logoff |
| Session storage | Server-side (httponly, secure cookies) | Prevent XSS token theft |
| CSRF protection | Synchronizer token pattern | Prevent cross-site request forgery |
| Cookie flags | HttpOnly, Secure, SameSite=Strict | Defense in depth |
| Session binding | IP hash + user agent | Detect session hijacking |

### 3.2 Authorization

| Role | Permissions |
|------|------------|
| credentialed_coder | View worklist, review encounters, approve codes, generate tokens |
| senior_coder | All coder permissions + review low-confidence suggestions |
| cdi_specialist | View CDI queries, track physician response status |
| readonly | View worklist and review screens (no approval) |
| admin | User management, audit log access (no coding approval unless also credentialed) |

**Role enforcement:**
- `credentialed_coder` role is required for POST /approve
- Role is checked server-side on every request
- Admin role does NOT grant coding approval unless the user
  also has credentialed_coder role
- Role changes are audited

---

## 4. Frontend Architecture

### 4.1 Technology Choice — HTMX (ADR-010)

The coder review UI uses HTMX for dynamic interactions with
server-rendered HTML templates. No React, no npm, no Node.js,
no build step.

**Rationale (ADR-010):**
- Coder review is a form-based workflow, not a complex SPA
- Server-rendered HTML is simpler to secure (no client-side
  state management for PHI)
- HTMX provides the specific interactions needed: partial
  page updates, form submissions, polling
- No npm/Node.js reduces supply chain attack surface
- Python developers can maintain the full stack

**HTMX patterns used:**

| Interaction | HTMX Attribute | Server Response |
|-------------|---------------|----------------|
| Accept/reject toggle | `hx-patch="/api/suggestion/{id}"` | Updated suggestion card HTML |
| DRG recalculation | `hx-trigger="change from:.suggestion-toggle"` | Updated DRG panel HTML |
| Worklist refresh | `hx-trigger="every 60s"` `hx-get="/queue/partial"` | Updated table body HTML |
| Evidence scroll | `hx-swap="none"` + JS event | No server call; client-side scroll |
| Approve action | `hx-post="/approve"` `hx-confirm="..."` | Token display or error |

### 4.2 Template Structure

```
src/api/templates/
├── base.html           ← Base layout with HTMX script tag
├── queue.html          ← Worklist page
├── review.html         ← Three-panel review page
├── partials/
│   ├── queue_table.html    ← Worklist table body (HTMX partial)
│   ├── suggestion_card.html ← Single suggestion card
│   ├── drg_panel.html      ← DRG impact panel
│   ├── note_panel.html     ← Clinical note with highlights
│   └── approval_modal.html ← Approval confirmation
└── components/
    ├── header.html     ← Navigation header
    ├── footer.html     ← Action buttons
    └── alerts.html     ← Warning/error messages
```

### 4.3 Static Assets

```
src/api/static/
├── css/
│   └── main.css        ← Single CSS file, no preprocessor
├── js/
│   ├── htmx.min.js     ← HTMX library (vendored, not CDN)
│   └── app.js          ← Minimal custom JS (evidence scroll)
└── img/
    └── logo.svg
```

**No CDN dependencies.** HTMX is vendored (copied into the
project) to avoid external dependencies in a healthcare
environment that may have restricted internet access.

---

## 5. Performance Requirements

| Metric | Target | Notes |
|--------|--------|-------|
| Worklist page load | <500ms | Server-rendered, no JS framework |
| Review page load | <2s | Includes note rendering and AI suggestions |
| Accept/reject toggle | <200ms | HTMX partial update |
| DRG recalculation | <500ms | Server-side calculation |
| Approval token generation | <300ms | HMAC computation + storage |
| Concurrent users | ≥50 | Per FastAPI instance |

---

## 6. Testing Strategy

### 6.1 Test Categories

| Category | Count | Coverage |
|----------|-------|----------|
| Compliance tests (written FIRST) | ≥10 | Article II.1 enforcement, HIPAA audit |
| Route tests | ≥15 | Each route, each error path |
| Approval token tests | ≥10 | Generation, validation, expiry, single-use, role check |
| Audit log tests | ≥8 | Every auditable event, PHI exclusion |
| Session security tests | ≥8 | Timeout, CSRF, cookie flags, role enforcement |
| Frontend tests | ≥5 | Template rendering, HTMX attributes present |

### 6.2 Critical Test Cases

```python
# Compliance tests (DESIGN-003 G-HARD-001)

def test_no_approval_without_credentialed_coder():
    """POST /approve rejects users without credentialed_coder role."""

def test_approval_token_binds_to_code_set():
    """Token code_set_hash changes when approved codes change."""

def test_approval_token_expires():
    """Token rejected after 15-minute expiration."""

def test_approval_token_single_use():
    """Token rejected on second use."""

def test_approval_requires_principal_diagnosis():
    """POST /approve rejects if no is_principal=True code."""

def test_excludes1_in_approved_set_rejected():
    """POST /approve rejects if approved codes have Excludes 1 conflict."""

def test_audit_log_no_phi():
    """Every audit log entry passes PHI field validation."""

def test_audit_log_written_on_approval():
    """Approval event creates audit log entry with encounter_id,
    coder_id, code_count, timestamp."""

def test_session_timeout():
    """Session expires after 30 minutes idle."""

def test_csrf_protection():
    """POST /approve rejects requests without valid CSRF token."""

def test_manual_mode_when_ai_unavailable():
    """Review page loads with manual code entry when AI
    suggestions unavailable (DegradedResult)."""

def test_health_check_always_200():
    """GET /health returns 200 even when components degraded."""
```

---

## 7. Acceptance Criteria

- [ ] Worklist displays encounters sorted by priority with
      auto-refresh every 60 seconds
- [ ] Three-panel review layout renders clinical note, AI
      suggestions, and DRG impact
- [ ] Evidence quotes highlighted in clinical note text
- [ ] Accept/reject toggles update without full page reload
- [ ] DRG impact recalculates when suggestion toggles change
- [ ] POST /approve requires credentialed_coder role
- [ ] Approval token is HMAC-SHA256, expires in 15 minutes,
      single-use, hash-bound to code set
- [ ] Approval rejects if approved codes violate Excludes 1
- [ ] Every user action logged to HIPAA audit trail
- [ ] No PHI in any audit log entry
- [ ] Session times out after 30 minutes idle
- [ ] CSRF protection on all POST routes
- [ ] Manual code entry available when AI is unavailable
- [ ] GET /health returns component status, always 200
- [ ] No npm, no Node.js, no build step — HTMX only

---

## References

- Constitution Article II.1 (No Autonomous Claims)
- Constitution Article II.4 (HIPAA)
- Constitution Article IV.3 (HIM Director as Champion)
- ADR-002 (No Autonomous Claim Submission)
- ADR-010 (HTMX for Coder Review UI)
- DESIGN-003 G-HARD-001 (Human Approval Token)
- DISC-002 (Documentation Failure Patterns)
- DISC-004 (Payer Denial Patterns)
