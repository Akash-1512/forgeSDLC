from __future__ import annotations

from datetime import UTC, datetime

import structlog

from interpret.record import InterpretRecord
from model_router.adapters.base_adapter import BaseLLMAdapter
from model_router.budget_optimizer import BudgetOptimizer
from model_router.catalog import AGENT_MODELS, ALWAYS_BYOK_MODELS
from model_router.fim_router import FIMRouter
from model_router.long_context_router import LongContextRouter
from model_router.selector import ModelSelector
from orchestrator.constants import FIM_TASK_TYPE, LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS
from orchestrator.exceptions import ForgeSDLCError
from subscription.byok_manager import BYOKManager
from subscription.tiers import get_tier, model_allowed_for_tier
from token_tracker.budget_monitor import BudgetMonitor, BudgetStatus

logger = structlog.get_logger()


class ModelRouter:
    """Single entry point for ALL internal LLM calls in forgeSDLC.

    Emits InterpretRecord Layer 4 before every adapter selection.
    Integrates BudgetMonitor, SubscriptionTier, BYOKManager.
    Agent 4 raises — it must delegate via ToolRouter, never ModelRouter.

    Routing priority:
      1. Agent 4 guard (raises immediately)
      2. FIM routing → codestral/devstral
      3. Long-context routing → gemini-3.1-pro-preview
      4. Budget optimisation → downgrade chain
      5. Subscription tier gate → groq fallback
      6. Claude BYOK gate → raises if no key
      7. Normal per-agent selection
    """

    def __init__(self) -> None:
        self._budget_monitor = BudgetMonitor()
        self._fim_router = FIMRouter()
        self._long_context_router = LongContextRouter()
        self._budget_optimizer = BudgetOptimizer()
        self._selector = ModelSelector()
        self._byok_manager = BYOKManager()

    async def route(
        self,
        agent: str,
        task_type: str,
        estimated_tokens: int,
        subscription_tier: str,
        budget_used: float,
        budget_total: float,
    ) -> BaseLLMAdapter:
        """Select and return the correct LLM adapter. Emits L4 InterpretRecord first."""

        # Step 1: Emit InterpretRecord Layer 4 BEFORE any selection
        self._emit_record(agent, task_type, estimated_tokens, subscription_tier)

        # Step 2: Agent 4 guard — no internal LLM, must use ToolRouter
        if AGENT_MODELS.get(agent) is None and agent in AGENT_MODELS:
            raise ForgeSDLCError(
                f"Agent '{agent}' has no internal LLM. "
                "It must delegate via ToolRouter, not ModelRouter."
            )

        # Step 3: FIM routing — strict, never OpenAI/Claude/Groq
        if task_type == FIM_TASK_TYPE:
            logger.info("model_router.fim_routing", agent=agent)
            return self._fim_router.select()

        # Step 4: Long-context routing
        if estimated_tokens > LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS:
            logger.info(
                "model_router.long_context_routing",
                estimated_tokens=estimated_tokens,
                threshold=LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS,
            )
            return self._long_context_router.select()

        # Step 5: Budget optimisation
        budget_status = await self._budget_monitor.check(budget_used, budget_total)
        if budget_status == BudgetStatus.OPTIMISE:
            logger.warning("model_router.budget_optimise", agent=agent)
            return self._budget_optimizer.downgrade(agent)

        # Step 6: Subscription tier gate
        default_model = AGENT_MODELS.get(agent) or ""
        tier = get_tier(subscription_tier)
        if default_model and not model_allowed_for_tier(default_model, tier):
            logger.info(
                "model_router.tier_override",
                agent=agent,
                model=default_model,
                tier=subscription_tier,
                fallback="groq/llama-3.3-70b-versatile",
            )
            from model_router.adapters.groq_adapter import GroqAdapter  # noqa: PLC0415

            return GroqAdapter(model="groq/llama-3.3-70b-versatile")

        # Step 7: Claude BYOK gate
        if default_model in ALWAYS_BYOK_MODELS:
            if not self._byok_manager.has_key("anthropic"):
                from model_router.adapters.claude_adapter import (
                    ClaudeNotConfiguredError,  # noqa: PLC0415
                )

                raise ClaudeNotConfiguredError(
                    "Claude requires BYOK. Configure your Anthropic API key in Settings → API Keys."
                )
            from model_router.adapters.claude_adapter import (
                ClaudeAdapter,  # noqa: PLC0415
            )

            return ClaudeAdapter(byok_manager=self._byok_manager, model=default_model)

        # Step 8: Normal per-agent selection
        logger.info("model_router.normal_selection", agent=agent, model=default_model)
        return self._selector.select(agent)

    def _emit_record(
        self,
        agent: str,
        task_type: str,
        estimated_tokens: int,
        subscription_tier: str,
    ) -> InterpretRecord:
        record = InterpretRecord(
            layer="model_router",
            component="ModelRouter",
            action=f"selecting model for agent={agent} task={task_type}",
            inputs={
                "agent": agent,
                "task_type": task_type,
                "estimated_tokens": estimated_tokens,
                "subscription_tier": subscription_tier,
            },
            expected_outputs={"adapter": "BaseLLMAdapter"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[],
            model_selected=AGENT_MODELS.get(agent),
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.model_router",
            layer=record.layer,
            agent=agent,
            task_type=task_type,
        )
        return record
