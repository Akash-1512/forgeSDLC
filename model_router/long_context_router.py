from __future__ import annotations

import structlog

from model_router.adapters.base_adapter import BaseLLMAdapter

logger = structlog.get_logger()

_LONG_CONTEXT_MODEL = "gemini-1.5-pro"  # 1M token context window


class LongContextRouter:
    """Routes requests with >100K estimated tokens to gemini-1.5-pro.

    gemini-1.5-pro provides a 1M token context window needed for large codebases.
    Triggered by ModelRouter when estimated_tokens > LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS.
    """

    def select(self) -> BaseLLMAdapter:
        """Return GeminiAdapter for 1M context window."""
        from model_router.adapters.gemini_adapter import GeminiAdapter  # noqa: PLC0415

        logger.info(
            "long_context_router.selected",
            model=_LONG_CONTEXT_MODEL,
            reason="estimated_tokens > 100_000",
        )
        return GeminiAdapter(model=_LONG_CONTEXT_MODEL)
