from __future__ import annotations

import asyncio

import structlog

from orchestrator.constants import MCP_TOOL_TIMEOUT_SECONDS
from orchestrator.exceptions import ToolRouterError
from tool_router.context import AvailableTool, ToolResult

logger = structlog.get_logger()


class ClaudeCodeAdapter:
    """Invokes 'claude' CLI as a subprocess.

    Uses the developer's own ANTHROPIC_API_KEY (BYOK — not forgeSDLC's key).
    Claude Code reads CLAUDE.md automatically from cwd — ContextFileManager
    writes CLAUDE.md before this adapter is called.

    cwd must be str() not Path for Windows asyncio subprocess compatibility.
    """

    async def generate(
        self, task: str, context: str, workspace_path: str
    ) -> ToolResult:
        cmd = [
            "claude",
            "--print",                        # non-interactive, output to stdout
            "--allowedTools", "Edit,Write,Read",
            task,
        ]
        logger.info(
            "claude_code_adapter.invoking",
            workspace_path=workspace_path,
            task=task[:80],
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(workspace_path),      # str() required on Windows
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=MCP_TOOL_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise ToolRouterError(
                "Claude Code CLI not found in PATH. "
                "Install with: npm install -g @anthropic-ai/claude-code"
            ) from exc
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ToolRouterError(
                f"Claude Code CLI timed out after {MCP_TOOL_TIMEOUT_SECONDS}s"
            ) from exc

        output = stdout.decode(errors="replace")
        err = stderr.decode(errors="replace") if stderr else None
        success = proc.returncode == 0

        logger.info(
            "claude_code_adapter.complete",
            returncode=proc.returncode,
            output_chars=len(output),
        )
        return ToolResult(
            tool=AvailableTool.CLAUDE_CODE,
            output=output,
            files_written=self._parse_written_files(output),
            success=success,
            stderr=err,
        )

    def _parse_written_files(self, output: str) -> list[str]:
        """Parse 'Wrote file: <path>' lines from Claude Code CLI output."""
        lines = [
            line for line in output.splitlines()
            if line.startswith("Wrote file:")
        ]
        return [line.replace("Wrote file:", "").strip() for line in lines]