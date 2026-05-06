"""Tests for mcp_server/shared_infrastructure.py (M22)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_build_infrastructure_returns_infrastructure_namedtuple() -> None:
    """build_infrastructure() returns a typed Infrastructure NamedTuple.

    Patches are on source modules because shared_infrastructure uses lazy imports.
    """
    from mcp_server.shared_infrastructure import Infrastructure, build_infrastructure

    # Patch the heavy deps at their source — lazy imports in build_infrastructure
    # mean we cannot patch "mcp_server.shared_infrastructure.X"
    with (
        patch("model_router.router.ModelRouter"),
        patch("context_management.token_estimator.TokenEstimator"),
        patch("context_management.context_compressor._get_router", return_value=MagicMock()),
        patch("context_management.context_compressor.ContextCompressor"),
        patch("context_management.context_window_manager.ContextWindowManager"),
        patch(
            "memory.memory_context_builder._get_stores",
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ),
        patch("memory.memory_archiver.MemoryArchiver"),
        patch("memory.memory_context_builder.MemoryContextBuilder"),
        patch("context_files.manager.ContextFileManager"),
        patch("workspace.bridge.WorkspaceBridge"),
        patch("workspace.diff_engine.DiffEngine"),
    ):
        infra = build_infrastructure()
        assert isinstance(infra, Infrastructure)


def test_build_agent_kwargs_returns_7_key_dict() -> None:
    """build_agent_kwargs() returns exactly the 7 keys BaseAgent expects."""
    from mcp_server.shared_infrastructure import Infrastructure, build_agent_kwargs

    infra = Infrastructure(
        model_router=MagicMock(),
        context_window_manager=MagicMock(),
        memory_archiver=MagicMock(),
        memory_context_builder=MagicMock(),
        context_file_manager=MagicMock(),
        workspace_bridge=MagicMock(),
        diff_engine=MagicMock(),
    )
    kwargs = build_agent_kwargs(infra)
    expected_keys = {
        "context_window_manager",
        "model_router",
        "memory_archiver",
        "memory_context_builder",
        "context_file_manager",
        "workspace_bridge",
        "diff_engine",
    }
    assert set(kwargs.keys()) == expected_keys


def test_build_agent_kwargs_maps_correctly() -> None:
    """build_agent_kwargs() maps Infrastructure fields to correct kwarg names."""
    from mcp_server.shared_infrastructure import Infrastructure, build_agent_kwargs

    mock_router = MagicMock(name="router")
    mock_cwm = MagicMock(name="cwm")

    infra = Infrastructure(
        model_router=mock_router,
        context_window_manager=mock_cwm,
        memory_archiver=MagicMock(),
        memory_context_builder=MagicMock(),
        context_file_manager=MagicMock(),
        workspace_bridge=MagicMock(),
        diff_engine=MagicMock(),
    )
    kwargs = build_agent_kwargs(infra)
    assert kwargs["model_router"] is mock_router
    assert kwargs["context_window_manager"] is mock_cwm
