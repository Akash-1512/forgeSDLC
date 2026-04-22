from __future__ import annotations

import structlog
from fastmcp import Context

logger = structlog.get_logger()


def _build_initial_state(prompt: str, project_id: str) -> dict[str, object]:
    """Build a fresh SDLCState for a new project."""
    import uuid

    return {
        "user_prompt": prompt,
        "mcp_session_id": project_id,
        "human_confirmation": "",
        "human_corrections": [],
        "displayed_interpretation": "",
        "interpret_round": 0,
        "interpret_log": [],
        "trace_id": str(uuid.uuid4()),
        "tool_router_context": None,
        "model_router_context": None,
        "workspace_context": None,
        "memory_context": None,
        "mode": "mcp",
        "service_graph": None,
        "prd": "",
        "adr": "",
        "rfc": "",
        "generated_files": [],
        "review_findings": [],
        "security_findings": None,
        "security_gate": None,
        "test_coverage": 0.0,
        "ci_pipeline_url": "",
        "deployment_url": None,
        "monitoring_config": None,
        "project_context_graph": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
        "session_token_records": [],
        "tool_delegated_to": None,
        "_agent0_raw": "",
    }


def _build_infrastructure() -> tuple:
    """Instantiate all infrastructure components."""
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


def _build_agents(infra: tuple) -> tuple:
    """Instantiate Agents 0, 1, 2."""
    from agents.agent_0_decompose import ServiceDecompositionAgent
    from agents.agent_1_requirements import RequirementsAgent
    from agents.agent_2_stack import TechStackAgent

    model_router, cwm, memory_archiver, memory_ctx_builder, cfm, workspace_bridge, diff_engine = (
        infra
    )

    kwargs = {
        "context_window_manager": cwm,
        "model_router": model_router,
        "memory_archiver": memory_archiver,
        "memory_context_builder": memory_ctx_builder,
        "context_file_manager": cfm,
        "workspace_bridge": workspace_bridge,
        "diff_engine": diff_engine,
    }
    agent_0 = ServiceDecompositionAgent(name="agent_0_decompose", **kwargs)
    agent_1 = RequirementsAgent(name="agent_1_requirements", **kwargs)
    agent_2 = TechStackAgent(name="agent_2_stack", **kwargs)
    return agent_0, agent_1, agent_2


async def gather_requirements(
    prompt: str,
    project_id: str,
    ctx: Context,
    human_confirmation: str = "",
    correction: str = "",
) -> dict[str, object]:
    """Convert a natural language description into structured requirements (PRD).

    Runs Agents 0→1→2 with HITL gate between each stage.
    State is persisted via SqliteSaver between calls (project_id = thread_id).

    CALL PATTERN (stateful — multiple calls per pipeline):
    Call 1: prompt="build a todo app", project_id="proj-1"
            → {"status": "awaiting_confirmation", "stage": "decomposition", ...}
    Call 2: human_confirmation="100% GO"
            → Agent 0 executes, Agent 1 interprets
            → {"status": "awaiting_confirmation", "stage": "requirements", ...}
    Call 3: human_confirmation="100% GO"
            → Agent 1 executes, Agent 2 interprets
            → {"status": "awaiting_confirmation", "stage": "stack_discussion", ...}
    Call 4: human_confirmation="100% GO"
            → Agent 2 executes
            → {"status": "complete", "prd": "...", "adr": "...", ...}
    """
    await ctx.report_progress(0, 100, "Loading pipeline state")
    logger.info(
        "gather_requirements.called",
        project_id=project_id,
        has_confirmation=bool(human_confirmation),
        has_correction=bool(correction),
    )

    # SqliteSaver for LangGraph HITL checkpointing
    # NOTE: SqliteSaver is LangGraph's checkpoint mechanism — NOT our application DB
    try:
        from pathlib import Path  # noqa: PLC0415

        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        Path("./data").mkdir(parents=True, exist_ok=True)
        import sqlite3  # noqa: PLC0415

        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": project_id}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
            logger.info("gather_requirements.state_restored", project_id=project_id)
        else:
            state = _build_initial_state(prompt, project_id)
    except Exception as exc:
        logger.warning("gather_requirements.checkpointer_failed", error=str(exc))
        state = _build_initial_state(prompt, project_id)

    # Simple JSON state persistence (SqliteSaver reads but doesn't auto-save here)
    _state_file = f"./data/state_{project_id}.json"

    def _save_state(s: dict) -> None:
        try:
            import json as j
            import pathlib as pl  # noqa: PLC0415

            pl.Path("./data").mkdir(parents=True, exist_ok=True)
            pl.Path(_state_file).write_text(j.dumps(s, default=str))
        except Exception:
            pass

    def _load_state() -> dict | None:
        try:
            import json as j
            import pathlib as pl  # noqa: PLC0415

            p = pl.Path(_state_file)
            if p.exists():
                return j.loads(p.read_text())
        except Exception:
            pass
        return None

    # Try to restore from JSON file first (more reliable than SqliteSaver)
    _saved = _load_state()
    if _saved:
        state = _saved
        logger.info("gather_requirements.json_state_restored", project_id=project_id)

    # Apply human confirmation and correction to state
    state["human_confirmation"] = human_confirmation
    if correction:
        corrections = list(state.get("human_corrections", []) or [])
        if corrections:
            corrections[-1] = correction
        else:
            corrections.append(correction)
        state["human_corrections"] = corrections

    # Build infrastructure and agents
    infra = _build_infrastructure()
    agent_0, agent_1, agent_2 = _build_agents(infra)

    # ── Agent 0: Service Decomposition ────────────────────────────────────
    if not state.get("service_graph"):
        await ctx.report_progress(10, 100, "Analysing project scope")
        state = await agent_0.run(state)
        _save_state(state)
        if not state.get("service_graph"):
            return {
                "status": "awaiting_confirmation",
                "stage": "decomposition",
                "interpretation": (
                    state["interpret_log"][-1] if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "instructions": (
                    "Review the scope analysis. "
                    "Pass human_confirmation='100% GO' to proceed, "
                    "or pass correction='<your feedback>' to refine."
                ),
                "project_id": project_id,
            }

    # ── Agent 1: Requirements ─────────────────────────────────────────────
    if not state.get("prd"):
        state["human_confirmation"] = human_confirmation
        await ctx.report_progress(40, 100, "Generating requirements")
        state = await agent_1.run(state)
        if not state.get("service_graph"):
            return {
                "status": "awaiting_confirmation",
                "stage": "requirements",
                "interpretation": (
                    state["interpret_log"][-1] if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "instructions": (
                    "Review the PRD interpretation. "
                    "Pass human_confirmation='100% GO' to generate the full PRD."
                ),
                "project_id": project_id,
            }

    # ── Agent 2: Tech Stack ───────────────────────────────────────────────
    if not state.get("service_graph"):
        state["human_confirmation"] = human_confirmation
        await ctx.report_progress(70, 100, "Recommending tech stack")
        state = await agent_2.run(state)
        if not state.get("prd"):
            return {
                "status": "awaiting_confirmation",
                "stage": "stack_discussion",
                "interpretation": (
                    state["interpret_log"][-1] if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "instructions": (
                    "Review the stack recommendation. "
                    "Pass human_confirmation='100% GO' to generate ADR-001."
                ),
                "project_id": project_id,
            }

    await ctx.report_progress(100, 100, "Requirements pipeline complete")
    logger.info("gather_requirements.complete", project_id=project_id)

    return {
        "status": "complete",
        "project_id": project_id,
        "prd": state.get("prd", ""),
        "adr": state.get("adr", ""),
        "service_graph": state.get("service_graph", {}),
        "files_written": [
            "docs/requirements/PRD.md",
            "docs/decisions/ADR-001-tech-stack.md",
        ],
        "context_files_updated": ["AGENTS.md", "CLAUDE.md", ".cursorrules"],
        "interpret_log": state.get("interpret_log", []),
        "interpret_rounds": int(state.get("interpret_round", 0) or 0),
    }
