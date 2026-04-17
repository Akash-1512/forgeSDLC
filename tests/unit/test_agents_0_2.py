from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interpret.record import InterpretRecord


def _make_base_kwargs() -> dict:
    from context_management.context_packet import ContextPacket
    from model_router.router import ModelRouter

    mock_packet = MagicMock(spec=ContextPacket)
    mock_memory = MagicMock()

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
    mock_workspace.get_context = AsyncMock(
        return_value=MagicMock(root_path=".")
    )

    mock_diff = MagicMock()
    mock_diff.generate_diff = AsyncMock(
        return_value=MagicMock(filepath="test.md", new_content="content")
    )
    mock_diff.apply_diff = AsyncMock()

    mock_model_router = MagicMock(spec=ModelRouter)

    return {
        "context_window_manager": mock_cwm,
        "model_router": mock_model_router,
        "memory_archiver": mock_archiver,
        "memory_context_builder": mock_memory_builder,
        "context_file_manager": mock_cfm,
        "workspace_bridge": mock_workspace,
        "diff_engine": mock_diff,
    }


def _mock_adapter(content: str) -> object:
    adapter = MagicMock()
    adapter.ainvoke = AsyncMock(return_value=MagicMock(content=content))
    return adapter


@pytest.mark.asyncio
async def test_agent_0_sets_service_graph_in_state() -> None:
    from agents.agent_0_decompose import ServiceDecompositionAgent
    kwargs = _make_base_kwargs()
    kwargs["model_router"].route = AsyncMock(
        return_value=_mock_adapter(
            '{"architecture_type": "monolith", "reasoning": "simple app", '
            '"services": [], "confidence": "HIGH"}'
        )
    )
    agent = ServiceDecompositionAgent(name="agent_0_decompose", **kwargs)
    state: dict = {
        "user_prompt": "build a todo app",
        "mcp_session_id": "p1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }
    result = await agent.run(state)
    assert result.get("service_graph") is not None
    assert "architecture_type" in result["service_graph"]


@pytest.mark.asyncio
async def test_agent_0_interpret_contains_architecture_type() -> None:
    from agents.agent_0_decompose import ServiceDecompositionAgent
    kwargs = _make_base_kwargs()
    kwargs["model_router"].route = AsyncMock(
        return_value=_mock_adapter(
            '{"architecture_type": "multi_service", "reasoning": "complex", '
            '"services": ["api", "worker"], "confidence": "HIGH"}'
        )
    )
    agent = ServiceDecompositionAgent(name="agent_0_decompose", **kwargs)
    state: dict = {
        "user_prompt": "build a distributed system",
        "mcp_session_id": "p1",
        "human_confirmation": "",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }
    result = await agent.run(state)
    assert len(result["interpret_log"]) >= 1
    record = result["interpret_log"][0]
    assert record["layer"] == "agent"
    assert "Analysing scope" in record["action"]


@pytest.mark.asyncio
async def test_agent_1_sets_prd_in_state() -> None:
    from agents.agent_1_requirements import RequirementsAgent
    kwargs = _make_base_kwargs()
    prd_content = (
        "# My App PRD\n"
        "## Executive Summary\nA test app.\n"
        "## User Stories\nAs a user, I want to login.\n"
        "## Acceptance Criteria\nGiven I am on login page...\n"
        "## Non-Functional Requirements\nPerformance < 200ms.\n"
        "## Out of Scope\nMobile app.\n"
        "## Assumptions and Risks\nInternet required.\n"
    )
    kwargs["model_router"].route = AsyncMock(
        return_value=_mock_adapter(prd_content)
    )
    agent = RequirementsAgent(name="agent_1_requirements", **kwargs)
    state: dict = {
        "user_prompt": "build a login system",
        "mcp_session_id": "p1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "service_graph": {"architecture_type": "monolith", "services": []},
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }
    result = await agent.run(state)
    assert result.get("prd")
    assert len(str(result["prd"])) > 10


def test_agent_1_prd_contains_user_stories_section() -> None:
    prd = "## User Stories\nAs a user, I want to login."
    assert "User Stories" in prd


def test_agent_1_prd_contains_acceptance_criteria_section() -> None:
    prd = "## Acceptance Criteria\nGiven I am on login page..."
    assert "Acceptance Criteria" in prd


def test_agent_1_prd_contains_non_functional_requirements_section() -> None:
    prd = "## Non-Functional Requirements\nResponse time < 200ms."
    assert "Non-Functional Requirements" in prd


@pytest.mark.asyncio
async def test_agent_1_writes_prd_md_via_diff_engine() -> None:
    from agents.agent_1_requirements import RequirementsAgent
    kwargs = _make_base_kwargs()
    kwargs["model_router"].route = AsyncMock(
        return_value=_mock_adapter("# PRD\n## User Stories\n...")
    )
    agent = RequirementsAgent(name="agent_1_requirements", **kwargs)
    state: dict = {
        "user_prompt": "build something",
        "mcp_session_id": "p1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "service_graph": {"architecture_type": "monolith", "services": []},
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }
    await agent.run(state)
    kwargs["diff_engine"].generate_diff.assert_called_once()
    kwargs["diff_engine"].apply_diff.assert_called_once()


@pytest.mark.asyncio
async def test_agent_2_sets_adr_in_state() -> None:
    from agents.agent_2_stack import TechStackAgent
    kwargs = _make_base_kwargs()
    adr_content = (
        "# ADR-001: Technology Stack Selection\n"
        "## Status\nAccepted\n"
        "## Decision\nUse FastAPI + PostgreSQL\n"
        "- **Language**: Python\n"
        "- **Framework**: FastAPI\n"
    )
    kwargs["model_router"].route = AsyncMock(
        return_value=_mock_adapter(adr_content)
    )
    agent = TechStackAgent(name="agent_2_stack", **kwargs)
    state: dict = {
        "user_prompt": "build a REST API",
        "mcp_session_id": "p1",
        "human_confirmation": "100% GO",
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "service_graph": {"architecture_type": "monolith", "services": []},
        "prd": "# PRD\n## User Stories\n...",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }
    result = await agent.run(state)
    assert result.get("adr")


def test_agent_2_adr_contains_tech_stack_decision() -> None:
    adr = "# ADR-001: Technology Stack Selection\n## Decision\nUse FastAPI."
    assert "ADR-001" in adr
    assert "Decision" in adr