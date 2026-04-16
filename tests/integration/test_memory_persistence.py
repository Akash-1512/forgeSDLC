from __future__ import annotations

"""Integration tests — require real ChromaDB on disk (no mocks).
PostgreSQL tests require Docker: make db-start

Run with:
    python -m pytest tests/integration/ -v
"""

import shutil
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from memory.organisational_memory import OrgMemory
from memory.schemas import OrgMemoryEntry


def _make_entry(project_id: str, content: str) -> OrgMemoryEntry:
    return OrgMemoryEntry(
        entry_id=str(uuid4()),
        project_id=project_id,
        content=content,
        category="architecture",
        source_run_id="integration-test",
        timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def chroma_tmp() -> str:  # type: ignore[return]
    """Temporary ChromaDB directory — isolated per test, cleaned up after."""
    tmp = tempfile.mkdtemp(prefix="forgesdlc_test_chroma_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_data_survives_server_restart(chroma_tmp: str) -> None:
    """Core persistence guarantee: data written by instance A is readable
    by a completely new instance B — simulating a server restart."""
    project_id = f"test-proj-{uuid4().hex[:8]}"

    # Instance A — write
    org_a = OrgMemory(chroma_path=chroma_tmp)
    await org_a.upsert(_make_entry(project_id, "use postgres for all storage"))
    await org_a.upsert(_make_entry(project_id, "prefer asyncpg over psycopg2"))
    await org_a.upsert(_make_entry(project_id, "circuit breaker on all LLM calls"))
    del org_a  # simulate server shutdown

    # Instance B — fresh init, same path
    org_b = OrgMemory(chroma_path=chroma_tmp)
    results = await org_b.search("database driver", project_id=project_id)

    assert len(results) >= 1, (
        "Data did not survive restart — ChromaDB may be using in-memory client"
    )


@pytest.mark.asyncio
async def test_recall_context_returns_data_after_3_save_decisions(
    chroma_tmp: str,
) -> None:
    """After 3 upserts, search must return at least 1 relevant result."""
    project_id = f"test-proj-{uuid4().hex[:8]}"
    org = OrgMemory(chroma_path=chroma_tmp)

    await org.upsert(_make_entry(project_id, "DECISION: use FastAPI\nRATIONALE: async support"))
    await org.upsert(_make_entry(project_id, "DECISION: use PostgreSQL\nRATIONALE: ACID"))
    await org.upsert(_make_entry(project_id, "DECISION: use ChromaDB\nRATIONALE: vector search"))

    results = await org.search("which database should I use", project_id=project_id)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_save_decision_immediately_retrievable_via_recall_context(
    chroma_tmp: str,
) -> None:
    """Entry upserted in the same session is immediately searchable."""
    project_id = f"test-proj-{uuid4().hex[:8]}"
    org = OrgMemory(chroma_path=chroma_tmp)

    entry = _make_entry(project_id, "DECISION: use argon2 for hashing\nRATIONALE: security")
    await org.upsert(entry)

    results = await org.search("password hashing", project_id=project_id)
    assert any(r.entry_id == entry.entry_id for r in results)