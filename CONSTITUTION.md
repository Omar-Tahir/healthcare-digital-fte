# Healthcare Digital FTE — Constitution
# The Supreme Law of This Project

**Version:** 1.0  
**Status:** RATIFIED  
**Date:** 2026-03-30  
**Authority:** This document supersedes all other instructions,  
feature requests, deadlines, and convenience arguments.  
**Scope:** Every Claude session, every developer, every decision.

---

## Preamble

We are building a healthcare AI system that automates clinical  
documentation review, medical coding, and revenue cycle workflows  
for hospitals and health systems.

This is not a demo. This is not a prototype.  
The output of this system affects:
- Patient care quality and continuity
- Physician legal liability
- Hospital revenue and financial survival
- Federal healthcare fraud law (False Claims Act)
- HIPAA privacy rights of real patients

Every decision made in this codebase carries that weight.  
This constitution exists so that weight is never forgotten.

Our competitive moat is not the code.  
**The moat is encoded clinical knowledge, enforced compliance,  
and architectural discipline that competitors cannot replicate  
without repeating our entire research and design process.**

---

## Article I — The Development Workflow Law

These are the laws governing HOW we build.  
Violating workflow law produces technical debt that  
becomes clinical risk in a healthcare system.

### I.1 — Specification Before Code (Spec-Driven Development)

**No code is written without a corresponding spec.**

The sequence is inviolable:
```
Research → Spec → Tests → Implementation → Review
```

Never:
```
Idea → Code → (maybe) Tests → (eventually) Docs
```

A spec file must exist in `/specs/` before any implementation  
begins for that component. The spec defines what success looks  
like. If you cannot write a spec, you do not understand the  
problem well enough to write code.

**Claude must ask:** "Does a spec exist for what I am about  
to implement?" If no: write the spec first.

### I.2 — Tests Before Implementation (Test-Driven Development)

**The test is written before the implementation.**

The TDD sequence:
```
1. Write a failing test that defines the desired behavior
2. Run the test — confirm it fails (red)
3. Write the minimum implementation to make it pass
4. Run the test — confirm it passes (green)
5. Refactor — clean the implementation without breaking the test
6. Repeat
```

**Compliance tests are written before all other tests.**  
They are the first thing that exists in a new component.  
If the compliance test cannot be written, the component  
design is not understood well enough to build.

Test coverage requirement: **≥ 80%** enforced in CI.  
Compliance test coverage requirement: **100%** — no exceptions.

### I.3 — Architecture Decisions Are Documented (ADR)

**Every architectural decision gets an ADR entry.**

An architectural decision is any choice that:
- Affects how components interact
- Affects data flow or storage
- Affects security or compliance posture
- Would be difficult or costly to reverse
- A future developer would need to understand to work safely

ADR location: `docs/adr/`  
ADR format: Standard template in `docs/adr/ADR-000-template.md`  
ADR index: `docs/adr/README.md` — updated with every new ADR

**No undocumented architectural decisions exist in this codebase.**  
If Claude makes an architectural choice, it creates the ADR  
in the same session. Not later. Now.

### I.4 — Prompts Are Preserved (Prompt History Records)

**All agents in this system are stateless.**  
The LLM has no memory between sessions.  
The prompt IS the behavior.  
Therefore the prompt IS the product.

PHR (Prompt History Records) preserve every significant  
prompt design decision so domain knowledge is never lost  
between sessions.

PHR location: `docs/phr/`  
PHR format: Standard template in `docs/phr/PHR-000-template.md`

A PHR entry is created or updated whenever:
- A new prompt is created for any agent
- An existing prompt is modified
- A prompt's performance is measured
- A prompt failure mode is discovered

Prompts are never inline strings scattered across agent files.  
**All prompts live in `/src/prompts/` as versioned Python constants.**  
Each prompt file references its PHR document.

### I.5 — Domain Knowledge Lives in Skills

**Reusable clinical and operational knowledge is encoded as Skills.**

Skills are structured knowledge documents in `docs/skills/`  
that Claude reads to understand a domain before acting in it.  
Skills reduce token usage by replacing long context injection  
with targeted knowledge retrieval.

A Skill is created whenever:
- The same domain knowledge is needed across multiple prompts
- A clinical rule is complex enough to warrant its own document
- An operational process requires step-by-step encoding

Skills are the encoded expertise that makes our system  
clinically accurate. They are core IP.

### I.6 — Real-World Connectivity via Skills + MCP

**MCP tools connect agents to live systems.**  
**Skills give agents the knowledge to use those connections correctly.**

The Skills + MCP combination is our token efficiency strategy:
```
Without Skills + MCP:
  Inject 10,000 tokens of ICD-10 rules into every prompt
  → Expensive, slow, context window pressure

With Skills + MCP:
  Agent reads Skill → knows which MCP tool to call →
  MCP tool returns specific data → Agent acts on it
  → Targeted, fast, cheap
```

MCP tools are defined in `src/mcp/`  
Skills that describe MCP tool usage are in `docs/skills/`  
Every MCP tool has a corresponding Skill document explaining  
when and how to use it correctly in the healthcare context.

---

## Article II — The Safety Law

**These rules cannot be overridden.**  
Not by a feature request. Not by a deadline.  
Not by a client asking nicely. Not by business pressure.  
Not by Claude's own reasoning about edge cases.

If a situation arises where violating Article II seems  
reasonable, that is a signal that the situation is being  
misunderstood — not that the constitution should bend.

### II.1 — No Autonomous Claim Submission

The system SHALL NEVER submit a coded insurance claim  
to any payer or clearinghouse without explicit human  
review and approval from a credentialed coder.

**Implementation requirement:**  
Every claim submission pathway must require a  
`human_approval_token` that is only generated after  
a coder explicitly approves the claim in the UI.  
Absence of this token raises `HumanApprovalRequiredError`.  
This error is never caught silently.

**Why this is law:**  
False Claims Act (31 USC §3729) penalties: $13,946–$27,894  
per false claim submitted to government payers.  
Olive AI raised $902M and partially collapsed from  
autonomous billing without adequate human oversight.  
Hospital CFOs will not purchase autonomous billing AI.  
Reference: ADR-002

### II.2 — No Clinical Assertion Without Source Citation

Every AI-generated clinical statement, diagnosis suggestion,  
or code recommendation MUST include an `evidence_quote` field  
containing the verbatim text from the source document  
that supports the assertion.

**Implementation requirement:**  
The Pydantic model for every suggestion type has  
`evidence_quote: str` as a required field (not Optional).  
Validation fails if `evidence_quote` is not a substring  
of the input document text.

**Why this is law:**  
A suggestion without a source is a hallucination.  
A hallucinated diagnosis in a signed medical record  
is a patient safety event and a legal liability.  
We do not generate clinical content. We extract and  
structure clinical content that already exists.

### II.3 — ICD-10 Official Guidelines Are Hard Constraints

The ICD-10-CM/PCS Official Coding Guidelines published by CMS  
are encoded as inviolable system constraints in the rules engine.  
They are not suggestions. They are not configurable.  
They do not have override flags.

The following are absolute prohibitions:
- Suggesting two codes that have an Excludes 1 relationship
- Coding an uncertain diagnosis as confirmed in outpatient setting
- Violating mandatory code sequencing rules
- Omitting a required paired code ("code also", "use additional")
- Assigning an invalid 7th character to an injury code

**Implementation requirement:**  
`src/core/icd10/rules_engine.py` validates every suggestion  
set before it reaches the coder interface. Violations raise  
`CodingGuidelineViolationError` — a hard stop, not a warning.

**Why this is law:**  
Incorrect coding of government-payer claims = False Claims Act.  
Incorrect POA indicators = Hospital-Acquired Condition penalties.  
Unbundling or upcoding = OIG audit and potential exclusion  
from Medicare/Medicaid programs.  
Reference: ADR-004

### II.4 — HIPAA Is Non-Negotiable Infrastructure

PHI (Protected Health Information) is never:
- Written to any log file in plain text or structured format
- Included in error messages, stack traces, or debug output
- Sent to any external service without an active BAA
- Stored beyond the minimum necessary retention period
- Accessible to any system component that doesn't require it

**Implementation requirement:**  
All Pydantic models containing PHI fields are annotated.  
Logging middleware strips PHI fields before any log write.  
PHI fields in logs are replaced with `[PHI-REDACTED]`.  
Audit logs record identifiers + actions, never PHI content.  
Reference: ADR-005

### II.5 — Graceful Degradation Is Mandatory

If any AI component fails for any reason, the clinical  
or administrative workflow MUST continue uninterrupted.  
AI assists humans. AI never blocks humans.

**Implementation requirement:**  
Every agent method wraps external calls in try/except.  
On failure: log the error (without PHI), return a  
`DegradedResult` with `is_degraded=True` and empty suggestions.  
The API never returns 500 to the coder interface.  
The UI always shows either AI suggestions or a manual mode.  
Never a broken state.

### II.6 — Conservative Defaults Always

When the AI system is uncertain between:
- A higher specificity code and a lower specificity code → lower
- Coding a condition and generating a CDI query → CDI query
- Submitting a claim and flagging for review → flag for review
- A confident suggestion and a hedged suggestion → hedged

**Why this is law:**  
Upcoding risk (FCA liability) is catastrophically worse  
than undercoding risk (revenue opportunity missed).  
CDI queries recover revenue safely.  
Autonomous overcoding destroys companies.

---

## Article III — The Technical Law

These define HOW we build technically.  
Violations create compounding technical debt that  
eventually becomes a patient safety or compliance issue.

### III.1 — Python With Strict Type Hints

Every function, method, and class has complete type hints.  
No `Any` types unless absolutely unavoidable with a comment explaining why.  
`mypy --strict` runs in CI and must pass.
```python
# CORRECT
async def extract_codes(
    note: FHIRDocumentReference,
    encounter: FHIREncounter,
    settings: CodingSettings,
) -> CodingAnalysisResult:

# WRONG
async def extract_codes(note, encounter, settings):
```

### III.2 — uv Is The Only Package Manager
```bash
# CORRECT
uv add anthropic
uv sync
uv run pytest

# WRONG — never do this
pip install anthropic
python -m pytest
```

No `requirements.txt`. No `pip install` in any script, Dockerfile,  
or CI file. All dependencies declared in `pyproject.toml`.  
`uv.lock` is committed and kept updated.

### III.3 — Linux/Bash Is The Environment

All scripts are bash. All paths use forward slashes.  
All commands are tested in WSL2 (Linux on Windows) environment.  
No PowerShell. No Windows-specific paths or commands.  
`scripts/` directory contains all utility scripts as `.sh` files.
```bash
# CORRECT
#!/usr/bin/env bash
set -euo pipefail

# WRONG
Set-ExecutionPolicy RemoteSigned
```

### III.4 — Pydantic V2 For All Data Structures

No raw Python dicts cross component boundaries.  
Every data structure that moves between functions,  
layers, or services is a Pydantic v2 model.  
`model_validate()` is called at every external boundary.
```python
# CORRECT
result = CodingAnalysisResult.model_validate(llm_response)

# WRONG
result = json.loads(llm_response)
codes = result["suggestions"]  # raw dict, no validation
```

### III.5 — Structured Logging Without PHI

All logging uses `structlog` with structured key-value format.  
Log level configuration via environment variable.  
PHI fields are never passed to any logger.
```python
# CORRECT
log.info("coding_analysis_complete",
         encounter_id=encounter.id,
         suggestion_count=len(result.suggestions),
         duration_ms=elapsed)

# WRONG
log.info(f"Analyzed note for {patient.name}: found {codes}")
```

### III.6 — Functions Under 40 Lines

If a function exceeds 40 lines, it is doing too much.  
Extract sub-functions. Name them clearly.  
The function name must describe what it does, not how.

### III.7 — No Hardcoded Secrets

API keys, database URLs, client secrets, and all credentials  
live in `.env` files only. Never in source code.  
`.env` is always in `.gitignore`.  
`.env.example` documents every required variable with description.

### III.8 — FastAPI For All HTTP Interfaces

Web framework is FastAPI. No Flask, no Django, no raw HTTP.  
All routes have Pydantic request and response models.  
All routes have OpenAPI documentation via docstrings.  
Health check endpoint at `/health` always returns 200 when running.

---

## Article IV — The Product Law

### IV.1 — Revenue Impact Is The North Star

Every feature is connected to a measurable financial outcome:
- DRG weight improvement (dollars per admission)
- Coder time reduction (hours per chart)
- Denial rate reduction (percentage points)
- Prior auth turnaround time (days reduced)

If a feature cannot be connected to one of these metrics,  
it is deprioritized until it can be.

### IV.2 — The Buyer Is The CFO

Every feature has a dollar-value story.  
Every metric is reported in revenue terms.  
Technical metrics (F1 score, precision, recall) are  
internal quality gates — they are never the CFO pitch.

The CFO pitch is always:
> "This feature improved DRG capture by X%, generating  
> $Y in additional annual revenue for your health system."

### IV.3 — The Champion Is The HIM Director

The HIM (Health Information Management) Director and  
CDI team understand the problem better than anyone.  
They are the internal champions who get deals approved.  
Every user interface decision considers their workflow.  
Every CDI query format follows AHIMA standards.

### IV.4 — Phase Discipline

We build in phases. We do not skip phases.
```
Phase 1: Coding AI + CDI (no ASR required)
Phase 2: Prior Auth Automation
Phase 3: Denial Prediction + Appeal Generation
Phase 4: ASR with Whisper (after Phase 1 revenue funds it)
```

No Phase 2 features are built while Phase 1 is incomplete.  
No ASR infrastructure is touched until Phase 1 has a paying customer.

---

## Article V — The Competitive Law

### V.1 — Research Before Building

The DISCOVER phase runs before the DESIGN phase.  
The DESIGN phase runs before the BUILD phase.  
Skipping DISCOVER means building without knowing edge cases.  
Edge cases discovered in production destroy client trust.

### V.2 — Skills Encode Irreplaceable Knowledge

Every piece of clinical domain knowledge learned through research  
is encoded in a Skill document before it influences any code.  
Skills are the accumulated expertise of our research phase.  
Skills cannot be reverse-engineered from the code.  
Skills are our deepest competitive moat.

### V.3 — The PHR Preserves Prompt Intelligence

Every prompt improvement is documented in its PHR entry  
with the exact scenario that motivated the change,  
the hypothesis tested, and the measured outcome.  
This creates a prompt evolution history that competitors  
cannot replicate without running the same experiments.

### V.4 — Compliance Is A Feature, Not A Constraint

Our guardrail architecture is not defensive engineering.  
It is a sales advantage.  
Hospital legal teams approve our system faster because  
we have documented every compliance decision in ADRs.  
Hospital CFOs trust our system because we cannot overcode  
even if we wanted to.  
We market our constraints as features.

---

## Article VI — The Amendment Process

### VI.1 — Articles I and III
May be amended by creating an ADR that explains the  
proposed change, alternatives considered, and rationale.  
ADR must be reviewed before any code adopts the change.

### VI.2 — Articles II and IV and V
May not be amended without explicit written rationale  
that addresses the specific compliance, patient safety,  
or competitive risk that motivated the original constraint.  
The bar for amending safety law is intentionally high.

### VI.3 — Emergency Exceptions
There are no emergency exceptions to Article II.  
If a client demands we violate Article II, we explain why  
we cannot and what alternative we offer instead.  
If a client insists, they are not the right client for us.

---

## Appendix A — Quick Reference For Claude

When beginning any session, Claude must:

1. Confirm constitution.md has been read
2. State which Articles are most relevant to today's task
3. Identify any potential Article II implications in the task
4. Check if an ADR exists for the architectural approach
5. Check if a PHR exists for any prompt being used or modified
6. Check if a Skill exists for the domain being worked in

When Claude is uncertain, Claude defaults to:
- The more conservative clinical coding choice
- The more documented architectural choice
- The more human-reviewed workflow option
- Creating an ADR rather than making an undocumented decision

When Claude is asked to violate Article II, Claude:
- Refuses clearly
- Explains which specific clause is at stake
- Proposes a compliant alternative that achieves the goal

---

## Appendix B — File Location Quick Reference
```
constitution.md          → This file. Read first. Always.
claude.md                → Project brief. Read second. Always.

docs/adr/                → Architecture Decision Records
docs/phr/                → Prompt History Records
docs/skills/             → Domain knowledge Skills
docs/research/           → DISCOVER phase research outputs

specs/                   → Spec-driven development specs

src/agents/              → Agent implementations
src/core/                → Domain logic (FHIR, ICD-10, DRG)
src/nlp/                 → NLP pipeline components
src/prompts/             → ALL prompts (versioned, never inline)
src/mcp/                 → MCP tool definitions
src/api/                 → FastAPI application

tests/unit/              → Unit tests (written before implementation)
tests/integration/       → Integration tests
tests/clinical/          → Clinical accuracy and compliance tests
tests/fixtures/          → Test data (de-identified)

scripts/                 → Bash utility scripts
data/icd10/              → ICD-10 reference data (CMS public)
data/drg/                → MS-DRG weights (CMS public)
data/mimic/              → MIMIC-IV (gitignored, local only)
```