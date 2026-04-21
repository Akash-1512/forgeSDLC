"""
Verifies Agents 11-13 leave NO interpret_log entries on monolith architecture.
The silent skip at the top of run() must return before super().run() is called.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.agent_11_integration import IntegrationAgent
from agents.agent_12_contracts import ContractAgent
from agents.agent_13_platform import PlatformAgent


def _make_monolith_state() -> dict[str, object]:
    return {
        "user_prompt": "build a simple app",
        "mcp_session_id": "test-skip-18",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "service_graph": {
            "architecture_type": "monolith",
            "services": [],
            "has_openapi": False,
        },
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
        "prd": "", "adr": "", "rfc": "",
    }


def _build_agent(AgentClass: type) -> object:
    """Build agent with all dependencies mocked."""
    from model_router.router import ModelRouter

    mock_cwm = MagicMock()
    mock_cwm.build_packet = AsyncMock(return_value=MagicMock())
    mock_cwm._specs = {}
    mock_archiver = MagicMock()
    mock_archiver.archive = AsyncMock()
    mock_cfm = MagicMock()
    mock_cfm.write_all = AsyncMock()
    mock_workspace = MagicMock()
    mock_workspace.get_context = AsyncMock(return_value=MagicMock(root_path="."))
    mock_diff = MagicMock()
    mock_diff.generate_diff = AsyncMock(
        return_value=MagicMock(filepath="out.py", new_content="")
    )
    mock_diff.apply_diff = AsyncMock()
    mock_memory_builder = MagicMock()
    mock_memory_builder.build = AsyncMock(return_value=MagicMock())
    mock_model_router = MagicMock(spec=ModelRouter)
    mock_adapter = MagicMock()
    mock_adapter.ainvoke = AsyncMock(return_value=MagicMock(content="generated"))
    mock_model_router.route = AsyncMock(return_value=mock_adapter)

    kwargs = dict(
        name=AgentClass.__name__,
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )

    # Agent 11 requires tool_router
    if AgentClass is IntegrationAgent:
        from tool_router.router import ToolRouter
        mock_tool_router = MagicMock(spec=ToolRouter)
        mock_tool_router.detect_available_tools = AsyncMock(return_value=[])
        mock_tool_router.route = AsyncMock(return_value=MagicMock())
        kwargs["tool_router"] = mock_tool_router

    return AgentClass(**kwargs)


@pytest.mark.parametrize("AgentClass,skip_key", [
    (IntegrationAgent, "agent_11_integration_skipped"),
    (ContractAgent, "agent_12_contracts_skipped"),
    (PlatformAgent, "agent_13_platform_skipped"),
])
@pytest.mark.asyncio
async def test_agent_skips_silently_on_monolith(
    AgentClass: type, skip_key: str
) -> None:
    """Agent skips, adds NO interpret_log entry, sets skipped marker."""
    agent = _build_agent(AgentClass)
    state = _make_monolith_state()
    initial_log_length = len(state["interpret_log"])

    result = await agent.run(state)  # type: ignore[union-attr]

    assert len(result["interpret_log"]) == initial_log_length, (
        f"{AgentClass.__name__} added {len(result['interpret_log']) - initial_log_length} "
        f"interpret_log entry/entries on monolith. "
        f"Silent skip must not call super().run()."
    )
    assert result.get(skip_key) is True, (
        f"Expected {skip_key}=True in state after skip. "
        f"Got: {result.get(skip_key)}"
    )


@pytest.mark.parametrize("AgentClass,skip_key", [
    (IntegrationAgent, "agent_11_integration_skipped"),
    (ContractAgent, "agent_12_contracts_skipped"),
    (PlatformAgent, "agent_13_platform_skipped"),
])
@pytest.mark.asyncio
async def test_agent_does_not_modify_state_on_skip(
    AgentClass: type, skip_key: str
) -> None:
    """Skipped agents must not mutate state beyond setting the skip marker."""
    agent = _build_agent(AgentClass)
    state = _make_monolith_state()
    state["prd"] = "original PRD"
    state["rfc"] = "original RFC"

    result = await agent.run(state)  # type: ignore[union-attr]

    assert result["prd"] == "original PRD"
    assert result["rfc"] == "original RFC"
    assert result[skip_key] is True


@pytest.mark.asyncio
async def test_agent_12_also_skips_when_multi_service_but_no_openapi() -> None:
    """Agent 12 skips when multi_service but has_openapi is False."""
    agent = _build_agent(ContractAgent)
    state = _make_monolith_state()
    state["service_graph"] = {
        "architecture_type": "multi_service",
        "services": [{"name": "api"}, {"name": "db"}],
        "has_openapi": False,
    }
    state["interpret_log"] = []
    initial_length = len(state["interpret_log"])

    result = await agent.run(state)  # type: ignore[union-attr]

    assert result.get("agent_12_contracts_skipped") is True
    assert len(result["interpret_log"]) == initial_length, (
        "Agent 12 must skip silently when has_openapi=False, even on multi_service."
    )