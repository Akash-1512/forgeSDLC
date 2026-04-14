from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def setup_monitoring(project_id: str, deployment_url: str) -> dict[str, object]:
    """Configure monitoring and alerting for a deployed project."""
    logger.info("setup_monitoring called", project_id=project_id)
    return {"status": "stub", "tool": "setup_monitoring", "project_id": project_id}