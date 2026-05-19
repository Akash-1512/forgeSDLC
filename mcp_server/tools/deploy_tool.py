from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

from orchestrator.constants import CHECKPOINT_DB_PATH
from subscription.tiers import FREE

try:
    from fastmcp import Context
except ImportError:  # pragma: no cover
    Context = object  # type: ignore[assignment,misc]

from mcp_server.tier_resolver import resolve_tier as _resolve_tier

logger = structlog.get_logger()


def _build_deploy_state(
    project_id: str, environment: str, human_confirmation: str
) -> dict[str, object]:
    import sqlite3
    import uuid
    from pathlib import Path

    # Load security gate from checkpoint so deploy respects a prior scan
    security_gate_from_checkpoint: dict[str, object] | None = None
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        Path("./data").mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False) as conn:
            checkpointer = SqliteSaver(conn)
            config = {"configurable": {"thread_id": project_id}}
            existing = checkpointer.get(config)
            if existing and existing.get("channel_values"):
                security_gate_from_checkpoint = existing["channel_values"].get("security_gate")
    except (KeyError, TypeError, OSError):
        pass  # no checkpoint — gate defaults to None (unscanned)

    return {
        "user_prompt": f"Deploy to {environment}",
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
        "generated_files": [],
        "review_findings": [],
        "security_findings": None,
        "security_gate": security_gate_from_checkpoint,
        "deployment_url": None,
        "deploy_blocked": False,
        "deploy_blocked_reason": "",
        "monitoring_config": None,
        "ci_pipeline_url": "",
        "tool_delegated_to": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": FREE.budget_usd_per_session,
        "subscription_tier": _resolve_tier(),
        "session_token_records": [],
        "tool_router_context": None,
        "model_router_context": None,
        "workspace_context": None,
        "memory_context": None,
        "arch_validation": None,
        "test_coverage": 0.0,
        "project_context_graph": None,
        "hitl_required": False,
        "hitl_reason": "",
    }


def _build_infrastructure_shared() -> object:
    """Instantiate the shared components needed by the deployment pipeline."""
    from mcp_server.shared_infrastructure import build_infrastructure  # noqa: PLC0415

    return build_infrastructure()


def _build_deploy_agent(infra: object) -> object:
    from agents.agent_8_deploy import DeployAgent

    return DeployAgent(
        name="agent_8_deploy",
        context_window_manager=infra.context_window_manager,
        model_router=infra.model_router,
        memory_archiver=infra.memory_archiver,
        memory_context_builder=infra.memory_context_builder,
        context_file_manager=infra.context_file_manager,
        workspace_bridge=infra.workspace_bridge,
        diff_engine=infra.diff_engine,
    )


async def deploy_project(
    project_id: str,
    ctx: Context,
    environment: str = "production",
    workspace_path: str = ".",
    human_confirmation: str = "",
) -> dict[str, object]:
    """Deploy the project to Render or local Docker.

    Security gate is enforced — if not cleared, returns blocked status.
    Writes PostMortem to Layer 5 on deployment failure.

    CALL PATTERN:
    Call 1: project_id="proj-1", environment="production"
            → {"status": "awaiting_confirmation", ...} or {"status": "blocked", ...}
    Call 2: human_confirmation="100% GO"
            → Agent 8 executes (Dockerfile + Render deploy)
            → {"status": "complete", "deployment_url": "...", ...}
    """
    await ctx.report_progress(0, 100, "Initialising deployment pipeline")
    logger.info(
        "deploy_project.called",
        project_id=project_id,
        environment=environment,
        has_confirmation=bool(human_confirmation),
    )

    # Restore or initialise state
    try:
        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"deploy-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
        else:
            state = _build_deploy_state(project_id, environment, human_confirmation)
    except Exception as exc:  # noqa: BLE001 — MCP tools must never crash the server
        logger.warning("deploy_project.checkpointer_failed", error=str(exc))
        state = _build_deploy_state(project_id, environment, human_confirmation)

    state["human_confirmation"] = human_confirmation

    infra = _build_infrastructure_shared()
    agent_8 = _build_deploy_agent(infra)

    await ctx.report_progress(20, 100, "Running deployment agent")
    state = await agent_8.run(state)  # type: ignore[union-attr]

    # Security gate blocked
    if state.get("deploy_blocked"):
        await ctx.report_progress(100, 100, "Deployment blocked by security gate")
        return {
            "status": "blocked",
            "project_id": project_id,
            "reason": state.get("deploy_blocked_reason", ""),
            "instructions": (
                "Run run_security_scan() and resolve all HIGH/CRITICAL findings, "
                "then re-call deploy_project()."
            ),
        }

    # Awaiting confirmation (interpret ran, execute did not)
    if state.get("deployment_url") is None and not state.get("deploy_blocked"):
        if not state.get("interpret_log"):
            return {
                "status": "awaiting_confirmation",
                "stage": "deployment",
                "project_id": project_id,
                "instructions": "Pass human_confirmation='100% GO' to deploy.",
            }
        return {
            "status": "awaiting_confirmation",
            "stage": "deployment",
            # Safe — interpret_log is guaranteed non-empty by the guard above
            "interpretation": state["interpret_log"][-1] if state.get("interpret_log") else {},
            "displayed_interpretation": state.get("displayed_interpretation", ""),
            "project_id": project_id,
            "instructions": (
                "Review the deployment plan. Pass human_confirmation='100% GO' to proceed."
            ),
        }

    await ctx.report_progress(100, 100, "Deployment complete")
    logger.info("deploy_project.complete", project_id=project_id)

    return {
        "status": "complete",
        "project_id": project_id,
        "deployment_url": state.get("deployment_url"),
        "environment": environment,
        "dockerfile_written": True,
        "health_check_passed": state.get("deployment_url") is not None,
    }
