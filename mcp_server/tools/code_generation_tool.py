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


def _build_codegen_state(
    task: str, project_id: str, workspace_path: str, human_confirmation: str
) -> dict[str, object]:
    import uuid

    return {
        "user_prompt": task,
        "mcp_session_id": project_id,
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "displayed_interpretation": "",
        "interpret_round": 0,
        "interpret_log": [],
        "trace_id": str(uuid.uuid4()),
        "mode": "mcp",
        "prd": task,
        "adr": "",
        "rfc": "",
        "service_graph": {"services": []},
        "generated_files": None,
        "review_findings": [],
        "tool_delegated_to": None,
        "tool_retry_count": 0,
        "review_delegation_count": 0,
        "review_corrections": "",
        "trigger_agent_4_retry": False,
        "hitl_required": False,
        "hitl_reason": "",
        "workspace_path": workspace_path,
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
        "arch_validation": None,
        "security_findings": None,
        "security_gate": None,
        "test_coverage": 0.0,
        "ci_pipeline_url": "",
        "deployment_url": None,
        "monitoring_config": None,
        "project_context_graph": None,
    }


def _build_infrastructure_shared() -> tuple:
    """H2 Fix: delegate to shared infrastructure factory."""
    from mcp_server.shared_infrastructure import build_infrastructure  # noqa: PLC0415
    from tool_router.router import ToolRouter  # noqa: PLC0415

    infra = build_infrastructure()
    tool_router = ToolRouter()
    return (
        infra.model_router,
        tool_router,
        infra.context_window_manager,
        infra.memory_archiver,
        infra.memory_context_builder,
        infra.context_file_manager,
        infra.workspace_bridge,
        infra.diff_engine,
    )


def _build_codegen_agents(infra: tuple) -> tuple:
    from agents.agent_4_tool_router import ToolRouterAgent
    from agents.agent_5_coord_review import CoordinatedReview
    from mcp_server.shared_infrastructure import build_agent_kwargs  # noqa: PLC0415
    from tool_router.router import ToolRouter  # noqa: PLC0415

    (
        model_router,
        tool_router,
        cwm,
        memory_archiver,
        memory_ctx_builder,
        cfm,
        workspace_bridge,
        diff_engine,
    ) = infra
    tool_router = ToolRouter()
    base_kwargs = build_agent_kwargs(infra)

    agent_4 = ToolRouterAgent(
        name="agent_4_tool_router",
        tool_router=tool_router,
        **base_kwargs,
    )
    agent_5 = CoordinatedReview(
        name="agent_5_coord_review",
        **base_kwargs,
    )
    return agent_4, agent_5


async def route_code_generation(
    task: str,
    project_id: str,
    ctx: Context,
    workspace_path: str = ".",
    human_confirmation: str = "",
) -> dict[str, object]:
    """Delegate code generation to the best available AI coding tool,
    then validate output against MAANG standards via 5-pass review.

    CALL PATTERN:
    Call 1: task="implement auth service", project_id="proj-1"
            → {"status": "awaiting_confirmation", "stage": "code_generation", ...}
    Call 2: human_confirmation="100% GO"
            → Agent 4 executes (writes context files then delegates)
            → {"status": "awaiting_confirmation", "stage": "code_review", ...}
    Call 3: human_confirmation="100% GO"
            → Agent 5 executes (5-pass review)
            → {"status": "complete", ...} or re-delegates to Agent 4 if BLOCKING
    """
    await ctx.report_progress(0, 100, "Initialising code generation pipeline")
    logger.info(
        "route_code_generation.called",
        project_id=project_id,
        has_confirmation=bool(human_confirmation),
    )

    # Restore or initialise state
    try:
        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"codegen-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
        else:
            state = _build_codegen_state(task, project_id, workspace_path, human_confirmation)
    except Exception as exc:
        logger.warning("route_code_generation.checkpointer_failed", error=str(exc))
        state = _build_codegen_state(task, project_id, workspace_path, human_confirmation)

    state["human_confirmation"] = human_confirmation

    # Build infrastructure and agents
    infra = _build_infrastructure_shared()
    agent_4, agent_5 = _build_codegen_agents(infra)

    # ── Retry loop: Agent 4 re-delegation driven by Agent 5 findings ────────
    max_loops = 3  # safety cap
    loop_count = 0

    while loop_count < max_loops:
        loop_count += 1

        # ── Agent 4: Code generation delegation ─────────────────────────────
        if not state.get("generated_files"):
            await ctx.report_progress(20, 100, "Delegating to coding tool")
            state = await agent_4.run(state)
            if not state.get("generated_files"):
                return {
                    "status": "awaiting_confirmation",
                    "stage": "code_generation",
                    "interpretation": (
                        state["interpret_log"][-1] if state.get("interpret_log") else {}
                    ),
                    "displayed_interpretation": state.get("displayed_interpretation", ""),
                    "project_id": project_id,
                    "instructions": (
                        "Review the code generation plan. "
                        "Pass human_confirmation='100% GO' to proceed."
                    ),
                }

        # Check HITL escalation from Agent 4
        if state.get("hitl_required"):
            return {
                "status": "hitl_required",
                "project_id": project_id,
                "reason": state.get("hitl_reason", ""),
                "instructions": "Manual intervention required. Review and correct the task.",
            }

        # ── Agent 5: 5-pass code review ──────────────────────────────────────
        state["human_confirmation"] = human_confirmation
        await ctx.report_progress(60, 100, "Running 5-pass code review")
        state = await agent_5.run(state)

        if not state.get("review_findings") and not state.get("trigger_agent_4_retry"):
            return {
                "status": "awaiting_confirmation",
                "stage": "code_review",
                "interpretation": (
                    state["interpret_log"][-1] if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "project_id": project_id,
                "instructions": (
                    "Review the code quality report. Pass human_confirmation='100% GO' to accept."
                ),
            }

        # Check HITL escalation from Agent 5
        if state.get("hitl_required"):
            return {
                "status": "hitl_required",
                "project_id": project_id,
                "reason": state.get("hitl_reason", ""),
                "review_findings": state.get("review_findings", []),
                "instructions": "Manual intervention required after 2 re-delegations.",
            }

        # Agent 5 triggered retry → clear generated files and re-run Agent 4
        if state.get("trigger_agent_4_retry"):
            logger.info(
                "route_code_generation.agent_4_retry",
                loop=loop_count,
                corrections=str(state.get("review_corrections", ""))[:100],
            )
            state["trigger_agent_4_retry"] = False
            state["generated_files"] = None
            state["human_confirmation"] = "100% GO"  # auto-approve Agent 4 retry
            continue

        # No blocking findings — complete
        break

    await ctx.report_progress(100, 100, "Code generation and review complete")
    logger.info("route_code_generation.complete", project_id=project_id)

    return {
        "status": "complete",
        "project_id": project_id,
        "tool_used": state.get("tool_delegated_to"),
        "generated_files": state.get("generated_files", []),
        "review_findings": state.get("review_findings", []),
        "blocking_count": sum(
            1
            for f in list(state.get("review_findings", []) or [])
            if f.get("severity") == "BLOCKING"
        ),
        "advisory_count": sum(
            1
            for f in list(state.get("review_findings", []) or [])
            if f.get("severity") == "ADVISORY"
        ),
    }
