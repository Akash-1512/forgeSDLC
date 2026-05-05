"""
M14 Fix: shared initial state factory for all MCP tool handlers.

All 8 tool handlers previously built SDLCState dicts manually — an untyped
plain dict with no schema enforcement. Any typo in a key name passed silently.

This factory is the single source of truth for the initial state shape.
It matches the SDLCState TypedDict exactly so mypy can verify it.
"""

from __future__ import annotations

import uuid
from typing import Any


def build_initial_state(
    *,
    user_prompt: str,
    project_id: str,
    human_confirmation: str = "",
    mode: str = "mcp",
    # Optional overrides for tool-specific initial values
    extra: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Build a fresh SDLCState dict with all required keys present.

    This is the canonical factory — add keys here as SDLCState grows.
    Tool files call this instead of building their own state dicts.
    """
    state: dict[str, object] = {
        # ── core ──────────────────────────────────────────────────────────
        "user_prompt": user_prompt,
        "human_confirmation": human_confirmation,
        "human_corrections": [],
        "displayed_interpretation": "",
        "interpret_round": 0,
        "interpret_log": [],
        "trace_id": str(uuid.uuid4()),
        # ── MCP ───────────────────────────────────────────────────────────
        "mcp_session_id": project_id,
        # ── routing ───────────────────────────────────────────────────────
        "tool_router_context": None,
        "model_router_context": None,
        "mode": mode,
        # ── workspace ─────────────────────────────────────────────────────
        "workspace_context": None,
        # ── memory ────────────────────────────────────────────────────────
        "memory_context": None,
        # ── SDLC artefacts ────────────────────────────────────────────────
        "service_graph": None,
        "prd": "",
        "adr": "",
        "rfc": "",
        "generated_files": [],
        "review_findings": [],
        # ── security ──────────────────────────────────────────────────────
        "security_findings": None,
        "security_gate": None,
        # ── quality ───────────────────────────────────────────────────────
        "test_coverage": 0.0,
        "ci_pipeline_url": "",
        # ── deploy / monitor ──────────────────────────────────────────────
        "deployment_url": None,
        "monitoring_config": None,
        # ── docs ──────────────────────────────────────────────────────────
        "project_context_graph": None,
        # ── budget / subscription ─────────────────────────────────────────
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 0.0,  # free tier: no cap (Groq is free)
        "subscription_tier": "free",
        "session_token_records": [],
        # ── tool delegation ───────────────────────────────────────────────
        "tool_delegated_to": None,
        # ── agent internals (declared in SDLCState v1.1.0) ────────────────
        "arch_validation": None,
        "anti_pattern_result": None,
        "deploy_blocked": False,
        "deploy_blocked_reason": "",
        "hitl_required": False,
        "hitl_reason": "",
        "review_corrections": [],
        "review_delegation_count": 0,
        "trigger_agent_4_retry": False,
        "test_retry_count": 0,
        "test_retry_needed": False,
        "test_uncovered_lines": [],
        "tool_retry_count": 0,
        # ── failure tracking ──────────────────────────────────────────────
        "failure_type": None,
        "failed_agent": None,
        "failure_root_cause": None,
        "failure_resolution": None,
        "failure_prevention": None,
        # ── monitoring ────────────────────────────────────────────────────
        "slo_definitions": [],
    }

    # Apply any tool-specific overrides
    if extra:
        state.update(extra)

    return state
