from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class AvailableTool(str, Enum):
    CURSOR      = "cursor_background_agent"
    CLAUDE_CODE = "claude_code_cli"
    DEVIN       = "devin_api"
    DIRECT_LLM  = "direct_llm"


class ToolResult(BaseModel):
    model_config = ConfigDict(strict=True)

    tool: AvailableTool
    output: str
    files_written: list[str]
    success: bool
    stderr: str | None


class ToolRouterContext(BaseModel):
    model_config = ConfigDict(strict=True)

    available_tools: list[AvailableTool]
    selected_tool: AvailableTool | None
    selection_reason: str
    user_cursor_subscription: bool
    user_claude_code_available: bool
    user_devin_available: bool
    fallback_to_direct_llm: bool
    context_files_written: list[str]   # files ContextFileManager wrote