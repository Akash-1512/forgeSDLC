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
    # ------------------------------------------------------------------ agent internals
    # Fix #99: all keys written by agents must be declared here so the
    # checkpointer serialises them correctly and mypy can verify access.
    arch_validation: dict[str, object] | None       # Agent 3 anti-pattern + NFR results
    anti_pattern_result: dict[str, object] | None   # Agent 3 AntiPatternDetector output
    deploy_blocked: bool                             # Agent 8 security gate block flag
    deploy_blocked_reason: str                       # Agent 8 block reason string
    hitl_required: bool                             # deploy_tool HITL escalation flag
    hitl_reason: str                                # deploy_tool HITL reason string
    review_corrections: list[str]                   # Agent 5 blocking findings for Agent 4 retry
    review_delegation_count: int                    # Agent 5 delegation counter (max 2)
    trigger_agent_4_retry: bool                     # Agent 5 → Agent 4 retry signal
    test_retry_count: int                           # Agent 6 coverage retry counter
    test_retry_needed: bool                         # Agent 6 coverage gate flag
    test_uncovered_lines: list[str]                 # Agent 6 uncovered line list for retry
    tool_retry_count: int                           # ToolRouter retry counter
    # ------------------------------------------------------------------ failure tracking
    failure_type: str | None                        # Layer 5 post-mortem failure type
    failed_agent: str | None                        # Layer 5 post-mortem agent identity
    failure_root_cause: str | None                  # Layer 5 post-mortem root cause
    failure_resolution: str | None                  # Layer 5 post-mortem resolution
    failure_prevention: str | None                  # Layer 5 post-mortem prevention rule
    # ------------------------------------------------------------------ monitoring
    slo_definitions: list[dict[str, object]]        # Agent 9 SLO definitions