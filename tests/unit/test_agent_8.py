from __future__ import annotations

import contextlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.agent_8_deploy import DeployAgent


def _make_agent_8() -> DeployAgent:
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
        return_value=MagicMock(filepath="Dockerfile", new_content="")
    )
    mock_diff.apply_diff = AsyncMock()
    mock_model_router = MagicMock(spec=ModelRouter)

    return DeployAgent(
        name="agent_8_deploy",
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )


def _base_state(
    human_confirmation: str = "100% GO",
    gate_blocked: bool = False,
) -> dict:
    return {
        "user_prompt": "deploy my app",
        "mcp_session_id": "proj-8",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "prd": "",
        "adr": "",
        "rfc": "",
        "security_gate": {
            "blocked": gate_blocked,
            "reason": "2 HIGH findings" if gate_blocked else None,
        },
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
        "trace_id": "test-trace",
    }


def test_agent_8_hard_gate_is_true() -> None:
    assert DeployAgent.hard_gate is True


@pytest.mark.asyncio
async def test_agent_8_security_pre_check_blocks_when_gate_blocked() -> None:
    agent = _make_agent_8()
    state = _base_state(human_confirmation="100% GO", gate_blocked=True)
    result = await agent.run(state)
    assert result.get("deploy_blocked") is True
    assert "Security gate" in str(result.get("deploy_blocked_reason", ""))


@pytest.mark.asyncio
async def test_agent_8_security_pre_check_does_not_call_super_when_blocked() -> None:
    """super().run() must NOT be called when security gate is blocked."""
    agent = _make_agent_8()
    state = _base_state(gate_blocked=True)

    super_called = []
    DeployAgent.__bases__[0].run  # BaseAgent.run

    async def spy_super(*args: object, **kwargs: object) -> object:
        super_called.append(True)
        return state

    with patch.object(type(agent).__bases__[0], "run", spy_super):
        await agent.run(state)

    assert len(super_called) == 0, "super().run() must not be called when gate is blocked"


@pytest.mark.asyncio
async def test_agent_8_proceeds_when_security_gate_cleared() -> None:
    agent = _make_agent_8()
    state = _base_state(gate_blocked=False, human_confirmation="")
    # Patch execute to avoid real deployment
    with patch.object(agent, "_execute", AsyncMock(return_value=state)):
        result = await agent.run(state)
    assert not result.get("deploy_blocked")


@pytest.mark.asyncio
async def test_agent_8_interpret_always_contains_cold_start_warning() -> None:
    """Cold start warning must appear regardless of tier or deployment target."""
    agent = _make_agent_8()
    # Test free tier (no RENDER_DEPLOY_HOOK_URL)
    env = {
        k: v for k, v in os.environ.items() if k not in ("RENDER_DEPLOY_HOOK_URL", "RENDER_TIER")
    }
    with patch.dict(os.environ, env, clear=True):
        state = _base_state(human_confirmation="")
        result = await agent.run(state)
    action = result["interpret_log"][0]["action"].lower()
    assert "cold start" in action


@pytest.mark.asyncio
async def test_agent_8_interpret_cold_start_warning_free_tier() -> None:
    agent = _make_agent_8()
    with patch.dict(
        os.environ,
        {
            "RENDER_DEPLOY_HOOK_URL": "https://hook.render.com/test",
            "RENDER_TIER": "free",
        },
    ):
        state = _base_state(human_confirmation="")
        result = await agent.run(state)
    action = result["interpret_log"][0]["action"]
    assert "30-60s" in action or "free tier" in action.lower()


@pytest.mark.asyncio
async def test_agent_8_interpret_cold_start_warning_paid_tier() -> None:
    agent = _make_agent_8()
    with patch.dict(
        os.environ,
        {
            "RENDER_DEPLOY_HOOK_URL": "https://hook.render.com/test",
            "RENDER_TIER": "starter",
        },
    ):
        state = _base_state(human_confirmation="")
        result = await agent.run(state)
    action = result["interpret_log"][0]["action"]
    assert "always-on" in action.lower() or "none" in action.lower()


def test_agent_8_dockerfile_contains_uid_1000() -> None:
    agent = _make_agent_8()
    dockerfile = agent._generate_dockerfile({})
    assert "--uid 1000" in dockerfile
    assert "USER appuser" in dockerfile


def test_agent_8_dockerfile_is_multi_stage() -> None:
    agent = _make_agent_8()
    dockerfile = agent._generate_dockerfile({})
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile


def test_agent_8_dockerfile_contains_healthcheck() -> None:
    agent = _make_agent_8()
    dockerfile = agent._generate_dockerfile({})
    assert "HEALTHCHECK" in dockerfile
    assert "/health" in dockerfile


@pytest.mark.asyncio
async def test_agent_8_writes_post_mortem_on_deployment_failure() -> None:
    from memory.post_mortem_records import PostMortemStore

    agent = _make_agent_8()

    with (
        patch.dict(os.environ, {"RENDER_DEPLOY_HOOK_URL": "https://hook.render.com/test"}),
        patch("agents.agent_8_deploy.RenderTool") as mock_render_cls,
        patch.object(PostMortemStore, "save_post_mortem", AsyncMock()) as mock_save,
    ):
        mock_render = MagicMock()
        mock_render.trigger_deploy = AsyncMock(side_effect=Exception("webhook 503"))
        mock_render_cls.return_value = mock_render

        state = _base_state(human_confirmation="100% GO")
        with contextlib.suppress(Exception):
            await agent.run(state)

        mock_save.assert_called_once()
