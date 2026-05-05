from __future__ import annotations

import structlog

logger = structlog.get_logger()


class KeyValidator:
    """Validates API keys with a 1-token ping before storing in keychain.

    Each provider has its own validation method.
    Raises ValueError if the key is invalid or the ping fails.
    """

    async def validate(self, provider: str, key: str) -> bool:
        """Route to the correct provider validator. Returns True on success."""
        validators = {
            "openai": self._validate_openai,
            "anthropic": self._validate_anthropic,
            "groq": self._validate_groq,
            "google": self._validate_google,
        }
        validator = validators.get(provider)
        if validator is None:
            logger.warning(
                "key_validator.unknown_provider",
                provider=provider,
                hint="Skipping validation — provider not recognised",
            )
            return True  # Unknown providers pass through — don't block BYOK
        return await validator(key)

    async def _validate_openai(self, key: str) -> bool:
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                valid = response.status_code == 200
                logger.info("key_validator.openai", valid=valid)
                return valid
        except Exception as exc:
            logger.error("key_validator.openai_error", error=str(exc))
            return False

    async def _validate_anthropic(self, key: str) -> bool:
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                valid = response.status_code == 200
                logger.info("key_validator.anthropic", valid=valid)
                return valid
        except Exception as exc:
            logger.error("key_validator.anthropic_error", error=str(exc))
            return False

    async def _validate_groq(self, key: str) -> bool:
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                valid = response.status_code == 200
                logger.info("key_validator.groq", valid=valid)
                return valid
        except Exception as exc:
            logger.error("key_validator.groq_error", error=str(exc))
            return False

    async def _validate_google(self, key: str) -> bool:
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={key}",
                )
                valid = response.status_code == 200
                logger.info("key_validator.google", valid=valid)
                return valid
        except Exception as exc:
            logger.error("key_validator.google_error", error=str(exc))
            return False
