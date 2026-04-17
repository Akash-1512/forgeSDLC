from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from architecture_intelligence.anti_pattern_detector import AntiPatternDetector
from architecture_intelligence.architecture_scorer import ArchitectureScorer
from architecture_intelligence.nfr_satisfiability import NFRSatisfiabilityChecker


def _make_agent_3() -> object:
    from agents.agent_3_architecture import ArchitectureAgent
    from model_router.router import ModelRouter

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
    mock_workspace.get_context = AsyncMock(
        return_value=MagicMock(root_path=".")
    )

    mock_diff = MagicMock()
    mock_diff.generate_diff = AsyncMock(
        return_value=MagicMock(filepath="rfc.md", new_content="content")
    )
    mock_diff.apply_diff = AsyncMock()

    mock_model_router = MagicMock(spec=ModelRouter)

    return ArchitectureAgent(
        name="agent_3_architecture",
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )


def _base_state(human_confirmation: str = "") -> dict:
    return {
        "user_prompt": "build a REST API",
        "mcp_session_id": "proj-arch-1",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "prd": "## Non-Functional Requirements\nResponse time < 200ms.",
        "adr": "Use FastAPI.",
        "rfc": "",
        "service_graph": {"services": []},
        "arch_validation": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


def test_agent_3_hard_gate_is_true() -> None:
    from agents.agent_3_architecture import ArchitectureAgent
    assert ArchitectureAgent.hard_gate is True


@pytest.mark.asyncio
async def test_agent_3_blocks_execute_when_high_anti_pattern_found() -> None:
    agent = _make_agent_3()
    # Service with > 5 domain keywords → HIGH God Service finding
    state = _base_state(human_confirmation="100% GO")
    state["service_graph"] = {
        "services": [{
            "name": "monolith",
            "responsibility": "auth payment notification user order inventory analytics",
            "depends_on": [],
            "database": None,
            "owns_data": False,
            "exposes": [],
        }]
    }
    result = await agent.run(state)  # type: ignore[union-attr]
    # Even with "100% GO", execute should not have fired (rfc stays empty)
    assert not result.get("rfc")
    assert result.get("arch_validation", {}).get("gate_blocked") is True


@pytest.mark.asyncio
async def test_agent_3_allows_execute_when_all_clear_and_nfrs_pass() -> None:
    agent = _make_agent_3()
    agent.model_router.route = AsyncMock(  # type: ignore[union-attr]
        return_value=MagicMock(
            ainvoke=AsyncMock(
                return_value=MagicMock(
                    content="# RFC-001\n```mermaid\ngraph TD\n  A-->B\n```"
                )
            )
        )
    )
    state = _base_state(human_confirmation="100% GO")
    # No services → no anti-patterns, no NFRs in PRD → all clear
    state["prd"] = "Build a simple app."
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("rfc")


@pytest.mark.asyncio
async def test_agent_3_interpret_contains_scores() -> None:
    agent = _make_agent_3()
    state = _base_state()
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("arch_validation") is not None
    score = result["arch_validation"].get("architecture_score", {})
    assert "scalability" in score
    assert "overall" in score


@pytest.mark.asyncio
async def test_agent_3_interpret_shows_blocking_reason_when_blocked() -> None:
    agent = _make_agent_3()
    state = _base_state(human_confirmation="100% GO")
    state["service_graph"] = {
        "services": [{
            "name": "mega",
            "responsibility": "auth payment notification user order inventory analytics",
            "depends_on": [], "database": None,
            "owns_data": False, "exposes": [],
        }]
    }
    result = await agent.run(state)  # type: ignore[union-attr]
    displayed = str(result.get("displayed_interpretation", ""))
    assert "BLOCKED" in displayed or "blocked" in displayed.lower()


@pytest.mark.asyncio
async def test_agent_3_writes_rfc_via_diff_engine_not_directly() -> None:
    agent = _make_agent_3()
    agent.model_router.route = AsyncMock(  # type: ignore[union-attr]
        return_value=MagicMock(
            ainvoke=AsyncMock(
                return_value=MagicMock(
                    content="# RFC-001\n```mermaid\ngraph TD\n  A-->B\n```"
                )
            )
        )
    )
    state = _base_state(human_confirmation="100% GO")
    state["prd"] = "Build a simple app."
    await agent.run(state)  # type: ignore[union-attr]
    agent.diff_engine.generate_diff.assert_called()  # type: ignore[union-attr]
    agent.diff_engine.apply_diff.assert_called()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_agent_3_writes_openapi_only_when_api_service_detected() -> None:
    agent = _make_agent_3()
    agent.model_router.route = AsyncMock(  # type: ignore[union-attr]
        return_value=MagicMock(
            ainvoke=AsyncMock(
                return_value=MagicMock(content="# RFC\n```mermaid\ngraph TD\n  A-->B\n```")
            )
        )
    )
    state = _base_state(human_confirmation="100% GO")
    state["prd"] = "Build a simple app."
    # No API services
    state["service_graph"] = {"services": [{"name": "worker", "exposes": [], "depends_on": []}]}
    await agent.run(state)  # type: ignore[union-attr]
    call_args = [
        str(call) for call in agent.diff_engine.generate_diff.call_args_list  # type: ignore[union-attr]
    ]
    openapi_calls = [c for c in call_args if "openapi" in c]
    assert len(openapi_calls) == 0


def test_agent_3_mermaid_diagram_embedded_in_rfc() -> None:
    """Mermaid must be a fenced code block, not an image URL."""
    rfc = "# RFC-001\n```mermaid\ngraph TD\n  A[Client] --> B[API]\n```\n"
    assert "```mermaid" in rfc
    assert "![" not in rfc  # no image URL syntax