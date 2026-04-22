from __future__ import annotations

import structlog

from interpret.gate import check_gate
from interpret.record import InterpretRecord
from orchestrator.exceptions import GateNotPassedError

logger = structlog.get_logger()


def interpret_node(
    record: InterpretRecord,
    correction: str | None = None,
) -> str:
    """Build the interpretation string shown in the companion panel.

    If a correction is supplied it is folded in — the previous interpretation
    is replaced, not appended to. The user always sees one current interpretation.
    """
    base = (
        f"[{record.layer.upper()}] {record.component} → {record.action}\n"
        f"reads:  {record.files_it_will_read}\n"
        f"writes: {record.files_it_will_write}\n"
        f"calls:  {record.external_calls}\n"
        f"model:  {record.model_selected} | delegate: {record.tool_delegated_to}\n"
        f"reversible: {record.reversible}"
    )
    if correction:
        base = f"[CORRECTED] {correction}\n\n{base}"
    logger.info(
        "interpret_node",
        layer=record.layer,
        component=record.component,
        action=record.action,
    )
    return base


def interrupt_node(displayed_interpretation: str) -> None:
    """Pause execution and surface the interpretation to the companion panel.

    In Session 17 this wires to the WebSocket / panel UI.
    For now it logs — the [✅ Approve] button will call check_gate() with
    HUMAN_CONFIRMATION_PHRASE before execute_node is allowed to fire.
    """
    logger.info("interrupt_node — awaiting gate", interpretation=displayed_interpretation)


def execute_node(confirmation: str, fn: object, *args: object) -> object:
    """Fire the actual action only after gate passes.

    Raises GateNotPassedError if confirmation is anything other than
    the exact gate phrase sent by [✅ Approve].
    """
    if not check_gate(confirmation):
        raise GateNotPassedError(
            f"execute_node blocked — gate phrase not matched. Received: {confirmation!r}"
        )
    logger.info("execute_node — gate passed, executing")
    # TODO: replace cast with proper callable protocol in Session 09
    import collections.abc  # noqa: PLC0415

    assert isinstance(fn, collections.abc.Callable)  # noqa: S101
    return fn(*args)
