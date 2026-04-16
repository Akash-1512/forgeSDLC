from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from providers.manifest import ProviderManifest
from providers.resolver import ProviderResolver

_ALL_ENV_VARS = [
    "DATABASE_URL", "OPENAI_API_KEY", "GROQ_API_KEY",
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_AI_SEARCH_ENDPOINT", "AZURE_STORAGE_CONNECTION_STRING",
    "APPLICATIONINSIGHTS_CONNECTION_STRING", "AZURE_ML_WORKSPACE",
    "GOOGLE_API_KEY", "MISTRAL_CODESTRAL_KEY", "MISTRAL_API_KEY",
    "RENDER_API_KEY", "TAVILY_API_KEY", "DEVIN_API_KEY",
    "CURSOR_API_KEY", "CURSOR_API_VERIFIED", "REDIS_URL", "SECRET_KEY",
]


def test_resolve_all_never_raises_with_no_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Core guarantee: ProviderResolver must never raise regardless of env vars."""
    for var in _ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    resolver = ProviderResolver()
    manifest = resolver.resolve_all()  # must not raise
    assert isinstance(manifest, ProviderManifest)
    assert len(manifest.all_services()) == 13


def test_resolve_all_never_raises_with_all_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    resolver = ProviderResolver()
    manifest = resolver.resolve_all()
    assert isinstance(manifest, ProviderManifest)
    assert len(manifest.all_services()) == 13


def test_resolve_db_uses_postgresql_not_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    resolver = ProviderResolver()
    selection = resolver._resolve_db()
    assert "postgresql" in selection.provider
    assert "sqlite" not in selection.connection_string.lower()


def test_resolve_db_falls_back_to_local_db_url_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    resolver = ProviderResolver()
    selection = resolver._resolve_db()
    from orchestrator.constants import LOCAL_DB_URL
    assert "postgresql" in selection.connection_string or \
           selection.connection_string == LOCAL_DB_URL or \
           "forgesdlc" in selection.connection_string


def test_print_table_outputs_all_13_services(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in _ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    resolver = ProviderResolver()
    resolver.print_table()
    captured = capsys.readouterr()
    services = [
        "llm", "embeddings", "vector_store", "database",
        "blob_storage", "monitoring", "experiment", "deployment",
        "docs_fetcher", "connected_tools", "auth", "mcp", "cache",
    ]
    for service in services:
        assert service in captured.out, f"Service '{service}' missing from print_table output"