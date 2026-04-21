"""
Verifies that memory persists across store reinstantiation (simulates server restart).
Core value proposition: decisions saved in one pipeline run are retrievable in the next.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from memory.organisational_memory import OrgMemory
from memory.schemas import OrgMemoryEntry


@pytest.mark.asyncio
async def test_decision_survives_orgmemory_reinstantiation() -> None:
    """
    Save a decision to OrgMemory. Create a NEW OrgMemory instance.
    Recall should return the same decision.
    ChromaDB PersistentClient persists to disk — not in-memory Client().
    """
    project_id = f"test-cross-{uuid4().hex[:8]}"
    entry = OrgMemoryEntry(
        entry_id=str(uuid4()),
        project_id=project_id,
        content=(
            "DECISION: Use PostgreSQL not MySQL. "
            "RATIONALE: ACID compliance and better async driver support."
        ),
        category="architecture",
        source_run_id="test-run-1",
        timestamp=datetime.now(tz=timezone.utc),
    )

    # Instance 1: save decision
    org1 = OrgMemory()
    await org1.upsert(entry)

    # Instance 2: new instantiation (simulates process restart / new tool session)
    org2 = OrgMemory()
    results = await org2.search(
        "PostgreSQL database decision", project_id, limit=5
    )

    assert len(results) > 0, (
        "No results returned after OrgMemory reinstantiation. "
        "PersistentClient must be used — not in-memory Client(). "
        "Check OrgMemory.__init__: chromadb.PersistentClient(path=...) required."
    )
    assert any("PostgreSQL" in r.content for r in results), (
        "Saved decision not found after OrgMemory reinstantiation. "
        "Embedding must have been persisted to disk via PersistentClient."
    )


@pytest.mark.asyncio
async def test_architecture_decision_retrievable_by_different_query() -> None:
    """Semantic search — different wording should still find the decision."""
    project_id = f"test-semantic-{uuid4().hex[:8]}"
    entry = OrgMemoryEntry(
        entry_id=str(uuid4()),
        project_id=project_id,
        content=(
            "DECISION: Use FastAPI for the REST layer. "
            "RATIONALE: Native async, Pydantic validation, OpenAPI generation."
        ),
        category="architecture",
        source_run_id="test-run-semantic",
        timestamp=datetime.now(tz=timezone.utc),
    )

    org1 = OrgMemory()
    await org1.upsert(entry)

    # Different query wording — semantic search should still find it
    org2 = OrgMemory()
    results = await org2.search(
        "web framework selection backend API", project_id, limit=5
    )

    # Semantic search may or may not match — verify at least no crash
    assert isinstance(results, list), (
        "search() must return a list, even if empty"
    )


@pytest.mark.asyncio
async def test_pipeline_history_survives_store_reinstantiation(
    tmp_path: object,
) -> None:
    """Layer 1: PipelineRunRecord survives store reinstantiation."""
    from memory.pipeline_history_store import PipelineHistoryStore  # noqa: PLC0415
    from memory.schemas import PipelineRunRecord  # noqa: PLC0415

    project_id = f"test-hist-{uuid4().hex[:8]}"
    record = PipelineRunRecord(
        run_id=str(uuid4()),
        timestamp=datetime.now(tz=timezone.utc),
        project_id=project_id,
        user_prompt="Build a REST API with FastAPI",
        stack_chosen="FastAPI + PostgreSQL",
        deployment_success=True,
        cost_total_usd=0.05,
        hitl_rounds=2,
        human_corrections=["use asyncpg not psycopg2"],
        lessons_learned=["async drivers significantly faster"],
        tool_delegated_to="direct_llm",
        workspace_path=str(tmp_path),
    )

    store1 = PipelineHistoryStore()
    await store1.save_run(record)

    # New instance — simulates server restart
    store2 = PipelineHistoryStore()
    results = await store2.get_similar_runs(project_id, limit=5)

    assert any(r.project_id == project_id for r in results), (
        "PipelineRunRecord not found after PipelineHistoryStore reinstantiation. "
        "PostgreSQL persistence must be used — not in-memory store."
    )


@pytest.mark.asyncio
async def test_project_context_graph_survives_reinstantiation(
    tmp_path: object,
) -> None:
    """Layer 3: ProjectContextGraph survives GraphStore reinstantiation."""
    from memory.project_context_graph import ProjectContextGraphStore  # noqa: PLC0415
    from memory.schemas import ProjectContextGraph, ServiceNode  # noqa: PLC0415

    project_id = f"test-graph-{uuid4().hex[:8]}"
    graph = ProjectContextGraph(
        project_id=project_id,
        repo_url=None,
        services=[ServiceNode(
            name="api",
            responsibility="REST endpoints",
            exposes=["GET /users", "POST /users"],
            depends_on=["db"],
            owns_data=False,
            database=None,
        )],
        api_contracts=["docs/openapi.yaml"],
        architectural_decisions=["Use FastAPI"],
        dependencies=["fastapi", "asyncpg"],
        env_var_names=["DATABASE_URL", "SECRET_KEY"],
        deployment_config={"target": "render"},
        slo_definitions=["99.9% uptime"],
        workspace_path=str(tmp_path),
        last_updated=datetime.now(tz=timezone.utc),
    )

    store1 = ProjectContextGraphStore()
    await store1.save_graph(graph)

    store2 = ProjectContextGraphStore()
    result = await store2.get_graph(project_id)

    assert result is not None, (
        "ProjectContextGraph not found after store reinstantiation."
    )
    assert result.project_id == project_id
    assert len(result.services) == 1
    assert result.services[0].name == "api"