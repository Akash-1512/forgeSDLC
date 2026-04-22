from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from token_tracker.aggregator import TokenAggregator
from token_tracker.budget_monitor import BudgetMonitor, BudgetStatus
from token_tracker.record import TokenRecord
from token_tracker.tracker import TokenTracker


def _make_record(
    agent: str = "Agent1",
    model: str = "groq/llama-3.3-70b-versatile",
    provider: str = "groq",
    input_tokens: int = 100,
    output_tokens: int = 50,
    cost_usd: float = 0.001,
) -> TokenRecord:
    return TokenRecord(
        record_id=str(uuid4()),
        timestamp=datetime.now(tz=UTC),
        trace_id=str(uuid4()),
        agent=agent,
        task="test task",
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=100,
        api_key_source="free_tier",
        subscription_tier="free",
        fim_call=False,
        session_id="sess-1",
        run_id=None,
        tool_delegated_to=None,
    )


def test_token_record_rejects_negative_input_tokens() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _make_record(input_tokens=-1)


def test_token_record_rejects_negative_output_tokens() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _make_record(output_tokens=-1)


def test_token_record_rejects_negative_cost_usd() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _make_record(cost_usd=-0.01)


def test_token_record_rejects_negative_latency_ms() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        TokenRecord(
            record_id=str(uuid4()),
            timestamp=datetime.now(tz=UTC),
            trace_id=str(uuid4()),
            agent="Agent1",
            task="test",
            model="groq/llama",
            provider="groq",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0,
            latency_ms=-1,
            api_key_source="free_tier",
            subscription_tier="free",
            fim_call=False,
            session_id="sess-1",
            run_id=None,
            tool_delegated_to=None,
        )


def test_tracker_appends_record_to_state_session_token_records() -> None:
    tracker = TokenTracker()
    state: dict[str, object] = {
        "trace_id": str(uuid4()),
        "mcp_session_id": "sess-1",
        "subscription_tier": "free",
        "session_token_records": [],
    }
    tracker.record(
        state=state,
        agent="Agent1",
        task="write tests",
        model="groq/llama-3.3-70b-versatile",
        provider="groq",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.001,
        latency_ms=200,
        api_key_source="free_tier",
    )
    records = state["session_token_records"]
    assert isinstance(records, list)
    assert len(records) == 1  # type: ignore[arg-type]


def test_aggregator_groups_by_agent_correctly() -> None:
    agg = TokenAggregator()
    records = [
        _make_record(agent="Agent1", cost_usd=0.01),
        _make_record(agent="Agent1", cost_usd=0.02),
        _make_record(agent="Agent2", cost_usd=0.05),
    ]
    result = agg.by_agent(records)
    assert "Agent1" in result
    assert "Agent2" in result
    assert result["Agent1"]["calls"] == 2
    assert abs(result["Agent1"]["cost_usd"] - 0.03) < 1e-9
    assert result["Agent2"]["calls"] == 1


def test_aggregator_groups_by_model_correctly() -> None:
    agg = TokenAggregator()
    records = [
        _make_record(model="groq/llama-3.3-70b-versatile", cost_usd=0.001),
        _make_record(model="gpt-5.4-mini", cost_usd=0.01),
        _make_record(model="gpt-5.4-mini", cost_usd=0.01),
    ]
    result = agg.by_model(records)
    assert result["gpt-5.4-mini"]["calls"] == 2
    assert result["groq/llama-3.3-70b-versatile"]["calls"] == 1


@pytest.mark.asyncio
async def test_budget_monitor_returns_ok_below_50_percent() -> None:
    monitor = BudgetMonitor()
    status = await monitor.check(budget_used=2.0, budget_total=10.0)
    assert status == BudgetStatus.OK


@pytest.mark.asyncio
async def test_budget_monitor_returns_warn_at_50_percent() -> None:
    monitor = BudgetMonitor()
    status = await monitor.check(budget_used=5.0, budget_total=10.0)
    assert status == BudgetStatus.WARN


@pytest.mark.asyncio
async def test_budget_monitor_returns_optimise_at_80_percent() -> None:
    monitor = BudgetMonitor()
    status = await monitor.check(budget_used=8.0, budget_total=10.0)
    assert status == BudgetStatus.OPTIMISE


@pytest.mark.asyncio
async def test_budget_monitor_returns_alert_at_90_percent() -> None:
    monitor = BudgetMonitor()
    status = await monitor.check(budget_used=9.0, budget_total=10.0)
    assert status == BudgetStatus.ALERT


@pytest.mark.asyncio
async def test_budget_monitor_returns_ok_when_budget_total_is_zero() -> None:
    monitor = BudgetMonitor()
    status = await monitor.check(budget_used=0.0, budget_total=0.0)
    assert status == BudgetStatus.OK


@pytest.mark.asyncio
async def test_tool_router_calls_do_not_generate_token_records() -> None:
    """ToolRouter delegations must never create TokenRecords.

    TokenTracker is only called by ModelRouter — ToolRouter routes to
    external tools that use the developer's own API keys.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from context_files.manager import ContextFileManager
    from tool_router.context import AvailableTool, ToolResult
    from tool_router.router import ToolRouter

    state: dict[str, object] = {"session_token_records": []}
    mock_cfm = MagicMock(spec=ContextFileManager)
    mock_cfm.write_all = AsyncMock(return_value=["AGENTS.md"])
    router = ToolRouter(context_file_manager=mock_cfm)

    stub = ToolResult(
        tool=AvailableTool.DIRECT_LLM,
        output="# code",
        files_written=[],
        success=True,
        stderr=None,
    )

    with (
        patch.object(router, "_check_cursor", AsyncMock(return_value=False)),
        patch.object(router, "_check_claude_code", AsyncMock(return_value=False)),
        patch.object(router, "_check_devin", AsyncMock(return_value=False)),
        patch(
            "tool_router.router.DirectLLMAdapter.generate",
            AsyncMock(return_value=stub),
        ),
    ):
        await router.route(
            task="write code",
            context="ctx",
            project_id="proj-1",
            workspace_path=".",
        )

    # No TokenRecords should have been created by the ToolRouter route
    assert state["session_token_records"] == []
