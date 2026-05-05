from __future__ import annotations

# AGENT_MODELS — authoritative source for agent→model assignment.
# Any discrepancy between this dict and prose documentation: THE DICT WINS.
# Agent 4 = None: ToolRouter only — ModelRouter raises if routed here.
# Agent 9 = groq: NOT gpt-4o-mini — a v3 catalog error fixed here.

AGENT_MODELS: dict[str, str | None] = {
    "agent_0_decompose": "groq/llama-3.3-70b-versatile",
    "agent_1_requirements": "groq/llama-3.3-70b-versatile",
    "agent_2_stack": "gpt-4o-mini",
    "agent_3_architecture": "gpt-4o",
    "agent_4_tool_router": None,  # NO LLM — raises if routed
    "agent_5_coord_review": "gpt-4o-mini",
    "agent_5b_security": "o3-mini",  # Responses API
    "agent_6_test_coord": "gpt-4o-mini",
    "agent_7_cicd": "gpt-4o-mini",
    "agent_8_deploy": "gpt-4o-mini",
    "agent_9_monitor": "groq/llama-3.3-70b-versatile",  # ← GROQ, NOT gpt-4o-mini
    "agent_10_docs": "gpt-4o-mini",  # BYOK Claude overrides via tier
    "agent_10_docs_byok": "claude-sonnet-4-6",  # BYOK only — better README prose
    "agent_11_integration": "gemini-1.5-pro",  # 1M context
    "agent_12_contracts": "gpt-4o",
    "agent_13_platform": "gpt-4o-mini",
    "interpret_node": "groq/llama-3.1-8b-instant",  # always free, no exceptions
    "context_compressor": "groq/llama-3.1-8b-instant",  # always free, no exceptions
    # Alias for DirectLLMAdapter fallback path (uses context_compressor model)
    "direct_llm_fallback": "groq/llama-3.1-8b-instant",
}

# Models that use Responses API (not Chat Completions)
# ONLY o3-mini uses client.responses.create — gpt-4o uses Chat Completions
RESPONSES_API_MODELS: frozenset[str] = frozenset({"o3-mini"})

# Models that require BYOK regardless of subscription tier
# o3-mini added: requires OPENAI_API_KEY even on free tier
ALWAYS_BYOK_MODELS: frozenset[str] = frozenset(
    {
        "claude-sonnet-4-6",
        "claude-sonnet-4-5",
        "o3-mini",  # requires OPENAI_API_KEY — never routes without it
        "gpt-4o",  # requires OPENAI_API_KEY
        "gpt-4o-mini",  # requires OPENAI_API_KEY
        "gemini-1.5-pro",  # requires GOOGLE_API_KEY
    }
)

# Budget downgrade chain — all models are real and available
BUDGET_DOWNGRADE_CHAIN: list[str] = [
    "gpt-4o",
    "gpt-4o-mini",
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.1-8b-instant",  # floor — always free
]
