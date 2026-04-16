from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from interpret.record import InterpretRecord
from memory.schemas import PipelineRunRecord
from orchestrator.constants import LOCAL_DB_URL

logger = structlog.get_logger()


class _Base(DeclarativeBase):
    pass


class _PipelineRunRow(_Base):
    __tablename__ = "pipeline_runs"

    run_id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    project_id = Column(String, nullable=False, index=True)
    user_prompt = Column(Text, nullable=False)
    stack_chosen = Column(String, nullable=True)
    deployment_success = Column(String, nullable=True)   # "true"/"false"/None
    cost_total_usd = Column(Float, nullable=False, default=0.0)
    hitl_rounds = Column(Integer, nullable=False, default=0)
    human_corrections = Column(JSONB, nullable=False, default=list)
    lessons_learned = Column(JSONB, nullable=False, default=list)
    tool_delegated_to = Column(String, nullable=True)
    workspace_path = Column(String, nullable=False)


class PipelineHistoryStore:
    """Layer 1 memory — every SDLC pipeline run stored in PostgreSQL.

    Emits InterpretRecord(layer="memory") before every read and write.
    Always asyncpg — no SQLite fallback.
    """

    def __init__(self) -> None:
        db_url = os.getenv("DATABASE_URL", LOCAL_DB_URL)
        if not db_url.startswith("postgresql"):
            raise ValueError(
                f"DATABASE_URL must be PostgreSQL. Got: {db_url[:40]!r}\n"
                "Run: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=forgesdlc "
                "--name forgesdlc-db postgres:16"
            )
        self._engine = create_async_engine(db_url, pool_size=5, max_overflow=10)
        self._session_factory: Any = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self) -> None:
        """Create tables if they don't exist. Call once on server startup."""
        async with self._engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)
        logger.info("pipeline_history_store.init_db_complete")

    async def save_run(self, record: PipelineRunRecord) -> None:
        """Upsert a pipeline run record. Emits InterpretRecord before write."""
        self._emit_record("write", "save_run", record.run_id)
        async with self._session_factory() as session:
            async with session.begin():
                # Delete existing row if present (upsert via delete+insert)
                existing = await session.get(_PipelineRunRow, record.run_id)
                if existing:
                    await session.delete(existing)
                row = _PipelineRunRow(
                    run_id=record.run_id,
                    timestamp=record.timestamp,
                    project_id=record.project_id,
                    user_prompt=record.user_prompt,
                    stack_chosen=record.stack_chosen,
                    deployment_success=(
                        str(record.deployment_success).lower()
                        if record.deployment_success is not None
                        else None
                    ),
                    cost_total_usd=record.cost_total_usd,
                    hitl_rounds=record.hitl_rounds,
                    human_corrections=record.human_corrections,
                    lessons_learned=record.lessons_learned,
                    tool_delegated_to=record.tool_delegated_to,
                    workspace_path=record.workspace_path,
                )
                session.add(row)
        logger.info("pipeline_history_store.save_run", run_id=record.run_id)

    async def get_similar_runs(
        self, project_id: str, limit: int = 5
    ) -> list[PipelineRunRecord]:
        """Fetch recent runs for a project ordered by timestamp desc.

        Emits InterpretRecord before read.
        """
        self._emit_record("read", "get_similar_runs", project_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(_PipelineRunRow)
                .where(_PipelineRunRow.project_id == project_id)
                .order_by(_PipelineRunRow.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()

        records = [
            PipelineRunRecord(
                run_id=row.run_id,
                timestamp=row.timestamp,
                project_id=row.project_id,
                user_prompt=row.user_prompt,
                stack_chosen=row.stack_chosen,
                deployment_success=(
                    row.deployment_success == "true"
                    if row.deployment_success is not None
                    else None
                ),
                cost_total_usd=row.cost_total_usd,
                hitl_rounds=row.hitl_rounds,
                human_corrections=row.human_corrections or [],
                lessons_learned=row.lessons_learned or [],
                tool_delegated_to=row.tool_delegated_to,
                workspace_path=row.workspace_path,
            )
            for row in rows
        ]
        logger.info(
            "pipeline_history_store.get_similar_runs",
            project_id=project_id,
            count=len(records),
        )
        return records

    def _emit_record(self, action_type: str, action: str, key: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="PipelineHistoryStore",
            action=f"{action_type}: {action} — key={key}",
            inputs={"key": key},
            expected_outputs={"rows": "list[PipelineRunRecord]"},
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