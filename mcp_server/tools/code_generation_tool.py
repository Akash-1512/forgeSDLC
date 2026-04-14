from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def route_code_generation(
    project_id: str, task: str, context: str
) -> dict[str, object]:
    """Delegate code generation to the highest-priority available tool (ToolRouter).

    Agent 4 does NOT call an internal LLM — it delegates to Cursor, Claude Code,
    Devin, or Direct LLM in priority order.
    """
    logger.info("route_code_generation called", project_id=project_id)
    return {
        "status": "stub",
        "tool": "route_code_generation",
        "project_id": project_id,
    }