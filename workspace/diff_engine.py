from __future__ import annotations

import difflib
from datetime import UTC, datetime
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from interpret.record import InterpretRecord

logger = structlog.get_logger()

_BAK_EXTENSION = ".forgesdlc.bak"


class UnifiedDiff(BaseModel):
    """Represents a computed unified diff ready to apply."""

    model_config = ConfigDict(strict=True)

    filepath: str
    diff: str
    reason: str
    original_content: str  # stored for backup and restore
    new_content: str


class DiffEngine:
    """Generates unified diffs and applies them with backup.

    Emits InterpretRecord Layer 3 (diff) before generation AND before apply.
    Backup: {filepath}.forgesdlc.bak — created BEFORE any write.
    Backup skipped for new files (nothing to back up).
    Restore: restore_from_backup() reverts to original and deletes backup.
    """

    async def generate_diff(
        self,
        filepath: str,
        new_content: str,
        reason: str,
    ) -> UnifiedDiff:
        """Compute a unified diff between current and new content.

        Emits L3 InterpretRecord before reading the current file.
        """
        InterpretRecord(
            layer="diff",
            component="DiffEngine",
            action=f"generating diff: {Path(filepath).name} — {reason}",
            inputs={"filepath": filepath, "reason": reason},
            expected_outputs={"diff": "unified diff string"},
            files_it_will_read=[filepath],
            files_it_will_write=[],
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[filepath],
            timestamp=datetime.now(tz=UTC),
        )
        p = Path(filepath)
        current = p.read_text(encoding="utf-8") if p.exists() else ""
        diff_text = self._compute_diff(current, new_content, filepath)
        logger.info(
            "diff_engine.generated",
            filepath=filepath,
            diff_lines=len(diff_text.splitlines()),
        )
        return UnifiedDiff(
            filepath=filepath,
            diff=diff_text,
            reason=reason,
            original_content=current,
            new_content=new_content,
        )

    async def apply_diff(self, diff: UnifiedDiff) -> None:
        """Apply diff to disk. Backup original BEFORE writing.

        Emits L3 InterpretRecord before any write.
        Backup extension: .forgesdlc.bak (exact — not .bak, not .backup).
        New files: backup skipped (nothing to back up — no empty .bak created).
        """
        p = Path(diff.filepath)
        bak = Path(f"{diff.filepath}{_BAK_EXTENSION}")

        InterpretRecord(
            layer="diff",
            component="DiffEngine",
            action=f"applying diff: {p.name}",
            inputs={"filepath": diff.filepath},
            expected_outputs={"backup": str(bak)},
            files_it_will_read=[diff.filepath],
            files_it_will_write=[diff.filepath, str(bak)],
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,  # backup exists — restore_from_backup() reverts
            workspace_files_affected=[diff.filepath],
            timestamp=datetime.now(tz=UTC),
        )

        # Write backup FIRST — only if original file exists
        if p.exists():
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info("diff_engine.backup_created", backup=str(bak))

        # Apply new content
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(diff.new_content, encoding="utf-8")
        logger.info("diff_engine.applied", filepath=diff.filepath)

    async def restore_from_backup(self, filepath: str) -> bool:
        """Restore original file from .forgesdlc.bak.

        Returns True if restored, False if no backup exists.
        Deletes the backup after successful restore.
        """
        bak = Path(f"{filepath}{_BAK_EXTENSION}")
        if not bak.exists():
            logger.info("diff_engine.no_backup_found", filepath=filepath)
            return False
        Path(filepath).write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
        bak.unlink()
        logger.info("diff_engine.restored_from_backup", filepath=filepath)
        return True

    def _compute_diff(self, original: str, new: str, filepath: str) -> str:
        """Compute unified diff between original and new content."""
        lines_old = original.splitlines(keepends=True)
        lines_new = new.splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                lines_old,
                lines_new,
                fromfile=f"a/{Path(filepath).name}",
                tofile=f"b/{Path(filepath).name}",
            )
        )
