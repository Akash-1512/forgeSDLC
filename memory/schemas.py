from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunRecord(BaseModel):
    model_config = ConfigDict(strict=True)

    run_id: str  # uuid4
    timestamp: datetime
    project_id: str
    user_prompt: str
    stack_chosen: str | None
    deployment_success: bool | None
    cost_total_usd: float = Field(ge=0.0)
    hitl_rounds: int = Field(ge=0)
    human_corrections: list[str]
    lessons_learned: list[str]
    tool_delegated_to: str | None  # which ToolRouter target was used
    workspace_path: str


class OrgMemoryEntry(BaseModel):
    model_config = ConfigDict(strict=True)

    entry_id: str  # uuid4
    project_id: str
    content: str  # learnable fact — 1-3 sentences
    category: Literal["architecture", "security", "pattern", "failure", "preference"]
    source_run_id: str
    timestamp: datetime
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Layer 3 — ProjectContextGraph (filesystem JSON)
# ---------------------------------------------------------------------------


class ServiceNode(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    responsibility: str
    exposes: list[str]  # API endpoints or events
    depends_on: list[str]
    owns_data: bool
    database: str | None


class ProjectContextGraph(BaseModel):
    model_config = ConfigDict(strict=True)

    project_id: str
    repo_url: str | None
    services: list[ServiceNode]
    api_contracts: list[str]  # OpenAPI spec paths
    architectural_decisions: list[str]  # ADR summaries
    dependencies: list[str]
    env_var_names: list[str]
    deployment_config: dict[str, object]
    slo_definitions: list[str]
    workspace_path: str
    last_updated: datetime


# ---------------------------------------------------------------------------
# Layer 4 — UserPreferenceProfile (PostgreSQL)
# ---------------------------------------------------------------------------


class UserPreferenceProfile(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: str
    preferred_code_gen_tool: str  # "cursor"|"claude_code"|"direct_llm"
    preferred_stack: list[str]
    subscription_tier: str
    byok_providers: list[str]
    recurring_security_findings: list[str]
    recurring_anti_patterns: list[str]
    last_updated: datetime


# ---------------------------------------------------------------------------
# Layer 5 — PostMortem (PostgreSQL)
# ---------------------------------------------------------------------------


class PostMortem(BaseModel):
    model_config = ConfigDict(strict=True)

    post_mortem_id: str
    run_id: str
    failure_type: Literal[
        "tool_timeout", "security_gate", "deployment", "architecture", "test_coverage"
    ]
    agent_that_failed: str
    root_cause: str
    resolution: str
    prevention_rule: str
    stack_context: str
    tool_involved: str | None  # v4: which ToolRouter target failed
    timestamp: datetime
