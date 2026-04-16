from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def deploy_project(project_id: str, environment: str) -> dict[str, object]:
    """Deploy the project to the target environment (HardGate — requires approval).

    Cold-start warning: Render free tier has 30-60s cold start.
    Use Render Starter ($7/mo) or equivalent for production.
    """
    logger.info("deploy_project called", project_id=project_id, environment=environment)
    return {"status": "stub", "tool": "deploy_project", "project_id": project_id}