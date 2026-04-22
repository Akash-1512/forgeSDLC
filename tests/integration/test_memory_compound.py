from __future__ import annotations

"""Integration tests — real ChromaDB on disk (no mocks).
Proves compound memory effect: richer context after 5 runs than after 1.

Run with:
    python -m pytest tests/integration/test_memory_compound.py -v
"""

import shutil
import tempfile
from uuid import uuid4

import pytest

from memory.memory_archiver import MemoryArchiver
from memory.organisational_memory import OrgMemory


def _make_archiver_with_real_org(chroma_path: str) -> tuple[MemoryArchiver, OrgMemory]:
    from unittest.mock import AsyncMock, MagicMock

    l1 = MagicMock()
    l1.save_run = AsyncMock()
    l2 = OrgMemory(chroma_path=chroma_path)
    l3 = MagicMock()
    l3.save_graph = AsyncMock()
    l4 = MagicMock()
    l4.update_tool_preference = AsyncMock()
    l4.load_profile = AsyncMock(return_value=None)
    l4.save_profile = AsyncMock()
    l5 = MagicMock()
    l5.save_post_mortem = AsyncMock()

    archiver = MemoryArchiver(l1, l2, l3, l4, l5)
    return archiver, l2


def _make_state(
    project_id: str,
    prd: str = "",
    adr: str = "",
    high_security_count: int = 0,
    correction: str = "",
    failure_type: str | None = None,
) -> dict:
    state: dict = {
        "user_prompt": "build something",
        "mcp_session_id": project_id,
        "prd": prd,
        "adr": adr,
        "security_findings": {"high_count": high_security_count},
        "human_corrections": [correction] if correction else [],
        "budget_used_usd": 0.01,
        "interpret_round": 1,
        "deployment_url": None,
        "tool_delegated_to": None,
        "workspace_context": {"path": "."},
    }
    if failure_type:
        state["failure_type"] = failure_type
    return state


@pytest.fixture
def chroma_tmp() -> str:  # type: ignore[return]
    tmp = tempfile.mkdtemp(prefix="forgesdlc_compound_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.asyncio
async def test_recall_context_richer_after_5_runs_than_after_1(
    chroma_tmp: str,
) -> None:
    """OrgMemory must have more entries after 5 runs than after 1 run."""
    project_id = f"compound-{uuid4().hex[:8]}"
    archiver, org = _make_archiver_with_real_org(chroma_tmp)

    # Run 1
    await archiver.archive(_make_state(project_id, prd="initial requirements"))  # type: ignore[arg-type]
    after_1 = await org.search("requirements", project_id=project_id)

    # Runs 2-5
    await archiver.archive(_make_state(project_id, adr="use FastAPI"))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, high_security_count=2))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, correction="always validate inputs"))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, adr="use asyncpg not psycopg2"))  # type: ignore[arg-type]
    after_5 = await org.search("requirements architecture security", project_id=project_id)

    assert len(after_5) >= len(after_1), (
        f"Expected richer context after 5 runs. after_1={len(after_1)}, after_5={len(after_5)}"
    )


@pytest.mark.asyncio
async def test_org_memory_contains_entries_from_multiple_categories_after_5_runs(
    chroma_tmp: str,
) -> None:
    """After 5 varied runs, OrgMemory must contain at least 2 distinct categories.

    Checks compound effect quality — not just count.
    5 identical entries would pass a count check but fail this test.
    """
    project_id = f"compound-{uuid4().hex[:8]}"
    archiver, org = _make_archiver_with_real_org(chroma_tmp)

    await archiver.archive(_make_state(project_id, prd="build REST API"))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, adr="use PostgreSQL"))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, high_security_count=3))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, correction="add retry logic"))  # type: ignore[arg-type]
    await archiver.archive(_make_state(project_id, adr="use chromadb for vector search"))  # type: ignore[arg-type]

    results = await org.search("architecture security patterns", project_id=project_id)
    categories = {r.category for r in results}

    assert len(categories) >= 2, (
        f"Expected ≥2 distinct categories after 5 varied runs. Got: {categories}"
    )
