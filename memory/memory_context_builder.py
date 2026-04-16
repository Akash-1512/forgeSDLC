from __future__ import annotations

from datetime import datetime, timezone
from typing import TypedDict

import structlog

from interpret.record import InterpretRecord
from memory.organisational_memory import OrgMemory
from memory.pipeline_history_store import PipelineHistoryStore
from memory.schemas import OrgMemoryEntry, PipelineRunRecord

logger = structlog.get_logger()


class MemoryContext(TypedDict):
    """Unified memory context assembled from all available layers.

    Passed to agents in Sessions 09+ so they have full project history
    before executing any SDLC action.
    """

    project_id: str
    query: str
    org_memory: list[OrgMemoryEntry]
    similar_runs: list[PipelineRunRecord]
    layers_queried: list[str]
    assembled_at: str  # ISO timestamp


class MemoryContextBuilder:
    """Assembles MemoryContext from Layers 1 and 2.

    Emits InterpretRecord(layer="memory") before assembly.
    Agents call build() once per SDLC action to get full project context.
    """

    def __init__(self) -> None:
        self._store = PipelineHistoryStore()
        self._org = OrgMemory()

    async def build(
        self,
        query: str,
        project_id: str,
        run_limit: int = 5,
        org_limit: int = 10,
    ) -> MemoryContext:
        """Query all available memory layers and return unified context."""
        self._emit_record(query, project_id)

        similar_runs = await self._store.get_similar_runs(
            project_id, limit=run_limit
        )
        org_entries = await self._org.search(
            query, project_id, limit=org_limit
        )

        context: MemoryContext = {
            "project_id": project_id,
            "query": query,
            "org_memory": org_entries,
            "similar_runs": similar_runs,
            "layers_queried": ["pipeline_history_store", "org_memory"],
            "assembled_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        logger.info(
            "memory_context_builder.build",
            project_id=project_id,
            org_entries=len(org_entries),
            similar_runs=len(similar_runs),
        )
        return context

    def _emit_record(self, query: str, project_id: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="MemoryContextBuilder",
            action=f"build: assembling context — project={project_id} query={query[:40]}",
            inputs={"query": query[:40], "project_id": project_id},
            expected_outputs={"context": "MemoryContext"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=["postgresql", "chromadb_local"],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "interpret_record.memory",
            action=record.action,
            layer=record.layer,
        )
        return record