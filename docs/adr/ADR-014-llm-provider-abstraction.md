# ADR-014: LLM Provider Abstraction Layer

**Status:** Accepted  
**Date:** 2026-04-13  
**Author:** Engineering  
**Constitution Articles:** I.3 (document decisions), III.8 (testable abstractions)

---

## Context

All three agents (CodingAgent, CDIAgent, DRGAgent) contain an identical
inner `_AsyncLLMClient` class that directly imports and instantiates
`anthropic.AsyncAnthropic()`. This creates two problems:

1. **Cost**: The Anthropic API is paid. During development, we need a free
   tier LLM to run live benchmarks without budget.

2. **Lock-in**: Hardcoded provider makes it impossible to switch, compare
   providers, or use a free tier for development.

The constraint: all existing tests mock `agent._llm_client.messages_create`
with the interface `(model, max_tokens, messages) → response` where
`response.content[0].text` returns the text. This interface must remain
stable.

---

## Decision

Create `src/core/llm/client.py` with a `create_llm_client()` factory
that returns an object with the same `messages_create(model, max_tokens,
messages)` interface regardless of provider.

The factory reads `LLM_PROVIDER` env var (default: `"anthropic"`).
Supported providers:
- `"anthropic"` — `anthropic.AsyncAnthropic()` (existing behavior)
- `"gemini"` — Google Generative AI SDK, normalized to the same interface

Each agent's `_AsyncLLMClient.__init__` is refactored to call
`create_llm_client()` instead of directly instantiating Anthropic.

**Model mapping** (env var `LLM_MODEL` overrides):
- Anthropic default: `claude-sonnet-4-6`
- Gemini default: `gemini-2.0-flash` (free tier, 1,500 RPM)

**Response normalization**: Gemini returns `response.text`; a thin wrapper
returns an object with `content[0].text` so the existing interface is
unchanged and no agent code needs updating.

---

## Alternatives Considered

### A: Multiple _AsyncLLMClient implementations per agent
- Rejected: N×3 duplicated code for N providers

### B: Abstract base class with subclasses
- Rejected: Over-engineering for 2 providers; factory function is simpler

### C: LangChain / LiteLLM
- Rejected: Heavy dependency, adds complexity, conflicts with constitution
  Article III preference for minimal deps

---

## Consequences

**Positive:**
- Development runs on Gemini free tier (zero cost)
- Production deploys on Anthropic (best quality)
- No existing tests need changes — interface is stable
- Single file to update when adding a third provider

**Negative:**
- Gemini response format differs from Anthropic; normalization adds a thin
  wrapper that could hide errors
- Model names must be tracked per provider (separate env var)

---

## Configuration

```bash
# .env — Gemini free tier (development)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_from_aistudio.google.com

# .env — Anthropic (production)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key
```

---

## Implementation Files

- `src/core/llm/__init__.py`
- `src/core/llm/client.py` — factory + provider implementations
- Updated: `src/agents/coding_agent.py`, `src/agents/cdi_agent.py`,
  `src/agents/drg_agent.py`
- Updated: `.env.example`
