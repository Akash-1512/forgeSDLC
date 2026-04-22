from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from pathlib import Path

import structlog
from git import InvalidGitRepositoryError, Repo
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from interpret.record import InterpretRecord
from workspace.context import GitCommit, WorkspaceContext

logger = structlog.get_logger()


class WorkspaceBridge:
    """Maintains a live snapshot of the developer's workspace.

    Runs as a background asyncio task — await start() to begin watching.
    READ-ONLY: never writes any file under any circumstance.
    files_it_will_write is always [] in every InterpretRecord emitted here.
    Emits InterpretRecord Layer 2 (workspace) before every get_context() call.
    """

    def __init__(self) -> None:
        self._context: WorkspaceContext | None = None
        self._observer: Observer | None = None
        self._path: Path | None = None

    async def start(self, workspace_path: str) -> None:
        """Begin watching the workspace. Triggers initial refresh."""
        self._path = Path(workspace_path)
        await self._refresh()
        handler = _RefreshHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._path), recursive=True)
        self._observer.start()
        logger.info("workspace_bridge.started", path=workspace_path)

    async def stop(self) -> None:
        """Stop the filesystem watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("workspace_bridge.stopped")

    async def get_context(self) -> WorkspaceContext:
        """Return the current workspace snapshot. Emits L2 InterpretRecord first."""
        # Emit InterpretRecord Layer 2 BEFORE returning — read-only, always
        InterpretRecord(
            layer="workspace",
            component="WorkspaceBridge",
            action="reading workspace context snapshot",
            inputs={"root_path": str(self._path)},
            expected_outputs={"workspace_context": "WorkspaceContext"},
            files_it_will_read=[str(self._path)] if self._path else [],
            files_it_will_write=[],  # ALWAYS [] — WorkspaceBridge is read-only
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        if self._context is None:
            await self._refresh()
        assert self._context is not None
        return self._context

    async def _refresh(self) -> None:
        """Rebuild WorkspaceContext from filesystem + git state. Never writes."""

        p = self._path or Path(".")

        # Git state — handle non-git directories gracefully
        branch: str | None = None
        uncommitted = False
        commits: list[GitCommit] = []
        try:
            repo = Repo(str(p))
            if not repo.head.is_detached:
                branch = repo.active_branch.name
            uncommitted = repo.is_dirty(untracked_files=True)
            commits = [
                GitCommit(
                    sha=c.hexsha[:8],
                    message=c.message.strip()[:72],
                    author=str(c.author),
                    timestamp=datetime.fromtimestamp(c.committed_date, tz=UTC),
                )
                for c in list(repo.iter_commits())[:5]
            ]
        except InvalidGitRepositoryError:
            pass  # not a git repo — all git fields stay at zero values
        except Exception as exc:
            logger.warning("workspace_bridge.git_error", error=str(exc))

        # Filesystem scan — language stats
        lang_stats: dict[str, int] = {}
        try:
            for f in p.rglob("*"):
                if f.is_file() and not any(
                    part.startswith(".") or part in ("__pycache__", "node_modules")
                    for part in f.relative_to(p).parts
                ):
                    ext = f.suffix.lstrip(".")
                    if ext:
                        lang_stats[ext] = lang_stats.get(ext, 0) + 1
        except Exception as exc:
            logger.warning("workspace_bridge.scan_error", error=str(exc))

        # Context files — confirm ContextFileManager has run
        context_files = [
            str(cf)
            for cf in [
                p / "AGENTS.md",
                p / "CLAUDE.md",
                p / ".cursorrules",
                p / ".github" / "copilot-instructions.md",
            ]
            if cf.exists()
        ]

        self._context = WorkspaceContext(
            root_path=str(p),
            active_file=None,
            selected_text=None,
            git_branch=branch,
            git_uncommitted=uncommitted,
            git_last_commits=commits,
            file_tree=self._build_file_tree(p),
            language_stats=lang_stats,
            package_files=self._find_files(
                p, ["requirements.txt", "pyproject.toml", "package.json"]
            ),
            existing_tests=self._find_pattern(p, "test_*.py"),
            existing_docs=self._find_pattern(p, "*.md"),
            docker_files=self._find_files(
                p, ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
            ),
            github_actions=[str(f) for f in p.glob(".github/workflows/*.yml")],
            context_files=context_files,
            last_updated=datetime.now(tz=UTC),
        )
        logger.info(
            "workspace_bridge.refreshed",
            branch=branch,
            uncommitted=uncommitted,
            context_files=len(context_files),
        )

    def _find_files(self, base: Path, names: list[str]) -> list[str]:
        return [str(base / n) for n in names if (base / n).exists()]

    def _find_pattern(self, base: Path, pattern: str) -> list[str]:
        return [
            str(f)
            for f in base.rglob(pattern)
            if "__pycache__" not in str(f) and "node_modules" not in str(f)
        ]

    def _build_file_tree(self, base: Path) -> dict[str, object]:
        """Shallow 2-level file tree for agent context (not full repo scan)."""
        tree: dict[str, object] = {}
        try:
            for item in sorted(base.iterdir()):
                if item.name.startswith(".") or item.name in (
                    "__pycache__",
                    "node_modules",
                    ".venv",
                    "venv",
                ):
                    continue
                if item.is_dir():
                    tree[item.name] = {
                        child.name: "file"
                        for child in sorted(item.iterdir())[:10]
                        if not child.name.startswith(".") and child.name != "__pycache__"
                    }
                else:
                    tree[item.name] = "file"
        except PermissionError:
            pass
        return tree


class _RefreshHandler(FileSystemEventHandler):
    """Watchdog handler that triggers async workspace refresh on file events."""

    def __init__(self, bridge: WorkspaceBridge) -> None:
        self._bridge = bridge
        self._loop: asyncio.AbstractEventLoop | None = None
        with contextlib.suppress(RuntimeError):
            self._loop = asyncio.get_event_loop()

    def on_any_event(self, event: object) -> None:
        if hasattr(event, "is_directory") and event.is_directory:  # type: ignore[union-attr]
            return
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._bridge._refresh(), self._loop)
