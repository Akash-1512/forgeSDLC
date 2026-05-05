from __future__ import annotations

from orchestrator.graph import _security_gate_router


def test_security_gate_router_returns_hitl_when_blocked() -> None:
    state = {"security_gate": {"blocked": True, "reason": "2 HIGH findings"}}
    result = _security_gate_router(state)
    assert result == "hitl_security_blocked"


def test_security_gate_router_returns_agent_7_when_not_blocked() -> None:
    state = {"security_gate": {"blocked": False, "reason": None}}
    result = _security_gate_router(state)
    assert result == "agent_7_cicd"
