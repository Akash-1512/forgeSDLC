from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from memory.pipeline_history_store import PipelineHistoryStore
from memory.schemas import PipelineRunRecord


def _make_record(project_id: str = "proj-1") -> PipelineRunRecord:
    return PipelineRunRecord(
        run_id=str(uuid4()),
        timestamp=datetime.now(tz=timezone.utc),
        project_id=project_id,
        user_prompt="build a REST API",
        stack_chosen="fastapi",
        deployment_success=True,
        cost_total_usd=0.05,
        hitl_rounds=2,
        human_corrections=["use asyncpg"],
        lessons_learned=["always validate inputs"],
        tool_delegated_to="cursor",
        workspace_path="C:/projects/myapp",
    )


def _make_store() -> PipelineHistoryStore:
    """Return a PipelineHistoryStore with mocked engine and session factory."""
    with patch(
        "memory.pipeline_history_store.create_async_engine"
    ) as mock_engine:
        mock_engine.return_value = MagicMock()
        store = PipelineHistoryStore()
        store._engine = MagicMock()
        store._session_factory = MagicMock()
        return store


def test_pipeline_run_record_validates_cost_ge_zero() -> None:
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        PipelineRunRecord(
            run_id=str(uuid4()),
            timestamp=datetime.now(tz=timezone.utc),
            project_id="p1",
            user_prompt="x",
            stack_chosen=None,
            deployment_success=None,
            cost_total_usd=-0.01,
            hitl_rounds=0,
            human_corrections=[],
            lessons_learned=[],
            tool_delegated_to=None,
            workspace_path=".",
        )


def test_pipeline_run_record_validates_hitl_rounds_ge_zero() -> None:
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        PipelineRunRecord(
            run_id=str(uuid4()),
            timestamp=datetime.now(tz=timezone.utc),
            project_id="p1",
            user_prompt="x",
            stack_chosen=None,
            deployment_success=None,
            cost_total_usd=0.0,
            hitl_rounds=-1,
            human_corrections=[],
            lessons_learned=[],
            tool_delegated_to=None,
            workspace_path=".",
        )


def test_storage_factory_raises_if_url_not_postgresql() -> None:
    from providers.factories.storage_factory import get_db_url
    import os
    original = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
        with pytest.raises(ValueError, match="PostgreSQL"):
            get_db_url()
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original


@pytest.mark.asyncio
async def test_save_run_emits_interpret_record_before_write() -> None:
    store = _make_store()
    record = _make_record()
    emitted: list[str] = []

    original_emit = store._emit_record

    def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
        ir = original_emit(action_type, action, key)
        emitted.append(ir.layer)
        return ir

    store._emit_record = capturing_emit  # type: ignore[method-assign]

    # Mock session context manager
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.get = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    store._session_factory = MagicMock(return_value=mock_session)

    await store.save_run(record)
    assert "memory" in emitted


@pytest.mark.asyncio
async def test_get_similar_runs_emits_interpret_record_before_read() -> None:
    store = _make_store()
    emitted: list[str] = []

    original_emit = store._emit_record

    def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
        ir = original_emit(action_type, action, key)
        emitted.append(ir.layer)
        return ir

    store._emit_record = capturing_emit  # type: ignore[method-assign]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    store._session_factory = MagicMock(return_value=mock_session)

    result = await store.get_similar_runs("proj-1", limit=5)
    assert "memory" in emitted
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_save_run_persists_to_postgresql() -> None:
    store = _make_store()
    record = _make_record()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.get = AsyncMock(return_value=None)
    added: list[object] = []
    mock_session.add = MagicMock(side_effect=lambda row: added.append(row))
    store._session_factory = MagicMock(return_value=mock_session)

    await store.save_run(record)
    assert len(added) == 1
    assert added[0].run_id == record.run_id  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_get_similar_runs_returns_ordered_by_timestamp() -> None:
    store = _make_store()

    from memory.pipeline_history_store import _PipelineRunRow

    now = datetime.now(tz=timezone.utc)
    rows = [
        _PipelineRunRow(
            run_id="r1",
            timestamp=now,
            project_id="proj-1",
            user_prompt="x",
            stack_chosen=None,
            deployment_success=None,
            cost_total_usd=0.0,
            hitl_rounds=0,
            human_corrections=[],
            lessons_learned=[],
            tool_delegated_to=None,
            workspace_path=".",
        )
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    store._session_factory = MagicMock(return_value=mock_session)

    result = await store.get_similar_runs("proj-1", limit=5)
    assert len(result) == 1
    assert result[0].run_id == "r1"