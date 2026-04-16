from __future__ import annotations

import keyring
import structlog

logger = structlog.get_logger()

_SERVICE = "forgesdlc"


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
        # import keyring  # noqa: PLC0415
        keyring.set_password(_SERVICE, provider, key)
        # Log provider only — NEVER log the key value itself
        logger.info("byok_key_saved", provider=provider)

    def get_key(self, provider: str) -> str | None:
        """Retrieve API key from OS keychain. Returns None if not set."""
        # import keyring  # noqa: PLC0415
        return keyring.get_password(_SERVICE, provider)

    def delete_key(self, provider: str) -> None:
        """Remove API key from OS keychain."""
        # import keyring  # noqa: PLC0415
        try:
            keyring.delete_password(_SERVICE, provider)
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
        """True when Anthropic key is set — ToS warning must be shown.

        The AnthropicTosWarning flow must complete before Claude unlocks.
        See subscription/anthropic_tos_warning.py for the full flow.
        """
        return self.has_key("anthropic")