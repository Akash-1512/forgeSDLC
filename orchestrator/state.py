from __future__ import annotations

from typing import TypedDict


class SDLCState(TypedDict):
    # ------------------------------------------------------------------ core
    user_prompt: str
    # Set only by [✅ Approve] button — never typed by user
    human_confirmation: str
    # [-1] = active correction; each submission overwrites, does not append
    human_corrections: list[str]
    # Single interpretation shown in companion panel at any time
    displayed_interpretation: str
    interpret_round: int
    # Full audit trail of all interpretation rounds
    interpret_log: list[dict[str, object]]
    trace_id: str
    # ------------------------------------------------------------------ MCP
    mcp_session_id: str | None
    # ------------------------------------------------------------------ routing
    tool_router_context: dict[str, object] | None
    model_router_context: dict[str, object] | None
    mode: str  # "inline" | "pipeline" | "mcp"
    # ------------------------------------------------------------------ workspace
    workspace_context: dict[str, object] | None
    # ------------------------------------------------------------------ memory
    memory_context: dict[str, object] | None
    # ------------------------------------------------------------------ SDLC artefacts
    service_graph: dict[str, object] | None
    prd: str
    adr: str
    rfc: str
    generated_files: list[dict[str, object]]
    review_findings: list[dict[str, object]]
    # ------------------------------------------------------------------ security
    security_findings: dict[str, object] | None
    security_gate: dict[str, object] | None
    # ------------------------------------------------------------------ quality
    test_coverage: float
    ci_pipeline_url: str
    # ------------------------------------------------------------------ deploy / monitor
    deployment_url: str | None
    monitoring_config: dict[str, object] | None
    # ------------------------------------------------------------------ docs
    project_context_graph: dict[str, object] | None
    # ------------------------------------------------------------------ budget / subscription
    budget_used_usd: float
    budget_remaining_usd: float
    subscription_tier: str
    session_token_records: list[dict[str, object]]
    # ------------------------------------------------------------------ tool delegation
    tool_delegated_to: str | None
