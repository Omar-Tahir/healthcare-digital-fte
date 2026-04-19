# Hygiene Check Results — /mnt/d/HealthCare_Digital_Fte

Date: 2026-04-19

---

### 1. ADR Index Currency — PASS

The `.claude/memory/adr-index.md` lists 14 ADRs (ADR-001 through ADR-014). The `docs/adr/` directory contains exactly 14 corresponding `.md` files plus a `README.md`. All index entries match files on disk with no gaps or extras. ADR-014 (LLM Provider Abstraction, 2026-04-13) is the newest and appears correctly in both the index and `docs/adr/README.md`.

One minor note: `docs/adr/README.md` references `ADR-000-template.md` but that file does not exist on disk. This is a dead reference — low priority.

---

### 2. Secrets — CRITICAL FINDING

**`.env` is NOT in `.gitignore`** — this is the most important finding.

The `.gitignore` file contains no entry for `.env`. The file is currently untracked (`??` in git status), so it hasn't been committed yet. But without the gitignore entry, any future `git add -A` or `git add .` will stage and commit real credentials.

The `.env` file contains:
- A real Groq API key: `GROQ_API_KEY=[REDACTED — rotated]` (not a placeholder — confirmed by comparing to `.env.example` which shows `gsk_your_key_here`)
- Real-looking 64-hex-char values for `APPROVAL_TOKEN_SECRET_KEY` and `CLAIM_TOKEN_SECRET_KEY`

**Recommended actions:**
1. Add `.env` to `.gitignore` immediately (before any commit)
2. Rotate the Groq API key as a precaution
3. Rotate the token secrets if used in any shared environment

**No hardcoded secrets in source or test code.** All `src/**/*.py` and `tests/**/*.py` files were scanned — zero matches for `gsk_`, `sk-`, `AKIA`, or hardcoded `api_key=`/`password=`. Scripts use `os.getenv()` correctly.

---

### 3. PHI Issues — PASS

PHI protection is comprehensive and correctly implemented at multiple layers:

- `src/api/middleware/phi_filter.py`: structlog processor blocks all PHI field names before any log sink (G-HARD-005)
- `src/core/models/audit.py`: `PHI_FIELD_NAMES` frozenset (all 18 HIPAA identifiers) enforced at model creation via Pydantic validator
- `src/core/models/fhir.py` and `encounter.py`: PHI fields intentionally absent from data models; only system identifiers retained
- Tests in `test_known_cases_benchmark.py` assert no PHI markers exist in fixture notes
- `test_compliance_guardrails.py` uses synthetic names (John Smith, MRN12345678) only as inputs to verify the PHI filter blocks them

No real patient data found anywhere in source or test files.

---

### Summary Table

| Check | Status | Severity |
|-------|--------|----------|
| ADR index vs. docs/adr/ files | PASS — 14/14 synchronized | — |
| ADR-000 template file missing | Minor dead reference | Low |
| Hardcoded secrets in src/ or tests/ | PASS — none found | — |
| `.env` in `.gitignore` | **FAIL — NOT gitignored** | **Critical** |
| Real API key in .env | **FAIL — real Groq key present** | **Critical** |
| PHI in source code / logs | PASS — PHI filter enforced | — |
| PHI in test fixtures | PASS — all synthetic | — |

**Blocking item before next git commit: add `.env` to `.gitignore`.**
