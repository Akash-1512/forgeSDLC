"""
MCP resource handlers — serve project artefacts via URI to MCP clients.

MCP resources expose project memory and generated documents as readable
URIs. Cursor, Claude Code, and Copilot can reference these via their
resource browsers without calling a tool.
"""

from __future__ import annotations

import json

import structlog

from orchestrator.constants import CHECKPOINT_DB_PATH

logger = structlog.get_logger()


async def get_project_prd(project_id: str) -> str:
    """MCP Resource: return the PRD for a project from the checkpoint."""
    import sqlite3
    from pathlib import Path

    try:
        if not Path(CHECKPOINT_DB_PATH).exists():
            return json.dumps({"error": "No checkpoint found. Run gather_requirements first."})
        with sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False) as conn:
            from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

            cp = SqliteSaver(conn)
            config = {"configurable": {"thread_id": project_id}}
            existing = cp.get(config)
            if not existing:
                return json.dumps({"error": f"No state for project_id={project_id!r}"})
            prd = existing.get("channel_values", {}).get("prd", "")
            return json.dumps({"project_id": project_id, "prd": prd})
    except (OSError, RuntimeError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


async def get_project_adr(project_id: str) -> str:
    """MCP Resource: return the ADR for a project from the checkpoint."""
    import sqlite3
    from pathlib import Path

    try:
        if not Path(CHECKPOINT_DB_PATH).exists():
            return json.dumps({"error": "No checkpoint found. Run gather_requirements first."})
        with sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False) as conn:
            from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415

            cp = SqliteSaver(conn)
            config = {"configurable": {"thread_id": project_id}}
            existing = cp.get(config)
            if not existing:
                return json.dumps({"error": f"No state for project_id={project_id!r}"})
            adr = existing.get("channel_values", {}).get("adr", "")
            return json.dumps({"project_id": project_id, "adr": adr})
    except (OSError, RuntimeError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


async def get_project_memory(project_id: str, query: str = "architecture decisions") -> str:
    """MCP Resource: return Layer 2 memory for a project."""
    try:
        from memory.organizational_memory import OrgMemory  # noqa: PLC0415

        org = OrgMemory()
        entries = await org.search(query=query, project_id=project_id, limit=10)
        return json.dumps(
            {
                "project_id": project_id,
                "query": query,
                "entries": [e.model_dump() for e in entries],
                "count": len(entries),
            }
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return json.dumps({"error": str(exc)})
