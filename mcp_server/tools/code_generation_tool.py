from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from fastmcp import Context

from interpret.gate import check_gate

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
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
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


def _build_codegen_infrastructure() -> tuple:
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
    from tool_router.router import ToolRouter
    from workspace.bridge import WorkspaceBridge
    from workspace.diff_engine import DiffEngine

    model_router = ModelRouter()
    tool_router = ToolRouter()
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
        model_router, tool_router, cwm, memory_archiver,
        memory_ctx_builder, cfm, workspace_bridge, diff_engine,
    )


def _build_codegen_agents(infra: tuple) -> tuple:
    from agents.agent_4_tool_router import ToolRouterAgent
    from agents.agent_5_coord_review import CoordinatedReview

    (
        model_router, tool_router, cwm, memory_archiver,
        memory_ctx_builder, cfm, workspace_bridge, diff_engine,
    ) = infra

    base_kwargs = {
        "context_window_manager": cwm,
        "model_router": model_router,
        "memory_archiver": memory_archiver,
        "memory_context_builder": memory_ctx_builder,
        "context_file_manager": cfm,
        "workspace_bridge": workspace_bridge,
        "diff_engine": diff_engine,
    }

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
    infra = _build_codegen_infrastructure()
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
                        state["interpret_log"][-1]
                        if state.get("interpret_log") else {}
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
                    state["interpret_log"][-1]
                    if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "project_id": project_id,
                "instructions": (
                    "Review the code quality report. "
                    "Pass human_confirmation='100% GO' to accept."
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
            1 for f in list(state.get("review_findings", []) or [])
            if f.get("severity") == "BLOCKING"
        ),
        "advisory_count": sum(
            1 for f in list(state.get("review_findings", []) or [])
            if f.get("severity") == "ADVISORY"
        ),
    }