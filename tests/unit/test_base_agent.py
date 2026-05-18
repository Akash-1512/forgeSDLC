from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from interpret.record import InterpretRecord


def _make_interpret_record(action: str = "test action") -> InterpretRecord:
    return InterpretRecord(
        layer="agent",
        component="TestAgent",
        action=action,
        inputs={},
        expected_outputs={},
        files_it_will_read=[],
        files_it_will_write=[],
        external_calls=[],
        model_selected=None,
        tool_delegated_to=None,
        reversible=True,
        workspace_files_affected=[],
        timestamp=datetime.now(tz=UTC),
    )


def _make_agent(interpretation_action: str = "test interpret action") -> object:
    """Create a concrete BaseAgent subclass for testing."""
    from agents.base_agent import BaseAgent
    from context_management.context_packet import ContextPacket

    mock_packet = MagicMock(spec=ContextPacket)
    mock_memory = MagicMock()

    class ConcreteAgent(BaseAgent):
        async def _interpret(self, packet, memory_context, state):
            return _make_interpret_record(interpretation_action)

        async def _execute(self, state, packet, memory_context):
            state["_executed"] = True
            return state

    mock_cwm = MagicMock()
    mock_cwm.build_packet = AsyncMock(return_value=mock_packet)
    mock_cwm._specs = {}

    mock_memory_builder = MagicMock()
    mock_memory_builder.build = AsyncMock(return_value=mock_memory)

    mock_archiver = MagicMock()
    mock_archiver.archive = AsyncMock()

    mock_cfm = MagicMock()
    mock_cfm.write_all = AsyncMock(return_value=["AGENTS.md"])

    mock_workspace = MagicMock()
    mock_workspace.get_context = AsyncMock(return_value=MagicMock(root_path="."))

    mock_diff = MagicMock()

    from model_router.router import ModelRouter

    mock_model_router = MagicMock(spec=ModelRouter)

    return ConcreteAgent(
        name="agent_0_decompose",
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )


@pytest.mark.asyncio
async def test_run_emits_interpret_record_l1_before_execute() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    assert len(result["interpret_log"]) >= 1
    assert result["interpret_log"][0]["layer"] == "agent"


@pytest.mark.asyncio
async def test_run_does_not_execute_without_100_percent_go() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    assert result.get("_executed") is None
    agent.memory_archiver.archive.assert_not_called()


@pytest.mark.asyncio
async def test_run_executes_when_confirmation_is_exactly_100_percent_go() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    assert result.get("_executed") is True


@pytest.mark.asyncio
async def test_run_rejects_approved_as_confirmation() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "APPROVED",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    assert result.get("_executed") is None


@pytest.mark.asyncio
async def test_run_resets_human_confirmation_after_execute() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    assert result["human_confirmation"] == ""


@pytest.mark.asyncio
async def test_run_calls_memory_archiver_after_execute() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    await agent.run(state)
    agent.memory_archiver.archive.assert_called_once()


@pytest.mark.asyncio
async def test_run_calls_context_file_manager_after_execute() -> None:
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    await agent.run(state)
    agent.cfm.write_all.assert_called_once()


@pytest.mark.asyncio
async def test_run_updates_displayed_interpretation_each_round() -> None:
    agent = _make_agent(interpretation_action="round 1 interpretation")
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    # displayed_interpretation holds only the CURRENT one
    # interpret_node() formats the record — check the action is present
    assert "round 1 interpretation" in result["displayed_interpretation"]
    assert result["interpret_round"] == 1


@pytest.mark.asyncio
async def test_run_accumulates_budget_used_usd_after_execute() -> None:
    """H7 regression test: budget_used_usd is updated after _execute completes."""
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "budget_used_usd": 0.0,
        "session_token_records": [],
    }
    result = await agent.run(state)
    # budget_used_usd must be a float >= 0.0 after run completes
    assert isinstance(result.get("budget_used_usd"), float)
    assert result.get("budget_used_usd", -1.0) >= 0.0
    # session_token_records must have at least 1 record
    assert len(result.get("session_token_records", [])) >= 1


@pytest.mark.asyncio
async def test_run_resets_human_confirmation_after_gate_passes() -> None:
    """After _execute, human_confirmation must be cleared for next agent."""
    agent = _make_agent()
    state: dict = {
        "user_prompt": "test",
        "mcp_session_id": "proj-1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
    }
    result = await agent.run(state)
    assert result["human_confirmation"] == ""
