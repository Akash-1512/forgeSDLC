from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from memory.project_context_graph import ProjectContextGraphStore
from memory.schemas import ProjectContextGraph, ServiceNode


def _make_graph(project_id: str = "proj-test") -> ProjectContextGraph:
    return ProjectContextGraph(
        project_id=project_id,
        repo_url="https://github.com/test/repo",
        services=[
            ServiceNode(
                name="api",
                responsibility="REST API",
                exposes=["/health", "/api/v1"],
                depends_on=["db"],
                owns_data=False,
                database=None,
            )
        ],
        api_contracts=["openapi.yaml"],
        architectural_decisions=["use FastAPI", "use PostgreSQL"],
        dependencies=["fastapi", "asyncpg"],
        env_var_names=["DATABASE_URL", "SECRET_KEY"],
        deployment_config={"platform": "render", "tier": "starter"},
        slo_definitions=["p99 < 200ms"],
        workspace_path="C:/projects/myapp",
        last_updated=datetime.now(tz=UTC),
    )


def _make_store(tmp_path: Path) -> ProjectContextGraphStore:
    store = ProjectContextGraphStore()
    store._base = tmp_path / "graphs"
    return store


def test_graph_exists_returns_false_for_new_project(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    import asyncio

    result = asyncio.run(store.graph_exists("nonexistent-proj"))
    assert result is False


@pytest.mark.asyncio
async def test_save_graph_writes_json_file_to_data_graphs_dir(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    graph = _make_graph()
    await store.save_graph(graph)
    expected_path = store._base / f"{graph.project_id}.json"
    assert expected_path.exists()
    assert expected_path.stat().st_size > 0


@pytest.mark.asyncio
async def test_load_graph_returns_none_for_unknown_project(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    result = await store.load_graph("does-not-exist")
    assert result is None


@pytest.mark.asyncio
async def test_save_graph_emits_interpret_record_layer_memory_before_write(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    emitted: list[str] = []
    original_emit = store._emit

    def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
        ir = original_emit(action_type, action, key)
        emitted.append(ir.layer)
        return ir

    store._emit = capturing_emit  # type: ignore[method-assign]
    graph = _make_graph()
    await store.save_graph(graph)
    assert "memory" in emitted


@pytest.mark.asyncio
async def test_load_graph_emits_interpret_record_layer_memory_before_read(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    emitted: list[str] = []
    original_emit = store._emit

    def capturing_emit(action_type: str, action: str, key: str):  # type: ignore[no-untyped-def]
        ir = original_emit(action_type, action, key)
        emitted.append(ir.layer)
        return ir

    store._emit = capturing_emit  # type: ignore[method-assign]
    await store.load_graph("any-project")
    assert "memory" in emitted


def test_save_graph_uses_pathlib_not_os_path() -> None:
    """AST check — os.path must not appear in project_context_graph.py."""
    import memory.project_context_graph as module

    source = inspect.getsource(module)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "os", (
                    "os imported in project_context_graph.py — use pathlib only"
                )
        if isinstance(node, ast.ImportFrom):
            assert node.module != "os.path", (
                "os.path imported in project_context_graph.py — use pathlib only"
            )
