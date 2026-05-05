from __future__ import annotations

import os

import httpx
import structlog

from tool_router.context import AvailableTool, ToolResult

logger = structlog.get_logger()

_DEVIN_BASE_URL = "https://api.devin.ai/v1"


class DevinAdapter:
    """Devin REST API adapter.

    Requires DEVIN_API_KEY environment variable.
    Emits structured logs for every request.
    """

    async def generate(self, task: str, context: str, workspace_path: str) -> ToolResult:
        api_key = os.getenv("DEVIN_API_KEY")
        if not api_key:
            return ToolResult(
                tool=AvailableTool.DEVIN,
                output="",
                files_written=[],
                success=False,
                stderr="DEVIN_API_KEY not set.",
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": task,
            "context": context,
            "workspace_path": workspace_path,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{_DEVIN_BASE_URL}/sessions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                output = data.get("output", "")
                files_written = data.get("files_written", [])
                logger.info(
                    "devin_adapter.success",
                    session_id=data.get("session_id"),
                    files_written=len(files_written),
                )
                return ToolResult(
                    tool=AvailableTool.DEVIN,
                    output=output,
                    files_written=files_written,
                    success=True,
                    stderr=None,
                )
        except Exception as exc:
            logger.error("devin_adapter.error", error=str(exc))
            return ToolResult(
                tool=AvailableTool.DEVIN,
                output="",
                files_written=[],
                success=False,
                stderr=str(exc),
            )
