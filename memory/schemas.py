from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunRecord(BaseModel):
    model_config = ConfigDict(strict=True)

    run_id: str                          # uuid4
    timestamp: datetime
    project_id: str
    user_prompt: str
    stack_chosen: str | None
    deployment_success: bool | None
    cost_total_usd: float = Field(ge=0.0)
    hitl_rounds: int = Field(ge=0)
    human_corrections: list[str]
    lessons_learned: list[str]
    tool_delegated_to: str | None        # which ToolRouter target was used
    workspace_path: str


class OrgMemoryEntry(BaseModel):
    model_config = ConfigDict(strict=True)

    entry_id: str                        # uuid4
    project_id: str
    content: str                         # learnable fact — 1-3 sentences
    category: Literal[
        "architecture", "security", "pattern", "failure", "preference"
    ]
    source_run_id: str
    timestamp: datetime
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)