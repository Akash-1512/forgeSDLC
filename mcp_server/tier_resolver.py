"""
Subscription tier resolution for MCP tool handlers.

Resolves the active subscription tier in this priority order:
1. ``FORGESDLC_TIER`` env var — set by the Electron app or Claude Desktop
2. ``FORGESDLC_SESSION_TOKEN`` JWT — decodes tier from token payload
3. Defaults to ``free``

Set ``FORGESDLC_TIER=pro`` locally to test pro-tier model routing without
going through the full login/JWT flow.
"""

from __future__ import annotations

import os

import structlog

logger = structlog.get_logger()


def resolve_tier() -> str:
    """Resolve subscription tier from environment.

    Priority:
    1. FORGESDLC_SESSION_TOKEN — JWT bearing tier claim
    2. FORGESDLC_TIER — direct env var override (for local dev)
    3. Default: 'free'
    """
    # Try JWT token first
    token = os.getenv("FORGESDLC_SESSION_TOKEN", "")
    if token:
        try:
            from subscription.session_manager import (
                verify_session_token,  # noqa: PLC0415
            )

            payload = verify_session_token(token)
            tier = str(payload.get("tier", "free"))
            if tier in {"free", "pro", "enterprise"}:
                logger.debug("tier_resolver.from_jwt", tier=tier)
                return tier
        except (ValueError, KeyError, TypeError, RuntimeError):
            pass  # expired, invalid, or unverifiable token → fall through

    # Try direct env var (local dev / Electron sets this)
    env_tier = os.getenv("FORGESDLC_TIER", "").lower().strip()
    if env_tier in {"free", "pro", "enterprise"}:
        logger.debug("tier_resolver.from_env", tier=env_tier)
        return env_tier

    return "free"
