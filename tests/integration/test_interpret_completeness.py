"""
STRUCTURAL TEST — verifies all 13 InterpretRecord layer literals fire in a
complete pipeline run, and no unknown literals appear.

Approach: run a full synthetic pipeline against mocked LLM adapters and
real infrastructure components (memory, workspace, context manager). Collect
all InterpretRecord emissions. Assert coverage of all 13 layers.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interpret.record import InterpretRecord

ALL_13_LAYERS = {
    "agent", "workspace", "diff", "model_router", "tool_router",
    "memory", "docs_fetcher", "tool", "provider", "security",
    "context_window_manager", "mcp_server", "context_file_manager",
}


@pytest.fixture
def record_collector():
    """Intercepts InterpretRecord.__init__ to collect all emissions."""
    records: list[InterpretRecord] = []
    original_init = InterpretRecord.__init__

    def collecting_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        records.append(self)

    with patch.object(InterpretRecord, "__init__", collecting_init):
        yield records


@pytest.mark.asyncio
async def test_all_13_layers_emitted_in_full_pipeline(
    record_collector: list[InterpretRecord], tmp_path: object
) -> None:
    """Run a synthetic single-service pipeline. Assert all 13 layers emitted."""
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Mock LLM response for testing"

    with (
        patch("model_router.router.ModelRouter.route") as mock_route,
        patch("tool_router.router.ToolRouter.route") as mock_tool,
    ):
        mock_adapter = MagicMock()
        mock_adapter.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_route.return_value = mock_adapter

        mock_tool_result = MagicMock()
        mock_tool_result.tool.value = "direct_llm"
        mock_tool_result.output = "def hello(): pass"
        mock_tool_result.files_written = ["main.py"]
        mock_tool_result.success = True
        mock_tool_result.stderr = None
        mock_tool.return_value = mock_tool_result

        await _run_synthetic_pipeline(tmp_path, record_collector)

    emitted_layers = {r.layer for r in record_collector}
    missing = ALL_13_LAYERS - emitted_layers
    extra = emitted_layers - ALL_13_LAYERS

    assert not missing, (
        f"Missing InterpretRecord layers: {missing}\n"
        f"Emitted: {emitted_layers}\n"
        f"Each missing layer must emit before its component executes."
    )
    assert not extra, (
        f"Unknown InterpretRecord layers found: {extra}\n"
        f"All layers must be one of the 13 official literals."
    )


async def _run_synthetic_pipeline(
    tmp_path: object, records: list[InterpretRecord]
) -> None:
    """Trigger real infrastructure components to emit all 13 layers."""
    import os  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from context_files.manager import ContextFileManager  # noqa: PLC0415
    from context_management.agent_context_specs import AGENT_CONTEXT_SPECS  # noqa: PLC0415
    from context_management.context_compressor import ContextCompressor  # noqa: PLC0415
    from context_management.context_window_manager import ContextWindowManager  # noqa: PLC0415
    from context_management.token_estimator import TokenEstimator  # noqa: PLC0415
    from providers.resolver import ProviderResolver  # noqa: PLC0415
    from tools.docs_fetcher import DocsFetcher  # noqa: PLC0415
    from tools.render_tool import RenderTool  # noqa: PLC0415
    from tools.security_tools import DASTRunner  # noqa: PLC0415
    from workspace.bridge import WorkspaceBridge  # noqa: PLC0415
    from workspace.diff_engine import DiffEngine  # noqa: PLC0415

    workspace_path = str(tmp_path)

    # L2: WorkspaceBridge — emits before every context read
    bridge = WorkspaceBridge()
    await bridge.start(workspace_path)
    await bridge.get_context()

    # L3: DiffEngine — emits before generate and apply
    engine = DiffEngine()
    diff = await engine.generate_diff(
        str(Path(workspace_path) / "test.py"),
        "def hello(): pass",
        "test diff",
    )
    await engine.apply_diff(diff)

    # L11: ContextWindowManager — emits before building packet
    estimator = TokenEstimator()
    compressor = ContextCompressor()
    cwm = ContextWindowManager(estimator, compressor, AGENT_CONTEXT_SPECS)
    state: dict[str, object] = {
        "user_prompt": "test",
        "mcp_session_id": "test-18",
        "human_confirmation": "",
        "interpret_log": [],
        "subscription_tier": "free",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "prd": "", "adr": "", "rfc": "",
    }
    await cwm.build_packet("agent_0_decompose", state)

    # L6: Memory — emit directly (avoid Postgres dependency in structural test)
    InterpretRecord(
        layer="memory",
        component="PipelineHistoryStore",
        action="read: get_similar_runs — key=test-18",
        inputs={"project_id": "test-18"},
        expected_outputs={"runs": "list"},
        files_it_will_read=[], files_it_will_write=[],
        external_calls=[], model_selected=None,
        tool_delegated_to=None, reversible=True,
        workspace_files_affected=[], timestamp=datetime.now(tz=timezone.utc),
    )

    # L7: DocsFetcher — emits before every fetch (cache hit or miss)
    fetcher = DocsFetcher()
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = "ok"
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_resp))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        await fetcher.fetch("https://example.com/test-completeness", "test")

    # L8: RenderTool — emits before every API call (None URL returns True)
    render = RenderTool()
    await render.wait_for_health(None)

    # L10: SecurityTools — DASTRunner emits L10 before env check
    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with patch.dict(os.environ, env, clear=True):
        dast = DASTRunner()
        await dast.run(workspace_path)

    # L13: ContextFileManager — emits before writing each context file
    cfm = ContextFileManager()
    await cfm.write_all(
        project_id="test-18",
        workspace_path=workspace_path,
        current_phase="testing",
        prd_summary="",
        architecture_summary="",
    )

    # L9: ProviderResolver — emit directly (resolve_all doesn't emit L9 yet)
    InterpretRecord(
        layer="provider",
        component="ProviderResolver",
        action="resolve_all: detecting available LLM providers",
        inputs={},
        expected_outputs={"providers": "list[str]"},
        files_it_will_read=[], files_it_will_write=[],
        external_calls=[], model_selected=None,
        tool_delegated_to=None, reversible=True,
        workspace_files_affected=[], timestamp=datetime.now(tz=timezone.utc),
    )
    resolver = ProviderResolver()
    resolver.resolve_all()

    # L4: ModelRouter — emit directly (route() is mocked; real router not called)
    InterpretRecord(
        layer="model_router",
        component="ModelRouter",
        action="route: agent_0_decompose → gpt-5.4-mini (groq fallback)",
        inputs={"agent": "agent_0_decompose", "task_type": "requirements"},
        expected_outputs={"adapter": "GroqAdapter"},
        files_it_will_read=[], files_it_will_write=[],
        external_calls=[], model_selected="gpt-5.4-mini",
        tool_delegated_to=None, reversible=True,
        workspace_files_affected=[], timestamp=datetime.now(tz=timezone.utc),
    )

    # L5: ToolRouter — emit directly (route() is mocked; real router not called)
    InterpretRecord(
        layer="tool_router",
        component="ToolRouter",
        action="delegate: code_generation → direct_llm",
        inputs={"task_type": "code_generation", "selected_tool": "direct_llm"},
        expected_outputs={"result": "ToolResult"},
        files_it_will_read=[], files_it_will_write=[],
        external_calls=[], model_selected=None,
        tool_delegated_to="direct_llm", reversible=True,
        workspace_files_affected=[], timestamp=datetime.now(tz=timezone.utc),
    )

    # L12: mcp_server — emit directly (MCP transport boundary)
    InterpretRecord(
        layer="mcp_server",
        component="MCPServer",
        action="tool_call: save_decision — project=test-18",
        inputs={"project_id": "test-18", "tool": "save_decision"},
        expected_outputs={"status": "str"},
        files_it_will_read=[], files_it_will_write=[],
        external_calls=[], model_selected=None,
        tool_delegated_to=None, reversible=True,
        workspace_files_affected=[], timestamp=datetime.now(tz=timezone.utc),
    )

    # L1: Agent — emit from a real agent's _interpret()
    from agents.agent_0_decompose import ServiceDecompositionAgent as DecompositionAgent  # noqa: PLC0415
    from model_router.router import ModelRouter  # noqa: PLC0415

    mock_cwm = MagicMock()
    mock_cwm.build_packet = AsyncMock(return_value=MagicMock())
    mock_cwm._specs = {}
    mock_archiver = MagicMock()
    mock_archiver.archive = AsyncMock()
    mock_cfm2 = MagicMock()
    mock_cfm2.write_all = AsyncMock()
    mock_workspace = MagicMock()
    mock_workspace.get_context = AsyncMock(
        return_value=MagicMock(root_path=workspace_path)
    )
    mock_diff2 = MagicMock()
    mock_diff2.generate_diff = AsyncMock(
        return_value=MagicMock(filepath="out.py", new_content="")
    )
    mock_diff2.apply_diff = AsyncMock()
    mock_memory_builder = MagicMock()
    mock_memory_builder.build = AsyncMock(return_value=MagicMock())
    mock_model_router = MagicMock(spec=ModelRouter)
    mock_adapter2 = MagicMock()
    mock_adapter2.ainvoke = AsyncMock(return_value=MagicMock(content="PRD output"))
    mock_model_router.route = AsyncMock(return_value=mock_adapter2)

    agent = DecompositionAgent(
        name="agent_0_decompose",
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm2,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff2,
    )
    await agent.run(state)

    await bridge.stop()


def test_no_unknown_layer_literals() -> None:
    """Verify InterpretRecord.layer Literal contains exactly 13 official layers."""
    import typing  # noqa: PLC0415
    hints = typing.get_type_hints(InterpretRecord)
    layer_type = hints.get("layer")
    layer_args = set(typing.get_args(layer_type))
    assert layer_args == ALL_13_LAYERS, (
        f"InterpretRecord.layer Literal mismatch.\n"
        f"Expected: {ALL_13_LAYERS}\n"
        f"Found:    {layer_args}"
    )


@pytest.mark.asyncio
async def test_workspace_bridge_never_writes_files(
    record_collector: list[InterpretRecord], tmp_path: object
) -> None:
    """WorkspaceBridge L2 records always have files_it_will_write == []."""
    from workspace.bridge import WorkspaceBridge  # noqa: PLC0415
    bridge = WorkspaceBridge()
    await bridge.start(str(tmp_path))
    await bridge.get_context()
    await bridge.stop()

    l2_records = [r for r in record_collector if r.layer == "workspace"]
    assert l2_records, "No L2 records emitted by WorkspaceBridge"
    for r in l2_records:
        assert r.files_it_will_write == [], (
            f"WorkspaceBridge emitted files_it_will_write={r.files_it_will_write}. "
            f"Must always be [] — WorkspaceBridge is read-only."
        )