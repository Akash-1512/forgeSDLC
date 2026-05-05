from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt  # PyJWT — import as 'jwt'. NOT python-jose (has CVEs, unmaintained)
import structlog

# CRITICAL: this must be PyJWT, not python-jose.
# Verify: import jwt; assert jwt.__version__  ← PyJWT exposes __version__
# python-jose does NOT expose __version__ at the top-level jwt module.
# If python-jose is installed alongside PyJWT, whichever resolves first in
# sys.path will be used — test_uses_pyjwt_not_python_jose catches the wrong one.

logger = structlog.get_logger()

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_HOURS = 24


def _get_secret() -> str:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "SECRET_KEY env var not set. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return secret


def create_session_token(user_id: str, tier: str) -> str:
    """Create a signed JWT session token.

    Raises RuntimeError if SECRET_KEY is not set.
    Uses PyJWT with HS256 — NOT python-jose.
    """
    secret = _get_secret()
    now = datetime.now(tz=UTC)
    payload = {
        "user_id": user_id,
        "tier": tier,
        "iat": now,
        "exp": now + timedelta(hours=_TOKEN_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, secret, algorithm=_ALGORITHM)
    logger.info("session_manager.token_created", user_id=user_id, tier=tier)
    return token


def verify_session_token(token: str) -> dict[str, object]:
    """Verify and decode a JWT session token.

    Raises jwt.ExpiredSignatureError if token is expired.
    Raises jwt.InvalidTokenError for any other verification failure.
    """
    secret = _get_secret()
    payload: dict[str, object] = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    logger.info(
        "session_manager.token_verified",
        user_id=payload.get("user_id"),
        tier=payload.get("tier"),
    )
    return payload


def get_user_id_from_token(token: str) -> str:
    """Convenience wrapper — returns user_id from a valid token."""
    payload = verify_session_token(token)
    return str(payload["user_id"])


def get_tier_from_token(token: str) -> str:
    """Convenience wrapper — returns tier from a valid token."""
    payload = verify_session_token(token)
    return str(payload["tier"])
