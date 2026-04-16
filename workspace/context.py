from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GitCommit(BaseModel):
    """A single git commit — truncated for agent context packets."""

    model_config = ConfigDict(strict=True)

    sha: str            # first 8 chars of hexsha only
    message: str        # truncated to 72 chars (conventional commit limit)
    author: str
    timestamp: datetime


class WorkspaceContext(BaseModel):
    """Live snapshot of the developer's workspace.

    Populated by WorkspaceBridge and injected into every agent's ContextPacket.
    context_files: AGENTS.md/CLAUDE.md/.cursorrules that actually exist on disk.
    Agents check this field before assuming ContextFileManager has run.
    """

    model_config = ConfigDict(strict=True)

    root_path: str
    active_file: str | None         # currently focused file (set by IDE extension)
    selected_text: str | None       # selected text in editor (set by IDE extension)
    git_branch: str | None          # None for non-git dirs or detached HEAD
    git_uncommitted: bool           # True if repo has uncommitted changes
    git_last_commits: list[GitCommit]
    file_tree: dict[str, object]    # shallow 2-level tree
    language_stats: dict[str, int]  # {"py": 42, "yaml": 7, ...}
    package_files: list[str]        # requirements.txt, pyproject.toml, package.json
    existing_tests: list[str]       # test_*.py paths
    existing_docs: list[str]        # *.md paths
    docker_files: list[str]         # Dockerfile, docker-compose.yml
    github_actions: list[str]       # .github/workflows/*.yml
    # AGENTS.md, CLAUDE.md, .cursorrules, copilot-instructions.md if present
    # Empty list = ContextFileManager has not run yet for this project
    context_files: list[str]
    last_updated: datetime