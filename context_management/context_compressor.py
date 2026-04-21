from __future__ import annotations

import structlog

logger = structlog.get_logger()


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
        """Summarise content to under 200 words. Routes via ModelRouter."""
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
        from model_router.router import ModelRouter  # noqa: PLC0415

        router = ModelRouter()
        adapter = await router.route(
            agent="context_compressor",     # → groq/llama-3.1-8b-instant always free
            task_type="compression",
            estimated_tokens=int(len(content.split()) * 1.33) + 50,
            subscription_tier="free",
            budget_used=0.0,
            budget_total=999.0,             # no budget constraint for compression
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