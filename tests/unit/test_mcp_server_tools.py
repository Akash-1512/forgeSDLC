from __future__ import annotations

import pytest

from unittest.mock import patch
from mcp_server.tools.architecture_tool import design_architecture
from mcp_server.tools.cicd_tool import generate_cicd
from mcp_server.tools.code_generation_tool import route_code_generation
from mcp_server.tools.deploy_tool import deploy_project
from mcp_server.tools.docs_tool import generate_docs
from mcp_server.tools.memory_tool import recall_context, save_decision
from mcp_server.tools.monitor_tool import setup_monitoring
from mcp_server.tools.progress_tool import track_progress
from mcp_server.tools.requirements_tool import gather_requirements
from mcp_server.tools.security_tool import run_security_scan


def _assert_valid_stub(result: dict[str, object], tool: str) -> None:
    assert isinstance(result, dict)
    assert result["status"] == "stub"
    assert result["tool"] == tool
    assert "project_id" in result


def test_server_instantiates_without_error() -> None:
    from mcp_server.server import mcp
    assert mcp.name == "forgesdlc"


@pytest.mark.asyncio
async def test_gather_requirements_stub_returns_valid_dict() -> None:
    result = await gather_requirements(prompt="build an API", project_id="p1")
    _assert_valid_stub(result, "gather_requirements")


@pytest.mark.asyncio
async def test_design_architecture_stub_returns_valid_dict() -> None:
    result = await design_architecture(project_id="p1", prd="some prd")
    _assert_valid_stub(result, "design_architecture")


@pytest.mark.asyncio
async def test_recall_context_stub_returns_valid_dict() -> None:
    from unittest.mock import AsyncMock, MagicMock
    from memory.organisational_memory import OrgMemory
    from memory.pipeline_history_store import PipelineHistoryStore
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    with (
        patch("mcp_server.tools.memory_tool.MemoryContextBuilder") as mock_builder,
    ):
        mock_context = {
            "org_memory": [],
            "similar_runs": [],
            "layers_queried": ["pipeline_history_store", "org_memory"],
            "assembled_at": "2026-01-01T00:00:00+00:00",
        }
        mock_builder.return_value.build = AsyncMock(return_value=mock_context)
        result = await recall_context(query="what stack?", project_id="p1", ctx=mock_ctx)
    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert "project_id" in result


@pytest.mark.asyncio
async def test_save_decision_stub_returns_valid_dict() -> None:
    from unittest.mock import AsyncMock, MagicMock
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    with patch("mcp_server.tools.memory_tool.OrgMemory") as mock_org:
        mock_org.return_value.upsert = AsyncMock()
        result = await save_decision(
            decision="use postgres", rationale="scale", project_id="p1", ctx=mock_ctx
        )
    assert isinstance(result, dict)
    assert result["status"] == "saved"
    assert "project_id" in result


@pytest.mark.asyncio
async def test_route_code_generation_stub_returns_valid_dict() -> None:
    from unittest.mock import AsyncMock, MagicMock
    from tool_router.context import AvailableTool, ToolResult
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    with patch("mcp_server.tools.code_generation_tool.ToolRouter.route",
               AsyncMock(return_value=ToolResult(
                   tool=AvailableTool.DIRECT_LLM,
                   output="# code",
                   files_written=[],
                   success=True,
                   stderr=None,
               ))):
        result = await route_code_generation(
            task="write tests", project_id="p1", ctx=mock_ctx
        )
    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert "project_id" in result


@pytest.mark.asyncio
async def test_run_security_scan_stub_returns_valid_dict() -> None:
    result = await run_security_scan(project_id="p1", target_path="./src")
    _assert_valid_stub(result, "run_security_scan")


@pytest.mark.asyncio
async def test_generate_cicd_stub_returns_valid_dict() -> None:
    result = await generate_cicd(project_id="p1", stack="fastapi")
    _assert_valid_stub(result, "generate_cicd")


@pytest.mark.asyncio
async def test_deploy_project_stub_returns_valid_dict() -> None:
    result = await deploy_project(project_id="p1", environment="staging")
    _assert_valid_stub(result, "deploy_project")


@pytest.mark.asyncio
async def test_setup_monitoring_stub_returns_valid_dict() -> None:
    result = await setup_monitoring(project_id="p1", deployment_url="https://app.example.com")
    _assert_valid_stub(result, "setup_monitoring")


@pytest.mark.asyncio
async def test_generate_docs_stub_returns_valid_dict() -> None:
    result = await generate_docs(project_id="p1", scope="full")
    _assert_valid_stub(result, "generate_docs")


@pytest.mark.asyncio
async def test_track_progress_stub_returns_valid_dict() -> None:
    result = await track_progress(project_id="p1")
    _assert_valid_stub(result, "track_progress")