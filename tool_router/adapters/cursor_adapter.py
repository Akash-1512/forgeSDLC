from __future__ import annotations

import os

import structlog

from tool_router.context import AvailableTool, ToolResult

logger = structlog.get_logger()


class CursorAdapter:
    """Cursor Background Agent API adapter.

    OFF BY DEFAULT — CURSOR_API_VERIFIED=true must be explicitly set.
    Cursor Background Agent API ToS has not yet been reviewed for commercial use.
    See legal/cursor_api_review.md for the pending review status.

    To enable:
        export CURSOR_API_KEY=<your-key>
        export CURSOR_API_VERIFIED=true
    """

    async def generate(
        self, task: str, context: str, workspace_path: str
    ) -> ToolResult:
        api_key = os.getenv("CURSOR_API_KEY")
        verified = os.getenv("CURSOR_API_VERIFIED", "false").lower() == "true"

        if not api_key or not verified:
            logger.warning(
                "cursor_adapter.not_enabled",
                hint="Set CURSOR_API_KEY and CURSOR_API_VERIFIED=true to enable",
            )
            return ToolResult(
                tool=AvailableTool.CURSOR,
                output="",
                files_written=[],
                success=False,
                stderr=(
                    "Cursor adapter disabled. "
                    "Set CURSOR_API_KEY and CURSOR_API_VERIFIED=true. "
                    "See legal/cursor_api_review.md"
                ),
            )

        # ToS-cleared path — implement when legal review complete
        # TODO legal/cursor_api_review.md: implement after ToS approval
        import httpx  # noqa: PLC0415

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "task": task,
            "context": context,
            "workspace_path": workspace_path,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.cursor.sh/v1/background-agent/generate",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                output = data.get("output", "")
                files_written = data.get("files_written", [])
                logger.info(
                    "cursor_adapter.success",
                    files_written=len(files_written),
                )
                return ToolResult(
                    tool=AvailableTool.CURSOR,
                    output=output,
                    files_written=files_written,
                    success=True,
                    stderr=None,
                )
        except Exception as exc:
            logger.error("cursor_adapter.error", error=str(exc))
            return ToolResult(
                tool=AvailableTool.CURSOR,
                output="",
                files_written=[],
                success=False,
                stderr=str(exc),
            )