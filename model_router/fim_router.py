from __future__ import annotations

import os

import structlog

from model_router.adapters.base_adapter import BaseLLMAdapter

logger = structlog.get_logger()


class FIMRouter:
    """FIM routing — companion panel InlineMode only.

    Priority: codestral (MISTRAL_CODESTRAL_KEY) → ollama/devstral (local fallback).
    NEVER routes FIM to: OpenAI, Claude, Groq — not FIM-specialist models.
    codestral.mistral.ai uses MISTRAL_CODESTRAL_KEY (NOT MISTRAL_API_KEY).
    """

    def select(self) -> BaseLLMAdapter:
        """Return CodestralAdapter if key set, else OllamaAdapter(devstral)."""
        if os.getenv("MISTRAL_CODESTRAL_KEY"):
            from model_router.adapters.codestral_adapter import (
                CodestralAdapter,  # noqa: PLC0415
            )

            logger.info("fim_router.selected", adapter="codestral")
            return CodestralAdapter()

        logger.info(
            "fim_router.fallback",
            adapter="ollama/devstral",
            reason="MISTRAL_CODESTRAL_KEY not set",
        )
        from model_router.adapters.ollama_adapter import OllamaAdapter  # noqa: PLC0415

        return OllamaAdapter(model="devstral")
