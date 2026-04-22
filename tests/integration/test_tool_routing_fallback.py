from __future__ import annotations

"""Integration tests — real ContextFileManager + mocked adapters.
Tests ordering guarantee and fallback chain without external tool dependencies.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tool_router.context import AvailableTool, ToolResult


def _stub_result(tool: AvailableTool = AvailableTool.DIRECT_LLM) -> ToolResult:
    return ToolResult(
        tool=tool,
        output="# generated code",
        files_written=[],
        success=True,
        stderr=None,
    )


@pytest.mark.asyncio
async def test_full_route_delegates_to_direct_llm_when_no_tools_configured(
    tmp_path: Path,
) -> None:
    from context_files.manager import ContextFileManager
    from tool_router.router import ToolRouter

    cfm = ContextFileManager()
    router = ToolRouter(context_file_manager=cfm)

    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=False)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
        patch(
            "tool_router.router.DirectLLMAdapter.generate",
            AsyncMock(return_value=_stub_result(AvailableTool.DIRECT_LLM)),
        ),
    ):
        result = await router.route(
            task="write hello world",
            context="ctx",
            project_id="integration-proj",
            workspace_path=str(tmp_path),
        )

    assert result.tool == AvailableTool.DIRECT_LLM
    assert result.success is True


@pytest.mark.asyncio
async def test_context_files_written_before_delegation(tmp_path: Path) -> None:
    """Ordering guarantee: context files must be written before adapter.generate()."""
    from context_files.manager import ContextFileManager
    from tool_router.router import ToolRouter

    call_order: list[str] = []
    cfm = ContextFileManager()

    original_write_all = cfm.write_all

    async def spying_write_all(**kwargs: object) -> list[str]:
        call_order.append("cfm")
        return await original_write_all(**kwargs)

    cfm.write_all = spying_write_all  # type: ignore[method-assign]
    router = ToolRouter(context_file_manager=cfm)

    async def fake_generate(
        self: object, task: str, context: str, workspace_path: str
    ) -> ToolResult:
        call_order.append("adapter")
        return _stub_result()

    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=False)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
        patch("tool_router.router.DirectLLMAdapter.generate", fake_generate),
    ):
        await router.route(
            task="write tests",
            context="ctx",
            project_id="ordering-proj",
            workspace_path=str(tmp_path),
        )

    assert "cfm" in call_order
    assert "adapter" in call_order
    assert call_order.index("cfm") < call_order.index("adapter"), (
        f"CFM must precede adapter. Order: {call_order}"
    )
    # Verify context files actually exist on disk
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".cursorrules").exists()


@pytest.mark.asyncio
async def test_fallback_chain_cursor_unavailable_then_claude_code(
    tmp_path: Path,
) -> None:
    """Cursor unavailable → Claude Code selected."""
    from context_files.manager import ContextFileManager
    from tool_router.router import ToolRouter

    cfm = ContextFileManager()
    router = ToolRouter(context_file_manager=cfm)

    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=True)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
        patch(
            "tool_router.router.ClaudeCodeAdapter.generate",
            AsyncMock(return_value=_stub_result(AvailableTool.CLAUDE_CODE)),
        ),
    ):
        result = await router.route(
            task="write a function",
            context="ctx",
            project_id="fallback-proj",
            workspace_path=str(tmp_path),
        )

    assert result.tool == AvailableTool.CLAUDE_CODE


@pytest.mark.asyncio
async def test_route_code_generation_mcp_tool_returns_valid_response(
    tmp_path: Path,
) -> None:
    from unittest.mock import AsyncMock

    from fastmcp import Context

    from agents.agent_4_tool_router import ToolRouterAgent
    from agents.agent_5_coord_review import CoordinatedReview

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.report_progress = AsyncMock()

    infra_tuple = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    async def fake_a4_run(state: dict) -> dict:
        state["generated_files"] = [{"path": "main.py", "content": "def foo(): pass"}]
        state["tool_delegated_to"] = "direct_llm"
        state["human_confirmation"] = ""
        return state

    async def fake_a5_run(state: dict) -> dict:
        state["review_findings"] = []
        state["trigger_agent_4_retry"] = False
        state["human_confirmation"] = ""
        return state

    mock_a4 = MagicMock(spec=ToolRouterAgent)
    mock_a4.run = AsyncMock(side_effect=fake_a4_run)
    mock_a5 = MagicMock(spec=CoordinatedReview)
    mock_a5.run = AsyncMock(side_effect=fake_a5_run)

    with (
        patch(
            "mcp_server.tools.code_generation_tool._build_codegen_infrastructure",
            return_value=infra_tuple,
        ),
        patch(
            "mcp_server.tools.code_generation_tool._build_codegen_agents",
            return_value=(mock_a4, mock_a5),
        ),
    ):
        from mcp_server.tools.code_generation_tool import route_code_generation

        result = await route_code_generation(
            task="write a hello world function",
            project_id=f"test-codegen-{tmp_path.name}",
            ctx=mock_ctx,
            human_confirmation="100% GO",
        )

    assert isinstance(result, dict)
    assert result["status"] in ("complete", "awaiting_confirmation", "hitl_required")
    assert "project_id" in result
