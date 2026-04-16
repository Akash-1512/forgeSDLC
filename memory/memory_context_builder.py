from __future__ import annotations

from datetime import datetime, timezone

import structlog
from pydantic import BaseModel

from interpret.record import InterpretRecord
from memory.organisational_memory import OrgMemory
from memory.pipeline_history_store import PipelineHistoryStore
from memory.post_mortem_records import PostMortemStore
from memory.project_context_graph import ProjectContextGraphStore
from memory.schemas import (
    OrgMemoryEntry,
    PipelineRunRecord,
    PostMortem,
    ProjectContextGraph,
    UserPreferenceProfile,
)
from memory.user_preference_profile import UserPreferenceStore

logger = structlog.get_logger()


class MemoryContext(BaseModel):
    """Assembled from all 5 memory layers.

    Injected into every agent's ContextPacket in Sessions 09+.
    Each layer read emits its own InterpretRecord via the respective store.
    """

    project_id: str
    query: str
    similar_runs: list[PipelineRunRecord]           # Layer 1 — PostgreSQL
    relevant_patterns: list[OrgMemoryEntry]         # Layer 2 — ChromaDB
    project_graph: ProjectContextGraph | None       # Layer 3 — filesystem JSON
    user_preferences: UserPreferenceProfile | None  # Layer 4 — PostgreSQL
    past_failures: list[PostMortem]                 # Layer 5 — PostgreSQL
    layers_queried: list[str]
    assembled_at: str                               # ISO timestamp


class MemoryContextBuilder:
    """Assembles MemoryContext from all 5 memory layers.

    Emits InterpretRecord(layer="memory") before assembly.
    Each layer store emits its own InterpretRecord during its read.
    """

    def __init__(self) -> None:
        self._l1 = PipelineHistoryStore()
        self._l2 = OrgMemory()
        self._l3 = ProjectContextGraphStore()
        self._l4 = UserPreferenceStore()
        self._l5 = PostMortemStore()

    async def build(
        self,
        query: str,
        project_id: str,
        user_id: str = "default",
        run_limit: int = 5,
        org_limit: int = 10,
        failure_limit: int = 5,
    ) -> MemoryContext:
        """Query all 5 memory layers and return unified context."""
        self._emit_record(query, project_id)

        similar_runs = await self._l1.get_similar_runs(project_id, limit=run_limit)
        relevant_patterns = await self._l2.search(query, project_id, limit=org_limit)
        project_graph = await self._l3.load_graph(project_id)
        user_preferences = await self._l4.load_profile(user_id)
        past_failures = await self._l5.get_recent_failures(project_id, limit=failure_limit)

        context = MemoryContext(
            project_id=project_id,
            query=query,
            similar_runs=similar_runs,
            relevant_patterns=relevant_patterns,
            project_graph=project_graph,
            user_preferences=user_preferences,
            past_failures=past_failures,
            layers_queried=[
                "pipeline_history_store",
                "org_memory",
                "project_context_graph",
                "user_preference_profile",
                "post_mortem_records",
            ],
            assembled_at=datetime.now(tz=timezone.utc).isoformat(),
        )

        logger.info(
            "memory_context_builder.build",
            project_id=project_id,
            similar_runs=len(similar_runs),
            relevant_patterns=len(relevant_patterns),
            project_graph=project_graph is not None,
            user_preferences=user_preferences is not None,
            past_failures=len(past_failures),
        )
        return context

    def _emit_record(self, query: str, project_id: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="MemoryContextBuilder",
            action=(
                f"build: assembling 5-layer context — "
                f"project={project_id} query={query[:40]}"
            ),
            inputs={"query": query[:40], "project_id": project_id},
            expected_outputs={"context": "MemoryContext"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=["postgresql", "chromadb_local", "filesystem"],
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