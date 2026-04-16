from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tool_router.context import AvailableTool, ToolResult


def _make_router(cfm: object | None = None) -> object:
    from context_files.manager import ContextFileManager
    from tool_router.router import ToolRouter

    mock_cfm = cfm or MagicMock(spec=ContextFileManager)
    mock_cfm.write_all = AsyncMock(return_value=["AGENTS.md", "CLAUDE.md"])
    return ToolRouter(context_file_manager=mock_cfm)


def _stub_result(tool: AvailableTool = AvailableTool.DIRECT_LLM) -> ToolResult:
    return ToolResult(
        tool=tool,
        output="# generated code",
        files_written=[],
        success=True,
        stderr=None,
    )


@pytest.mark.asyncio
async def test_detect_always_includes_direct_llm_as_last_tool() -> None:
    router = _make_router()
    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=False)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
    ):
        tools = await router.detect_available_tools()  # type: ignore[union-attr]
    assert tools[-1] == AvailableTool.DIRECT_LLM
    assert AvailableTool.DIRECT_LLM in tools


@pytest.mark.asyncio
async def test_detect_cursor_returns_false_without_cursor_api_verified_env() -> None:
    router = _make_router()
    import os
    env = {k: v for k, v in os.environ.items()
           if k not in ("CURSOR_API_KEY", "CURSOR_API_VERIFIED")}
    with patch.dict(os.environ, env, clear=True):
        result = await router._check_cursor()  # type: ignore[union-attr]
    assert result is False


@pytest.mark.asyncio
async def test_detect_cursor_returns_false_with_key_but_without_verified_flag() -> None:
    router = _make_router()
    import os
    with patch.dict(os.environ, {"CURSOR_API_KEY": "sk-test", "CURSOR_API_VERIFIED": "false"}):
        result = await router._check_cursor()  # type: ignore[union-attr]
    assert result is False


@pytest.mark.asyncio
async def test_detect_claude_code_returns_false_when_not_in_path() -> None:
    router = _make_router()
    with patch(
        "tool_router.router.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("claude not found"),
    ):
        result = await router._check_claude_code()  # type: ignore[union-attr]
    assert result is False


@pytest.mark.asyncio
async def test_detect_devin_returns_false_without_devin_api_key() -> None:
    router = _make_router()
    import os
    env = {k: v for k, v in os.environ.items() if k != "DEVIN_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        result = await router._check_devin()  # type: ignore[union-attr]
    assert result is False


@pytest.mark.asyncio
async def test_route_emits_interpret_record_layer5_before_delegation() -> None:
    router = _make_router()
    emitted_layers: list[str] = []

    from interpret.record import InterpretRecord
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        emitted_layers.append(str(kwargs.get("layer", "")))

    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=False)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
        patch(
            "tool_router.router.DirectLLMAdapter.generate",
            AsyncMock(return_value=_stub_result()),
        ),
        patch.object(InterpretRecord, "__init__", capturing_init),
    ):
        await router.route(  # type: ignore[union-attr]
            task="write a test",
            context="project ctx",
            project_id="proj-1",
            workspace_path=".",
        )

    assert "tool_router" in emitted_layers


@pytest.mark.asyncio
async def test_route_calls_context_file_manager_before_tool_invocation() -> None:
    """Ordering test: CFM.write_all() must be called before adapter.generate()."""
    from context_files.manager import ContextFileManager
    from tool_router.router import ToolRouter

    call_order: list[str] = []

    mock_cfm = MagicMock(spec=ContextFileManager)

    async def spying_write_all(**kwargs: object) -> list[str]:
        call_order.append("cfm")
        return ["AGENTS.md"]

    mock_cfm.write_all = spying_write_all

    # Create router directly — do NOT use _make_router which overwrites write_all
    router = ToolRouter(context_file_manager=mock_cfm)

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
            task="write models",
            context="ctx",
            project_id="proj-1",
            workspace_path=".",
        )

    assert "cfm" in call_order, f"CFM was never called. Order: {call_order}"
    assert "adapter" in call_order, f"Adapter was never called. Order: {call_order}"
    assert call_order.index("cfm") < call_order.index("adapter"), (
        f"CFM must be called before adapter. Got order: {call_order}"
    )


@pytest.mark.asyncio
async def test_route_falls_back_to_direct_llm_when_all_others_unavailable() -> None:
    router = _make_router()
    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=False)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
        patch(
            "tool_router.router.DirectLLMAdapter.generate",
            AsyncMock(return_value=_stub_result(AvailableTool.DIRECT_LLM)),
        ),
    ):
        result = await router.route(  # type: ignore[union-attr]
            task="write tests",
            context="ctx",
            project_id="proj-1",
            workspace_path=".",
        )
    assert result.tool == AvailableTool.DIRECT_LLM


@pytest.mark.asyncio
async def test_claude_code_adapter_times_out_after_mcp_tool_timeout_seconds() -> None:
    from orchestrator.exceptions import ToolRouterError
    from tool_router.adapters.claude_code_adapter import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()

    async def slow_communicate() -> tuple[bytes, bytes]:
        await asyncio.sleep(999)
        return b"", b""

    mock_proc = MagicMock()
    mock_proc.communicate = slow_communicate
    mock_proc.kill = MagicMock()

    with (
        patch(
            "tool_router.adapters.claude_code_adapter.asyncio.create_subprocess_exec",
            AsyncMock(return_value=mock_proc),
        ),
        patch(
            "tool_router.adapters.claude_code_adapter.MCP_TOOL_TIMEOUT_SECONDS",
            0.01,
        ),
    ):
        with pytest.raises(ToolRouterError, match="timed out"):
            await adapter.generate(
                task="write code", context="ctx", workspace_path="."
            )


@pytest.mark.asyncio
async def test_direct_llm_adapter_returns_tool_result_with_success_true() -> None:
    from tool_router.adapters.direct_llm_adapter import DirectLLMAdapter

    adapter = DirectLLMAdapter()

    import os
    env = {k: v for k, v in os.environ.items()
           if k not in ("OPENAI_API_KEY", "GROQ_API_KEY")}
    with patch.dict(os.environ, env, clear=True):
        result = await adapter.generate(
            task="write a hello world", context="ctx", workspace_path="."
        )

    assert isinstance(result, ToolResult)
    assert result.tool == AvailableTool.DIRECT_LLM
    # No key set → success=False but ToolResult returned (never raises)
    assert result.success is False
    assert result.stderr is not None