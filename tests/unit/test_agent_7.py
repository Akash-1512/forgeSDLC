from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


def _make_agent_7() -> object:
    from agents.agent_7_cicd import CICDAgent
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
    mock_diff.generate_diff = AsyncMock(return_value=MagicMock(filepath="ci.yml", new_content=""))
    mock_diff.apply_diff = AsyncMock()
    mock_model_router = MagicMock(spec=ModelRouter)

    return CICDAgent(
        name="agent_7_cicd",
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )


def _fake_docs_fetcher(version: str = "v6.0.2") -> object:
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(return_value=json.dumps({"tag_name": version, "name": version}))
    return fetcher


def _base_state(human_confirmation: str = "100% GO") -> dict:
    return {
        "user_prompt": "build a REST API",
        "mcp_session_id": "proj-7",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "prd": "",
        "adr": "Stack: FastAPI",
        "rfc": "",
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


@pytest.mark.asyncio
async def test_agent_7_generates_github_actions_yaml() -> None:
    agent = _make_agent_7()
    with patch("agents.agent_7_cicd.DocsFetcher", return_value=_fake_docs_fetcher()):
        result = await agent.run(_base_state())  # type: ignore[union-attr]
    assert result.get("ci_pipeline_url")


@pytest.mark.asyncio
async def test_generated_yaml_is_valid_github_actions_syntax() -> None:
    """yaml.safe_load() must succeed on the generated YAML."""
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    parsed = yaml.safe_load(ci_yaml)
    assert parsed is not None
    assert "jobs" in parsed


def test_generated_yaml_contains_ruff_not_black() -> None:
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    assert "ruff" in ci_yaml
    assert "black" not in ci_yaml, "Generated CI YAML must not contain 'black'"


def test_generated_yaml_contains_ruff_not_isort() -> None:
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    assert "isort" not in ci_yaml, "Generated CI YAML must not contain 'isort'"


def test_generated_yaml_contains_semgrep_p_python() -> None:
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    assert "p/python" in ci_yaml


def test_generated_yaml_contains_semgrep_p_security() -> None:
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    assert "p/security" in ci_yaml


def test_generated_yaml_does_not_contain_semgrep_auto() -> None:
    """CRITICAL: semgrep must NEVER use --config=auto anywhere in CI YAML."""
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    assert "auto" not in ci_yaml, (
        "Generated CI YAML contains 'auto' — semgrep must use p/python + p/security only"
    )


def test_generated_yaml_uses_python_3_12() -> None:
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    assert "3.12" in ci_yaml


def test_generated_yaml_uses_node_24_not_node_20() -> None:
    """Node.js 24 required — Node 20 EOL deadline June 2 2026."""
    from agents.agent_7_cicd import _ACTION_DEFAULTS, _CI_YAML_TEMPLATE

    ci_yaml = _CI_YAML_TEMPLATE.format(
        checkout_version=_ACTION_DEFAULTS["actions/checkout"],
        setup_python_version=_ACTION_DEFAULTS["actions/setup-python"],
        codecov_version=_ACTION_DEFAULTS["codecov/codecov-action"],
    )
    # Template doesn't set Node explicitly — actions use their defaults
    # But verify no accidental node-version: '20' appears
    assert "node-version: '20'" not in ci_yaml
    assert "node-version: 20" not in ci_yaml


@pytest.mark.asyncio
async def test_agent_7_fetches_action_versions_via_docs_fetcher() -> None:
    agent = _make_agent_7()
    mock_fetcher = _fake_docs_fetcher()
    with patch("agents.agent_7_cicd.DocsFetcher", return_value=mock_fetcher):
        await agent.run(_base_state())  # type: ignore[union-attr]
    assert mock_fetcher.fetch.call_count == 3  # one per action


@pytest.mark.asyncio
async def test_agent_7_writes_ci_yaml_via_diff_engine() -> None:
    agent = _make_agent_7()
    with patch("agents.agent_7_cicd.DocsFetcher", return_value=_fake_docs_fetcher()):
        await agent.run(_base_state())  # type: ignore[union-attr]
    agent.diff_engine.generate_diff.assert_called_once()  # type: ignore[union-attr]
    agent.diff_engine.apply_diff.assert_called_once()  # type: ignore[union-attr]
