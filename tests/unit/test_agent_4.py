from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from tool_router.context import AvailableTool, ToolResult


def _make_tool_result(output: str = "def foo(): pass", files: list[str] | None = None) -> ToolResult:
    return ToolResult(
        tool=AvailableTool.DIRECT_LLM,
        output=output,
        files_written=files or [],
        success=True,
        stderr=None,
    )


def _make_agent_4(tool_result: ToolResult | None = None) -> object:
    from agents.agent_4_tool_router import ToolRouterAgent
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
    mock_tool_router.route = AsyncMock(
        return_value=tool_result or _make_tool_result()
    )

    return ToolRouterAgent(
        name="agent_4_tool_router",
        tool_router=mock_tool_router,
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )


def _base_state(human_confirmation: str = "100% GO") -> dict:
    return {
        "user_prompt": "build an API",
        "mcp_session_id": "proj-1",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "prd": "# PRD",
        "adr": "# ADR",
        "rfc": "# RFC",
        "tool_retry_count": 0,
        "review_corrections": "",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


def test_agent_4_has_no_model_router_import() -> None:
    """CRITICAL: agent_4_tool_router.py must never import model_router."""
    source = Path("agents/agent_4_tool_router.py").read_text(encoding="utf-8")
    assert "model_router" not in source, (
        "agent_4_tool_router.py contains 'model_router' — "
        "Agent 4 must never import or reference ModelRouter."
    )


@pytest.mark.asyncio
async def test_agent_4_execute_calls_context_file_manager_before_tool_router() -> None:
    """CFM.write_all() must be called BEFORE ToolRouter.route() — ordering invariant."""
    agent = _make_agent_4()
    call_order: list[str] = []

    original_cfm_write = agent.cfm.write_all.side_effect  # type: ignore[union-attr]
    original_tr_route = agent._tool_router.route.side_effect  # type: ignore[union-attr]

    async def cfm_spy(*args: object, **kwargs: object) -> object:
        call_order.append("cfm.write_all")
        return ["AGENTS.md"]

    async def tr_spy(*args: object, **kwargs: object) -> ToolResult:
        call_order.append("tool_router.route")
        return _make_tool_result()

    agent.cfm.write_all = AsyncMock(side_effect=cfm_spy)  # type: ignore[union-attr]
    agent._tool_router.route = AsyncMock(side_effect=tr_spy)  # type: ignore[union-attr]

    await agent.run(_base_state())  # type: ignore[union-attr]

    cfm_idx = next(i for i, c in enumerate(call_order) if c == "cfm.write_all")
    tr_idx = next(i for i, c in enumerate(call_order) if c == "tool_router.route")
    assert cfm_idx < tr_idx, (
        f"ContextFileManager called at position {cfm_idx} "
        f"but ToolRouter called at position {tr_idx} — CFM must come first"
    )


@pytest.mark.asyncio
async def test_agent_4_interpret_shows_selected_tool_and_reason() -> None:
    agent = _make_agent_4()
    state = _base_state(human_confirmation="")
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("interpret_log")
    record = result["interpret_log"][0]
    assert "direct_llm" in record["action"].lower() or "DIRECT_LLM" in record["action"]


@pytest.mark.asyncio
async def test_agent_4_interpret_model_selected_is_none() -> None:
    """Agent 4 has no internal LLM — model_selected must be None in InterpretRecord."""
    agent = _make_agent_4()
    state = _base_state(human_confirmation="")
    result = await agent.run(state)  # type: ignore[union-attr]
    record = result["interpret_log"][0]
    assert record["model_selected"] is None


@pytest.mark.asyncio
async def test_agent_4_tool_delegated_to_set_in_state_after_execute() -> None:
    agent = _make_agent_4()
    result = await agent.run(_base_state())  # type: ignore[union-attr]
    assert result.get("tool_delegated_to") == "direct_llm"


@pytest.mark.asyncio
async def test_agent_4_auto_retries_on_blocking_maang_violation() -> None:
    """BLOCKING MAANG violation triggers auto-retry — ToolRouter called twice."""
    bad_code = "def foo():\n" + "    pass\n" * 55  # 55 lines > 50
    agent = _make_agent_4(tool_result=_make_tool_result(output=bad_code))

    await agent.run(_base_state())  # type: ignore[union-attr]

    # ToolRouter.route() should be called twice: initial + retry
    assert agent._tool_router.route.call_count >= 2  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_agent_4_max_2_retries_then_hitl_escalation() -> None:
    """After 2 retries, HITL is escalated — no more ToolRouter calls."""
    bad_code = "def foo():\n" + "    pass\n" * 55
    agent = _make_agent_4(tool_result=_make_tool_result(output=bad_code))
    state = _base_state()
    state["tool_retry_count"] = 2  # already at max

    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("hitl_required") is True
    assert "MAANG" in str(result.get("hitl_reason", ""))


@pytest.mark.asyncio
async def test_agent_4_correction_notes_appended_to_task_on_retry() -> None:
    """Second ToolRouter call must contain 'Fix required' in task string."""
    bad_code = "def foo():\n" + "    pass\n" * 55
    agent = _make_agent_4(tool_result=_make_tool_result(output=bad_code))

    await agent.run(_base_state())  # type: ignore[union-attr]

    # Get the task string from the second ToolRouter.route() call
    calls = agent._tool_router.route.call_args_list  # type: ignore[union-attr]
    assert len(calls) >= 2
    second_task = calls[1][1].get("task") or calls[1][0][0]
    assert "Fix required" in str(second_task)