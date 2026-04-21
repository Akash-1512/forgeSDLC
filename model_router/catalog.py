from __future__ import annotations

# AGENT_MODELS — authoritative source for agent→model assignment.
# Any discrepancy between this dict and prose documentation: THE DICT WINS.
# Agent 4 = None: ToolRouter only — ModelRouter raises if routed here.
# Agent 9 = groq: NOT gpt-5.4-mini — a v3 catalog error fixed here.

AGENT_MODELS: dict[str, str | None] = {
    "agent_0_decompose":       "groq/llama-3.3-70b-versatile",
    "agent_1_requirements":    "groq/llama-3.3-70b-versatile",
    "agent_2_stack":           "gpt-5.4-mini",
    "agent_3_architecture":    "gpt-5.4",
    "agent_4_tool_router":     None,                         # NO LLM — raises if routed
    "agent_5_coord_review":    "gpt-5.4-mini",
    "agent_5b_security":       "o3-mini",                    # Responses API
    "agent_6_test_coord":      "gpt-5.4-mini",
    "agent_7_cicd":            "gpt-5.4-mini",
    "agent_8_deploy":          "gpt-5.4-mini",
    "agent_9_monitor":         "groq/llama-3.3-70b-versatile", # ← GROQ, NOT gpt-5.4-mini
    "agent_10_docs":           "gpt-5.4-mini",               # BYOK Claude overrides via tier
    "agent_10_docs_byok":      "claude-sonnet-4-6",          # BYOK only — better README prose
    "agent_11_integration":    "gemini-3.1-pro-preview",     # 1M context
    "agent_12_contracts":      "gpt-5.4",
    "agent_13_platform":       "gpt-5.4-mini",
    "interpret_node":          "groq/llama-3.1-8b-instant",  # always free, no exceptions
    "context_compressor":      "groq/llama-3.1-8b-instant",  # always free, no exceptions
    # Alias for DirectLLMAdapter fallback path (uses context_compressor model)
    "direct_llm_fallback":     "groq/llama-3.1-8b-instant",
}

# Models that use Responses API (not Chat Completions)
RESPONSES_API_MODELS: frozenset[str] = frozenset({"o3-mini", "gpt-5.4-pro"})

# Models that require BYOK regardless of subscription tier
ALWAYS_BYOK_MODELS: frozenset[str] = frozenset({
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
})

# Budget downgrade chain: when OPTIMISE threshold hit, step down
BUDGET_DOWNGRADE_CHAIN: list[str] = [
    "gpt-5.4",
    "gpt-5.4-mini",
    "groq/llama-3.3-70b-versatile",
]
