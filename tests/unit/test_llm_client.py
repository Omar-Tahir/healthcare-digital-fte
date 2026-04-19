"""
LLM Provider Abstraction Tests — ADR-014.

Verifies that create_llm_client() returns the correct provider based on
LLM_PROVIDER env var, and that _NormalisedResponse matches the interface
agents expect (response.content[0].text).
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestCreateLLMClient:
    """create_llm_client() returns the right provider."""

    def test_defaults_to_anthropic(self) -> None:
        """No LLM_PROVIDER set → AnthropicClient."""
        from src.core.llm.client import _AnthropicClient, create_llm_client

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_PROVIDER", None)
            client = create_llm_client()
        assert isinstance(client, _AnthropicClient)

    def test_anthropic_explicit(self) -> None:
        """LLM_PROVIDER=anthropic → AnthropicClient."""
        from src.core.llm.client import _AnthropicClient, create_llm_client

        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
            client = create_llm_client()
        assert isinstance(client, _AnthropicClient)

    def test_gemini_provider(self) -> None:
        """LLM_PROVIDER=gemini → GeminiClient (requires GEMINI_API_KEY)."""
        from src.core.llm.client import _GeminiClient, create_llm_client

        with patch.dict(os.environ, {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "fake-key-for-test",
        }):
            try:
                client = create_llm_client()
                assert isinstance(client, _GeminiClient)
            except ImportError:
                pytest.skip("google-genai not installed")

    def test_gemini_missing_key_raises(self) -> None:
        """LLM_PROVIDER=gemini without GEMINI_API_KEY raises EnvironmentError."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}):
            os.environ.pop("GEMINI_API_KEY", None)
            try:
                from src.core.llm.client import create_llm_client
                with pytest.raises(EnvironmentError, match="GEMINI_API_KEY"):
                    create_llm_client()
            except ImportError:
                pytest.skip("google-genai not installed")


class TestDefaultModel:
    """default_model() returns the right model ID per provider."""

    def test_anthropic_default(self) -> None:
        from src.core.llm.client import default_model

        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
            os.environ.pop("LLM_MODEL", None)
            assert default_model() == "claude-sonnet-4-6"

    def test_gemini_default(self) -> None:
        from src.core.llm.client import default_model

        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}):
            os.environ.pop("LLM_MODEL", None)
            assert default_model() == "gemini-2.0-flash"

    def test_override_with_env_var(self) -> None:
        from src.core.llm.client import default_model

        with patch.dict(os.environ, {
            "LLM_PROVIDER": "anthropic",
            "LLM_MODEL": "claude-opus-4-6",
        }):
            assert default_model() == "claude-opus-4-6"


class TestNormalisedResponse:
    """_NormalisedResponse satisfies the response.content[0].text interface."""

    def test_content_text_accessible(self) -> None:
        from src.core.llm.client import _NormalisedResponse

        r = _NormalisedResponse("hello world")
        assert r.content[0].text == "hello world"

    def test_content_is_list(self) -> None:
        from src.core.llm.client import _NormalisedResponse

        r = _NormalisedResponse("test")
        assert isinstance(r.content, list)
        assert len(r.content) == 1
