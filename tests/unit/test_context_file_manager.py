from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from context_files.manager import ContextFileManager


def _make_cfm() -> ContextFileManager:
    return ContextFileManager()


@pytest.mark.asyncio
async def test_write_all_creates_agents_md_file(tmp_path: Path) -> None:
    cfm = _make_cfm()
    await cfm.write_all(project_id="proj-1", workspace_path=str(tmp_path))
    assert (tmp_path / "AGENTS.md").exists()


@pytest.mark.asyncio
async def test_write_all_creates_claude_md_file(tmp_path: Path) -> None:
    cfm = _make_cfm()
    await cfm.write_all(project_id="proj-1", workspace_path=str(tmp_path))
    assert (tmp_path / "CLAUDE.md").exists()


@pytest.mark.asyncio
async def test_write_all_creates_cursorrules_file(tmp_path: Path) -> None:
    cfm = _make_cfm()
    await cfm.write_all(project_id="proj-1", workspace_path=str(tmp_path))
    assert (tmp_path / ".cursorrules").exists()


@pytest.mark.asyncio
async def test_agents_md_contains_project_id(tmp_path: Path) -> None:
    cfm = _make_cfm()
    await cfm.write_all(project_id="my-unique-project", workspace_path=str(tmp_path))
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "my-unique-project" in content


@pytest.mark.asyncio
async def test_agents_md_contains_current_phase(tmp_path: Path) -> None:
    cfm = _make_cfm()
    await cfm.write_all(
        project_id="proj-1",
        workspace_path=str(tmp_path),
        current_phase="architecture",
    )
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "architecture" in content


@pytest.mark.asyncio
async def test_agents_md_contains_maang_standards_section(tmp_path: Path) -> None:
    cfm = _make_cfm()
    await cfm.write_all(project_id="proj-1", workspace_path=str(tmp_path))
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "Code Standards" in content
    assert "structlog" in content
    assert "Pydantic v2" in content


@pytest.mark.asyncio
async def test_cursorrules_contains_architecture_summary_when_provided(
    tmp_path: Path,
) -> None:
    cfm = _make_cfm()
    await cfm.write_all(
        project_id="proj-1",
        workspace_path=str(tmp_path),
        architecture_summary="FastAPI + PostgreSQL + ChromaDB",
    )
    content = (tmp_path / ".cursorrules").read_text(encoding="utf-8")
    assert "FastAPI + PostgreSQL + ChromaDB" in content


@pytest.mark.asyncio
async def test_write_all_emits_interpret_record_layer13_before_each_write(
    tmp_path: Path,
) -> None:
    cfm = _make_cfm()
    emitted: list[str] = []
    original_emit = cfm._emit_record

    def capturing_emit(
        filename: str, project_id: str, workspace_path: str
    ) -> object:
        ir = original_emit(filename, project_id, workspace_path)
        emitted.append(ir.layer)
        return ir

    cfm._emit_record = capturing_emit  # type: ignore[method-assign]
    await cfm.write_all(project_id="proj-1", workspace_path=str(tmp_path))
    assert all(layer == "context_file_manager" for layer in emitted)
    assert len(emitted) == 4  # one per writer


@pytest.mark.asyncio
async def test_write_all_is_idempotent(tmp_path: Path) -> None:
    cfm = _make_cfm()
    kwargs = {
        "project_id": "proj-1",
        "workspace_path": str(tmp_path),
        "current_phase": "requirements",
        "prd_summary": "Build a REST API",
        "architecture_summary": "FastAPI + PostgreSQL",
        "key_decisions": ["use asyncpg"],
        "security_rules": ["validate inputs"],
    }
    await cfm.write_all(**kwargs)
    content_first = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    await cfm.write_all(**kwargs)
    content_second = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    # Strip the timestamp line before comparing (it will differ between calls)
    def strip_timestamp(text: str) -> str:
        return "\n".join(
            line for line in text.splitlines()
            if "Last Updated:" not in line
        )

    assert strip_timestamp(content_first) == strip_timestamp(content_second)