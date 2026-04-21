from __future__ import annotations

import os

import structlog

from model_router.adapters.base_adapter import BaseLLMAdapter
from model_router.catalog import (
    AGENT_MODELS,
    BUDGET_DOWNGRADE_CHAIN,
    RESPONSES_API_MODELS,
)

logger = structlog.get_logger()


class ModelSelector:
    """Selects the correct adapter for a given agent from AGENT_MODELS catalog.

    Called by ModelRouter after all gates (budget, tier, BYOK) have passed.
    """

    def select(self, agent: str) -> BaseLLMAdapter:
        """Return the adapter for the agent's default model."""
        model = AGENT_MODELS.get(agent)
        if model is None:
            from orchestrator.exceptions import ForgeSDLCError  # noqa: PLC0415
            raise ForgeSDLCError(
                f"Agent '{agent}' has no internal LLM. "
                "It must delegate via ToolRouter."
            )
        return self._build_adapter(model)

    def select_downgraded(self, current_model: str) -> BaseLLMAdapter:
        """Return the next cheaper adapter in the downgrade chain."""
        try:
            idx = BUDGET_DOWNGRADE_CHAIN.index(current_model)
            next_model = BUDGET_DOWNGRADE_CHAIN[min(idx + 1, len(BUDGET_DOWNGRADE_CHAIN) - 1)]
        except ValueError:
            next_model = BUDGET_DOWNGRADE_CHAIN[-1]
        logger.info(
            "model_selector.downgraded",
            from_model=current_model,
            to_model=next_model,
        )
        return self._build_adapter(next_model)

    def _build_adapter(self, model: str) -> BaseLLMAdapter:
        """Instantiate the correct adapter class for a model string."""
        if model in RESPONSES_API_MODELS:
            from model_router.adapters.openai_reasoning_adapter import OpenAIReasoningAdapter  # noqa: PLC0415
            return OpenAIReasoningAdapter(model=model)

        if model.startswith("groq/"):
            from model_router.adapters.groq_adapter import GroqAdapter  # noqa: PLC0415
            return GroqAdapter(model=model)

        if model.startswith("gemini-"):
            from model_router.adapters.gemini_adapter import GeminiAdapter  # noqa: PLC0415
            return GeminiAdapter(model=model)

        if model.startswith("codestral"):
            from model_router.adapters.codestral_adapter import CodestralAdapter  # noqa: PLC0415
            return CodestralAdapter(model=model)

        if model.startswith("devstral") or model.startswith("ollama/"):
            from model_router.adapters.ollama_adapter import OllamaAdapter  # noqa: PLC0415
            return OllamaAdapter(model=model)

        if "azure" in model:
            from model_router.adapters.azure_adapter import AzureOpenAIAdapter  # noqa: PLC0415
            return AzureOpenAIAdapter(deployment=model)

        # Default: OpenAI Chat Completions (gpt-5.4, gpt-5.4-mini)
        from model_router.adapters.openai_adapter import OpenAIAdapter  # noqa: PLC0415
        return OpenAIAdapter(model=model)