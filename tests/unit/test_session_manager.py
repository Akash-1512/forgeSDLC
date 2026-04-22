from __future__ import annotations

from datetime import UTC

import pytest


def test_create_token_encodes_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32chars-xxxxxxxxx")
    from subscription.session_manager import create_session_token, verify_session_token

    token = create_session_token("user-123", "pro")
    payload = verify_session_token(token)
    assert payload["user_id"] == "user-123"


def test_create_token_encodes_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32chars-xxxxxxxxx")
    from subscription.session_manager import create_session_token, verify_session_token

    token = create_session_token("user-456", "enterprise")
    payload = verify_session_token(token)
    assert payload["tier"] == "enterprise"


def test_verify_token_returns_correct_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32chars-xxxxxxxxx")
    from subscription.session_manager import (
        create_session_token,
        get_user_id_from_token,
    )

    token = create_session_token("akash", "pro")
    assert get_user_id_from_token(token) == "akash"


def test_expired_token_raises_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32chars-xxxxxxxxx")
    from datetime import datetime, timedelta

    import jwt

    secret = "test-secret-key-32chars-xxxxxxxxx"
    payload = {
        "user_id": "user-exp",
        "tier": "free",
        "iat": datetime.now(tz=UTC) - timedelta(hours=48),
        "exp": datetime.now(tz=UTC) - timedelta(hours=24),
    }
    expired_token = jwt.encode(payload, secret, algorithm="HS256")
    from subscription.session_manager import verify_session_token

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_session_token(expired_token)


def test_uses_pyjwt_not_python_jose() -> None:
    """PyJWT exposes jwt.__version__. python-jose does not."""
    import jwt

    assert hasattr(jwt, "__version__"), (
        "jwt module does not have __version__ — python-jose may be installed instead of PyJWT."
    )
    secret = "a" * 32  # 32 bytes — meets PyJWT minimum for HS256
    payload = {"test": True}
    result = jwt.encode(payload, secret, algorithm="HS256")
    assert isinstance(result, str)
