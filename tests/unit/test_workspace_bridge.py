from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workspace.bridge import WorkspaceBridge
from workspace.context import WorkspaceContext


async def _make_context(tmp_path: Path) -> WorkspaceContext:
    bridge = WorkspaceBridge()
    bridge._path = tmp_path
    await bridge._refresh()
    return await bridge.get_context()


@pytest.mark.asyncio
async def test_get_context_emits_interpret_record_layer2(tmp_path: Path) -> None:
    from interpret.record import InterpretRecord
    bridge = WorkspaceBridge()
    bridge._path = tmp_path
    await bridge._refresh()

    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        emitted.append(str(kwargs.get("layer", "")))

    with patch.object(InterpretRecord, "__init__", capturing_init):
        await bridge.get_context()

    assert "workspace" in emitted


@pytest.mark.asyncio
async def test_get_context_returns_valid_workspace_context_schema(
    tmp_path: Path,
) -> None:
    ctx = await _make_context(tmp_path)
    assert isinstance(ctx, WorkspaceContext)
    assert ctx.root_path == str(tmp_path)
    assert isinstance(ctx.git_last_commits, list)
    assert isinstance(ctx.language_stats, dict)
    assert isinstance(ctx.context_files, list)


@pytest.mark.asyncio
async def test_refresh_handles_non_git_directory_gracefully(
    tmp_path: Path,
) -> None:
    """tmp_path is not a git repo — must not raise."""
    ctx = await _make_context(tmp_path)
    assert ctx.git_branch is None
    assert ctx.git_uncommitted is False
    assert ctx.git_last_commits == []


@pytest.mark.asyncio
async def test_refresh_detects_uncommitted_changes(tmp_path: Path) -> None:
    """Mock gitpython to simulate uncommitted changes."""
    bridge = WorkspaceBridge()
    bridge._path = tmp_path

    mock_repo = MagicMock()
    mock_repo.head.is_detached = False
    mock_repo.active_branch.name = "feat/test"
    mock_repo.is_dirty.return_value = True
    mock_repo.iter_commits.return_value = []

    with patch("workspace.bridge.Repo", return_value=mock_repo):
        await bridge._refresh()

    ctx = await bridge.get_context()
    assert ctx.git_uncommitted is True
    assert ctx.git_branch == "feat/test"


@pytest.mark.asyncio
async def test_refresh_finds_existing_test_files(tmp_path: Path) -> None:
    (tmp_path / "test_example.py").write_text("def test_x(): pass", encoding="utf-8")
    (tmp_path / "test_another.py").write_text("def test_y(): pass", encoding="utf-8")
    ctx = await _make_context(tmp_path)
    assert any("test_example.py" in f for f in ctx.existing_tests)
    assert any("test_another.py" in f for f in ctx.existing_tests)


@pytest.mark.asyncio
async def test_refresh_finds_context_files_written_by_context_file_manager(
    tmp_path: Path,
) -> None:
    (tmp_path / "AGENTS.md").write_text("# forgeSDLC", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Claude", encoding="utf-8")
    (tmp_path / ".cursorrules").write_text("rules", encoding="utf-8")
    ctx = await _make_context(tmp_path)
    assert any("AGENTS.md" in f for f in ctx.context_files)
    assert any("CLAUDE.md" in f for f in ctx.context_files)
    assert any(".cursorrules" in f for f in ctx.context_files)


@pytest.mark.asyncio
async def test_workspace_bridge_never_writes_files(tmp_path: Path) -> None:
    """Structural test: every InterpretRecord from WorkspaceBridge must have
    files_it_will_write == [] — read-only contract enforced at semantic layer."""
    from interpret.record import InterpretRecord
    bridge = WorkspaceBridge()
    bridge._path = tmp_path
    await bridge._refresh()

    written_files: list[list[str]] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "WorkspaceBridge":
            written_files.append(list(kwargs.get("files_it_will_write", [])))

    with patch.object(InterpretRecord, "__init__", capturing_init):
        await bridge.get_context()

    assert len(written_files) >= 1, "Expected at least one InterpretRecord from WorkspaceBridge"
    for record_writes in written_files:
        assert record_writes == [], (
            f"WorkspaceBridge emitted files_it_will_write={record_writes} — must be []"
        )


@pytest.mark.asyncio
async def test_get_context_git_branch_is_none_for_detached_head(
    tmp_path: Path,
) -> None:
    bridge = WorkspaceBridge()
    bridge._path = tmp_path

    mock_repo = MagicMock()
    mock_repo.head.is_detached = True
    mock_repo.is_dirty.return_value = False
    mock_repo.iter_commits.return_value = []

    with patch("workspace.bridge.Repo", return_value=mock_repo):
        await bridge._refresh()

    ctx = await bridge.get_context()
    assert ctx.git_branch is None
