from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.security_tools import (
    BanditRunner,
    DASTRunner,
    PipAuditRunner,
    SemgrepRunner,
)


def _make_proc(stdout: bytes = b"", returncode: int = 0) -> object:
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    proc.returncode = returncode
    proc.terminate = MagicMock()
    proc.wait = AsyncMock()
    return proc


@pytest.mark.asyncio
async def test_bandit_runner_emits_interpret_record_l10_before_subprocess() -> None:
    from interpret.record import InterpretRecord
    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "BanditRunner":
            emitted.append(str(kwargs.get("layer", "")))

    with (
        patch.object(InterpretRecord, "__init__", capturing_init),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_proc(b'{"results": []}'),
        ),
    ):
        runner = BanditRunner()
        await runner.run("/tmp/test")

    assert "security" in emitted


@pytest.mark.asyncio
async def test_semgrep_runner_emits_interpret_record_l10_before_subprocess() -> None:
    from interpret.record import InterpretRecord
    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "SemgrepRunner":
            emitted.append(str(kwargs.get("layer", "")))

    with (
        patch.object(InterpretRecord, "__init__", capturing_init),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_proc(b'{"results": []}'),
        ),
    ):
        runner = SemgrepRunner()
        await runner.run("/tmp/test")

    assert "security" in emitted


@pytest.mark.asyncio
async def test_semgrep_runner_command_contains_config_p_python() -> None:
    captured_args: list[tuple] = []

    async def mock_exec(*args: object, **kwargs: object) -> object:
        captured_args.append(args)
        return _make_proc(b'{"results": []}')

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        runner = SemgrepRunner()
        await runner.run("/tmp/test")

    assert captured_args
    cmd = " ".join(str(a) for a in captured_args[0])
    assert "p/python" in cmd


@pytest.mark.asyncio
async def test_semgrep_runner_command_contains_config_p_security() -> None:
    captured_args: list[tuple] = []

    async def mock_exec(*args: object, **kwargs: object) -> object:
        captured_args.append(args)
        return _make_proc(b'{"results": []}')

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        runner = SemgrepRunner()
        await runner.run("/tmp/test")

    assert captured_args
    cmd = " ".join(str(a) for a in captured_args[0])
    assert "p/security" in cmd


@pytest.mark.asyncio
async def test_semgrep_runner_command_does_not_contain_auto() -> None:
    """CRITICAL: semgrep must NEVER use --config=auto."""
    captured_args: list[tuple] = []

    async def mock_exec(*args: object, **kwargs: object) -> object:
        captured_args.append(args)
        return _make_proc(b'{"results": []}')

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        runner = SemgrepRunner()
        await runner.run("/tmp/test")

    assert captured_args
    cmd = " ".join(str(a) for a in captured_args[0])
    assert "auto" not in cmd, (
        f"semgrep command contains 'auto': {cmd}\n"
        "NEVER use --config=auto — always use p/python + p/security"
    )


@pytest.mark.asyncio
async def test_pip_audit_runner_emits_interpret_record_l10_before_subprocess(
    tmp_path: object,
) -> None:
    from pathlib import Path
    from interpret.record import InterpretRecord

    p = Path(str(tmp_path))
    (p / "requirements.txt").write_text("requests==2.28.0\n", encoding="utf-8")

    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "PipAuditRunner":
            emitted.append(str(kwargs.get("layer", "")))

    with (
        patch.object(InterpretRecord, "__init__", capturing_init),
        patch(
            "asyncio.create_subprocess_exec",
            return_value=_make_proc(b"[]"),
        ),
    ):
        runner = PipAuditRunner()
        await runner.run(str(tmp_path))

    assert "security" in emitted


@pytest.mark.asyncio
async def test_pip_audit_runner_skips_gracefully_when_no_requirements_file(
    tmp_path: object,
) -> None:
    """No requirements.txt or pyproject.toml → return [], no exception."""
    runner = PipAuditRunner()
    result = await runner.run(str(tmp_path))
    assert result == []


@pytest.mark.asyncio
async def test_dast_runner_returns_empty_list_when_run_dast_not_set() -> None:
    """RUN_DAST not set → always returns []."""
    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with patch.dict(os.environ, env, clear=True):
        runner = DASTRunner()
        result = await runner.run("/tmp/test")
    assert result == []


@pytest.mark.asyncio
async def test_dast_runner_returns_empty_list_when_run_dast_false() -> None:
    """RUN_DAST=false → always returns []."""
    with patch.dict(os.environ, {"RUN_DAST": "false"}):
        runner = DASTRunner()
        result = await runner.run("/tmp/test")
    assert result == []


@pytest.mark.asyncio
async def test_dast_runner_emits_interpret_record_even_when_skipped() -> None:
    """L10 InterpretRecord fires BEFORE the env var check — always."""
    from interpret.record import InterpretRecord
    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "DASTRunner":
            emitted.append(str(kwargs.get("layer", "")))

    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with (
        patch.object(InterpretRecord, "__init__", capturing_init),
        patch.dict(os.environ, env, clear=True),
    ):
        runner = DASTRunner()
        await runner.run("/tmp/test")

    assert "security" in emitted, (
        "DASTRunner must emit L10 InterpretRecord even when DAST is skipped"
    )