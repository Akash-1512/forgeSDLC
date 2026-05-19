"""Track SDLC pipeline progress and token usage for a project."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

from orchestrator.constants import CHECKPOINT_DB_PATH

logger = structlog.get_logger()


async def track_progress(project_id: str) -> dict[str, object]:
    """Return current SDLC phase, completion status, and token spend for a project.

    Reads checkpoint state and aggregates token usage via TokenAggregator.
    Reads checkpoint to determine which pipeline stages have completed.
    """
    logger.info("track_progress.called", project_id=project_id)

    # ── 1. Read checkpoint state ─────────────────────────────────────────
    stages_complete: list[str] = []
    current_stage: str = "not_started"
    token_records: list[dict[str, object]] = []
    budget_used: float = 0.0

    checkpoint_db = Path(CHECKPOINT_DB_PATH)
    if checkpoint_db.exists():
        try:
            with sqlite3.connect(str(checkpoint_db), check_same_thread=False) as conn:
                from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

                cp = SqliteSaver(conn)
                config = {"configurable": {"thread_id": project_id}}
                existing = cp.get(config)
                if existing and existing.get("channel_values"):
                    cv = existing["channel_values"]
                    if cv.get("adr"):
                        stages_complete.append("stack_selection")
                    if cv.get("prd"):
                        stages_complete.append("requirements")
                    if cv.get("service_graph"):
                        stages_complete.append("decomposition")
                    if cv.get("rfc"):
                        stages_complete.append("architecture")
                    if cv.get("generated_files"):
                        stages_complete.append("code_generation")
                    if cv.get("security_gate"):
                        stages_complete.append("security_scan")
                    if cv.get("ci_pipeline_url"):
                        stages_complete.append("cicd")
                    if cv.get("deployment_url"):
                        stages_complete.append("deployment")
                    if cv.get("monitoring_config"):
                        stages_complete.append("monitoring")
                    if cv.get("project_context_graph"):
                        stages_complete.append("documentation")

                    current_stage = stages_complete[-1] if stages_complete else "not_started"
                    token_records = list(cv.get("session_token_records") or [])
                    budget_used = float(cv.get("budget_used_usd") or 0.0)
        except Exception as exc:
            logger.warning("track_progress.checkpoint_read_failed", error=str(exc))

    # ── 2. Aggregate token data ───────────────────────────────────────────
    token_summary: dict[str, object] = {
        "total_calls": 0,
        "by_agent": {},
        "by_model": {},
    }
    if token_records:
        try:
            from token_tracker.aggregator import TokenAggregator  # noqa: PLC0415

            agg = TokenAggregator()
            token_summary = {
                "total_calls": len(token_records),
                "by_agent": agg.by_agent(token_records),
                "by_model": agg.by_model(token_records),
                "by_provider": agg.by_provider(token_records),
            }
        except Exception as exc:
            logger.warning("track_progress.aggregation_failed", error=str(exc))

    all_stages = [
        "decomposition",
        "requirements",
        "stack_selection",
        "architecture",
        "code_generation",
        "security_scan",
        "cicd",
        "deployment",
        "monitoring",
        "documentation",
    ]
    pct = int(len(stages_complete) / len(all_stages) * 100)

    return {
        "status": "ok",
        "project_id": project_id,
        "current_stage": current_stage,
        "stages_complete": stages_complete,
        "stages_remaining": [s for s in all_stages if s not in stages_complete],
        "completion_pct": pct,
        "budget_used_usd": budget_used,
        "token_summary": token_summary,
    }
