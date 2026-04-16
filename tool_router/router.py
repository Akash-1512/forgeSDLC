from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from interpret.record import InterpretRecord
from orchestrator.constants import HEALTH_CHECK_TIMEOUT_SECONDS, MCP_TOOL_TIMEOUT_SECONDS
from orchestrator.exceptions import ToolRouterError
from tool_router.adapters.claude_code_adapter import ClaudeCodeAdapter
from tool_router.adapters.cursor_adapter import CursorAdapter
from tool_router.adapters.devin_adapter import DevinAdapter
from tool_router.adapters.direct_llm_adapter import DirectLLMAdapter
from tool_router.context import AvailableTool, ToolResult

if TYPE_CHECKING:
    from context_files.manager import ContextFileManager

logger = structlog.get_logger()


class ToolRouter:
    """Routes code generation tasks to the best available external tool.

    Priority: Cursor Background Agent → Claude Code CLI → Devin → Direct LLM.
    Direct LLM is always appended last — never removed. route() never raises
    due to missing tools.

    ORDERING GUARANTEE (tested explicitly):
      1. ContextFileManager.write_all() — writes context files (L13 InterpretRecord)
      2. adapter.generate()            — delegates to external tool

    Emits InterpretRecord Layer 5 (tool_router) before every delegation.
    Agent 4 uses this class — it NEVER calls an LLM internally.
    """

    def __init__(self, context_file_manager: ContextFileManager) -> None:
        self._cfm = context_file_manager

    async def detect_available_tools(self) -> list[AvailableTool]:
        """Probe each tool and return available ones in priority order."""
        tools: list[AvailableTool] = []
        if await self._check_cursor():
            tools.append(AvailableTool.CURSOR)
        if await self._check_claude_code():
            tools.append(AvailableTool.CLAUDE_CODE)
        if await self._check_devin():
            tools.append(AvailableTool.DEVIN)
        tools.append(AvailableTool.DIRECT_LLM)  # always last, always present
        return tools

    async def route(
        self,
        task: str,
        context: str,
        project_id: str,
        workspace_path: str,
    ) -> ToolResult:
        """Detect tools, emit L5 InterpretRecord, write context files, then delegate."""
        tools = await self.detect_available_tools()
        selected = tools[0]
        reason = self._selection_reason(selected)

        # Step 1: Emit InterpretRecord Layer 5 BEFORE any action
        record = InterpretRecord(
            layer="tool_router",
            component="ToolRouter",
            action=f"delegating code gen to {selected.value}",
            inputs={
                "task": task[:100],
                "project_id": project_id,
                "selected_tool": selected.value,
                "reason": reason,
            },
            expected_outputs={"tool_result": "ToolResult"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[selected.value],
            model_selected=None,
            tool_delegated_to=selected.value,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "tool_router.delegating",
            tool=selected.value,
            project_id=project_id,
            reason=reason,
        )

        # Step 2: Write context files BEFORE invoking the tool (ORDERING GUARANTEE)
        written = await self._cfm.write_all(
            project_id=project_id,
            workspace_path=workspace_path,
        )
        logger.info("tool_router.context_files_written", files=written)

        # Step 3: Invoke the selected adapter
        adapter = self._get_adapter(selected)
        result = await adapter.generate(
            task=task,
            context=context,
            workspace_path=workspace_path,
        )
        logger.info(
            "tool_router.complete",
            tool=result.tool.value,
            success=result.success,
            files_written=len(result.files_written),
        )
        return result

    # ------------------------------------------------------------------ detection

    async def _check_cursor(self) -> bool:
        """Cursor Background Agent — off by default until ToS reviewed."""
        api_key = os.getenv("CURSOR_API_KEY")
        verified = os.getenv("CURSOR_API_VERIFIED", "false").lower() == "true"
        return bool(api_key) and verified

    async def _check_claude_code(self) -> bool:
        """Detect Claude Code CLI by running 'claude --version'."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                proc.wait(), timeout=HEALTH_CHECK_TIMEOUT_SECONDS
            )
            return proc.returncode == 0
        except (FileNotFoundError, asyncio.TimeoutError):
            return False

    async def _check_devin(self) -> bool:
        """Detect Devin by checking API key and hitting health endpoint."""
        api_key = os.getenv("DEVIN_API_KEY")
        if not api_key:
            return False
        try:
            import httpx  # noqa: PLC0415
            async with httpx.AsyncClient(
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS
            ) as client:
                response = await client.get(
                    "https://api.devin.ai/v1/health",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return response.status_code == 200
        except Exception: