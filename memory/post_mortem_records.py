from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from interpret.record import InterpretRecord
from memory.schemas import PostMortem
from providers.factories.storage_factory import get_db_url

logger = structlog.get_logger()


class _Base(DeclarativeBase):
    pass


class _PostMortemRow(_Base):
    __tablename__ = "post_mortems"

    post_mortem_id = Column(String, primary_key=True)
    run_id = Column(String, nullable=False, index=True)
    failure_type = Column(String, nullable=False)
    agent_that_failed = Column(String, nullable=False)
    root_cause = Column(String, nullable=False)
    resolution = Column(String, nullable=False)
    prevention_rule = Column(String, nullable=False)
    stack_context = Column(String, nullable=False)
    tool_involved = Column(String, nullable=True)   # v4: ToolRouter target that failed
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)


class PostMortemStore:
    """Layer 5 memory — failure records in PostgreSQL post_mortems table.

    tool_involved (v4): tracks which ToolRouter target failed
    (e.g. "cursor", "claude_code_cli", "devin"). None for non-ToolRouter failures.
    Emits InterpretRecord(layer="memory") before every read and write.
    """

    def __init__(self) -> None:
        self._engine = create_async_engine(get_db_url(), pool_size=5, max_overflow=10)
        self._session_factory: Any = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self) -> None:
        """Create post_mortems table if it doesn't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)
        logger.info("post_mortem_store.init_db_complete")

    async def save_post_mortem(self, pm: PostMortem) -> None:
        """Insert a post-mortem record. Emits InterpretRecord before write."""
        self._emit("write", "save_post_mortem", pm.post_mortem_id)
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.get(_PostMortemRow, pm.post_mortem_id)
                if existing:
                    await session.delete(existing)
                row = _PostMortemRow(
                    post_mortem_id=pm.post_mortem_id,
                    run_id=pm.run_id,
                    failure_type=pm.failure_type,
                    agent_that_failed=pm.agent_that_failed,
                    root_cause=pm.root_cause,
                    resolution=pm.resolution,
                    prevention_rule=pm.prevention_rule,
                    stack_context=pm.stack_context,
                    tool_involved=pm.tool_involved,
                    timestamp=pm.timestamp,
                )
                session.add(row)
        logger.info(
            "post_mortem_store.saved",
            post_mortem_id=pm.post_mortem_id,
            failure_type=pm.failure_type,
            tool_involved=pm.tool_involved,
        )

    async def get_recent_failures(
        self, project_id: str, limit: int = 5
    ) -> list[PostMortem]:
        """Fetch recent post-mortems for a project ordered by timestamp desc.

        Emits InterpretRecord before read.
        Note: post_mortems table uses run_id as the project link —
        project_id filtering added in Session 09 when agents populate run_id
        with structured project context. For now returns most recent N records.
        """
        self._emit("read", "get_recent_failures", project_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(_PostMortemRow)
                .order_by(_PostMortemRow.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()

        records = [
            PostMortem(
                post_mortem_id=row.post_mortem_id,
                run_id=row.run_id,
                failure_type=row.failure_type,  # type: ignore[arg-type]
                agent_that_failed=row.agent_that_failed,
                root_cause=row.root_cause,
                resolution=row.resolution,
                prevention_rule=row.prevention_rule,
                stack_context=row.stack_context,
                tool_involved=row.tool_involved,
                timestamp=row.timestamp,
            )
            for row in rows
        ]
        logger.info(
            "post_mortem_store.get_recent_failures",
            project_id=project_id,
            count=len(records),
        )
        return records

    def _emit(self, action_type: str, action: str, key: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="PostMortemStore",
            action=f"{action_type}: {action} — key={key}",
            inputs={"key": key},
            expected_outputs={"post_mortems": "list[PostMortem]"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=["postgresql"],
            model_selected=None,
            tool_delegated_to=None,
            reversible=(action_type == "read"),
            workspace_files_affected=[],
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "interpret_record.memory",
            action=record.action,
            layer=record.layer,
        )
        return record