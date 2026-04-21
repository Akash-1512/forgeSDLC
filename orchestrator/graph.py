from __future__ import annotations

"""LangGraph pipeline graph definition for forgeSDLC.

This module defines the StateGraph edges and conditional routing logic.
Agents are registered as nodes; edges define the execution flow.

Security gate conditional edge (Session 12):
  agent_5b_security → HITL (if gate_blocked) or agent_7_cicd (if clear)

Agent 8 (deploy) and Agent 7 (CI/CD) are placeholders until Sessions 13-14.
"""

import structlog

logger = structlog.get_logger()


# ── Conditional edge routers ─────────────────────────────────────────────────

def _security_gate_router(state: dict[str, object]) -> str:
    """Route after Agent 5b based on security gate status.

    Returns:
        "hitl_security_blocked" — if any HIGH/CRITICAL finding blocks deployment
        "agent_7_cicd"          — if gate is clear, proceed to CI/CD (Session 13)
    """
    gate = dict(state.get("security_gate") or {})
    blocked = bool(gate.get("blocked", False))

    if blocked:
        reason = str(gate.get("reason", "Security gate blocked"))
        logger.warning(
            "security_gate.blocked",
            reason=reason,
        )
        return "hitl_security_blocked"

    logger.info("security_gate.clear", next="agent_7_cicd")
    return "agent_7_cicd"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> object:
    """Build and return the forgeSDLC StateGraph.

    Nodes registered here:
    - agent_5b_security (Session 12)
    - hitl_node         (placeholder — Session 17 Desktop wires this to UI)
    - agent_7_cicd      (placeholder — Session 13)

    Conditional edges:
    - agent_5b_security → _security_gate_router → hitl_security_blocked | agent_7_cicd

    Full 14-agent graph is assembled incrementally across Sessions 09-16.
    """
    try:
        from langgraph.graph import StateGraph  # noqa: PLC0415
    except ImportError:
        logger.warning("build_graph.langgraph_not_available")
        return None

    # State type is dict — full TypedDict defined in orchestrator/state.py
    graph = StateGraph(dict)

    # ── Placeholder nodes (replaced in later sessions) ────────────────────
    graph.add_node("hitl_node", lambda state: state)          # Session 17
    graph.add_node("agent_7_cicd", lambda state: state)       # Session 13
    graph.add_node("agent_5b_security", lambda state: state)  # real agent injected

    # ── Security gate conditional edge (Session 12) ───────────────────────
    graph.add_conditional_edges(
        "agent_5b_security",
        _security_gate_router,
        {
            "hitl_security_blocked": "hitl_node",
            "agent_7_cicd": "agent_7_cicd",
        },
    )

    logger.info("build_graph.complete")
    return graph