"""LangGraph pipeline graph for forgeSDLC batch/automated runs.

Usage:
    from orchestrator.graph import build_graph
    graph = build_graph()
    compiled = graph.compile()
    result = await compiled.ainvoke(state)
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


def _security_gate_router(state: dict[str, object]) -> str:
    """Route after Agent 5b based on security gate status.

    Returns:
        "hitl_security_blocked" — HIGH/CRITICAL findings block deployment
        "agent_7_cicd"          — gate is clear, proceed to CI/CD
    """
    gate = dict(state.get("security_gate") or {})
    blocked = bool(gate.get("blocked", False))
    if blocked:
        logger.warning("security_gate.blocked", reason=str(gate.get("reason", "")))
        return "hitl_security_blocked"
    logger.info("security_gate.clear")
    return "agent_7_cicd"


def _review_retry_router(state: dict[str, object]) -> str:
    """Route after Agent 5 based on whether a retry is needed."""
    if state.get("trigger_agent_4_retry"):
        return "agent_4_tool_router"
    if state.get("hitl_required"):
        return "hitl_review_escalation"
    return "agent_5b_security"


def build_graph(agents: dict[str, object] | None = None) -> object:
    """Build and return the compiled forgeSDLC StateGraph.

    Accepts real agent instances; pass None to use passthrough lambdas (testing only).

    Args:
        agents: dict mapping node name → callable (BaseAgent or lambda).
                If None, lambda pass-throughs are used (testing only).

    Returns:
        Compiled StateGraph ready for ainvoke(), or None if LangGraph unavailable.

    Example:
        from agents.agent_5b_security import SecurityAgent
        graph = build_graph({"agent_5b_security": security_agent_instance})
        compiled = graph.compile()
    """
    try:
        from langgraph.graph import StateGraph  # noqa: PLC0415
    except ImportError:
        logger.warning("build_graph.langgraph_not_available")
        return None

    _agents = agents or {}
    _passthrough = lambda state: state  # noqa: E731

    graph = StateGraph(dict)

    # Register nodes — real agents injected from caller, lambdas as fallback
    graph.add_node("agent_5b_security", _agents.get("agent_5b_security", _passthrough))
    graph.add_node("agent_4_tool_router", _agents.get("agent_4_tool_router", _passthrough))
    graph.add_node("agent_5_coord_review", _agents.get("agent_5_coord_review", _passthrough))
    graph.add_node("agent_7_cicd", _agents.get("agent_7_cicd", _passthrough))
    graph.add_node("agent_8_deploy", _agents.get("agent_8_deploy", _passthrough))
    graph.add_node("hitl_node", _agents.get("hitl_node", _passthrough))
    graph.add_node("hitl_security_blocked", _agents.get("hitl_security_blocked", _passthrough))
    graph.add_node("hitl_review_escalation", _agents.get("hitl_review_escalation", _passthrough))

    # Security gate conditional edge
    graph.add_conditional_edges(
        "agent_5b_security",
        _security_gate_router,
        {
            "hitl_security_blocked": "hitl_security_blocked",
            "agent_7_cicd": "agent_7_cicd",
        },
    )

    # Code review retry edge
    graph.add_conditional_edges(
        "agent_5_coord_review",
        _review_retry_router,
        {
            "agent_4_tool_router": "agent_4_tool_router",
            "hitl_review_escalation": "hitl_review_escalation",
            "agent_5b_security": "agent_5b_security",
        },
    )

    graph.add_edge("agent_4_tool_router", "agent_5_coord_review")
    graph.add_edge("agent_7_cicd", "agent_8_deploy")
    graph.set_entry_point("agent_4_tool_router")
    graph.set_finish_point("agent_8_deploy")

    logger.info("build_graph.complete", nodes=list(_agents.keys()))
    return graph
