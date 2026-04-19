from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from fastmcp import Context

from interpret.gate import check_gate

logger = structlog.get_logger()


def _build_cicd_state(
    project_id: str, stack: str, human_confirmation: str
) -> dict[str, object]:
    import uuid
    return {
        "user_prompt": f"Generate CI/CD for {stack}",
        "mcp_session_id": project_id,
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "displayed_interpretation": "",
        "interpret_round": 0,
        "interpret_log": [],
        "trace_id": str(uuid.uuid4()),
        "mode": "mcp",
        "prd": "",
        "adr": f"Stack: {stack}",
        "rfc": "",
        "service_graph": {"services": []},
        "generated_files": [],
        "review_findings": [],
        "security_findings": None,
        "security_gate": None,
        "test_coverage": 0.0,
        "test_retry_count": 0,
        "test_retry_needed": False,
        "test_uncovered_lines": [],
        "ci_pipeline_url": "",
        "deployment_url": None,
        "monitoring_config": None,
        "project_context_graph": None,
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
        "hitl_required": False,
        "hitl_reason": "",
        "review_delegation_count": 0,
        "review_corrections": "",
        "trigger_agent_4_retry": False,
    }


def _build_cicd_infrastructure() -> tuple:
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


def _build_cicd_agents(infra: tuple) -> tuple:
    from agents.agent_6_test_coordinator import TestCoordinatorAgent
    from agents.agent_7_cicd import CICDAgent

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

    agent_6 = TestCoordinatorAgent(
        name="agent_6_test_coord",
        tool_router=tool_router,
        **base_kwargs,
    )
    agent_7 = CICDAgent(
        name="agent_7_cicd",
        **base_kwargs,
    )
    return agent_6, agent_7


async def generate_cicd(
    project_id: str,
    ctx: Context,
    stack: str = "fastapi",
    workspace_path: str = ".",
    human_confirmation: str = "",
) -> dict[str, object]:
    """Generate GitHub Actions CI/CD workflow with verified action versions.

    Runs Agent 6 (test coordination + coverage gate) then Agent 7 (CI YAML).
    Action versions fetched from GitHub Releases API via DocsFetcher (24h cache).

    Generated YAML:
    - ruff for linting (NOT black, NOT isort)
    - semgrep --config=p/python --config=p/security (NOT --config=auto)
    - Node.js 24 (NOT 20)
    - Python 3.12
    - PostgreSQL 16 service container

    CALL PATTERN:
    Call 1: project_id="proj-1", stack="fastapi"
            → {"status": "awaiting_confirmation", "stage": "test_generation", ...}
    Call 2: human_confirmation="100% GO"
            → Agent 6 executes (delegates test gen, measures coverage)
            → {"status": "awaiting_confirmation", "stage": "cicd_generation", ...}
    Call 3: human_confirmation="100% GO"
            → Agent 7 executes (fetches versions, generates YAML, writes file)
            → {"status": "complete", "ci_yaml_path": ".github/workflows/ci.yml", ...}
    """
    await ctx.report_progress(0, 100, "Initialising CI/CD pipeline")
    logger.info(
        "generate_cicd.called",
        project_id=project_id,
        stack=stack,
        has_confirmation=bool(human_confirmation),
    )

    # Restore or initialise state
    try:
        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415
        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"cicd-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
        else:
            state = _build_cicd_state(project_id, stack, human_confirmation)
    except Exception as exc:
        logger.warning("generate_cicd.checkpointer_failed", error=str(exc))
        state = _build_cicd_state(project_id, stack, human_confirmation)

    state["human_confirmation"] = human_confirmation

    # Build infrastructure and agents
    infra = _build_cicd_infrastructure()
    agent_6, agent_7 = _build_cicd_agents(infra)

    # ── Agent 6: Test generation + coverage gate ─────────────────────────────
    if not state.get("ci_pipeline_url") and state.get("test_retry_needed") is not True:
        await ctx.report_progress(20, 100, "Delegating test generation")
        state = await agent_6.run(state)

        if not state.get("generated_files") and not state.get("test_retry_needed"):
            return {
                "status": "awaiting_confirmation",
                "stage": "test_generation",
                "interpretation": (
                    state["interpret_log"][-1] if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "project_id": project_id,
                "instructions": (
                    "Review the test generation plan. "
                    "Pass human_confirmation='100% GO' to proceed."
                ),
            }

        if state.get("hitl_required"):
            return {
                "status": "hitl_required",
                "project_id": project_id,
                "reason": state.get("hitl_reason", ""),
                "coverage": state.get("test_coverage", 0.0),
                "instructions": "Test coverage below 80% after 3 retries. Manual intervention required.",
            }

    # ── Agent 7: CI/CD YAML generation ──────────────────────────────────────
    if not state.get("ci_pipeline_url"):
        state["human_confirmation"] = human_confirmation
        await ctx.report_progress(60, 100, "Generating CI/CD YAML")
        state = await agent_7.run(state)

        if not state.get("ci_pipeline_url"):
            return {
                "status": "awaiting_confirmation",
                "stage": "cicd_generation",
                "interpretation": (
                    state["interpret_log"][-1] if state.get("interpret_log") else {}
                ),
                "displayed_interpretation": state.get("displayed_interpretation", ""),
                "project_id": project_id,
                "instructions": (
                    "Review the CI/CD YAML plan. "
                    "Pass human_confirmation='100% GO' to generate the workflow file."
                ),
            }

    await ctx.report_progress(100, 100, "CI/CD pipeline complete")
    logger.info("generate_cicd.complete", project_id=project_id)

    return {
        "status": "complete",
        "project_id": project_id,
        "ci_yaml_path": ".github/workflows/ci.yml",
        "ci_pipeline_url": state.get("ci_pipeline_url", ""),
        "test_coverage": state.get("test_coverage", 0.0),
        "stack": stack,
        "features": {
            "linter": "ruff",
            "security": "semgrep p/python p/security",
            "node_version": 24,
            "python_version": "3.12",
            "db": "postgresql:16",
        },
    }