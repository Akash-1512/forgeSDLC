from __future__ import annotations

from pathlib import Path

import pytest

from workspace.diff_engine import DiffEngine, UnifiedDiff


def _make_engine() -> DiffEngine:
    return DiffEngine()


@pytest.mark.asyncio
async def test_generate_diff_emits_interpret_record_layer3_before_read(
    tmp_path: Path,
) -> None:
    from unittest.mock import patch
    from interpret.record import InterpretRecord

    engine = _make_engine()
    target = tmp_path / "hello.py"
    target.write_text("x = 1\n", encoding="utf-8")

    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "DiffEngine":
            emitted.append(str(kwargs.get("layer", "")))

    with patch.object(InterpretRecord, "__init__", capturing_init):
        await engine.generate_diff(str(target), "x = 2\n", "test change")

    assert "diff" in emitted


@pytest.mark.asyncio
async def test_apply_diff_emits_interpret_record_layer3_before_write(
    tmp_path: Path,
) -> None:
    from unittest.mock import patch
    from interpret.record import InterpretRecord

    engine = _make_engine()
    target = tmp_path / "app.py"
    target.write_text("a = 1\n", encoding="utf-8")
    diff = await engine.generate_diff(str(target), "a = 2\n", "update a")

    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "DiffEngine":
            emitted.append(str(kwargs.get("layer", "")))

    with patch.object(InterpretRecord, "__init__", capturing_init):
        await engine.apply_diff(diff)

    assert "diff" in emitted


@pytest.mark.asyncio
async def test_apply_diff_creates_bak_backup_before_writing(
    tmp_path: Path,
) -> None:
    engine = _make_engine()
    target = tmp_path / "main.py"
    target.write_text("version = 1\n", encoding="utf-8")
    diff = await engine.generate_diff(str(target), "version = 2\n", "bump version")
    await engine.apply_diff(diff)
    bak = Path(f"{target}.forgesdlc.bak")
    assert bak.exists(), ".forgesdlc.bak must exist after apply"


@pytest.mark.asyncio
async def test_apply_diff_backup_contains_original_content(tmp_path: Path) -> None:
    engine = _make_engine()
    target = tmp_path / "config.py"
    original = "DEBUG = True\n"
    target.write_text(original, encoding="utf-8")
    diff = await engine.generate_diff(str(target), "DEBUG = False\n", "disable debug")
    await engine.apply_diff(diff)
    bak = Path(f"{target}.forgesdlc.bak")
    assert bak.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_apply_diff_skips_backup_when_file_does_not_exist(
    tmp_path: Path,
) -> None:
    engine = _make_engine()
    target = tmp_path / "new_file.py"
    # File does not exist — no backup should be created
    diff = await engine.generate_diff(str(target), "x = 1\n", "new file")
    await engine.apply_diff(diff)
    bak = Path(f"{target}.forgesdlc.bak")
    assert not bak.exists(), "No backup should be created for new files"
    assert target.read_text(encoding="utf-8") == "x = 1\n"


@pytest.mark.asyncio
async def test_restore_from_backup_restores_original_content(
    tmp_path: Path,
) -> None:
    engine = _make_engine()
    target = tmp_path / "service.py"
    original = "PORT = 8080\n"
    target.write_text(original, encoding="utf-8")
    diff = await engine.generate_diff(str(target), "PORT = 9090\n", "change port")
    await engine.apply_diff(diff)
    assert target.read_text(encoding="utf-8") == "PORT = 9090\n"
    restored = await engine.restore_from_backup(str(target))
    assert restored is True
    assert target.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_restore_from_backup_returns_false_when_no_backup_exists(
    tmp_path: Path,
) -> None:
    engine = _make_engine()
    target = tmp_path / "no_backup.py"
    result = await engine.restore_from_backup(str(target))
    assert result is False


@pytest.mark.asyncio
async def test_apply_diff_creates_parent_dirs_if_missing(tmp_path: Path) -> None:
    engine = _make_engine()
    target = tmp_path / "deep" / "nested" / "module.py"
    diff = await engine.generate_diff(str(target), "x = 1\n", "nested new file")
    await engine.apply_diff(diff)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "x = 1\n"


def test_bak_extension_is_dot_forgesdlc_dot_bak() -> None:
    from workspace.diff_engine import _BAK_EXTENSION
    assert _BAK_EXTENSION == ".forgesdlc.bak"