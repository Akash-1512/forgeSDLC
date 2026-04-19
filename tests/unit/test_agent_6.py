from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tool_router.context import AvailableTool, ToolResult


def _make_tool_result(output: str = "def test_foo(): pass") -> ToolResult:
    return ToolResult(
        tool=AvailableTool.DIRECT_LLM,
        output=output,
        files_written=["tests/test_main.py"],
        success=True,
        stderr=None,
    )


def _make_agent_6(coverage: float = 85.0) -> object:
    from agents.agent_6_test_coordinator import TestCoordinatorAgent
    from model_router.router import ModelRouter
    from tool_router.router import ToolRouter

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
    mock_model_router = MagicMock(spec=ModelRouter)

    mock_tool_router = MagicMock(spec=ToolRouter)
    mock_tool_router.detect_available_tools = AsyncMock(
        return_value=[AvailableTool.DIRECT_LLM]
    )
    mock_tool_router.route = AsyncMock(return_value=_make_tool_result())

    agent = TestCoordinatorAgent(
        name="agent_6_test_coord",
        tool_router=mock_tool_router,
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )
    # Patch coverage measurement
    agent._measure_coverage = AsyncMock(return_value=coverage)  # type: ignore[method-assign]
    agent._get_uncovered_lines = AsyncMock(return_value=["src/api.py: lines [45, 67]"])  # type: ignore[method-assign]
    return agent


def _base_state(human_confirmation: str = "100% GO") -> dict:
    return {
        "user_prompt": "generate tests",
        "mcp_session_id": "proj-6",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "prd": "# PRD",
        "adr": "# ADR",
        "rfc": "# RFC",
        "test_retry_count": 0,
        "test_coverage": 0.0,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


@pytest.mark.asyncio
async def test_agent_6_delegates_test_gen_via_tool_router() -> None:
    agent = _make_agent_6(coverage=85.0)
    await agent.run(_base_state())  # type: ignore[union-attr]
    agent._tool_router.route.assert_called_once()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_agent_6_uses_sys_executable_not_hardcoded_python() -> None:
    """pytest subprocess must use sys.executable, not 'python' or 'python3'."""
    agent = _make_agent_6(coverage=85.0)
    # Un-patch _measure_coverage to check the actual subprocess call
    agent._measure_coverage = TestCoordinatorAgent._measure_coverage.__get__(agent)  # type: ignore[method-assign]

    captured_args: list[tuple] = []

    async def mock_exec(*args: object, **kwargs: object) -> object:
        captured_args.append(args)
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(b"", b""))
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        await agent._measure_coverage(".", sys.executable)  # type: ignore[union-attr]

    assert captured_args
    first_arg = captured_args[0][0]
    assert first_arg == sys.executable, (
        f"Expected sys.executable ({sys.executable!r}), got {first_arg!r}. "
        "Never hardcode 'python' — use sys.executable."
    )


@pytest.mark.asyncio
async def test_agent_6_retries_when_coverage_below_80() -> None:
    agent = _make_agent_6(coverage=60.0)  # below threshold
    state = _base_state()
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("test_retry_needed") is True
    assert int(result.get("test_retry_count", 0)) == 1


@pytest.mark.asyncio
async def test_agent_6_retry_task_contains_uncovered_lines() -> None:
    agent = _make_agent_6(coverage=60.0)
    state = _base_state()
    state["test_retry_count"] = 1  # simulate retry round
    state["test_uncovered_lines"] = ["src/api.py: lines [45, 67]"]
    task = agent._build_test_task(state, retry_count=1)  # type: ignore[union-attr]
    assert "Fix required" in task
    assert "uncovered lines" in task.lower()


@pytest.mark.asyncio
async def test_agent_6_max_3_retries_then_hitl_escalation() -> None:
    agent = _make_agent_6(coverage=60.0)
    state = _base_state()
    state["test_retry_count"] = 3  # already at max
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("hitl_required") is True
    assert "80%" in str(result.get("hitl_reason", ""))


@pytest.mark.asyncio
async def test_agent_6_proceeds_when_coverage_meets_80() -> None:
    agent = _make_agent_6(coverage=80.0)  # exactly at threshold
    result = await agent.run(_base_state())  # type: ignore[union-attr]
    assert result.get("test_retry_needed") is False
    assert not result.get("hitl_required")


def test_agent_6_tool_router_context_in_context_spec() -> None:
    """Verify Session 08 spec: tool_router_context required for Agent 6."""
    from context_management.agent_context_specs import AGENT_CONTEXT_SPECS
    spec = AGENT_CONTEXT_SPECS["agent_6_test_coord"]
    assert "tool_router_context" in spec.required_fields