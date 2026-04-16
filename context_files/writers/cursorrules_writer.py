from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger()

FILENAME = ".cursorrules"


class CursorrulesWriter:
    """Writes .cursorrules — auto-read by Cursor from project root.

    Cursor reads .cursorrules automatically when opening the workspace.
    ContextFileManager writes this before CursorAdapter is called.
    """

    filename: str = FILENAME

    async def write(
        self,
        workspace_path: str,
        project_id: str,
        current_phase: str = "requirements",
        prd_summary: str = "",
        architecture_summary: str = "",
        key_decisions: list[str] | None = None,
        security_rules: list[str] | None = None,
    ) -> Path:
        decisions = key_decisions or []
        rules = security_rules or []
        decisions_text = (
            "\n".join(f"  - {d}" for d in decisions)
            if decisions else "  - None yet"
        )
        security_text = (
            "\n".join(f"  - {r}" for r in rules)
            if rules else "  - None yet"
        )

        content = f"""# forgeSDLC Cursor Rules
# Project: {project_id} | Phase: {current_phase}
# Auto-generated. Do not edit manually.

You are working on project '{project_id}' managed by forgeSDLC.

## Current Phase
{current_phase}

## Project Context
{prd_summary or "Requirements not yet available."}

## Architecture
{architecture_summary or "Architecture not yet designed."}

## Key Decisions
{decisions_text}

## Security Rules
{security_text}

## Code Standards
  - Type hints on all functions and variables
  - structlog for all logging — never print()
  - Pydantic v2 with ConfigDict(strict=True)
  - Specific exception handling — no bare except
  - No magic numbers — import from constants.py
  - Functions ≤ 50 lines | Files ≤ 300 lines
  - ruff for linting (not black, not isort)

## File Reporting
When writing files, output: Wrote file: <relative_path>
"""
        path = Path(workspace_path) / FILENAME
        path.write_text(content, encoding="utf-8")
        logger.info("cursorrules_writer.written", path=str(path))
        return path