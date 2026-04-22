from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from fastmcp import Context

logger = structlog.get_logger()


def _build_security_state(
    project_id: str, workspace_path: str, human_confirmation: str
) -> dict[str, object]:
    import uuid

    return {
        "user_prompt": f"Security scan for project {project_id}",
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
        "tool_delegated_to": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 999.0,
        "subscription_tier": "free",
        "session_token_records": [],
        "workspace_context": {"root_path": workspace_path},
        "tool_router_context": None,
        "model_router_context": None,
        "memory_context": None,
        "arch_validation": None,
        "test_coverage": 0.0,
        "ci_pipeline_url": "",
        "deployment_url": None,
        "monitoring_config": None,
        "project_context_graph": None,
    }


def _build_security_infrastructure() -> tuple:
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


def _build_security_agent(infra: tuple, workspace_path: str) -> object:
    from agents.agent_5b_security import SecurityAgent

    (
        model_router,
        cwm,
        memory_archiver,
        memory_ctx_builder,
        cfm,
        workspace_bridge,
        diff_engine,
    ) = infra

    # Pre-initialise workspace bridge to the scan path
    import asyncio

    async def _start_bridge() -> None:
        await workspace_bridge.start(workspace_path)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            pass  # bridge started lazily on get_context()
        else:
            loop.run_until_complete(_start_bridge())
    except Exception:
        pass

    return SecurityAgent(
        name="agent_5b_security",
        context_window_manager=cwm,
        model_router=model_router,
        memory_archiver=memory_archiver,
        memory_context_builder=memory_ctx_builder,
        context_file_manager=cfm,
        workspace_bridge=workspace_bridge,
        diff_engine=diff_engine,
    )


async def run_security_scan(
    project_id: str,
    ctx: Context,
    target_path: str = ".",
    rfc: str = "",
    human_confirmation: str = "",
) -> dict[str, object]:
    """Run full security scan: SAST + DAST + STRIDE + detect-secrets.

    SAST: bandit + semgrep (p/python + p/security — never --config=auto)
    DAST: uvicorn subprocess on port 18080 (skipped unless RUN_DAST=true)
    Secrets: detect-secrets scan
    STRIDE: o3-mini threat model of RFC (Responses API)

    Gate: HIGH or CRITICAL finding → security_gate.blocked = True
          This blocks Agent 8 (deployment) via graph conditional edge.

    CALL PATTERN:
    Call 1: project_id="proj-1", target_path="./src"
            → {"status": "awaiting_confirmation", ...}
    Call 2: human_confirmation="100% GO"
            → runs all tools, returns {"status": "complete", "gate_blocked": bool, ...}
    """
    await ctx.report_progress(0, 100, "Initialising security scan")
    logger.info(
        "run_security_scan.called",
        project_id=project_id,
        target_path=target_path,
        has_confirmation=bool(human_confirmation),
    )

    # Restore or initialise state
    try:
        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"security-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
        else:
            state = _build_security_state(project_id, target_path, human_confirmation)
    except Exception as exc:
        logger.warning("run_security_scan.checkpointer_failed", error=str(exc))
        state = _build_security_state(project_id, target_path, human_confirmation)

    # Inject RFC if provided
    if rfc:
        state["rfc"] = rfc

    state["human_confirmation"] = human_confirmation

    # Build infrastructure and agent
    infra = _build_security_infrastructure()
    agent_5b = _build_security_agent(infra, target_path)

    # Run Agent 5b
    await ctx.report_progress(20, 100, "Running SAST + DAST + STRIDE")
    state = await agent_5b.run(state)  # type: ignore[union-attr]

    # If gate not yet passed (interpret only)
    if not state.get("security_findings"):
        await ctx.report_progress(60, 100, "Awaiting security review approval")
        return {
            "status": "awaiting_confirmation",
            "project_id": project_id,
            "interpretation": (state["interpret_log"][-1] if state.get("interpret_log") else {}),
            "displayed_interpretation": state.get("displayed_interpretation", ""),
            "instructions": (
                "Review the security scan plan. Pass human_confirmation='100% GO' to run all tools."
            ),
        }

    security_gate = dict(state.get("security_gate") or {})
    security_findings = dict(state.get("security_findings") or {})
    gate_blocked = bool(security_gate.get("blocked", False))

    await ctx.report_progress(100, 100, "Security scan complete")
    logger.info(
        "run_security_scan.complete",
        project_id=project_id,
        gate_blocked=gate_blocked,
    )

    return {
        "status": "complete",
        "project_id": project_id,
        "gate_blocked": gate_blocked,
        "gate_reason": security_gate.get("reason"),
        "security_findings": security_findings,
        "threat_model_path": security_findings.get("threat_model_path"),
        "finding_counts": {
            "bandit": len(security_findings.get("bandit_findings", [])),
            "semgrep": len(security_findings.get("semgrep_findings", [])),
            "pip_audit": len(security_findings.get("pip_audit_findings", [])),
            "dast": len(security_findings.get("dast_findings", [])),
            "detect_secrets": len(security_findings.get("detect_secrets_findings", [])),
        },
        "instructions": (
            "Security gate BLOCKED — resolve HIGH/CRITICAL findings before deployment."
            if gate_blocked
            else "Security gate CLEAR — safe to proceed to deployment."
        ),
    }
