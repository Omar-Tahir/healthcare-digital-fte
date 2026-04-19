# ADR-003: Claude as Primary LLM Provider

**Status:** ACCEPTED
**Date:** 2026-03-30
**Decision makers:** Engineering team
**Constitution references:** Article III (Technical Law)

---

## Context

The system requires an LLM for five distinct tasks:
1. ICD-10 code extraction from clinical notes (PROMPT-001)
2. CDI physician query generation (PROMPT-002)
3. DRG impact narrative generation (PROMPT-003)
4. Appeal letter generation (PROMPT-004)
5. Future tasks as the system expands

Each task requires strong instruction following, structured
JSON output, clinical reasoning capability, and reliable
behavior under complex multi-rule prompts (15 qualifier words,
sequencing rules, Excludes logic, setting-specific behavior).

We must choose an LLM provider.

---

## Decision

**Use Anthropic Claude exclusively.**

- **claude-sonnet-4-6** for default tasks: coding extraction,
  CDI queries, DRG narratives (~95% of LLM calls)
- **claude-opus-4-6** for complex reasoning: appeal letters
  (~5% of LLM calls)

Design choices enabling this:
1. **Skills + MCP pattern** — domain knowledge in Skills
   documents + live data via MCP tools reduces context window
   usage by 99.4% vs injecting full ICD-10 tables
2. **Prompt caching** — system prompts are cached (stable
   across calls), user prompts vary per encounter. Reduces
   cost significantly.
3. **Token budget** — $37.55 per 1,000 charts across all
   4 prompts. Less than 0.1% of captured revenue.

---

## Alternatives Considered

### Alternative 1: GPT-4 / GPT-4o (OpenAI)

Strong general capability, Azure deployment option for
healthcare compliance.

**Not selected because:**
- DISC-005 benchmarks show GPT-4 achieves <50% (33.9%)
  exact match on full-code ICD-10 prediction tasks
- Claude's instruction following is stronger for our complex
  prompt architecture (15 qualifier words, Excludes logic,
  setting-specific rules in a single system prompt)
- Azure OpenAI adds deployment complexity without clear
  accuracy advantage for our use case
- Not a hard rejection — could be revisited if Claude
  pricing or availability changes

### Alternative 2: Open-Source Models (Llama, Mistral)

Self-hosted models for cost control and data privacy.

**Rejected because:**
- Insufficient clinical reasoning capability for complex
  tasks (sepsis sequencing, uncertain diagnosis rules)
- No prompt caching — higher per-call cost at scale
- Operational burden of GPU infrastructure, model updates,
  and reliability engineering
- Healthcare-specific fine-tuning would require labeled
  clinical datasets we don't have in Phase 1

### Alternative 3: Multi-Model Approach

Use different models for different tasks based on cost
and capability.

**Deferred (not rejected):**
- Valid Phase 3+ approach when we have benchmarks per task
- In Phase 1, single-vendor simplicity reduces integration
  risk and prompt maintenance burden
- Maintaining prompts for multiple models multiplies the
  PHR documentation overhead
- Could revisit when open-source clinical models mature

---

## Consequences

### Positive

1. **Strong instruction following** — Claude handles complex
   multi-rule prompts reliably (P1-P5 principles)
2. **Prompt caching** — system prompt reuse across calls
   reduces cost significantly
3. **Single vendor simplicity** — one API, one SDK, one
   set of prompts to maintain
4. **Structured output** — reliable JSON generation for
   Pydantic model parsing
5. **Model family flexibility** — Sonnet for volume,
   Opus for complexity, within same API

### Negative

1. **Vendor lock-in** — if Anthropic changes pricing,
   availability, or model behavior, migration is costly.
   Mitigation: prompts are documented in PHRs with design
   rationale, making adaptation to other models feasible.
2. **No on-premise option** — Claude is cloud-only. Some
   highly regulated environments require on-premise LLM.
   Mitigation: PHI never reaches the LLM (placeholder
   tokens per PROMPT-004, encounter_id only in audit logs).
3. **Pricing uncertainty** — $37.55/1K charts is current
   estimate. Model pricing changes affect unit economics.

---

## References

- Constitution Article III (Technical Law)
- DISC-005 (Competitor Technical Analysis — LLM benchmarks)
- DESIGN-004 (Prompt Engineering Architecture)
- PHR-001 through PHR-004 (Prompt History Records)
