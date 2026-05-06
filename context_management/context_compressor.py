from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Module-level shared router — created once per process.
# Previously every compress() call created a new ModelRouter() which instantiates
# BudgetMonitor, ModelSelector, BudgetOptimizer — lightweight but wasteful.
_SHARED_ROUTER: object | None = None


def _get_router() -> object:
    global _SHARED_ROUTER
    if _SHARED_ROUTER is None:
        from model_router.router import ModelRouter  # noqa: PLC0415

        _SHARED_ROUTER = ModelRouter()
    return _SHARED_ROUTER


class ContextCompressor:
    """Summarises large optional fields using groq/llama-3.1-8b-instant via ModelRouter.

    Routes through ModelRouter — never imports groq or openai directly.
    This ensures:
    - Budget tracking via TokenTracker
    - Tier filtering via SubscriptionTier
    - Non-Negotiable #1 compliance (all internal LLM calls through ModelRouter)
    - context_compressor maps to groq/llama-3.1-8b-instant (always free)
    """

    async def compress(self, content: str, field_name: str) -> str:
        """Summarise content to under 200 words. Routes via shared ModelRouter."""
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        # Reuse shared router
        router = _get_router()
        adapter = await router.route(  # type: ignore[union-attr]
            agent="context_compressor",  # → groq/llama-3.1-8b-instant always free
            task_type="compression",
            estimated_tokens=int(len(content.split()) * 1.33) + 50,
            subscription_tier="free",
            budget_used=0.0,
            budget_total=0.0,  # free tier — no budget cap for compression
        )

        response = await adapter.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Summarise the following content concisely for use as context "
                        f"in an AI agent. Field: {field_name}. "
                        "Keep all technical decisions, file paths, and key facts. "
                        "Target: under 200 words."
                    )
                ),
                HumanMessage(content=content[:4000]),  # cap input to avoid token overflow
            ]
        )

        summary = str(response.content) if response.content else ""
        logger.info(
            "context_compressor.compressed",
            field=field_name,
            original_chars=len(content),
            summary_chars=len(summary),
        )
        return summary
