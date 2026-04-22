from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from fastmcp import Context

logger = structlog.get_logger()


def _build_deploy_state(
    project_id: str, environment: str, human_confirmation: str
) -> dict[str, object]:
    import uuid

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
        "security_gate": None,
        "deployment_url": None,
        "deploy_blocked": False,
        "deploy_blocked_reason": "",
        "monitoring_config": None,
        "ci_pipeline_url": "",
        "tool_delegated_to": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
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


def _build_deploy_infrastructure() -> tuple:
    from context_files.manager import ContextFileManager
    from context_management.agent_context_specs import AGENT_CONTEXT_SPECS
    from context_management.context_compressor import ContextCompressor
    from context_management.context_window_manager import ContextWindowManager
    from context_management.token_estimator import TokenEstimator
    from memory.memory_archiver import MemoryArchiver
    from memory.memory_context_builder import MemoryContextBuilder
    from memory.organisational_memory import OrgMemory
    from memory.pipeline_history_store import PipelineHistoryStore
    from memory.post_mortem_records import PostMortemStore
    from memory.project_context_graph import ProjectContextGraphStore
    from memory.user_preference_profile import UserPreferenceStore
    from model_router.router import ModelRouter
    from workspace.bridge import WorkspaceBridge
    from workspace.diff_engine import DiffEngine

    model_router = ModelRouter()
    estimator = TokenEstimator()
    compressor = ContextCompressor()
    cwm = ContextWindowManager(
        estimator=estimator,
        compressor=compressor,
        specs=AGENT_CONTEXT_SPECS,
    )
    l1 = PipelineHistoryStore()
    l2 = OrgMemory()
    l3 = ProjectContextGraphStore()
    l4 = UserPreferenceStore()
    l5 = PostMortemStore()
    memory_archiver = MemoryArchiver(l1, l2, l3, l4, l5)
    memory_ctx_builder = MemoryContextBuilder()
    cfm = ContextFileManager()
    workspace_bridge = WorkspaceBridge()
    diff_engine = DiffEngine()

    return (
        model_router,
        cwm,
        memory_archiver,
        memory_ctx_builder,
        cfm,
        workspace_bridge,
        diff_engine,
    )


def _build_deploy_agent(infra: tuple) -> object:
    from agents.agent_8_deploy import DeployAgent

    (
        model_router,
        cwm,
        memory_archiver,
        memory_ctx_builder,
        cfm,
        workspace_bridge,
        diff_engine,
    ) = infra
    return DeployAgent(
        name="agent_8_deploy",
        context_window_manager=cwm,
        model_router=model_router,
        memory_archiver=memory_archiver,
        memory_context_builder=memory_ctx_builder,
        context_file_manager=cfm,
        workspace_bridge=workspace_bridge,
        diff_engine=diff_engine,
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
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"deploy-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
        else:
            state = _build_deploy_state(project_id, environment, human_confirmation)
    except Exception as exc:
        logger.warning("deploy_project.checkpointer_failed", error=str(exc))
        state = _build_deploy_state(project_id, environment, human_confirmation)

    state["human_confirmation"] = human_confirmation

    infra = _build_deploy_infrastructure()
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
            "interpretation": state["interpret_log"][-1],
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
