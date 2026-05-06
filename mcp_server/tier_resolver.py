"""
Subscription tier resolution for MCP tool handlers.

Previously all 8 tool handlers hardcoded subscription_tier='free', which meant:
- Pro and Enterprise users got Groq-only free models regardless of payment
- Tier enforcement in ModelRouter was always bypassed

Now resolves tier from:
1. FORGESDLC_TIER env var (set by the Electron app or Claude Desktop on startup)
2. FORGESDLC_SESSION_TOKEN JWT (decodes tier from token payload)
3. Falls back to 'free'

Full JWT enforcement requires the auth flow (login → token → MCP header).
This is the pragmatic intermediate fix that at least reads env var so
developers can test pro-tier routing locally by setting FORGESDLC_TIER=pro.
"""

from __future__ import annotations

import os

import structlog

logger = structlog.get_logger()

_VALID_TIERS = {"free", "pro", "enterprise"}


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
            if tier in _VALID_TIERS:
                logger.debug("tier_resolver.from_jwt", tier=tier)
                return tier
        except Exception:
            pass  # expired or invalid token → fall through

    # Try direct env var (local dev / Electron sets this)
    env_tier = os.getenv("FORGESDLC_TIER", "").lower().strip()
    if env_tier in _VALID_TIERS:
        logger.debug("tier_resolver.from_env", tier=env_tier)
        return env_tier

    return "free"
