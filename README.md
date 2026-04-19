# Healthcare Digital FTE

> AI-powered medical coding, CDI automation, and revenue cycle optimization.  
> Anthropic AI Hackathon submission — Phase 1 complete.

---

## What This Is

Healthcare Digital FTE automates the work of hospital coders and Clinical Documentation Improvement (CDI) specialists. It takes a clinical note, extracts ICD-10 codes with evidence citations, identifies documentation gaps that suppress revenue, generates AHIMA-compliant physician queries, and calculates DRG revenue impact — all in under 3 minutes per chart, versus 15–20 minutes manually.

**No claim is ever submitted without a credentialed human coder's approval.** The system is a decision-support tool, not an autonomous billing engine.

---

## Revenue Impact Demonstrated

| Scenario | Before | After | Impact |
|----------|--------|-------|--------|
| Sepsis specificity (organ dysfunction documented) | DRG 872 — $12,641 | DRG 870 — $55,400 | **+$42,759/case** |
| HTN + CHF linkage (hypertensive heart disease) | Separate codes | I13.0 linkage | **+$9,000+/case** |
| AKI documentation (acute vs. chronic) | CC tier | MCC tier | **+$6,384/case** |

These scenarios are encoded as reproducible test cases in `tests/fixtures/known_cases/`.

---

## Architecture

```
Clinical Note (FHIR R4)
        │
        ▼
 NLP Pipeline ──── NegEx negation detection
 src/nlp/          Temporal classification
                   Section parsing (HPI/Assessment/Plan)
        │
        ▼
 Coding Agent ──── ICD-10-CM extraction
 src/agents/       Evidence citation (exact text spans)
 coding_agent.py   Specificity upgrade suggestions
        │
        ▼
 Rules Engine ──── Hard constraints (Excludes1, sex/age edits)
 src/core/icd10/   CCI edits, manifestation sequencing
                   CC/MCC tier assignment
        │
        ▼
 CDI Agent ──────── Documentation gap detection
 src/agents/        AHIMA-compliant query generation
 cdi_agent.py       Physician query templates
        │
        ▼
 DRG Agent ──────── MS-DRG grouping (CMS logic)
 src/agents/        Revenue impact calculation
 drg_agent.py       MCC/CC tier optimization
        │
        ▼
 Guardrail Layer ── 12 constitution-enforced guardrails
 src/core/          No autonomous claim submission
 guardrails/        PHI filter on all logs
                    Evidence required on all suggestions
        │
        ▼
 Coder Review UI ── HTMX single-page interface
 src/api/static/    HMAC approval token workflow
                    Human-in-the-loop before claim output
```

---

## Engineering Proof Points

| Metric | Value |
|--------|-------|
| Test suite | **287 passed, 5 skipped** (MIMIC data-gated) |
| Compliance guardrail tests | **36/36 green** |
| Specs written before code | **7 specs** |
| Architecture Decision Records | **14 ADRs** |
| Prompt History Records | **4 PHRs** |
| Functions over 40 lines | **0** |
| Inline prompts | **0** (all in `src/prompts/` as versioned constants) |
| PHI in any log | **0** (structlog PHI filter enforced) |

---

## Constitution (The Law)

Six inviolable rules enforced at every layer:

1. **No autonomous claim submission** — human coder approval required
2. **Evidence citation required** — every suggestion cites exact text from the note
3. **ICD-10 guidelines as hard constraints** — not soft suggestions
4. **No PHI in any log** — structlog PHI filter blocks all 18 HIPAA identifiers
5. **DegradedResult on failure** — never raise, never guess
6. **Guardrails as architecture** — compliance enforced in code, not prompts

See [`CONSTITUTION.md`](CONSTITUTION.md) for the full specification.

---

## Key Components

### `src/agents/`
- `coding_agent.py` — ICD-10 extraction with evidence citation
- `cdi_agent.py` — CDI gap detection + AHIMA-compliant query generation
- `drg_agent.py` — MS-DRG grouping and revenue impact calculation

### `src/core/`
- `icd10/rules_engine.py` — Excludes1, sex/age, manifestation, CCI hard constraints
- `drg/grouper.py` — MS-DRG grouper with CC/MCC tier logic
- `guardrails/` — 12 guardrail modules (claim, evidence, ICD-10, CDI, DRG, PHI, FHIR)
- `fhir/client.py` — SMART on FHIR / JWT auth, Epic sandbox integration

### `src/nlp/`
- `pipeline.py` — Full NLP pipeline orchestrator
- `negation.py` — NegEx negation detection
- `temporal.py` — Temporal classification (current vs. historical)
- `section_parser.py` — Clinical note section segmentation

### `src/api/`
- `main.py` — FastAPI application
- `static/index.html` — HTMX coder review UI
- `security/approval_token.py` — HMAC token workflow

### `src/prompts/`
Versioned prompt constants (never inline):
- `coding_extraction.py` — PHR-001
- `cdi_query.py` — PHR-002
- `drg_analysis.py` — PHR-003

---

## Running Locally

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/Omar-Tahir/healthcare-digital-fte.git
cd healthcare-digital-fte

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env — add your Groq or Anthropic API key

# Run tests
uv run pytest tests/ --tb=short -q

# Start the API server
uv run python main.py
```

### LLM Provider Options

The system supports three providers (configured via `LLM_PROVIDER` in `.env`):

| Provider | Use Case | Notes |
|----------|----------|-------|
| `groq` | Development (default) | Free tier, 30 req/min |
| `gemini` | Development | Free tier (no billing account) |
| `anthropic` | Production | Claude Sonnet 4.6 |

---

## Validation Status

| Benchmark | Status | Result |
|-----------|--------|--------|
| VALIDATE-001 — Guardrail tests | COMPLETE | 36/36 green |
| VALIDATE-002 — Known-cases benchmark | COMPLETE | 5/5 cases correct |
| VALIDATE-003 — MIMIC-IV accuracy | PENDING | Requires MIMIC data download |
| VALIDATE-004 — End-to-end pilot | PENDING | Pilot site TBD |

---

## Docs

- [`CONSTITUTION.md`](CONSTITUTION.md) — The six inviolable rules
- [`docs/adr/`](docs/adr/) — 14 Architecture Decision Records
- [`docs/phr/`](docs/phr/) — 4 Prompt History Records
- [`docs/research/`](docs/research/) — 5 research documents (DISC-001..005)
- [`specs/`](specs/) — 7 component specifications

---

## Built With

- [Anthropic Claude API](https://www.anthropic.com/) — LLM backbone (production)
- [FHIR R4](https://hl7.org/fhir/R4/) — Clinical data standard
- [FastAPI](https://fastapi.tiangolo.com/) + [HTMX](https://htmx.org/) — API + UI
- [Pydantic v2](https://docs.pydantic.dev/) — All structured data
- [structlog](https://www.structlog.org/) — HIPAA-safe structured logging
- [uv](https://docs.astral.sh/uv/) — Package management

---

*Anthropic AI Hackathon — April 2026*
