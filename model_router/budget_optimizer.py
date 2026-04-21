from __future__ import annotations

import structlog

from model_router.adapters.base_adapter import BaseLLMAdapter
from model_router.catalog import AGENT_MODELS, BUDGET_DOWNGRADE_CHAIN

logger = structlog.get_logger()


class BudgetOptimizer:
    """Auto-downgrades expensive models when BudgetMonitor returns OPTIMISE.

    Downgrade chain: gpt-5.4 → gpt-5.4-mini → groq/llama-3.3-70b-versatile
    interpret_node and context_compressor are already on groq — never downgraded.
    Triggered at ≥80% budget used (BUDGET_OPTIMISE_THRESHOLD from constants.py).
    """

    def downgrade(self, agent: str) -> BaseLLMAdapter:
        """Return the next cheaper adapter for this agent."""
        from model_router.selector import ModelSelector  # noqa: PLC0415

        current_model = AGENT_MODELS.get(agent) or ""
        selector = ModelSelector()

        if current_model not in BUDGET_DOWNGRADE_CHAIN:
            # Already on groq or Gemini — can't downgrade further, return as-is
            logger.info(
                "budget_optimizer.no_downgrade_needed",
                agent=agent,
                model=current_model,
            )
            return selector.select(agent)

        idx = BUDGET_DOWNGRADE_CHAIN.index(current_model)
        if idx >= len(BUDGET_DOWNGRADE_CHAIN) - 1:
            # Already at the cheapest option in the chain
            logger.info(
                "budget_optimizer.already_at_floor",
                agent=agent,
                model=current_model,
            )
            return selector._build_adapter(current_model)

        downgraded_model = BUDGET_DOWNGRADE_CHAIN[idx + 1]
        logger.warning(
            "budget_optimizer.downgraded",
            agent=agent,
            from_model=current_model,
            to_model=downgraded_model,
            reason="budget >= BUDGET_OPTIMISE_THRESHOLD (80%)",
        )
        return selector._build_adapter(downgraded_model)
