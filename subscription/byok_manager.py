from __future__ import annotations

import structlog

logger = structlog.get_logger()

_SERVICE = "forgesdlc"

# Lazy import — keyring requires D-Bus on Linux (unavailable in CI without setup).
# Set PYTHON_KEYRING_BACKEND=keyrings.alt.PlaintextKeyring in CI.
# In tests: always mock keyring.set_password / keyring.get_password.
try:
    import keyring as _keyring
except ImportError:  # pragma: no cover
    _keyring = None  # type: ignore[assignment]


def _get_keyring() -> object:
    """Return keyring module or raise a clear error if not installed."""
    if _keyring is None:
        raise RuntimeError(
            "keyring package is required for BYOK. "
            "Install it: pip install keyring. "
            "In CI: set PYTHON_KEYRING_BACKEND=keyrings.alt.PlaintextKeyring"
        )
    return _keyring


class BYOKManager:
    """Stores API keys in the OS keychain via keyring.

    NEVER stores keys in plaintext — not in .env, not in DB, not in logs.
    Validates key with a 1-token ping (via KeyValidator) before storing.

    CI NOTE: keyring uses D-Bus SecretService on Linux which is unavailable
    in GitHub Actions. Set PYTHON_KEYRING_BACKEND=keyrings.alt.PlaintextKeyring
    in CI. In tests: always mock keyring.set_password / keyring.get_password.
    """

    def save_key(self, provider: str, key: str) -> None:
        """Store API key in OS keychain. Never logs the key value."""
        kr = _get_keyring()
        kr.set_password(_SERVICE, provider, key)  # type: ignore[union-attr]
        logger.info("byok_key_saved", provider=provider)

    def get_key(self, provider: str) -> str | None:
        """Retrieve API key from OS keychain. Returns None if not set or unavailable."""
        if _keyring is None:
            return None
        try:
            return _keyring.get_password(_SERVICE, provider)
        except Exception:
            # keyring installed but no backend available (e.g. no D-Bus on headless Linux)
            return None

    def delete_key(self, provider: str) -> None:
        """Remove API key from OS keychain."""
        kr = _get_keyring()
        try:
            kr.delete_password(_SERVICE, provider)  # type: ignore[union-attr]
            logger.info("byok_key_deleted", provider=provider)
        except Exception as exc:
            logger.warning("byok_key_delete_failed", provider=provider, error=str(exc))

    def has_key(self, provider: str) -> bool:
        """Return True if a key is stored for this provider."""
        return self.get_key(provider) is not None

    def list_providers(self) -> list[str]:
        """Return list of providers with keys stored. Checks known providers."""
        known = ["openai", "anthropic", "groq", "google", "devin", "cursor"]
        return [p for p in known if self.has_key(p)]

    def anthropic_byok_requires_tos_warning(self) -> bool:
        """True when Anthropic key is set — ToS warning must be shown."""
        return self.has_key("anthropic")
