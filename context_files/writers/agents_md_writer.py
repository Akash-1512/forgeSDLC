from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog

logger = structlog.get_logger()

FILENAME = "AGENTS.md"


class AgentsMdWriter:
    """Writes AGENTS.md — universal context readable by any AI coding tool.

    Linux Foundation standard for multi-agent projects.
    Auto-updated after every SDLC action. Do not edit manually.
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
        decisions_bullets = "\n".join(f"- {d}" for d in decisions) if decisions else "- None yet"
        security_bullets = "\n".join(f"- {r}" for r in rules) if rules else "- None yet"

        content = f"""# forgeSDLC Project Context
# Auto-updated after every SDLC action. Do not edit manually.

## Project: {project_id}
## Current Phase: {current_phase}
## Last Updated: {datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}

## Requirements Summary
{prd_summary or "Not yet generated."}

## Architecture
{architecture_summary or "Not yet generated."}

## Key Decisions
{decisions_bullets}

## Security Rules
{security_bullets}

## Code Standards (enforced on all generated code)
- Functions ≤ 50 lines | Files ≤ 300 lines | Type hints everywhere
- Specific exceptions only — no bare `except Exception`
- `structlog` for logging — never `print()`
- Pydantic v2 for all data models
- Constants in `constants.py` — no magic numbers
- `ruff` for linting — not black, not isort
"""
        path = Path(workspace_path) / FILENAME
        path.write_text(content, encoding="utf-8")
        logger.info("agents_md_writer.written", path=str(path))
        return path
