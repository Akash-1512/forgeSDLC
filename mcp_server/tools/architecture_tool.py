from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

from subscription.tiers import FREE

try:
    from fastmcp import Context
except ImportError:  # pragma: no cover
    Context = object  # type: ignore[assignment,misc]

from mcp_server.tier_resolver import resolve_tier as _resolve_tier

logger = structlog.get_logger()


def _build_initial_arch_state(requirements: str, project_id: str) -> dict[str, object]:
    """Build a fresh SDLCState for the architecture pipeline."""
    import uuid

    return {
        "user_prompt": requirements,
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
        "prd": requirements,  # requirements passed directly as PRD
        "adr": "",
        "rfc": "",
        "arch_validation": None,
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
        "budget_remaining_usd": FREE.budget_usd_per_session,
        "subscription_tier": _resolve_tier(),
        "session_token_records": [],
        "tool_delegated_to": None,
        "_agent0_raw": "",
    }


def _build_infrastructure_shared() -> object:
    """Instantiate the shared components needed by the architecture agent."""
    from mcp_server.shared_infrastructure import build_infrastructure  # noqa: PLC0415

    return build_infrastructure()


def _build_arch_agent(infra: object) -> object:
    """Instantiate Agent 3."""
    from agents.agent_3_architecture import ArchitectureAgent

    return ArchitectureAgent(
        name="agent_3_architecture",
        context_window_manager=infra.context_window_manager,
        model_router=infra.model_router,
        memory_archiver=infra.memory_archiver,
        memory_context_builder=infra.memory_context_builder,
        context_file_manager=infra.context_file_manager,
        workspace_bridge=infra.workspace_bridge,
        diff_engine=infra.diff_engine,
    )


async def design_architecture(
    requirements: str,
    project_id: str,
    ctx: Context,
    human_confirmation: str = "",
    correction: str = "",
) -> dict[str, object]:
    """Generate and validate software architecture from requirements.

    Returns scored, anti-pattern-checked architecture for human review.
    HIGH anti-pattern or NFR failure → blocked status, no RFC written.
    On 100% GO (with no blocking issues) → writes RFC-001-system-design.md
    and optional openapi.yaml.

    CALL PATTERN (stateful — two calls minimum):
    Call 1: requirements="...", project_id="proj-1"
            → {"status": "awaiting_confirmation", "arch_validation": {...}, ...}
    Call 2: human_confirmation="100% GO"
            → {"status": "complete", "rfc": "...", ...}
            OR {"status": "blocked", "reason": "...", ...} if HIGH findings
    """
    await ctx.report_progress(0, 100, "Loading architecture pipeline state")
    logger.info(
        "design_architecture.called",
        project_id=project_id,
        has_confirmation=bool(human_confirmation),
        has_correction=bool(correction),
    )

    # Restore or initialise state via SqliteSaver
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

        Path("./data").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("./data/checkpoints.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        config = {"configurable": {"thread_id": f"arch-{project_id}"}}
        existing = checkpointer.get(config)
        if existing and existing.get("channel_values"):
            state: dict[str, object] = dict(existing["channel_values"])
            logger.info("design_architecture.state_restored", project_id=project_id)
        else:
            state = _build_initial_arch_state(requirements, project_id)
    except Exception as exc:
        logger.warning("design_architecture.checkpointer_failed", error=str(exc))
        state = _build_initial_arch_state(requirements, project_id)

    # Apply human confirmation and correction
    state["human_confirmation"] = human_confirmation
    if correction:
        corrections = list(state.get("human_corrections", []) or [])
        if corrections:
            corrections[-1] = correction
        else:
            corrections.append(correction)
        state["human_corrections"] = corrections

    # Build infrastructure and Agent 3
    infra = _build_infrastructure_shared()
    agent_3 = _build_arch_agent(infra)

    # ── Run Agent 3 ────────────────────────────────────────────────────────
    await ctx.report_progress(20, 100, "Running architecture validation")
    state = await agent_3.run(state)  # type: ignore[union-attr]

    arch_validation = dict(state.get("arch_validation") or {})
    gate_blocked = bool(arch_validation.get("gate_blocked", False))

    # Gate blocked by HIGH findings or NFR failure
    if gate_blocked:
        await ctx.report_progress(100, 100, "Architecture blocked — review required")
        ap_result = arch_validation.get("anti_pattern_result", {})
        nfr_checks = arch_validation.get("nfr_checks", [])
        failed_nfrs = [c for c in nfr_checks if not c.get("satisfied", True)]
        blocking_findings = [f for f in ap_result.get("findings", []) if f.get("blocking", False)]
        return {
            "status": "blocked",
            "project_id": project_id,
            "reason": (
                f"{len(blocking_findings)} HIGH anti-pattern(s) and/or "
                f"{len(failed_nfrs)} NFR failure(s) detected."
            ),
            "blocking_findings": blocking_findings,
            "failed_nfrs": failed_nfrs,
            "architecture_score": arch_validation.get("architecture_score", {}),
            "displayed_interpretation": state.get("displayed_interpretation", ""),
            "instructions": (
                "Fix the blocking issues above and re-call design_architecture() "
                "with your corrected requirements. Pass correction='<your fix>'."
            ),
        }

    # Awaiting human confirmation (interpret ran but execute did not)
    if not state.get("rfc"):
        await ctx.report_progress(60, 100, "Awaiting architecture approval")
        return {
            "status": "awaiting_confirmation",
            "project_id": project_id,
            "interpretation": (state["interpret_log"][-1] if state.get("interpret_log") else {}),
            "displayed_interpretation": state.get("displayed_interpretation", ""),
            "architecture_score": arch_validation.get("architecture_score", {}),
            "anti_pattern_summary": {
                "high_count": arch_validation.get("anti_pattern_result", {}).get("high_count", 0),
                "medium_count": arch_validation.get("anti_pattern_result", {}).get(
                    "medium_count", 0
                ),
                "all_clear": arch_validation.get("anti_pattern_result", {}).get("all_clear", True),
            },
            "instructions": (
                "Architecture validated. Pass human_confirmation='100% GO' to generate RFC."
            ),
        }

    # Complete
    await ctx.report_progress(100, 100, "Architecture RFC complete")
    logger.info("design_architecture.complete", project_id=project_id)

    return {
        "status": "complete",
        "project_id": project_id,
        "rfc": state.get("rfc", ""),
        "arch_validation": arch_validation,
        "files_written": ["docs/architecture/RFC-001-system-design.md"],
        "context_files_updated": ["AGENTS.md", "CLAUDE.md", ".cursorrules"],
        "interpret_log": state.get("interpret_log", []),
        "interpret_rounds": int(state.get("interpret_round", 0) or 0),
    }
