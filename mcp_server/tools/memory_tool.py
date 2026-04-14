from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def recall_context(project_id: str, query: str) -> dict[str, object]:
    """Retrieve relevant cross-session memory for a project."""
    logger.info("recall_context called", project_id=project_id)
    return {"status": "stub", "tool": "recall_context", "project_id": project_id}


async def save_decision(
    project_id: str, decision: str, rationale: str
) -> dict[str, object]:
    """Persist an architectural decision to long-term memory."""
    logger.info("save_decision called", project_id=project_id)
    return {"status": "stub", "tool": "save_decision", "project_id": project_id}