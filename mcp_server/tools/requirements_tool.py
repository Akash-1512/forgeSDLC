from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def gather_requirements(prompt: str, project_id: str) -> dict[str, object]:
    """Convert a natural language description into structured requirements (PRD)."""
    logger.info("gather_requirements called", project_id=project_id)
    return {"status": "stub", "tool": "gather_requirements", "project_id": project_id}