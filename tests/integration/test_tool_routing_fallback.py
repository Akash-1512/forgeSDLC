from __future__ import annotations

"""Integration tests — real ContextFileManager + mocked adapters.
Tests ordering guarantee and fallback chain without external tool dependencies.
"""

import tempfile
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
    from unittest.mock import MagicMock
    from mcp_server.tools.code_generation_tool import route_code_generation

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with (
        patch(
            "mcp_server.tools.code_generation_tool.ToolRouter.route",
            AsyncMock(return_value=_stub_result(AvailableTool.DIRECT_LLM)),
        ),
        patch(
            "mcp_server.tools.code_generation_tool.ContextFileManager.write_all",
            AsyncMock(return_value=["AGENTS.md"]),
        ),
    ):
        result = await route_code_generation(
            task="write a FastAPI endpoint",
            project_id="mcp-test",
            ctx=mock_ctx,
            workspace_path=str(tmp_path),
        )

    assert result["status"] == "ok"
    assert result["tool_used"] == AvailableTool.DIRECT_LLM.value
    assert result["project_id"] == "mcp-test"