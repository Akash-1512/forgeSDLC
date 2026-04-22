from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 12 InterpretRecord layers — every component must emit one before executing.
# L1  agent                 L2  workspace
# L3  diff                  L4  model_router
# L5  tool_router           L6  memory
# L7  docs_fetcher          L8  tool
# L9  provider              L10 security
# L11 context_window_manager  L12 context_file_manager
# NOTE: mcp_server emits at the transport boundary (between L11 and L12)
LayerLiteral = Literal[
    "agent",
    "workspace",
    "diff",
    "model_router",
    "tool_router",
    "memory",
    "docs_fetcher",
    "tool",
    "provider",
    "security",
    "context_window_manager",
    "mcp_server",
    "context_file_manager",
]


class InterpretRecord(BaseModel):
    """Emitted by every forgeSDLC component before it executes.

    Zero silent executions — test_interpret_completeness.py enforces this
    across all 12 layers (Session 18).
    """

    model_config = ConfigDict(strict=True)

    layer: LayerLiteral
    component: str
    action: str
    inputs: dict[str, object]
    expected_outputs: dict[str, object]
    files_it_will_read: list[str]
    files_it_will_write: list[str]
    external_calls: list[str]
    model_selected: str | None
    # Set by ToolRouter when delegating code gen to Cursor / Claude Code / Devin
    tool_delegated_to: str | None
    # ge=0 enforced — negative tokens or cost indicate a bug, not a valid state
    estimated_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    reversible: bool
    workspace_files_affected: list[str]
    timestamp: datetime
