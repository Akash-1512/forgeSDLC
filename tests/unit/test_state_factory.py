"""Tests for mcp_server/state_factory.py (M21)."""

from __future__ import annotations

from mcp_server.state_factory import build_initial_state


def test_build_initial_state_returns_dict() -> None:
    state = build_initial_state(user_prompt="build an API", project_id="proj-1")
    assert isinstance(state, dict)


def test_build_initial_state_required_keys_present() -> None:
    state = build_initial_state(user_prompt="test", project_id="p1")
    required = [
        "user_prompt",
        "mcp_session_id",
        "human_confirmation",
        "trace_id",
        "service_graph",
        "prd",
        "adr",
        "rfc",
        "security_findings",
        "security_gate",
        "budget_used_usd",
        "budget_remaining_usd",
        "subscription_tier",
        "session_token_records",
        "deploy_blocked",
        "slo_definitions",
    ]
    for key in required:
        assert key in state, f"Missing key: {key}"


def test_build_initial_state_user_prompt_set() -> None:
    state = build_initial_state(user_prompt="build a todo app", project_id="p1")
    assert state["user_prompt"] == "build a todo app"


def test_build_initial_state_project_id_as_session_id() -> None:
    state = build_initial_state(user_prompt="x", project_id="my-project")
    assert state["mcp_session_id"] == "my-project"


def test_build_initial_state_trace_id_is_uuid() -> None:
    import uuid

    state = build_initial_state(user_prompt="x", project_id="p1")
    trace = state["trace_id"]
    assert isinstance(trace, str)
    uuid.UUID(trace)  # raises ValueError if not valid UUID


def test_build_initial_state_fresh_trace_each_call() -> None:
    s1 = build_initial_state(user_prompt="x", project_id="p1")
    s2 = build_initial_state(user_prompt="x", project_id="p1")
    assert s1["trace_id"] != s2["trace_id"]


def test_build_initial_state_extra_overrides_applied() -> None:
    state = build_initial_state(
        user_prompt="x",
        project_id="p1",
        extra={"subscription_tier": "enterprise", "custom_key": "custom_value"},
    )
    assert state["subscription_tier"] == "enterprise"
    assert state["custom_key"] == "custom_value"


def test_build_initial_state_budget_zero_for_free() -> None:
    state = build_initial_state(user_prompt="x", project_id="p1")
    assert state["budget_used_usd"] == 0.0
    assert state["budget_remaining_usd"] == 0.0


def test_build_initial_state_default_human_confirmation_empty() -> None:
    state = build_initial_state(user_prompt="x", project_id="p1")
    assert state["human_confirmation"] == ""


def test_build_initial_state_with_human_confirmation() -> None:
    state = build_initial_state(user_prompt="x", project_id="p1", human_confirmation="100% GO")
    assert state["human_confirmation"] == "100% GO"
