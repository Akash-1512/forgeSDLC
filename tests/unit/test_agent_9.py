from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from model_router.catalog import AGENT_MODELS


def _make_agent_9() -> object:
    from agents.agent_9_monitoring import MonitoringAgent
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
    mock_workspace.get_context = AsyncMock(return_value=MagicMock(root_path="."))
    mock_diff = MagicMock()
    mock_diff.generate_diff = AsyncMock(
        return_value=MagicMock(filepath="runbook.md", new_content="")
    )
    mock_diff.apply_diff = AsyncMock()
    mock_model_router = MagicMock(spec=ModelRouter)
    mock_adapter = MagicMock()
    mock_adapter.ainvoke = AsyncMock(return_value=MagicMock(content="# Runbook\n..."))
    mock_model_router.route = AsyncMock(return_value=mock_adapter)

    return MonitoringAgent(
        name="agent_9_monitor",
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
        "user_prompt": "setup monitoring",
        "mcp_session_id": "proj-9",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "prd": "## Non-Functional Requirements\n99.9% uptime and < 200ms latency.",
        "adr": "", "rfc": "# RFC-001\nFastAPI service.",
        "deployment_url": "https://myapp.onrender.com",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


def test_agent_9_uses_groq_not_gpt_mini() -> None:
    """REGRESSION GUARD: Agent 9 must use groq, never gpt-5.4-mini."""
    # Assertion 1: catalog check
    assert AGENT_MODELS["agent_9_monitor"] == "groq/llama-3.3-70b-versatile", (
        "AGENT_MODELS['agent_9_monitor'] must be 'groq/llama-3.3-70b-versatile' — "
        "NOT gpt-5.4-mini. This is the most commonly confused assignment."
    )
    # Assertion 2: agent passes correct name to ModelRouter
    agent = _make_agent_9()
    # model_selected in interpret record
    from agents.agent_9_monitoring import _MODEL
    assert _MODEL == "groq/llama-3.3-70b-versatile"


def test_agent_9_model_selected_in_interpret_is_groq() -> None:
    import asyncio
    from agents.agent_9_monitoring import _MODEL
    agent = _make_agent_9()
    state = _base_state(human_confirmation="")
    result = asyncio.run(agent.run(state))
    record = result["interpret_log"][0]
    assert record["model_selected"] == _MODEL
    assert "groq" in record["model_selected"]


def test_agent_9_extracts_slo_from_99_9_nfr() -> None:
    from agents.agent_9_monitoring import MonitoringAgent
    agent = _make_agent_9()
    prd = "System must achieve 99.9% uptime and < 200ms latency."
    slos = agent._extract_slos(prd)  # type: ignore[union-attr]
    names = [s["name"] for s in slos]
    assert "Availability" in names
    targets = [s["target"] for s in slos]
    assert 99.9 in targets


def test_agent_9_generates_default_slo_when_no_nfr() -> None:
    agent = _make_agent_9()
    slos = agent._extract_slos("")  # type: ignore[union-attr]
    assert len(slos) >= 1
    assert slos[0]["name"] == "Availability"
    assert slos[0]["target"] == 99.0


@pytest.mark.asyncio
async def test_agent_9_writes_runbook_via_diff_engine() -> None:
    agent = _make_agent_9()
    await agent.run(_base_state())  # type: ignore[union-attr]
    agent.diff_engine.generate_diff.assert_called()  # type: ignore[union-attr]
    agent.diff_engine.apply_diff.assert_called()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_monitoring_config_stored_in_state() -> None:
    agent = _make_agent_9()
    result = await agent.run(_base_state())  # type: ignore[union-attr]
    assert "monitoring_config" in result
    config = result["monitoring_config"]
    assert "slo_definitions" in config
    assert "runbook_path" in config
    assert config.get("otel_configured") is True

