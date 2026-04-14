from __future__ import annotations

from orchestrator.constants import HUMAN_CONFIRMATION_PHRASE


def check_gate(confirmation: str) -> bool:
    """Return True only when the [✅ Approve] button sends the gate phrase.

    Pure function — no side effects, no I/O, no state mutation.
    Users never see or type the gate phrase; the button sends it internally.
    """
    return confirmation == HUMAN_CONFIRMATION_PHRASE