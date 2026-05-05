from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog

from context_files.writers.agents_md_writer import AgentsMdWriter
from context_files.writers.claude_md_writer import ClaudeMdWriter
from context_files.writers.copilot_instructions_writer import CopilotInstructionsWriter
from context_files.writers.cursorrules_writer import CursorrulesWriter
from interpret.record import InterpretRecord

logger = structlog.get_logger()


class ContextFileManager:
    """Writes AGENTS.md, CLAUDE.md, .cursorrules, copilot-instructions.md.

    Called BEFORE ToolRouter.route() — ordering is tested explicitly.
    Emits InterpretRecord Layer 13 (context_file_manager) before each write.
    Idempotent: same inputs → same file content. Calling twice is safe.
    """

    def __init__(self) -> None:
        self._writers = [
            AgentsMdWriter(),
            ClaudeMdWriter(),
            CursorrulesWriter(),
            CopilotInstructionsWriter(),
        ]

    async def write_all(
        self,
        project_id: str,
        workspace_path: str,
        current_phase: str = "requirements",
        prd_summary: str = "",
        architecture_summary: str = "",
        key_decisions: list[str] | None = None,
        security_rules: list[str] | None = None,
    ) -> list[str]:
        """Write all context files. Returns list of written file paths."""
        written: list[str] = []
        kwargs = {
            "workspace_path": workspace_path,
            "project_id": project_id,
            "current_phase": current_phase,
            "prd_summary": prd_summary,
            "architecture_summary": architecture_summary,
            "key_decisions": key_decisions or [],
            "security_rules": security_rules or [],
        }

        for writer in self._writers:
            # Emit InterpretRecord Layer 13 BEFORE each file write
            self._emit_record(writer.filename, project_id, workspace_path)
            path = await writer.write(**kwargs)
            written.append(str(path))

        logger.info(
            "context_file_manager.write_all_complete",
            project_id=project_id,
            files_written=len(written),
        )
        return written

    def _emit_record(self, filename: str, project_id: str, workspace_path: str) -> InterpretRecord:
        record = InterpretRecord(
            layer="context_file_manager",
            component="ContextFileManager",
            action=f"writing {filename} for project {project_id}",
            inputs={"project_id": project_id, "filename": filename},
            expected_outputs={"file": filename},
            files_it_will_read=[],
            files_it_will_write=[str(Path(workspace_path) / filename)],
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[filename],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.context_file_manager",
            action=record.action,
            layer=record.layer,
        )
        return record
