from __future__ import annotations

import structlog

logger = structlog.get_logger()


async def run_security_scan(project_id: str, target_path: str) -> dict[str, object]:
    """Run SAST + STRIDE security analysis on the project."""
    logger.info("run_security_scan called", project_id=project_id)
    return {"status": "stub", "tool": "run_security_scan", "project_id": project_id}