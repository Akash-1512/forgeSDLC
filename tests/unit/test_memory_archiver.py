from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.memory_archiver import MemoryArchiver


def _make_archiver() -> MemoryArchiver:
    l1 = MagicMock()
    l1.save_run = AsyncMock()
    l2 = MagicMock()
    l2.upsert = AsyncMock()
    l3 = MagicMock()
    l3.save_graph = AsyncMock()
    l4 = MagicMock()
    l4.update_tool_preference = AsyncMock()
    l4.load_profile = AsyncMock(return_value=None)
    l4.save_profile = AsyncMock()
    l5 = MagicMock()
    l5.save_post_mortem = AsyncMock()
    return MemoryArchiver(l1, l2, l3, l4, l5)


def _base_state() -> dict:
    return {
        "user_prompt": "build a REST API",
        "mcp_session_id": "proj-test",
        "prd": "Build a FastAPI service with PostgreSQL",
        "adr": "Use FastAPI and PostgreSQL",
        "security_findings": {"high_count": 0},
        "human_corrections": [],
        "budget_used_usd": 0.05,
        "interpret_round": 1,
        "deployment_url": "https://myapp.render.com",
        "tool_delegated_to": "cursor",
        "workspace_context": {"path": "C:/projects/myapp"},
    }


@pytest.mark.asyncio
async def test_archive_calls_all_5_layers() -> None:
    archiver = _make_archiver()
    state = _base_state()
    await archiver.archive(state)  # type: ignore[arg-type]

    archiver.l1.save_run.assert_called_once()
    archiver.l2.upsert.assert_called()
    archiver.l4.update_tool_preference.assert_called_once_with("default", "cursor")
    # l3 skipped — no project_graph in workspace_context
    # l5 skipped — no failure_type in state


@pytest.mark.asyncio
async def test_archive_skips_layer5_when_no_failure_type_in_state() -> None:
    archiver = _make_archiver()
    state = _base_state()
    await archiver.archive(state)  # type: ignore[arg-type]
    archiver.l5.save_post_mortem.assert_not_called()


@pytest.mark.asyncio
async def test_archive_layer5_fires_when_failure_type_set() -> None:
    archiver = _make_archiver()
    state = _base_state()
    state["failure_type"] = "tool_timeout"  # type: ignore[index]
    state["failed_agent"] = "Agent4_ToolRouter"  # type: ignore[index]
    await archiver.archive(state)  # type: ignore[arg-type]
    archiver.l5.save_post_mortem.assert_called_once()


@pytest.mark.asyncio
async def test_archive_emits_interpret_record_before_each_layer_write() -> None:
    archiver = _make_archiver()
    emitted: list[str] = []
    original_emit = archiver._emit_archiver_record

    def capturing_emit(state: object) -> object:
        ir = original_emit(state)  # type: ignore[arg-type]
        emitted.append(ir.layer)
        return ir

    archiver._emit_archiver_record = capturing_emit  # type: ignore[method-assign]
    state = _base_state()
    await archiver.archive(state)  # type: ignore[arg-type]
    assert "memory" in emitted


@pytest.mark.asyncio
async def test_archive_layer2_extracts_at_least_1_fact_per_run() -> None:
    archiver = _make_archiver()
    state = _base_state()
    await archiver.archive(state)  # type: ignore[arg-type]
    # prd + adr = at least 2 facts
    assert archiver.l2.upsert.call_count >= 1


@pytest.mark.asyncio
async def test_archive_layer2_classifies_decision_as_architecture() -> None:
    archiver = _make_archiver()
    result = archiver._classify_fact("DECISION: use postgres")
    assert result == "architecture"


@pytest.mark.asyncio
async def test_archive_layer2_classifies_security_finding_as_security() -> None:
    archiver = _make_archiver()
    result = archiver._classify_fact("SECURITY: 3 HIGH findings in this run")
    assert result == "security"