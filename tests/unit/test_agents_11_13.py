from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.agent_11_integration import IntegrationAgent
from agents.agent_12_contracts import ContractAgent
from agents.agent_13_platform import PlatformAgent


def _make_base_kwargs() -> dict:
    from model_router.router import ModelRouter

    mock_cwm = MagicMock()
    mock_cwm.build_packet = AsyncMock(return_value=MagicMock())
    mock_cwm._specs = {}
    mock_memory_builder = MagicMock()
    mock_memory_builder.build = AsyncMock(return_value=MagicMock())
    mock_archiver = MagicMock()
    mock_archiver.archive = AsyncMock()
    mock_cfm = MagicMock()
    mock_cfm.write_all = AsyncMock(return_value=["AGENTS.md"])
    mock_workspace = MagicMock()
    mock_workspace.get_context = AsyncMock(return_value=MagicMock(root_path="."))
    mock_diff = MagicMock()
    mock_diff.generate_diff = AsyncMock(
        return_value=MagicMock(filepath="test.py", new_content="")
    )
    mock_diff.apply_diff = AsyncMock()
    mock_model_router = MagicMock(spec=ModelRouter)
    mock_adapter = MagicMock()
    mock_adapter.ainvoke = AsyncMock(return_value=MagicMock(content="# generated"))
    mock_model_router.route = AsyncMock(return_value=mock_adapter)

    return {
        "context_window_manager": mock_cwm,
        "model_router": mock_model_router,
        "memory_archiver": mock_archiver,
        "memory_context_builder": mock_memory_builder,
        "context_file_manager": mock_cfm,
        "workspace_bridge": mock_workspace,
        "diff_engine": mock_diff,
    }


def _monolith_state() -> dict:
    return {
        "user_prompt": "build a simple app",
        "mcp_session_id": "proj-mono",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "service_graph": {"architecture_type": "monolith", "services": []},
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


def _multi_state(has_openapi: bool = True) -> dict:
    return {
        "user_prompt": "build a microservices app",
        "mcp_session_id": "proj-multi",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "service_graph": {
            "architecture_type": "multi_service",
            "has_openapi": has_openapi,
            "services": [
                {"name": "api", "depends_on": ["db"], "exposes": ["GET /users"]},
                {"name": "db", "depends_on": [], "owns_data": True},
            ],
        },
        "rfc": "# RFC-001\nMulti-service system.",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


# ── Agent 11 ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_11_skips_silently_for_monolith() -> None:
    agent = IntegrationAgent(name="agent_11_integration", **_make_base_kwargs())
    state = _monolith_state()
    result = await agent.run(state)
    assert result.get("agent_11_integration_skipped") is True


@pytest.mark.asyncio
async def test_agent_11_no_interpret_log_entry_when_skipped() -> None:
    """Silent skip must add ZERO entries to interpret_log."""
    agent = IntegrationAgent(name="agent_11_integration", **_make_base_kwargs())
    state = _monolith_state()
    before = len(state["interpret_log"])
    await agent.run(state)
    assert len(state["interpret_log"]) == before


@pytest.mark.asyncio
async def test_agent_11_sets_skipped_marker_in_state() -> None:
    agent = IntegrationAgent(name="agent_11_integration", **_make_base_kwargs())
    result = await agent.run(_monolith_state())
    assert "agent_11_integration_skipped" in result
    assert result["agent_11_integration_skipped"] is True


@pytest.mark.asyncio
async def test_agent_11_runs_for_multi_service() -> None:
    agent = IntegrationAgent(name="agent_11_integration", **_make_base_kwargs())
    state = _multi_state()
    result = await agent.run(state)
    assert not result.get("agent_11_integration_skipped")
    assert len(result["interpret_log"]) >= 1


@pytest.mark.asyncio
async def test_agent_11_uses_gemini_via_long_context_router() -> None:
    """ModelRouter selects Gemini when estimated_tokens=150_000 > 100K threshold."""
    from model_router.adapters.gemini_adapter import GeminiAdapter
    from model_router.router import ModelRouter

    kwargs = _make_base_kwargs()
    # Use REAL ModelRouter — not mock — to test routing logic
    real_router = ModelRouter()
    kwargs["model_router"] = real_router

    agent = IntegrationAgent(name="agent_11_integration", **kwargs)

    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        adapter = await real_router.route(
            agent="agent_11_integration",
            task_type="integration_testing",
            estimated_tokens=150_000,   # > 100K → long-context router → gemini
            subscription_tier="pro",
            budget_used=0.0,
            budget_total=50.0,
        )

    assert isinstance(adapter, GeminiAdapter), (
        f"Expected GeminiAdapter for 150K tokens, got {type(adapter).__name__}. "
        "Long-context router should select gemini-3.1-pro-preview."
    )


# ── Agent 12 ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_12_skips_when_monolith() -> None:
    agent = ContractAgent(name="agent_12_contracts", **_make_base_kwargs())
    result = await agent.run(_monolith_state())
    assert result.get("agent_12_contracts_skipped") is True


@pytest.mark.asyncio
async def test_agent_12_skips_when_multi_service_but_no_openapi() -> None:
    agent = ContractAgent(name="agent_12_contracts", **_make_base_kwargs())
    state = _multi_state(has_openapi=False)
    result = await agent.run(state)
    assert result.get("agent_12_contracts_skipped") is True


@pytest.mark.asyncio
async def test_agent_12_runs_when_multi_service_and_openapi_exists() -> None:
    agent = ContractAgent(name="agent_12_contracts", **_make_base_kwargs())
    state = _multi_state(has_openapi=True)
    result = await agent.run(state)
    assert not result.get("agent_12_contracts_skipped")
    assert len(result["interpret_log"]) >= 1


# ── Agent 13 ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_13_skips_silently_for_monolith() -> None:
    agent = PlatformAgent(name="agent_13_platform", **_make_base_kwargs())
    state = _monolith_state()
    before = len(state["interpret_log"])
    result = await agent.run(state)
    assert result.get("agent_13_platform_skipped") is True
    assert len(result["interpret_log"]) == before  # no entries added


def test_agent_13_topological_sort_respects_depends_on_order() -> None:
    """Kahn's algorithm: dependency must appear before dependant."""
    agent = PlatformAgent(name="agent_13_platform", **_make_base_kwargs())
    services = [
        {"name": "api", "depends_on": ["db"]},
        {"name": "db", "depends_on": []},
        {"name": "worker", "depends_on": ["db", "queue"]},
        {"name": "queue", "depends_on": []},
    ]
    order = agent._topological_sort(services)
    assert order.index("db") < order.index("api")
    assert order.index("db") < order.index("worker")
    assert order.index("queue") < order.index("worker")


@pytest.mark.asyncio
async def test_agent_13_generates_docker_compose() -> None:
    agent = PlatformAgent(name="agent_13_platform", **_make_base_kwargs())
    state = _multi_state()
    await agent.run(state)
    # DiffEngine was called for docker-compose.yml
    calls = agent.diff_engine.generate_diff.call_args_list  # type: ignore[union-attr]
    compose_calls = [
        c for c in calls
        if "docker-compose" in str(c.args[0] if c.args else c.kwargs.get("filepath", ""))
    ]
    assert len(compose_calls) >= 1