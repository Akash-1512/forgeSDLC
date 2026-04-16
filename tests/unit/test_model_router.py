from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from model_router.catalog import AGENT_MODELS
from model_router.adapters.base_adapter import BaseLLMAdapter


def _make_router() -> object:
    from model_router.router import ModelRouter
    return ModelRouter()


def _mock_byok(has_key: bool = False) -> object:
    m = MagicMock()
    m.has_key.return_value = has_key
    m.get_key.return_value = "sk-ant-test" if has_key else None
    return m


@pytest.mark.asyncio
async def test_route_agent_0_returns_groq_adapter() -> None:
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        adapter = await router.route(  # type: ignore[union-attr]
            agent="agent_0_decompose",
            task_type="decompose",
            estimated_tokens=100,
            subscription_tier="pro",
            budget_used=0.0,
            budget_total=5.0,
        )
    from model_router.adapters.groq_adapter import GroqAdapter
    assert isinstance(adapter, GroqAdapter)


@pytest.mark.asyncio
async def test_route_agent_3_returns_gpt_5_4_adapter() -> None:
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        adapter = await router.route(  # type: ignore[union-attr]
            agent="agent_3_architecture",
            task_type="architecture",
            estimated_tokens=100,
            subscription_tier="pro",
            budget_used=0.0,
            budget_total=5.0,
        )
    from model_router.adapters.openai_adapter import OpenAIAdapter
    assert isinstance(adapter, OpenAIAdapter)
    assert adapter.model_name == "gpt-5.4"


@pytest.mark.asyncio
async def test_route_agent_9_returns_groq_not_gpt_mini() -> None:
    """Regression guard: Agent 9 must return groq, never gpt-5.4-mini."""
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        adapter = await router.route(  # type: ignore[union-attr]
            agent="agent_9_monitor",
            task_type="monitor",
            estimated_tokens=100,
            subscription_tier="pro",
            budget_used=0.0,
            budget_total=5.0,
        )
    from model_router.adapters.groq_adapter import GroqAdapter
    assert isinstance(adapter, GroqAdapter), (
        f"Agent 9 must use GroqAdapter, got {type(adapter).__name__}"
    )
    assert "groq" in adapter.model_name


@pytest.mark.asyncio
async def test_route_agent_4_raises_error() -> None:
    """Agent 4 (ToolRouter) must never be routed through ModelRouter."""
    from orchestrator.exceptions import ForgeSDLCError
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        with pytest.raises(ForgeSDLCError):
            await router.route(  # type: ignore[union-attr]
                agent="agent_4_tool_router",
                task_type="code_gen",
                estimated_tokens=100,
                subscription_tier="pro",
                budget_used=0.0,
                budget_total=5.0,
            )


@pytest.mark.asyncio
async def test_route_interpret_node_returns_groq_8b_instant() -> None:
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        adapter = await router.route(  # type: ignore[union-attr]
            agent="interpret_node",
            task_type="interpret",
            estimated_tokens=100,
            subscription_tier="free",
            budget_used=0.0,
            budget_total=0.0,
        )
    from model_router.adapters.groq_adapter import GroqAdapter
    assert isinstance(adapter, GroqAdapter)
    assert "8b-instant" in adapter.model_name


@pytest.mark.asyncio
async def test_long_context_routing_over_100k_uses_gemini() -> None:
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        adapter = await router.route(  # type: ignore[union-attr]
            agent="agent_3_architecture",
            task_type="architecture",
            estimated_tokens=150_000,
            subscription_tier="enterprise",
            budget_used=0.0,
            budget_total=50.0,
        )
    from model_router.adapters.gemini_adapter import GeminiAdapter
    assert isinstance(adapter, GeminiAdapter)


@pytest.mark.asyncio
async def test_budget_optimise_downgrades_gpt_5_4_to_mini() -> None:
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        # 85% budget used → OPTIMISE → downgrade gpt-5.4 → gpt-5.4-mini
        adapter = await router.route(  # type: ignore[union-attr]
            agent="agent_3_architecture",
            task_type="architecture",
            estimated_tokens=100,
            subscription_tier="pro",
            budget_used=4.25,
            budget_total=5.0,
        )
    from model_router.adapters.openai_adapter import OpenAIAdapter
    from model_router.adapters.groq_adapter import GroqAdapter
    # Should be downgraded — either gpt-5.4-mini or groq
    assert isinstance(adapter, (OpenAIAdapter, GroqAdapter))
    if isinstance(adapter, OpenAIAdapter):
        assert adapter.model_name != "gpt-5.4"


@pytest.mark.asyncio
async def test_free_tier_forces_groq_for_openai_agents() -> None:
    router = _make_router()
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        # Free tier: gpt-5.4-mini not allowed → falls back to groq
        adapter = await router.route(  # type: ignore[union-attr]
            agent="agent_2_stack",
            task_type="stack",
            estimated_tokens=100,
            subscription_tier="free",
            budget_used=0.0,
            budget_total=0.0,
        )
    from model_router.adapters.groq_adapter import GroqAdapter
    assert isinstance(adapter, GroqAdapter)


@pytest.mark.asyncio
async def test_route_emits_interpret_record_layer4_before_selection() -> None:
    from interpret.record import InterpretRecord
    router = _make_router()
    emitted: list[str] = []
    original_emit = router._emit_record  # type: ignore[union-attr]

    def capturing_emit(*args: object, **kwargs: object) -> object:
        ir = original_emit(*args, **kwargs)
        emitted.append(ir.layer)
        return ir

    router._emit_record = capturing_emit  # type: ignore[union-attr, method-assign]
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        await router.route(  # type: ignore[union-attr]
            agent="agent_0_decompose",
            task_type="decompose",
            estimated_tokens=100,
            subscription_tier="pro",
            budget_used=0.0,
            budget_total=5.0,
        )
    assert "model_router" in emitted


@pytest.mark.asyncio
async def test_claude_raises_when_no_byok_key() -> None:
    from model_router.adapters.claude_adapter import ClaudeNotConfiguredError
    from model_router.catalog import ALWAYS_BYOK_MODELS
    router = _make_router()
    with (
        patch("subscription.byok_manager.keyring") as mk,
        patch.dict(
            "model_router.router.AGENT_MODELS",
            {"agent_10_docs": "claude-sonnet-4-6"},
        ),
    ):
        mk.get_password.return_value = None
        with pytest.raises(ClaudeNotConfiguredError):
            await router.route(  # type: ignore[union-attr]
                agent="agent_10_docs",
                task_type="docs",
                estimated_tokens=100,
                subscription_tier="enterprise",
                budget_used=0.0,
                budget_total=50.0,
            )


def test_agent_models_catalog_has_correct_agent_9() -> None:
    assert AGENT_MODELS["agent_9_monitor"] == "groq/llama-3.3-70b-specdec"


def test_agent_models_catalog_agent_4_is_none() -> None:
    assert AGENT_MODELS["agent_4_tool_router"] is None