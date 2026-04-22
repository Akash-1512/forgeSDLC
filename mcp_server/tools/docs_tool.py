from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from fastmcp import Context

logger = structlog.get_logger()


def _build_docs_state(project_id: str, human_confirmation: str, scope: str) -> dict[str, object]:
    import uuid

    return {
        "user_prompt": f"Generate documentation for project {project_id}",
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
        "monitoring_config": None,
        "project_context_graph": None,
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
        "hitl_required": False,
        "hitl_reason": "",
        "scope": scope,
    }


def _build_docs_infrastructure() -> tuple:
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


def _build_docs_agent(infra: tuple) -> object:
    from agents.agent_10_docs import DocsAgent

    (
        model_router,
        cwm,
        memory_archiver,
        memory_ctx_builder,
        cfm,
        workspace_bridge,
        diff_engine,
    ) = infra
    return DocsAgent(
        name="agent_10_docs",
        context_window_manager=cwm,
        model_router=model_router,
        memory_archiver=memory_archiver,
        memory_context_builder=memory_ctx_builder,
        context_file_manager=cfm,
        workspace_bridge=workspace_bridge,
        diff_engine=diff_engine,
    )


async def generate_docs(
    project_id: str,
    ctx: Context,
    scope: str = "full",
    human_confirmation: str = "",
) -> dict[str, object]:
    """Generate README, CHANGELOG, and build ProjectContextGraph.

    Performs comprehensive 5-layer memory archive.
    Sets pipeline_complete=True — marks single-service SDLC as done.
    ProjectContextGraph saved to Layer 3 — recall_context() now returns
    rich structured context for this project on all future calls.

    Model: claude-sonnet-4-6 (BYOK) | gpt-5.4-mini (default) → groq
    Attribution "Built with forgeSDLC" always present in README.

    CALL PATTERN:
    Call 1: project_id="proj-1", scope="full"
            → {"status": "awaiting_confirmation", "stage": "documentation", ...}
    Call 2: human_confirmation="100% GO"
            → {"status": "complete", "pipeline_complete": True, ...}
    """
    await ctx.report_progress(0, 100, "Loading project state for documentation")
    logger.info(
        "generate_docs.called",
        project_id=project_id,
        scope=scope,
        has_confirmation=bool(human_confirmation),
    )

    # Restore or initialise state
    try:
        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"docs-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
            logger.info("generate_docs.state_restored", project_id=project_id)
        else:
            state = _build_docs_state(project_id, human_confirmation, scope)
    except Exception as exc:
        logger.warning("generate_docs.checkpointer_failed", error=str(exc))
        state = _build_docs_state(project_id, human_confirmation, scope)

    state["human_confirmation"] = human_confirmation

    # Build infrastructure and agent
    infra = _build_docs_infrastructure()
    agent_10 = _build_docs_agent(infra)

    # Run Agent 10
    await ctx.report_progress(20, 100, "Generating documentation")
    state = await agent_10.run(state)  # type: ignore[union-attr]

    # Awaiting confirmation (interpret ran, execute did not)
    if not state.get("project_context_graph"):
        return {
            "status": "awaiting_confirmation",
            "stage": "documentation",
            "interpretation": (state["interpret_log"][-1] if state.get("interpret_log") else {}),
            "displayed_interpretation": state.get("displayed_interpretation", ""),
            "project_id": project_id,
            "instructions": (
                "Review the documentation plan. "
                "Pass human_confirmation='100% GO' to generate README, CHANGELOG, "
                "and save ProjectContextGraph."
            ),
        }

    await ctx.report_progress(100, 100, "Documentation complete — pipeline done")
    logger.info("generate_docs.complete", project_id=project_id)

    return {
        "status": "complete",
        "project_id": project_id,
        "files_written": ["README.md", "CHANGELOG.md"],
        "project_context_graph": state.get("project_context_graph"),
        "memory_archived": True,
        "pipeline_complete": True,  # single-service SDLC fully complete
        "attribution": "Built with forgeSDLC — https://github.com/Akash-1512/forgesdlc",
        "next_steps": (
            "Your project is deployed and documented. "
            "Use recall_context() to retrieve rich project context on future calls. "
            "For multi-service projects, continue with Agents 11-13."
        ),
    }
