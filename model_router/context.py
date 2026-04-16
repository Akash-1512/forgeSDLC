from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ModelRouterContext(BaseModel):
    """Records the ModelRouter's selection decision for observability."""

    model_config = ConfigDict(strict=True)

    agent: str
    task_type: str
    estimated_tokens: int
    subscription_tier: str
    budget_used: float
    budget_total: float
    selected_model: str | None
    selection_reason: str
    downgraded: bool
    long_context_routed: bool
    fim_routed: bool
    byok_required: bool
    tier_override: bool
    timestamp: datetime