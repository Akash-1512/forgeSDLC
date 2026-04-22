from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.security_tools import SecurityFinding


def _make_finding(severity: str, tool: str = "bandit") -> SecurityFinding:
    return SecurityFinding(
        tool=tool,  # type: ignore[arg-type]
        rule="TEST001",
        severity=severity,  # type: ignore[arg-type]
        file="main.py",
        line=10,
        description=f"{severity} test finding",
        fix_suggestion=None,
        blocking=severity in ("CRITICAL", "HIGH"),
    )


def _make_agent_5b() -> object:
    from agents.agent_5b_security import SecurityAgent
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
        return_value=MagicMock(filepath="threat_model.md", new_content="content")
    )
    mock_diff.apply_diff = AsyncMock()

    mock_model_router = MagicMock(spec=ModelRouter)
    mock_adapter = MagicMock()
    mock_adapter.ainvoke = AsyncMock(
        return_value=MagicMock(content="# STRIDE Threat Model\n## Spoofing\n...")
    )
    mock_model_router.route = AsyncMock(return_value=mock_adapter)

    return SecurityAgent(
        name="agent_5b_security",
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
        "user_prompt": "scan my project",
        "mcp_session_id": "proj-sec",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "rfc": "# RFC-001\n## Security\nUse TLS everywhere.",
        "prd": "",
        "adr": "",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


def _patch_all_tools(
    bandit_findings: list = None,
    semgrep_findings: list = None,
    pip_findings: list = None,
    dast_findings: list = None,
    secrets_findings: list = None,
) -> object:
    if secrets_findings is None:
        secrets_findings = []
    if dast_findings is None:
        dast_findings = []
    if pip_findings is None:
        pip_findings = []
    if semgrep_findings is None:
        semgrep_findings = []
    if bandit_findings is None:
        bandit_findings = []
    return patch.multiple(
        "agents.agent_5b_security",
        BanditRunner=MagicMock(return_value=MagicMock(run=AsyncMock(return_value=bandit_findings))),
        SemgrepRunner=MagicMock(
            return_value=MagicMock(run=AsyncMock(return_value=semgrep_findings))
        ),
        PipAuditRunner=MagicMock(return_value=MagicMock(run=AsyncMock(return_value=pip_findings))),
        DASTRunner=MagicMock(return_value=MagicMock(run=AsyncMock(return_value=dast_findings))),
    )


@pytest.mark.asyncio
async def test_gate_blocked_true_when_any_high_finding() -> None:
    agent = _make_agent_5b()
    with _patch_all_tools(bandit_findings=[_make_finding("HIGH")]):
        with patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])):
            with patch.object(agent, "_run_stride", AsyncMock(return_value=None)):
                result = await agent.run(_base_state())
    assert result["security_gate"]["blocked"] is True


@pytest.mark.asyncio
async def test_gate_blocked_true_when_any_critical_finding() -> None:
    agent = _make_agent_5b()
    with _patch_all_tools(semgrep_findings=[_make_finding("CRITICAL", "semgrep")]):
        with patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])):
            with patch.object(agent, "_run_stride", AsyncMock(return_value=None)):
                result = await agent.run(_base_state())
    assert result["security_gate"]["blocked"] is True


@pytest.mark.asyncio
async def test_gate_blocked_false_when_only_medium_and_low() -> None:
    agent = _make_agent_5b()
    with (
        _patch_all_tools(bandit_findings=[_make_finding("MEDIUM"), _make_finding("LOW")]),
        patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])),
    ):
        with patch.object(agent, "_run_stride", AsyncMock(return_value=None)):
            result = await agent.run(_base_state())
    assert result["security_gate"]["blocked"] is False


@pytest.mark.asyncio
async def test_security_findings_stored_in_state() -> None:
    agent = _make_agent_5b()
    with _patch_all_tools():
        with patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])):
            with patch.object(agent, "_run_stride", AsyncMock(return_value=None)):
                result = await agent.run(_base_state())
    assert "security_findings" in result
    assert isinstance(result["security_findings"], dict)


@pytest.mark.asyncio
async def test_security_gate_stored_in_state() -> None:
    agent = _make_agent_5b()
    with _patch_all_tools():
        with patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])):
            with patch.object(agent, "_run_stride", AsyncMock(return_value=None)):
                result = await agent.run(_base_state())
    assert "security_gate" in result
    assert "blocked" in result["security_gate"]


@pytest.mark.asyncio
async def test_threat_model_written_to_docs_security_via_diff_engine() -> None:
    agent = _make_agent_5b()
    with _patch_all_tools():
        with patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])):
            await agent.run(_base_state())
    agent.diff_engine.generate_diff.assert_called()
    agent.diff_engine.apply_diff.assert_called()


@pytest.mark.asyncio
async def test_agent_5b_uses_o3_mini_not_gpt_mini_for_stride() -> None:
    """ModelRouter.route must be called with agent='agent_5b_security'."""
    agent = _make_agent_5b()
    with _patch_all_tools():
        with patch.object(agent, "_run_detect_secrets", AsyncMock(return_value=[])):
            await agent.run(_base_state())
    agent.model_router.route.assert_called()
    call_kwargs = agent.model_router.route.call_args
    assert call_kwargs.kwargs.get("agent") == "agent_5b_security"


@pytest.mark.asyncio
async def test_agent_5b_interpret_shows_dast_disabled_status_when_env_not_set() -> None:
    agent = _make_agent_5b()
    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with patch.dict(os.environ, env, clear=True):
        state = _base_state(human_confirmation="")
        result = await agent.run(state)
    log = result.get("interpret_log", [])
    assert log
    action = log[0].get("action", "")
    assert "disabled" in action.lower() or "RUN_DAST" in action


@pytest.mark.asyncio
async def test_agent_5b_interpret_shows_dast_enabled_status_when_env_set() -> None:
    agent = _make_agent_5b()
    with patch.dict(os.environ, {"RUN_DAST": "true"}):
        state = _base_state(human_confirmation="")
        result = await agent.run(state)
    log = result.get("interpret_log", [])
    assert log
    action = log[0].get("action", "")
    assert "enabled" in action.lower() or "18080" in action
