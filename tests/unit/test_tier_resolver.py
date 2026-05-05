"""Tests for mcp_server/tier_resolver.py (M20)."""

from __future__ import annotations

import os
from unittest.mock import patch


def test_resolve_tier_defaults_to_free() -> None:
    """No env vars set → must return 'free'."""
    with patch.dict(os.environ, {}, clear=False):
        env_backup = {
            k: os.environ.pop(k)
            for k in ["FORGESDLC_TIER", "FORGESDLC_SESSION_TOKEN"]
            if k in os.environ
        }
        try:
            from mcp_server.tier_resolver import resolve_tier

            result = resolve_tier()
            assert result == "free"
        finally:
            os.environ.update(env_backup)


def test_resolve_tier_reads_forgesdlc_tier_env_var() -> None:
    """FORGESDLC_TIER=pro → returns 'pro'."""
    with patch.dict(os.environ, {"FORGESDLC_TIER": "pro", "FORGESDLC_SESSION_TOKEN": ""}):
        from mcp_server.tier_resolver import resolve_tier

        result = resolve_tier()
        assert result == "pro"


def test_resolve_tier_rejects_invalid_tier() -> None:
    """FORGESDLC_TIER=admin → falls back to 'free' (not a valid tier)."""
    with patch.dict(os.environ, {"FORGESDLC_TIER": "admin", "FORGESDLC_SESSION_TOKEN": ""}):
        from mcp_server.tier_resolver import resolve_tier

        result = resolve_tier()
        assert result == "free"


def test_resolve_tier_enterprise() -> None:
    """FORGESDLC_TIER=enterprise → returns 'enterprise'."""
    with patch.dict(os.environ, {"FORGESDLC_TIER": "enterprise", "FORGESDLC_SESSION_TOKEN": ""}):
        from mcp_server.tier_resolver import resolve_tier

        result = resolve_tier()
        assert result == "enterprise"


def test_resolve_tier_invalid_jwt_falls_back_to_env() -> None:
    """Malformed JWT → falls through to FORGESDLC_TIER env var."""
    with patch.dict(os.environ, {"FORGESDLC_SESSION_TOKEN": "not.a.jwt", "FORGESDLC_TIER": "pro"}):
        from mcp_server.tier_resolver import resolve_tier

        result = resolve_tier()
        assert result == "pro"
