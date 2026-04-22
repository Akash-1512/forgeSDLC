"""
Verifies DASTRunner emits L10 InterpretRecord BEFORE the RUN_DAST env check.
The audit trail must show every intent to run a component, not just successful runs.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from interpret.record import InterpretRecord
from tools.security_tools import DASTRunner


@pytest.mark.asyncio
async def test_dast_emits_l10_before_env_check(tmp_path: object) -> None:
    """L10 fires even when RUN_DAST is not set."""
    records: list[InterpretRecord] = []
    original_init = InterpretRecord.__init__

    def collecting_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        records.append(self)

    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with (
        patch.object(InterpretRecord, "__init__", collecting_init),
        patch.dict(os.environ, env, clear=True),
    ):
        runner = DASTRunner()
        result = await runner.run(str(tmp_path))

    assert result == [], (
        "DASTRunner must return [] when RUN_DAST not set — DAST was unexpectedly run"
    )
    l10_records = [r for r in records if r.layer == "security"]
    assert len(l10_records) >= 1, (
        "DASTRunner must emit L10 InterpretRecord before the RUN_DAST env check. "
        "If L10 is inside the 'if RUN_DAST == true' block, it will not fire on skip."
    )
    assert l10_records[0].component == "DASTRunner", (
        f"Expected component='DASTRunner', got '{l10_records[0].component}'"
    )


@pytest.mark.asyncio
async def test_dast_emits_l10_even_when_run_dast_false(tmp_path: object) -> None:
    """L10 fires when RUN_DAST=false (explicit false, not just absent)."""
    records: list[InterpretRecord] = []
    original_init = InterpretRecord.__init__

    def collecting_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        records.append(self)

    with (
        patch.object(InterpretRecord, "__init__", collecting_init),
        patch.dict(os.environ, {"RUN_DAST": "false"}),
    ):
        runner = DASTRunner()
        result = await runner.run(str(tmp_path))

    assert result == []
    l10_records = [r for r in records if r.layer == "security"]
    assert len(l10_records) >= 1, (
        "DASTRunner must emit L10 when RUN_DAST=false — skip is after the emit"
    )


@pytest.mark.asyncio
async def test_dast_l10_record_has_correct_fields(tmp_path: object) -> None:
    """L10 record has required fields populated."""
    records: list[InterpretRecord] = []
    original_init = InterpretRecord.__init__

    def collecting_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        records.append(self)

    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with (
        patch.object(InterpretRecord, "__init__", collecting_init),
        patch.dict(os.environ, env, clear=True),
    ):
        runner = DASTRunner()
        await runner.run(str(tmp_path))

    l10 = next((r for r in records if r.layer == "security" and r.component == "DASTRunner"), None)
    assert l10 is not None
    assert l10.layer == "security"
    assert l10.component == "DASTRunner"
    assert l10.action is not None and len(l10.action) > 0
    assert l10.timestamp is not None


@pytest.mark.asyncio
async def test_l10_emission_order_before_skip(tmp_path: object) -> None:
    """L10 must be the FIRST thing that happens — before any conditional logic."""
    emission_order: list[str] = []
    original_init = InterpretRecord.__init__

    def collecting_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "DASTRunner":
            emission_order.append("L10_emitted")

    env = {k: v for k, v in os.environ.items() if k != "RUN_DAST"}
    with (
        patch.object(InterpretRecord, "__init__", collecting_init),
        patch.dict(os.environ, env, clear=True),
    ):
        runner = DASTRunner()
        result = await runner.run(str(tmp_path))
        emission_order.append("run_returned")

    assert emission_order[0] == "L10_emitted", (
        f"Expected L10 to be emitted before run() returns. Actual order: {emission_order}"
    )
    assert result == [], "DAST must have skipped (RUN_DAST not set)"
