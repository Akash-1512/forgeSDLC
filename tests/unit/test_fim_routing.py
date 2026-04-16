from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def _make_fim_router() -> object:
    from model_router.fim_router import FIMRouter
    return FIMRouter()


def test_fim_returns_codestral_when_key_set() -> None:
    router = _make_fim_router()
    with patch.dict(os.environ, {"MISTRAL_CODESTRAL_KEY": "test-codestral-key"}):
        adapter = router.select()  # type: ignore[union-attr]
    from model_router.adapters.codestral_adapter import CodestralAdapter
    assert isinstance(adapter, CodestralAdapter)


def test_fim_returns_devstral_when_no_codestral_key() -> None:
    router = _make_fim_router()
    env = {k: v for k, v in os.environ.items() if k != "MISTRAL_CODESTRAL_KEY"}
    with patch.dict(os.environ, env, clear=True):
        adapter = router.select()  # type: ignore[union-attr]
    from model_router.adapters.ollama_adapter import OllamaAdapter
    assert isinstance(adapter, OllamaAdapter)
    assert adapter.model_name == "devstral"


def test_fim_never_returns_openai_adapter() -> None:
    router = _make_fim_router()
    env = {k: v for k, v in os.environ.items() if k != "MISTRAL_CODESTRAL_KEY"}
    with patch.dict(os.environ, env, clear=True):
        adapter = router.select()  # type: ignore[union-attr]
    from model_router.adapters.openai_adapter import OpenAIAdapter
    assert not isinstance(adapter, OpenAIAdapter)


def test_fim_never_returns_claude_adapter() -> None:
    router = _make_fim_router()
    env = {k: v for k, v in os.environ.items() if k != "MISTRAL_CODESTRAL_KEY"}
    with patch.dict(os.environ, env, clear=True):
        adapter = router.select()  # type: ignore[union-attr]
    from model_router.adapters.claude_adapter import ClaudeAdapter
    assert not isinstance(adapter, ClaudeAdapter)


def test_fim_never_returns_groq_adapter() -> None:
    router = _make_fim_router()
    env = {k: v for k, v in os.environ.items() if k != "MISTRAL_CODESTRAL_KEY"}
    with patch.dict(os.environ, env, clear=True):
        adapter = router.select()  # type: ignore[union-attr]
    from model_router.adapters.groq_adapter import GroqAdapter
    assert not isinstance(adapter, GroqAdapter)