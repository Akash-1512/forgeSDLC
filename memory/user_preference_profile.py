from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import Column, DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from interpret.record import InterpretRecord
from memory.schemas import UserPreferenceProfile
from providers.factories.storage_factory import get_db_url

logger = structlog.get_logger()


class _Base(DeclarativeBase):
    pass


class _UserPreferenceRow(_Base):
    __tablename__ = "user_preferences"

    user_id = Column(String, primary_key=True)
    preferred_code_gen_tool = Column(String, nullable=False)
    preferred_stack = Column(JSONB, nullable=False, default=list)
    subscription_tier = Column(String, nullable=False, default="free")
    byok_providers = Column(JSONB, nullable=False, default=list)
    recurring_security_findings = Column(JSONB, nullable=False, default=list)
    recurring_anti_patterns = Column(JSONB, nullable=False, default=list)
    last_updated = Column(DateTime(timezone=True), nullable=False)


class UserPreferenceStore:
    """Layer 4 memory — user preferences in PostgreSQL.

    Shares the same PostgreSQL engine as Layer 1 via StorageFactory.
    Emits InterpretRecord(layer="memory") before every read and write.
    """

    def __init__(self) -> None:
        self._engine = create_async_engine(get_db_url(), pool_size=5, max_overflow=10)
        self._session_factory: Any = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self) -> None:
        """Create user_preferences table if it doesn't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)
        logger.info("user_preference_store.init_db_complete")

    async def save_profile(self, profile: UserPreferenceProfile) -> None:
        """Upsert a user preference profile. Emits InterpretRecord before write."""
        self._emit("write", "save_profile", profile.user_id)
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.get(_UserPreferenceRow, profile.user_id)
                if existing:
                    await session.delete(existing)
                row = _UserPreferenceRow(
                    user_id=profile.user_id,
                    preferred_code_gen_tool=profile.preferred_code_gen_tool,
                    preferred_stack=profile.preferred_stack,
                    subscription_tier=profile.subscription_tier,
                    byok_providers=profile.byok_providers,
                    recurring_security_findings=profile.recurring_security_findings,
                    recurring_anti_patterns=profile.recurring_anti_patterns,
                    last_updated=profile.last_updated,
                )
                session.add(row)
        logger.info("user_preference_store.save_profile", user_id=profile.user_id)

    async def load_profile(self, user_id: str) -> UserPreferenceProfile | None:
        """Fetch user profile by user_id. Emits InterpretRecord before read."""
        self._emit("read", "load_profile", user_id)
        async with self._session_factory() as session:
            result = await session.execute(
                select(_UserPreferenceRow).where(
                    _UserPreferenceRow.user_id == user_id
                )
            )
            row = result.scalars().first()
        if row is None:
            logger.info("user_preference_store.not_found", user_id=user_id)
            return None
        return UserPreferenceProfile(
            user_id=row.user_id,
            preferred_code_gen_tool=row.preferred_code_gen_tool,
            preferred_stack=row.preferred_stack or [],
            subscription_tier=row.subscription_tier,
            byok_providers=row.byok_providers or [],
            recurring_security_findings=row.recurring_security_findings or [],
            recurring_anti_patterns=row.recurring_anti_patterns or [],
            last_updated=row.last_updated,
        )

    async def update_tool_preference(self, user_id: str, tool: str) -> None:
        """Record tool preference signal after every HITL correction."""
        profile = await self.load_profile(user_id) or UserPreferenceProfile(
            user_id=user_id,
            preferred_code_gen_tool=tool,
            preferred_stack=[],
            subscription_tier="free",
            byok_providers=[],
            recurring_security_findings=[],
            recurring_anti_patterns=[],
            last_updated=datetime.now(tz=timezone.utc),
        )
        profile.preferred_code_gen_tool = tool
        profile.last_updated = datetime.now(tz=timezone.utc)
        await self.save_profile(profile)
        logger.info(
            "user_preference_store.tool_preference_updated",
            user_id=user_id,
            tool=tool,
        )

    def _emit(self, action_type: str, action: str, key: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="UserPreferenceStore",
            action=f"{action_type}: {action} — user={key}",
            inputs={"user_id": key},
            expected_outputs={"profile": "UserPreferenceProfile | None"},
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