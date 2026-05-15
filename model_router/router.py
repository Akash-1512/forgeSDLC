from __future__ import annotations

import time
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
from token_tracker.tracker import TokenTracker

logger = structlog.get_logger()


class _TrackingAdapter:
    """Wraps any BaseLLMAdapter to record token usage via TokenTracker.

    Intercepts ainvoke() responses and extracts usage metadata from
    the response object, and calls TokenTracker.record() to update state.
    budget_used_usd is incremented so BudgetMonitor thresholds actually fire.
    """

    def __init__(
        self,
        inner: BaseLLMAdapter,
        agent: str,
        task_type: str,
        state: dict[str, object] | None,
        tracker: TokenTracker,
    ) -> None:
        self._inner = inner
        self._agent = agent
        self._task_type = task_type
        self._state = state
        self._tracker = tracker

    async def ainvoke(self, messages: object, **kwargs: object) -> object:
        t0 = time.monotonic()
        response = await self._inner.ainvoke(messages, **kwargs)  # type: ignore[arg-type]
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Extract token counts if available (LangChain AIMessage carries usage_metadata)
        usage = getattr(response, "usage_metadata", None) or {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        cost = self._estimate_cost(input_tokens, output_tokens)

        if self._state is not None:
            self._tracker.record(
                state=self._state,
                agent=self._agent,
                task=self._task_type,
                model=self._inner.model_name,
                provider=self._inner.model_name.split("/")[0],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                latency_ms=latency_ms,
                api_key_source=(
                    "byok"
                    if self._byok_manager.has_key(self._inner.model_name.split("/")[0])
                    else "free_tier"
                    if "groq" in self._inner.model_name
                    else "subscription"
                ),
            )
            # Update running budget total in state
            current = float(self._state.get("budget_used_usd", 0.0) or 0.0)
            self._state["budget_used_usd"] = current + cost

        return response

    async def astream(self, messages: object, **kwargs: object) -> object:
        return await self._inner.astream(messages, **kwargs)  # type: ignore[arg-type]

    async def afim(self, prefix: str, suffix: str, **kwargs: object) -> str:
        return await self._inner.afim(prefix, suffix, **kwargs)  # type: ignore[arg-type]

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def inner(self) -> object:
        """Return the underlying adapter — for testing and inspection only."""
        return self._inner

    @property
    def context_window(self) -> int:
        return self._inner.context_window

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return self._inner.cost_per_1k_input_tokens

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return self._inner.cost_per_1k_output_tokens

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1000 * self._inner.cost_per_1k_input_tokens
            + output_tokens / 1000 * self._inner.cost_per_1k_output_tokens
        )


class ModelRouter:
    """Single entry point for ALL internal LLM calls in forgeSDLC.

    Emits InterpretRecord Layer 4 before every adapter selection.
    Integrates BudgetMonitor, SubscriptionTier, BYOKManager, TokenTracker.
    Agent 4 raises — it must delegate via ToolRouter, never ModelRouter.

    Routing priority:
      1. Agent 4 guard (raises immediately)
      2. FIM routing → codestral/devstral
      3. Long-context routing → gemini-1.5-pro
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
        self._tracker = TokenTracker()

    async def route(
        self,
        agent: str,
        task_type: str,
        estimated_tokens: int,
        subscription_tier: str,
        budget_used: float,
        budget_total: float,
        state: dict[str, object] | None = None,
    ) -> BaseLLMAdapter:
        """Select and return the correct LLM adapter. Emits L4 InterpretRecord first.

        Wraps the returned adapter in _TrackingAdapter so every
        ainvoke() call records token usage and updates state["budget_used_usd"].
        state parameter is optional for callers that don't have access to it.
        """

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
            adapter = self._fim_router.select()
            return _TrackingAdapter(adapter, agent, task_type, state, self._tracker)

        # Step 4: Long-context routing
        if estimated_tokens > LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS:
            logger.info(
                "model_router.long_context_routing",
                estimated_tokens=estimated_tokens,
                threshold=LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS,
            )
            adapter = self._long_context_router.select()
            return _TrackingAdapter(adapter, agent, task_type, state, self._tracker)

        # Step 5: Budget optimisation
        budget_status = await self._budget_monitor.check(budget_used, budget_total)
        if budget_status == BudgetStatus.OPTIMISE:
            logger.warning("model_router.budget_optimise", agent=agent)
            adapter = self._budget_optimizer.downgrade(agent)
            return _TrackingAdapter(adapter, agent, task_type, state, self._tracker)

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

            adapter = GroqAdapter(model="groq/llama-3.3-70b-versatile")
            return _TrackingAdapter(adapter, agent, task_type, state, self._tracker)

        # Step 7: BYOK gate — models requiring API keys beyond Groq free tier
        if default_model in ALWAYS_BYOK_MODELS:
            # Claude models require Anthropic BYOK
            if "claude" in default_model.lower():
                if not self._byok_manager.has_key("anthropic"):
                    from model_router.adapters.claude_adapter import (
                        ClaudeNotConfiguredError,  # noqa: PLC0415
                    )

                    raise ClaudeNotConfiguredError(
                        "Claude requires BYOK. Configure your Anthropic API key in Settings → API Keys."  # noqa: E501
                    )
                from model_router.adapters.claude_adapter import (
                    ClaudeAdapter,  # noqa: PLC0415
                )

                adapter = ClaudeAdapter(byok_manager=self._byok_manager, model=default_model)
                return _TrackingAdapter(adapter, agent, task_type, state, self._tracker)

            # OpenAI models require OPENAI_API_KEY — fall back to Groq if missing
            openai_models = {"o3-mini", "gpt-4o", "gpt-4o-mini"}
            if default_model in openai_models:
                import os  # noqa: PLC0415

                if not os.getenv("OPENAI_API_KEY"):
                    logger.warning(
                        "model_router.openai_key_missing",
                        model=default_model,
                        agent=agent,
                        fallback="groq/llama-3.3-70b-versatile",
                    )
                    from model_router.adapters.groq_adapter import (
                        GroqAdapter,  # noqa: PLC0415
                    )

                    return _TrackingAdapter(
                        GroqAdapter(model="groq/llama-3.3-70b-versatile"),
                        agent,
                        task_type,
                        state,
                        self._tracker,
                    )

            # Google models require GOOGLE_API_KEY
            if default_model.startswith("gemini"):
                import os  # noqa: PLC0415

                if not os.getenv("GOOGLE_API_KEY"):
                    logger.warning(
                        "model_router.google_key_missing",
                        model=default_model,
                        agent=agent,
                        fallback="groq/llama-3.3-70b-versatile",
                    )
                    from model_router.adapters.groq_adapter import (
                        GroqAdapter,  # noqa: PLC0415
                    )

                    return _TrackingAdapter(
                        GroqAdapter(model="groq/llama-3.3-70b-versatile"),
                        agent,
                        task_type,
                        state,
                        self._tracker,
                    )

        # Step 8: Normal per-agent selection
        logger.info("model_router.normal_selection", agent=agent, model=default_model)
        adapter = self._selector.select(agent)
        return _TrackingAdapter(adapter, agent, task_type, state, self._tracker)

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
