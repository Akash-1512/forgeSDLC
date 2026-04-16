from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from memory.schemas import PostMortem


def _make_post_mortem(tool_involved: str | None = "cursor") -> PostMortem:
    return PostMortem(
        post_mortem_id=str(uuid4()),
        run_id=str(uuid4()),
        failure_type="tool_timeout",
        agent_that_failed="Agent4_ToolRouter",
        root_cause="Cursor API timed out after 30s",
        resolution="Fell back to direct LLM",
        prevention_rule="Set CURSOR_API_TIMEOUT=60 in env",
        stack_context="fastapi + postgresql",
        tool_involved=tool_involved,
        timestamp=datetime.now(tz=timezone.utc),
    )


def _make_store() -> object:
    with patch("memory.post_mortem_records.create_async_engine"):
        from memory.post_mortem_records import PostMortemStore
        store = PostMortemStore()
        store._engine = MagicMock()
        store._session_factory = MagicMock()
        return store


def test_post_mortem_includes_tool_involved_field() -> None:
    """v4 field — tool_involved must exist and accept None."""
    pm = _make_post_mortem(tool_involved="claude_code_cli")
    assert pm.tool_involved == "claude_code_cli"

    pm_none = _make_post_mortem(tool_involved=None)
    assert pm_none.tool_involved is None


@pytest.mark.asyncio
async def test_save_post_mortem_persists_to_postgresql() -> None:
    store = _make_store()
    pm = _make_post_mortem()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.get = AsyncMock(return_value=None)
    added: list[object] = []
    mock_session.add = MagicMock(side_effect=lambda row: added.append(row))
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    await store.save_post_mortem(pm)  # type: ignore[union-attr]
    assert len(added) == 1
    assert added[0].post_mortem_id == pm.post_mortem_id  # type: ignore[attr-defined]
    assert added[0].tool_involved == pm.tool_involved  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_save_post_mortem_emits_interpret_record_before_write() -> None:
    store = _make_store()
    pm = _make_post_mortem()
    emitted: list[str] = []

    original_emit = store._emit  # type: ignore[union-attr]

    def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
        ir = original_emit(action_type, action, key)
        emitted.append(ir.layer)
        return ir

    store._emit = capturing_emit  # type: ignore[union-attr,method-assign]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    await store.save_post_mortem(pm)  # type: ignore[union-attr]
    assert "memory" in emitted


@pytest.mark.asyncio
async def test_get_recent_failures_returns_ordered_by_timestamp_desc() -> None:
    store = _make_store()

    from memory.post_mortem_records import _PostMortemRow
    now = datetime.now(tz=timezone.utc)
    rows = [
        _PostMortemRow(
            post_mortem_id="pm-1",
            run_id="run-1",
            failure_type="tool_timeout",
            agent_that_failed="Agent4",
            root_cause="timeout",
            resolution="fallback",
            prevention_rule="increase timeout",
            stack_context="fastapi",
            tool_involved="cursor",
            timestamp=now,
        )
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    result = await store.get_recent_failures("proj-1", limit=5)  # type: ignore[union-attr]
    assert len(result) == 1
    assert result[0].post_mortem_id == "pm-1"
    assert result[0].tool_involved == "cursor"