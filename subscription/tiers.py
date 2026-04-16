from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SubscriptionTier:
    """Defines what models and tools a subscription tier permits.

    models_allowed: fnmatch patterns matched against model strings.
    code_gen_tools: AvailableTool values permitted for ToolRouter.
    budget_usd_per_session: 0.0 for Free (Groq free tier — no spend tracking).
    """

    name: str
    monthly_usd: float
    models_allowed: list[str]
    code_gen_tools: list[str]
    budget_usd_per_session: float


FREE = SubscriptionTier(
    name="free",
    monthly_usd=0.0,
    # No OpenAI, no Claude, no Gemini — Groq free tier only
    models_allowed=["groq/*", "ollama/*"],
    # ToolRouter limited to DirectLLMAdapter (Groq path)
    code_gen_tools=["direct_llm"],
    budget_usd_per_session=0.0,  # Groq free — no spend tracking needed
)

PRO = SubscriptionTier(
    name="pro",
    monthly_usd=20.0,
    models_allowed=[
        "gpt-5.4",
        "gpt-5.4*",
        "gpt-5.4-mini*",
        "o3-mini",
        "gemini-*",
        "codestral-*",
        "groq/*",
    ],
    # Cursor + Claude Code available; Devin requires Enterprise
    code_gen_tools=["cursor_background_agent", "claude_code_cli", "direct_llm"],
    budget_usd_per_session=5.0,
)

ENTERPRISE = SubscriptionTier(
    name="enterprise",
    monthly_usd=80.0,
    models_allowed=["*"],  # all providers
    code_gen_tools=[
        "cursor_background_agent",
        "claude_code_cli",
        "devin_api",
        "direct_llm",
    ],
    budget_usd_per_session=50.0,
)

# Claude (any variant) requires BYOK regardless of tier.
# Model pattern matching is checked AFTER BYOK key presence.
ALWAYS_BYOK_PROVIDERS: list[str] = ["anthropic"]

_TIERS: dict[str, SubscriptionTier] = {
    "free": FREE,
    "pro": PRO,
    "enterprise": ENTERPRISE,
}


def get_tier(name: str) -> SubscriptionTier:
    """Return tier by name. Raises KeyError for unknown tiers."""
    if name not in _TIERS:
        raise KeyError(
            f"Unknown subscription tier: {name!r}. "
            f"Valid tiers: {list(_TIERS.keys())}"
        )
    return _TIERS[name]


def model_allowed_for_tier(model: str, tier: SubscriptionTier) -> bool:
    """Return True if the model matches any allowed pattern for this tier.

    Uses fnmatch for glob-style pattern matching:
      "groq/*"    matches "groq/llama-3.3-70b-specdec"
      "gpt-5.4*"  matches "gpt-5.4" and "gpt-5.4-mini"
      "*"         matches everything (Enterprise)
    """
    return any(fnmatch.fnmatch(model, pattern) for pattern in tier.models_allowed)


def tool_allowed_for_tier(tool: str, tier: SubscriptionTier) -> bool:
    """Return True if the ToolRouter tool value is permitted for this tier."""
    return tool in tier.code_gen_tools