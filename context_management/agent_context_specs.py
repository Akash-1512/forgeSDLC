from __future__ import annotations

from context_management.context_packet import AgentContextSpec

# RULES enforced by Pydantic validator + tests:
# 1. required_fields ∩ excluded_fields = ∅  (validator fires on authoring error)
# 2. model_router_context REQUIRED for ALL 14 agents
# 3. tool_router_context REQUIRED for Agent 4 + Agent 6 ONLY
#    (they delegate code/test gen via ToolRouter — others do not)

AGENT_CONTEXT_SPECS: dict[str, AgentContextSpec] = {
    "agent_0_decompose": AgentContextSpec(
        agent_name="agent_0_decompose",
        required_fields=[
            "user_prompt",
            "provider_manifest",
            "workspace_context",
            "model_router_context",
        ],
        optional_fields=["memory_context"],
        excluded_fields=[
            "review_findings",
            "security_findings",
            "generated_files",
            "interpret_log",
            "session_token_records",
            "ci_pipeline_url",
        ],
        max_context_tokens=8_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[3, 4],
        priority_order=["user_prompt", "workspace_context", "model_router_context"],
    ),
    "agent_1_requirements": AgentContextSpec(
        agent_name="agent_1_requirements",
        required_fields=[
            "user_prompt",
            "service_graph",
            "workspace_context",
            "model_router_context",
        ],
        optional_fields=["memory_context"],
        excluded_fields=[
            "review_findings",
            "security_findings",
            "generated_files",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=10_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[1, 4],
        priority_order=["user_prompt", "service_graph", "workspace_context"],
    ),
    "agent_2_stack": AgentContextSpec(
        agent_name="agent_2_stack",
        required_fields=[
            "user_prompt",
            "prd",
            "service_graph",
            "model_router_context",
        ],
        optional_fields=["memory_context"],
        excluded_fields=[
            "review_findings",
            "security_findings",
            "generated_files",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=10_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[4, 2],
        priority_order=["prd", "user_prompt", "service_graph"],
    ),
    "agent_3_architecture": AgentContextSpec(
        agent_name="agent_3_architecture",
        required_fields=[
            "user_prompt",
            "prd",
            "adr",
            "service_graph",
            "workspace_context",
            "model_router_context",
        ],
        optional_fields=["memory_context", "research_context"],
        excluded_fields=[
            "review_findings",
            "security_findings",
            "generated_files",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=15_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[2, 4],
        priority_order=["prd", "adr", "service_graph", "workspace_context"],
    ),
    "agent_4_tool_router": AgentContextSpec(
        agent_name="agent_4_tool_router",
        required_fields=[
            "prd",
            "rfc",
            "adr",
            "workspace_context",
            "model_router_context",
            "tool_router_context",  # ← required: delegates code gen
        ],
        optional_fields=["memory_context"],
        excluded_fields=[
            "review_findings",
            "security_findings",
            "interpret_log",
            "session_token_records",
            "monitoring_config",
        ],
        max_context_tokens=8_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[4],
        priority_order=["rfc", "prd", "adr", "workspace_context", "tool_router_context"],
    ),
    "agent_5_coord_review": AgentContextSpec(
        agent_name="agent_5_coord_review",
        required_fields=[
            "rfc",
            "adr",
            "model_router_context",
            "tool_router_context",
        ],
        optional_fields=["generated_files", "memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "security_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=12_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[2],
        priority_order=["rfc", "adr", "generated_files"],
    ),
    "agent_5b_security": AgentContextSpec(
        agent_name="agent_5b_security",
        required_fields=["rfc", "adr", "model_router_context"],
        optional_fields=["generated_files", "memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=12_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[2, 5],
        priority_order=["rfc", "adr", "generated_files"],
    ),
    "agent_6_test_coord": AgentContextSpec(
        agent_name="agent_6_test_coord",
        required_fields=[
            "rfc",
            "workspace_context",
            "model_router_context",
            "tool_router_context",  # ← required: delegates test gen
        ],
        optional_fields=["generated_files", "memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "interpret_log",
            "session_token_records",
            "monitoring_config",
        ],
        max_context_tokens=10_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[2],
        priority_order=["rfc", "workspace_context", "generated_files"],
    ),
    "agent_7_cicd": AgentContextSpec(
        agent_name="agent_7_cicd",
        required_fields=["adr", "workspace_context", "model_router_context"],
        optional_fields=["memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "review_findings",
            "security_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=6_000,
        summarise_threshold_tokens=1_500,
        memory_layers=[],
        priority_order=["adr", "workspace_context"],
    ),
    "agent_8_deploy": AgentContextSpec(
        agent_name="agent_8_deploy",
        required_fields=["rfc", "workspace_context", "model_router_context"],
        optional_fields=["memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "review_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=8_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[5],
        priority_order=["rfc", "workspace_context"],
    ),
    "agent_9_monitor": AgentContextSpec(
        agent_name="agent_9_monitor",
        required_fields=["rfc", "deployment_url", "model_router_context"],
        optional_fields=["memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "review_findings",
            "security_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=6_000,
        summarise_threshold_tokens=1_500,
        memory_layers=[],
        priority_order=["rfc", "deployment_url"],
    ),
    "agent_10_docs": AgentContextSpec(
        agent_name="agent_10_docs",
        required_fields=[
            "prd",
            "rfc",
            "adr",
            "deployment_url",
            "workspace_context",
            "model_router_context",
        ],
        optional_fields=["memory_context"],
        excluded_fields=[
            "review_findings",
            "security_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=15_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[3],
        priority_order=["prd", "rfc", "adr", "workspace_context"],
    ),
    "agent_11_integration": AgentContextSpec(
        agent_name="agent_11_integration",
        required_fields=[
            "service_graph",
            "rfc",
            "workspace_context",
            "model_router_context",
        ],
        optional_fields=["memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "review_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=20_000,  # gemini-3.1-pro-preview 1M context allowance
        summarise_threshold_tokens=3_000,
        memory_layers=[3],
        priority_order=["service_graph", "rfc", "workspace_context"],
    ),
    "agent_12_contracts": AgentContextSpec(
        agent_name="agent_12_contracts",
        required_fields=["service_graph", "rfc", "model_router_context"],
        optional_fields=["memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "review_findings",
            "security_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=12_000,
        summarise_threshold_tokens=2_000,
        memory_layers=[3],
        priority_order=["service_graph", "rfc"],
    ),
    "agent_13_platform": AgentContextSpec(
        agent_name="agent_13_platform",
        required_fields=["service_graph", "deployment_url", "model_router_context"],
        optional_fields=["memory_context"],
        excluded_fields=[
            "user_prompt",
            "prd",
            "review_findings",
            "interpret_log",
            "session_token_records",
        ],
        max_context_tokens=8_000,
        summarise_threshold_tokens=1_500,
        memory_layers=[],
        priority_order=["service_graph", "deployment_url"],
    ),
}


def print_spec_table() -> None:
    """Print a summary table of all 14 agent context specs.

    Used by: make context-stats
    """
    print(f"\n{'Agent':<25} {'MaxTokens':>10} {'Required':>8} {'Optional':>8} {'Excluded':>8}")
    print("-" * 65)
    for name, spec in AGENT_CONTEXT_SPECS.items():
        print(
            f"{name:<25} {spec.max_context_tokens:>10,} "
            f"{len(spec.required_fields):>8} "
            f"{len(spec.optional_fields):>8} "
            f"{len(spec.excluded_fields):>8}"
        )
    print(f"\nTotal specs: {len(AGENT_CONTEXT_SPECS)}\n")
