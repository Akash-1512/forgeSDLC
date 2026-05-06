from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

try:
    from fastmcp import Context
except ImportError:  # pragma: no cover
    Context = object  # type: ignore[assignment,misc]

from mcp_server.tier_resolver import resolve_tier as _resolve_tier

logger = structlog.get_logger()


def _build_monitor_state(
    project_id: str, deployment_url: str, human_confirmation: str
) -> dict[str, object]:
    import uuid

    return {
        "user_prompt": f"Setup monitoring for {deployment_url}",
        "mcp_session_id": project_id,
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "displayed_interpretation": "",
        "interpret_round": 0,
        "interpret_log": [],
        "trace_id": str(uuid.uuid4()),
        "mode": "mcp",
        "prd": "",
        "adr": "",
        "rfc": "",
        "service_graph": {"services": []},
        "deployment_url": deployment_url or None,
        "monitoring_config": None,
        "security_gate": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": __import__("subscription.tiers", fromlist=["get_tier"])
        .get_tier("free")
        .budget_usd_per_session
        if True
        else 5.0,
        "subscription_tier": _resolve_tier(),
        "session_token_records": [],
        "tool_router_context": None,
        "model_router_context": None,
        "workspace_context": None,
        "memory_context": None,
        "generated_files": [],
        "review_findings": [],
        "security_findings": None,
        "arch_validation": None,
        "test_coverage": 0.0,
        "ci_pipeline_url": "",
        "tool_delegated_to": None,
        "project_context_graph": None,
        "hitl_required": False,
        "hitl_reason": "",
    }


def _build_infrastructure_shared() -> tuple:
    """Build infrastructure using the shared factory."""
    from mcp_server.shared_infrastructure import build_infrastructure  # noqa: PLC0415

    infra = build_infrastructure()
    return (
        infra.model_router,
        infra.context_window_manager,
        infra.memory_archiver,
        infra.memory_context_builder,
        infra.context_file_manager,
        infra.workspace_bridge,
        infra.diff_engine,
    )


def _build_monitor_agent(infra: tuple) -> object:
    from agents.agent_9_monitoring import MonitoringAgent

    (
        model_router,
        cwm,
        memory_archiver,
        memory_ctx_builder,
        cfm,
        workspace_bridge,
        diff_engine,
    ) = infra
    return MonitoringAgent(
        name="agent_9_monitor",
        context_window_manager=cwm,
        model_router=model_router,
        memory_archiver=memory_archiver,
        memory_context_builder=memory_ctx_builder,
        context_file_manager=cfm,
        workspace_bridge=workspace_bridge,
        diff_engine=diff_engine,
    )


async def setup_monitoring(
    project_id: str,
    ctx: Context,
    deployment_url: str = "",
    human_confirmation: str = "",
) -> dict[str, object]:
    """Generate SLO definitions, runbook, on-call playbook, and OTel config.

    Model: groq/llama-3.3-70b-versatile (NOT gpt-4o-mini).
    SLOs extracted from PRD NFRs (keyword-based, zero LLM).
    Runbook written to docs/ops/runbook.md via DiffEngine.

    CALL PATTERN:
    Call 1: project_id="proj-1", deployment_url="https://myapp.onrender.com"
            → {"status": "awaiting_confirmation", ...}
    Call 2: human_confirmation="100% GO"
            → {"status": "complete", "monitoring_config": {...}, ...}
    """
    await ctx.report_progress(0, 100, "Initialising monitoring setup")
    logger.info(
        "setup_monitoring.called",
        project_id=project_id,
        deployment_url=deployment_url,
        has_confirmation=bool(human_confirmation),
    )

    # Restore or initialise state
    try:
        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"monitor-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
        else:
            state = _build_monitor_state(project_id, deployment_url, human_confirmation)
    except Exception as exc:
        logger.warning("setup_monitoring.checkpointer_failed", error=str(exc))
        state = _build_monitor_state(project_id, deployment_url, human_confirmation)

    if deployment_url:
        state["deployment_url"] = deployment_url
    state["human_confirmation"] = human_confirmation

    infra = _build_infrastructure_shared()
    agent_9 = _build_monitor_agent(infra)

    await ctx.report_progress(20, 100, "Running monitoring agent")
    state = await agent_9.run(state)  # type: ignore[union-attr]

    if not state.get("monitoring_config"):
        return {
            "status": "awaiting_confirmation",
            "stage": "monitoring_setup",
            "interpretation": (state["interpret_log"][-1] if state.get("interpret_log") else {}),
            "displayed_interpretation": state.get("displayed_interpretation", ""),
            "project_id": project_id,
            "instructions": (
                "Review the monitoring setup plan. "
                "Pass human_confirmation='100% GO' to generate runbook and SLOs."
            ),
        }

    await ctx.report_progress(100, 100, "Monitoring setup complete")
    logger.info("setup_monitoring.complete", project_id=project_id)

    monitoring_config = dict(state.get("monitoring_config") or {})
    return {
        "status": "complete",
        "project_id": project_id,
        "deployment_url": deployment_url,
        "monitoring_config": monitoring_config,
        "slo_count": len(monitoring_config.get("slo_definitions", [])),
        "runbook_path": monitoring_config.get("runbook_path"),
        "otel_configured": monitoring_config.get("otel_configured", False),
    }
