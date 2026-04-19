"""
LLM Provider Abstraction — ADR-014.

Factory that returns a unified LLM client regardless of provider.
The returned object always exposes:

    await client.messages_create(
        model=..., max_tokens=..., messages=[{"role": ..., "content": ...}]
    )
    # response.content[0].text → str

Supported providers (LLM_PROVIDER env var):
  "anthropic" — Anthropic Claude API (default)
  "gemini"    — Google Generative AI (requires billing-free GCP project)
  "groq"      — Groq free tier (recommended for development, no billing needed)

ADR: docs/adr/ADR-014-llm-provider-abstraction.md
Constitution: I.3 (documented decision), II.4 (no PHI in logs), II.5 (never raises to caller)
"""
from __future__ import annotations

import os
from typing import Any


# ─── Response normalisation ───────────────────────────────────────────────────

class _TextContent:
    """Mimics anthropic.types.TextBlock — exposes .text attribute."""

    def __init__(self, text: str) -> None:
        self.text = text


class _NormalisedResponse:
    """
    Wraps any provider response so callers can always do
    response.content[0].text without caring about the underlying SDK.
    """

    def __init__(self, text: str) -> None:
        self.content = [_TextContent(text)]


# ─── Anthropic provider ───────────────────────────────────────────────────────

class _AnthropicClient:
    """Thin async wrapper around anthropic.AsyncAnthropic."""

    def __init__(self) -> None:
        import anthropic  # lazy import — only needed if provider=anthropic
        self._client = anthropic.AsyncAnthropic()

    async def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
    ) -> Any:
        return await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )


# ─── Gemini provider ──────────────────────────────────────────────────────────

class _GeminiClient:
    """
    Async wrapper around Google Generative AI SDK.

    Normalises Gemini responses to the same interface as Anthropic:
    response.content[0].text

    Note: requires a GCP project with NO billing account linked.
    Keys from billing-enabled projects have free-tier quota = 0.
    """

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY not set. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        from google import genai  # lazy import — only needed if provider=gemini
        self._client = genai.Client(api_key=api_key).aio

    async def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
    ) -> _NormalisedResponse:
        from google.genai import types as genai_types

        prompt_parts = [m["content"] for m in messages if m.get("role") == "user"]
        prompt = "\n\n".join(prompt_parts)

        response = await self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
            ),
        )

        return _NormalisedResponse(response.text)


# ─── Groq provider ───────────────────────────────────────────────────────────

class _GroqClient:
    """
    Async wrapper around the Groq SDK.

    Groq is the recommended free-tier provider for development:
    - No billing account required
    - 30 req/min, 14,400 req/day on free tier
    - Get API key at https://console.groq.com (email only)

    Default model: llama-3.3-70b-versatile (best reasoning on free tier)
    """

    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set. "
                "Get a free key (no credit card) at https://console.groq.com"
            )
        from groq import AsyncGroq  # lazy import — only needed if provider=groq
        self._client = AsyncGroq(api_key=api_key)

    async def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, str]],
    ) -> _NormalisedResponse:
        response = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,  # type: ignore[arg-type]
        )
        return _NormalisedResponse(response.choices[0].message.content or "")


# ─── Utility ─────────────────────────────────────────────────────────────────

def strip_markdown_fences(text: str) -> str:
    """
    Remove markdown code fences that some LLMs (Llama/Groq) wrap JSON in.

    Handles:
      ```json\\n{...}\\n```
      ```\\n{...}\\n```
      {plain json with no fences}
    """
    text = text.strip()
    if text.startswith("```"):
        # drop the opening fence line (```json or ```)
        text = text[text.index("\n") + 1:] if "\n" in text else text[3:]
        # drop the closing fence
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_llm_client() -> _AnthropicClient | _GeminiClient | _GroqClient:
    """
    Return the appropriate LLM client based on LLM_PROVIDER env var.

    LLM_PROVIDER=anthropic (default) → _AnthropicClient
    LLM_PROVIDER=gemini              → _GeminiClient
    LLM_PROVIDER=groq                → _GroqClient (recommended for dev)
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "gemini":
        return _GeminiClient()
    if provider == "groq":
        return _GroqClient()
    return _AnthropicClient()


# ─── Default model names per provider ────────────────────────────────────────

def default_model() -> str:
    """
    Return the default model ID for the active provider.

    Override with LLM_MODEL env var.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "gemini":
        return os.getenv("LLM_MODEL", "gemini-2.0-flash")
    if provider == "groq":
        return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    return os.getenv("LLM_MODEL", "claude-sonnet-4-6")
