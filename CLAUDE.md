# Healthcare Digital FTE — Claude Project Brief
# READ THIS BEFORE EVERY TASK. READ REFERENCED FILES AS NEEDED.

## What This Is
AI system: clinical note → ICD-10 suggestions → CDI queries → DRG narrative → draft claim.
Enforces constitution.md at every layer. No autonomous claim submission. No PHI in logs.

## Current Status
Phase: VALIDATE (BUILD complete — 271 passed, 5 skipped)
Last completed: VALIDATE-005 (performance benchmark, 2026-04-27) — all 10 charts <30s, median ~6s
Active task: VALIDATE-006 pending VALIDATE-003 (MIMIC, blocked on PhysioNet creds)

## Session Start Ritual (Required)
Read in this order BEFORE writing any code:
1. constitution.md                        ← The law. Non-negotiable.
2. This file                              ← Project brief.
3. .claude/memory/build-status.md         ← Only if continuing BUILD work
4. .claude/memory/validate-phase.md       ← Only if working on validation
5. .claude/memory/architecture.md         ← Only if making structural changes
6. .claude/memory/adr-index.md            ← Only if making architectural decisions
7. Relevant Skill from .claude/skills/

Claude must confirm relevant files read and state which constitution Articles apply.

## Model Selection
DISCOVER / DESIGN tasks → claude-opus-4-6
BUILD / debug / tests   → claude-sonnet-4-6

## Skills — When to Use Each
Always:          hipaa-compliance
Coding work:     icd10-coding-rules
CDI work:        cdi-query-writing
DRG work:        drg-optimization
FHIR work:       fhir-r4-integration
Denial work:     payer-denial-patterns

## Development Sequence (Always Follow)
1. Does a spec exist? NO → write it first (specs/README.md template)
2. Does a compliance test exist? NO → write it first
3. Write failing test (TDD red)
4. Implement minimum to pass (TDD green)
5. Refactor without breaking tests
6. Architectural decision made? → create ADR immediately (docs/adr/)
7. Prompt created/modified? → update PHR immediately (docs/phr/)
8. Reusable domain knowledge encoded? → create/update Skill (.claude/skills/)

## Hard Constraints (Full details in constitution.md)
- No code without spec. No implementation before failing test.
- No autonomous claim submission (Article II.1)
- Evidence citation required on all suggestions (Article II.2)
- ICD-10 guidelines as hard constraints, not prompts (Article II.3)
- No PHI in any log (Article II.4)
- DegradedResult on failure — never raise (Article II.5)
- uv only (never pip). Bash only (never PowerShell).
- Functions under 40 lines. Pydantic for all structured data. structlog only.
- Prompts in src/prompts/ as versioned constants. Never inline.
