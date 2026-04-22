from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from fastmcp import Context

from interpret.record import InterpretRecord
from memory.memory_context_builder import MemoryContextBuilder
from memory.organisational_memory import OrgMemory
from memory.schemas import OrgMemoryEntry

logger = structlog.get_logger()


async def recall_context(
    query: str,
    project_id: str,
    ctx: Context,
) -> dict[str, object]:
    """Retrieve cross-session, cross-tool project memory.

    Returns relevant decisions, patterns, and past runs for this project.
    Works across Cursor, Claude Code, VS Code+Copilot simultaneously.
    Layers queried: PipelineHistoryStore (L1) + OrgMemory (L2).
    """
    await ctx.report_progress(0, 100, "Searching project memory")

    record = InterpretRecord(
        layer="mcp_server",
        component="recall_context_tool",
        action=f"search memory: {query[:50]}",
        inputs={"query": query, "project_id": project_id},
        expected_outputs={"org_memory": "list", "similar_runs": "list"},
        files_it_will_read=[],
        files_it_will_write=[],
        external_calls=["postgresql", "chromadb_local"],
        model_selected=None,
        tool_delegated_to=None,
        reversible=True,
        workspace_files_affected=[],
        timestamp=datetime.now(tz=UTC),
    )
    logger.info(
        "recall_context.interpret_record",
        layer=record.layer,
        action=record.action,
    )

    builder = MemoryContextBuilder()
    context = await builder.build(query=query, project_id=project_id)

    await ctx.report_progress(100, 100, "Memory retrieved")

    return {
        "status": "ok",
        "project_id": project_id,
        "org_memory": [e.model_dump() for e in context.relevant_patterns],
        "similar_runs": [r.model_dump() for r in context.similar_runs],
        "layers_queried": context.layers_queried,
        "assembled_at": context.assembled_at,
        "interpret_record": record.model_dump(),
    }


async def save_decision(
    decision: str,
    rationale: str,
    project_id: str,
    ctx: Context,
) -> dict[str, object]:
    """Store an architectural decision visible to all connected tools.

    Persisted to ChromaDB (PersistentClient) — survives server restarts.
    Immediately retrievable via recall_context().
    """
    await ctx.report_progress(0, 100, "Saving decision to memory")

    entry = OrgMemoryEntry(
        entry_id=str(uuid4()),
        project_id=project_id,
        content=f"DECISION: {decision}\nRATIONALE: {rationale}",
        category="architecture",
        source_run_id="manual",
        timestamp=datetime.now(tz=UTC),
    )

    record = InterpretRecord(
        layer="mcp_server",
        component="save_decision_tool",
        action=f"upsert decision: {decision[:50]}",
        inputs={"decision": decision[:50], "project_id": project_id},
        expected_outputs={"entry_id": "str"},
        files_it_will_read=[],
        files_it_will_write=[],
        external_calls=["chromadb_local"],
        model_selected=None,
        tool_delegated_to=None,
        reversible=False,
        workspace_files_affected=[],
        timestamp=datetime.now(tz=UTC),
    )
    logger.info(
        "save_decision.interpret_record",
        layer=record.layer,
        action=record.action,
    )

    org = OrgMemory()
    await org.upsert(entry)

    await ctx.report_progress(100, 100, "Decision saved")

    return {
        "status": "saved",
        "entry_id": entry.entry_id,
        "project_id": project_id,
        "interpret_record": record.model_dump(),
    }
