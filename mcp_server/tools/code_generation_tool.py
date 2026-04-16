from __future__ import annotations

import structlog
from fastmcp import Context

from context_files.manager import ContextFileManager
from tool_router.router import ToolRouter

logger = structlog.get_logger()


async def route_code_generation(
    task: str,
    project_id: str,
    ctx: Context,
    workspace_path: str = ".",
    prd_summary: str = "",
    architecture_summary: str = "",
) -> dict[str, object]:
    """Delegate code generation to the best available AI coding tool.

    Context files (AGENTS.md / CLAUDE.md / .cursorrules / copilot-instructions.md)
    are written to the workspace BEFORE delegation so the tool has full project
    context. Emits InterpretRecord L13 (context_file_manager) then L5 (tool_router).

    Tool priority: Cursor Background Agent → Claude Code CLI → Devin → Direct LLM.
    """
    await ctx.report_progress(0, 100, "Detecting available tools")
    logger.info(
        "route_code_generation.start",
        project_id=project_id,
        workspace_path=workspace_path,
        task=task[:80],
    )

    cfm = ContextFileManager()
    router = ToolRouter(context_file_manager=cfm)

    await ctx.report_progress(20, 100, "Writing context files to workspace")

    # ToolRouter.route() writes context files (L13) then delegates (L5)
    result = await router.route(
        task=task,
        context=(
            f"Project: {project_id}\n"
            f"Requirements:\n{prd_summary}\n"
            f"Architecture:\n{architecture_summary}"
        ),
        project_id=project_id,
        workspace_path=workspace_path,
    )

    await ctx.report_progress(
        100, 100, f"Code generation complete via {result.tool.value}"
    )
    logger.info(
        "route_code_generation.complete",
        tool_used=result.tool.value,
        success=result.success,
        files_written=len(result.files_written),
    )

    return {
        "status": "ok" if result.success else "error",
        "tool_used": result.tool.value,
        "output": result.output,
        "files_written": result.files_written,
        "stderr": result.stderr,
        "project_id": project_id,
    }