from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.schemas import UserPreferenceProfile


def _make_profile(user_id: str = "user-1") -> UserPreferenceProfile:
    return UserPreferenceProfile(
        user_id=user_id,
        preferred_code_gen_tool="cursor",
        preferred_stack=["fastapi", "postgresql"],
        subscription_tier="pro",
        byok_providers=["openai"],
        recurring_security_findings=["sql_injection"],
        recurring_anti_patterns=["no_error_handling"],
        last_updated=datetime.now(tz=UTC),
    )


def _make_store() -> object:
    with patch("memory.user_preference_profile.create_async_engine"):
        from memory.user_preference_profile import UserPreferenceStore

        store = UserPreferenceStore()
        store._engine = MagicMock()
        store._session_factory = MagicMock()
        return store


@pytest.mark.asyncio
async def test_save_profile_persists_to_postgresql() -> None:
    store = _make_store()
    profile = _make_profile()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.get = AsyncMock(return_value=None)
    added: list[object] = []
    mock_session.add = MagicMock(side_effect=lambda row: added.append(row))
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    await store.save_profile(profile)  # type: ignore[union-attr]
    assert len(added) == 1
    assert added[0].user_id == profile.user_id  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_load_profile_returns_none_for_unknown_user() -> None:
    store = _make_store()

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    result = await store.load_profile("unknown-user")  # type: ignore[union-attr]
    assert result is None


@pytest.mark.asyncio
async def test_save_profile_emits_interpret_record_before_write() -> None:
    store = _make_store()
    profile = _make_profile()
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

    await store.save_profile(profile)  # type: ignore[union-attr]
    assert "memory" in emitted


@pytest.mark.asyncio
async def test_load_profile_emits_interpret_record_before_read() -> None:
    store = _make_store()
    emitted: list[str] = []

    original_emit = store._emit  # type: ignore[union-attr]

    def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
        ir = original_emit(action_type, action, key)
        emitted.append(ir.layer)
        return ir

    store._emit = capturing_emit  # type: ignore[union-attr,method-assign]

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    await store.load_profile("user-1")  # type: ignore[union-attr]
    assert "memory" in emitted


@pytest.mark.asyncio
async def test_update_tool_preference_changes_preferred_code_gen_tool() -> None:
    store = _make_store()

    # load_profile returns None → creates new profile with new tool
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin = MagicMock(return_value=mock_session)
    mock_session.get = AsyncMock(return_value=None)
    added: list[object] = []
    mock_session.add = MagicMock(side_effect=lambda row: added.append(row))
    mock_session.execute = AsyncMock(return_value=mock_result)
    store._session_factory = MagicMock(return_value=mock_session)  # type: ignore[union-attr]

    await store.update_tool_preference("user-1", "claude_code")  # type: ignore[union-attr]
    assert len(added) == 1
    assert added[0].preferred_code_gen_tool == "claude_code"  # type: ignore[attr-defined]
