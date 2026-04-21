from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_agent_5() -> object:
    from agents.agent_5_coord_review import CoordinatedReview
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
    mock_model_router = MagicMock(spec=ModelRouter)
    # LLM passes return empty findings by default
    mock_adapter = MagicMock()
    mock_adapter.ainvoke = AsyncMock(return_value=MagicMock(content="[]"))
    mock_model_router.route = AsyncMock(return_value=mock_adapter)

    return CoordinatedReview(
        name="agent_5_coord_review",
        context_window_manager=mock_cwm,
        model_router=mock_model_router,
        memory_archiver=mock_archiver,
        memory_context_builder=mock_memory_builder,
        context_file_manager=mock_cfm,
        workspace_bridge=mock_workspace,
        diff_engine=mock_diff,
    )


def _base_state(human_confirmation: str = "100% GO", files: list | None = None) -> dict:
    return {
        "user_prompt": "build something",
        "mcp_session_id": "proj-5",
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "interpret_log": [],
        "interpret_round": 0,
        "generated_files": files or [{"path": "main.py", "content": "def foo(): pass"}],
        "tool_delegated_to": "direct_llm",
        "review_delegation_count": 0,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
    }


def test_pass_4_maang_blocking_on_function_over_50_lines() -> None:
    from agents.agent_5_coord_review import CoordinatedReview
    agent = _make_agent_5()
    long_func = "def big_function():\n" + "    x = 1\n" * 55
    findings = agent._pass_maang_standards(long_func)  # type: ignore[union-attr]
    blocking = [f for f in findings if f["severity"] == "BLOCKING" and f["rule"] == "function_length"]
    assert len(blocking) >= 1


def test_pass_4_maang_blocking_on_bare_except() -> None:
    from agents.agent_5_coord_review import CoordinatedReview
    agent = _make_agent_5()
    code = "try:\n    pass\nexcept:\n    pass\n"
    findings = agent._pass_maang_standards(code)  # type: ignore[union-attr]
    blocking = [f for f in findings if f["severity"] == "BLOCKING" and f["rule"] == "bare_except"]
    assert len(blocking) >= 1


def test_pass_4_maang_advisory_on_missing_type_hints() -> None:
    from agents.agent_5_coord_review import CoordinatedReview
    agent = _make_agent_5()
    code = "def my_func(x, y):\n    return x + y\n"
    findings = agent._pass_maang_standards(code)  # type: ignore[union-attr]
    advisory = [f for f in findings if f["severity"] == "ADVISORY" and f["rule"] == "type_hints"]
    assert len(advisory) >= 1


def test_pass_4_is_deterministic_no_llm_call() -> None:
    """Pass 4 must never call ModelRouter — zero LLM."""
    from agents.agent_5_coord_review import CoordinatedReview
    from model_router.router import ModelRouter
    with patch.object(ModelRouter, "route") as mock_route:
        agent = _make_agent_5()
        code = "def foo():\n    pass\n"
        agent._pass_maang_standards(code)  # type: ignore[union-attr]
        mock_route.assert_not_called()


@pytest.mark.asyncio
async def test_blocking_finding_triggers_agent_4_re_delegation() -> None:
    agent = _make_agent_5()
    bad_code = "def foo():\n" + "    pass\n" * 55  # > 50 lines → BLOCKING
    state = _base_state(files=[{"path": "main.py", "content": bad_code}])
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("trigger_agent_4_retry") is True
    assert result.get("review_delegation_count", 0) == 1


@pytest.mark.asyncio
async def test_max_2_delegations_then_hitl_escalation() -> None:
    agent = _make_agent_5()
    bad_code = "def foo():\n" + "    pass\n" * 55
    state = _base_state(files=[{"path": "main.py", "content": bad_code}])
    state["review_delegation_count"] = 2  # already at max
    result = await agent.run(state)  # type: ignore[union-attr]
    assert result.get("hitl_required") is True
    assert result.get("trigger_agent_4_retry") is False


@pytest.mark.asyncio
async def test_review_findings_stored_in_state() -> None:
    agent = _make_agent_5()
    state = _base_state()
    result = await agent.run(state)  # type: ignore[union-attr]
    assert "review_findings" in result
    assert isinstance(result["review_findings"], list)


@pytest.mark.asyncio
async def test_correction_notes_sent_with_re_delegation_task() -> None:
    agent = _make_agent_5()
    bad_code = "def foo():\n" + "    pass\n" * 55
    state = _base_state(files=[{"path": "main.py", "content": bad_code}])
    result = await agent.run(state)  # type: ignore[union-attr]
    corrections = str(result.get("review_corrections", ""))
    assert "foo" in corrections or "function_length" in corrections or "50" in corrections