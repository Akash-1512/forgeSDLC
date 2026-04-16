from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TokenRecord(BaseModel):
    """Records a single internal LLM call made by forgeSDLC's ModelRouter.

    SCOPE: forgeSDLC's own orchestration calls ONLY.
    ToolRouter delegations (Cursor / Claude Code / Devin) run on the developer's
    own API keys and subscriptions — those costs NEVER appear here.
    tool_delegated_to is set only for forgeSDLC orchestration overhead incurred
    on behalf of a ToolRouter route, not for the delegated tool's own LLM calls.
    """

    model_config = ConfigDict(strict=True)

    record_id: str                          # uuid4
    timestamp: datetime
    trace_id: str
    agent: str
    task: str
    model: str
    provider: str
    input_tokens: int = Field(ge=0)         # ge=0 on ALL numeric fields — no exceptions
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    latency_ms: int = Field(ge=0)
    api_key_source: Literal["byok", "subscription", "free_tier"]
    subscription_tier: str
    fim_call: bool
    session_id: str
    run_id: str | None
    # v4: set only for forgeSDLC overhead tracking; NOT for delegated tool costs
    tool_delegated_to: str | None