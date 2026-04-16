from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from interpret.record import InterpretRecord

ALL_LAYERS = [
    "agent",
    "workspace",
    "diff",
    "model_router",
    "tool_router",
    "memory",
    "docs_fetcher",
    "tool",
    "provider",
    "security",
    "context_window_manager",
    "mcp_server",
    "context_file_manager",
]


def _make_record(layer: str) -> InterpretRecord:
    return InterpretRecord(
        layer=layer,  # type: ignore[arg-type]
        component="TestComponent",
        action="test_action",
        inputs={},
        expected_outputs={},
        files_it_will_read=[],
        files_it_will_write=[],
        external_calls=[],
        model_selected=None,
        tool_delegated_to=None,
        estimated_tokens=None,
        estimated_cost_usd=None,
        reversible=True,
        workspace_files_affected=[],
        timestamp=datetime.now(tz=timezone.utc),
    )


def test_all_12_layer_literals_accepted() -> None:
    for layer in ALL_LAYERS:
        record = _make_record(layer)
        assert record.layer == layer


def test_unknown_layer_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        _make_record("unknown_layer")


def test_negative_tokens_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        InterpretRecord(
            layer="agent",
            component="X",
            action="x",
            inputs={},
            expected_outputs={},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            estimated_tokens=-1,
            estimated_cost_usd=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=timezone.utc),
        )


def test_negative_cost_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        InterpretRecord(
            layer="agent",
            component="X",
            action="x",
            inputs={},
            expected_outputs={},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            estimated_tokens=None,
            estimated_cost_usd=-0.01,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=timezone.utc),
        )


def test_tool_delegated_to_is_optional_and_none_by_default() -> None:
    record = _make_record("tool_router")
    assert record.tool_delegated_to is None