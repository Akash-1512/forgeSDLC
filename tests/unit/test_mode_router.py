from __future__ import annotations

from datetime import datetime, timezone

import pytest

from workspace.context import WorkspaceContext
from workspace.mode_router import Mode, ModeRouter


def _make_context(active_file: str | None = None) -> WorkspaceContext:
    return WorkspaceContext(
        root_path="/tmp/project",
        active_file=active_file,
        selected_text=None,
        git_branch="main",
        git_uncommitted=False,
        git_last_commits=[],
        file_tree={},
        language_stats={},
        package_files=[],
        existing_tests=[],
        existing_docs=[],
        docker_files=[],
        github_actions=[],
        context_files=[],
        last_updated=datetime.now(tz=timezone.utc),
    )


def _route(request: str, active_file: str | None = None) -> Mode:
    router = ModeRouter()
    ctx = _make_context(active_file=active_file)
    return router.route(request, ctx)


def test_requirements_keyword_routes_to_pipeline() -> None:
    assert _route("generate requirements for my API", active_file="app.py") == Mode.PIPELINE


def test_architecture_keyword_routes_to_pipeline() -> None:
    assert _route("design architecture for this service", active_file="app.py") == Mode.PIPELINE


def test_deploy_keyword_routes_to_pipeline() -> None:
    assert _route("deploy to production", active_file="app.py") == Mode.PIPELINE


def test_short_request_with_active_file_routes_to_inline() -> None:
    result = _route("fix this function", active_file="utils.py")
    assert result == Mode.INLINE


def test_short_request_without_active_file_routes_to_pipeline() -> None:
    result = _route("fix this function", active_file=None)
    assert result == Mode.PIPELINE


def test_long_request_with_active_file_routes_to_pipeline() -> None:
    long_request = "refactor " + "this code " * 30  # > 200 chars
    result = _route(long_request, active_file="main.py")
    assert result == Mode.PIPELINE


def test_ambiguous_request_routes_to_pipeline() -> None:
    """Medium-length request, no pipeline keywords, no active file → PIPELINE."""
    result = _route("update the handler to return JSON instead", active_file=None)
    assert result == Mode.PIPELINE