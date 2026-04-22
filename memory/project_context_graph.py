from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog

from interpret.record import InterpretRecord
from memory.schemas import ProjectContextGraph

logger = structlog.get_logger()


class ProjectContextGraphStore:
    """Layer 3 memory — structured project knowledge on the filesystem.

    Storage path: ./data/graphs/{project_id}.json
    Uses pathlib exclusively — no os.path imports.
    Emits InterpretRecord(layer="memory") before every read and write.
    """

    _base: Path = Path("./data/graphs")

    def _path(self, project_id: str) -> Path:
        return self._base / f"{project_id}.json"

    async def save_graph(self, graph: ProjectContextGraph) -> None:
        """Serialize and write project graph to disk. Emits InterpretRecord before write."""
        self._emit("write", "save_graph", graph.project_id)
        self._base.mkdir(parents=True, exist_ok=True)
        self._path(graph.project_id).write_text(graph.model_dump_json(indent=2), encoding="utf-8")
        logger.info("layer3_graph_saved", project_id=graph.project_id)

    async def load_graph(self, project_id: str) -> ProjectContextGraph | None:
        """Read and deserialize project graph from disk. Emits InterpretRecord before read."""
        self._emit("read", "load_graph", project_id)
        path = self._path(project_id)
        if not path.exists():
            logger.info("layer3_graph_not_found", project_id=project_id)
            return None
        graph = ProjectContextGraph.model_validate_json(path.read_text(encoding="utf-8"))
        logger.info("layer3_graph_loaded", project_id=project_id)
        return graph

    async def graph_exists(self, project_id: str) -> bool:
        """Return True if a graph file exists for this project."""
        return self._path(project_id).exists()

    def _emit(self, action_type: str, action: str, key: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="ProjectContextGraphStore",
            action=f"{action_type}: {action} — project={key}",
            inputs={"project_id": key},
            expected_outputs={"graph": "ProjectContextGraph | None"},
            files_it_will_read=[str(self._path(key))],
            files_it_will_write=([str(self._path(key))] if action_type == "write" else []),
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            reversible=(action_type == "read"),
            workspace_files_affected=[str(self._path(key))],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.memory",
            action=record.action,
            layer=record.layer,
        )
        return record
