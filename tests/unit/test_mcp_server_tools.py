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
    from unittest.mock import AsyncMock, MagicMock
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    with patch("mcp_server.tools.requirements_tool._build_infrastructure"):
        with patch("mcp_server.tools.requirements_tool._build_agents") as mock_build:
            from agents.agent_0_decompose import ServiceDecompositionAgent
            from agents.agent_1_requirements import RequirementsAgent
            from agents.agent_2_stack import TechStackAgent

            async def fake_a0_run(state: dict) -> dict:
                state["service_graph"] = {"architecture_type": "monolith", "services": []}
                state["human_confirmation"] = ""
                return state

            async def fake_a1_run(state: dict) -> dict:
                state["prd"] = "# PRD\n## User Stories\n..."
                state["human_confirmation"] = ""
                return state

            async def fake_a2_run(state: dict) -> dict:
                state["adr"] = "# ADR-001\n## Decision\nFastAPI"
                state["human_confirmation"] = ""
                return state

            mock_a0 = MagicMock(spec=ServiceDecompositionAgent)
            mock_a0.run = AsyncMock(side_effect=fake_a0_run)
            mock_a1 = MagicMock(spec=RequirementsAgent)
            mock_a1.run = AsyncMock(side_effect=fake_a1_run)
            mock_a2 = MagicMock(spec=TechStackAgent)
            mock_a2.run = AsyncMock(side_effect=fake_a2_run)
            mock_build.return_value = (mock_a0, mock_a1, mock_a2)

            result = await gather_requirements(
                prompt="build an API", project_id="p1",
                ctx=mock_ctx, human_confirmation="100% GO"
            )
    assert isinstance(result, dict)
    assert result["status"] in ("complete", "awaiting_confirmation")
    assert "project_id" in result
    

@pytest.mark.asyncio
async def test_design_architecture_stub_returns_valid_dict() -> None:
    from unittest.mock import AsyncMock, MagicMock
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    with (
        patch(
            "mcp_server.tools.architecture_tool._build_arch_infrastructure",
            return_value=(
                MagicMock(), MagicMock(), MagicMock(),
                MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            ),
        ),
        patch(
            "mcp_server.tools.architecture_tool._build_arch_agent",
        ) as mock_build,
    ):
        from agents.agent_3_architecture import ArchitectureAgent
        mock_agent = MagicMock(spec=ArchitectureAgent)

        async def fake_run(state: dict) -> dict:
            state["arch_validation"] = {"gate_blocked": False, "anti_pattern_result": {"high_count": 0, "medium_count": 0, "all_clear": True, "findings": []}, "nfr_checks": [], "architecture_score": {"scalability": 1, "reliability": 1, "security": 1, "maintainability": 1, "cost": 1, "overall": 1.0}}
            state["rfc"] = "# RFC-001\n```mermaid\ngraph TD\n  A-->B\n```"
            state["human_confirmation"] = ""
            return state

        mock_agent.run = AsyncMock(side_effect=fake_run)
        mock_build.return_value = mock_agent
        result = await design_architecture(
            requirements="some requirements", project_id="p1", ctx=mock_ctx,
            human_confirmation="100% GO",
        )
    assert isinstance(result, dict)
    assert result["status"] in ("complete", "awaiting_confirmation", "blocked")
    assert "project_id" in result

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

    infra_tuple = (
        MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
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

    with (
        patch(
            "mcp_server.tools.code_generation_tool._build_codegen_infrastructure",
            return_value=infra_tuple,
        ),
        patch(
            "mcp_server.tools.code_generation_tool._build_codegen_agents",
        ) as mock_build,
    ):
        from agents.agent_4_tool_router import ToolRouterAgent
        from agents.agent_5_coord_review import CoordinatedReview
        mock_a4 = MagicMock(spec=ToolRouterAgent)
        mock_a4.run = AsyncMock(side_effect=fake_a4_run)
        mock_a5 = MagicMock(spec=CoordinatedReview)
        mock_a5.run = AsyncMock(side_effect=fake_a5_run)
        mock_build.return_value = (mock_a4, mock_a5)

        result = await route_code_generation(
            task="build something", project_id="p1",
            ctx=mock_ctx, human_confirmation="100% GO",
        )
    assert isinstance(result, dict)
    assert result["status"] in ("complete", "awaiting_confirmation", "hitl_required")
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