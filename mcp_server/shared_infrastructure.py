"""
H2 Fix: shared infrastructure factory for all MCP tool handlers.

Previously each of the 8 tool files had an identical copy of _build_infrastructure()
(400+ lines of duplication). Any change to the infrastructure stack required updating
8 files. This module is the single source of truth.

Usage:
    from mcp_server.shared_infrastructure import build_infrastructure

    infra = build_infrastructure()
    model_router, cwm, memory_archiver, memory_ctx_builder, cfm, workspace_bridge, diff_engine = infra  # noqa: E501
"""

from __future__ import annotations

from typing import NamedTuple

import structlog

logger = structlog.get_logger()


class Infrastructure(NamedTuple):
    """Typed container for all shared infrastructure components."""

    model_router: object
    context_window_manager: object
    memory_archiver: object
    memory_context_builder: object
    context_file_manager: object
    workspace_bridge: object
    diff_engine: object


def build_infrastructure() -> Infrastructure:
    """Instantiate all shared infrastructure components.

    H1 + H2 combined fix:
    - Stores use module-level singletons (MemoryContextBuilder fix from H1)
    - This function called from all 8 tool handlers (H2 deduplication)
    - ModelRouter, ContextWindowManager, WorkspaceBridge: one instance per tool call
      (acceptable — these are lightweight, stateless coordinators)
    """
    from context_files.manager import ContextFileManager
    from context_management.agent_context_specs import AGENT_CONTEXT_SPECS
    from context_management.context_compressor import ContextCompressor
    from context_management.context_window_manager import ContextWindowManager
    from context_management.token_estimator import TokenEstimator
    from memory.memory_archiver import MemoryArchiver
    from memory.memory_context_builder import MemoryContextBuilder, _get_stores
    from model_router.router import ModelRouter
    from workspace.bridge import WorkspaceBridge
    from workspace.diff_engine import DiffEngine

    model_router = ModelRouter()
    estimator = TokenEstimator()

    # H13 Fix: ContextCompressor uses module-level ModelRouter singleton
    compressor = ContextCompressor()

    cwm = ContextWindowManager(
        estimator=estimator,
        compressor=compressor,
        specs=AGENT_CONTEXT_SPECS,
    )

    # H1 Fix: stores are singletons — reuses existing engines
    l1, l2, l3, l4, l5 = _get_stores()
    memory_archiver = MemoryArchiver(l1, l2, l3, l4, l5)

    # H1 Fix: MemoryContextBuilder.__init__ now fetches singletons
    memory_ctx_builder = MemoryContextBuilder()

    cfm = ContextFileManager()
    workspace_bridge = WorkspaceBridge()
    diff_engine = DiffEngine()

    logger.info("shared_infrastructure.built")
    return Infrastructure(
        model_router=model_router,
        context_window_manager=cwm,
        memory_archiver=memory_archiver,
        memory_context_builder=memory_ctx_builder,
        context_file_manager=cfm,
        workspace_bridge=workspace_bridge,
        diff_engine=diff_engine,
    )


def build_agent_kwargs(infra: Infrastructure) -> dict[str, object]:
    """Return the kwargs dict passed to every BaseAgent subclass constructor."""
    return {
        "context_window_manager": infra.context_window_manager,
        "model_router": infra.model_router,
        "memory_archiver": infra.memory_archiver,
        "memory_context_builder": infra.memory_context_builder,
        "context_file_manager": infra.context_file_manager,
        "workspace_bridge": infra.workspace_bridge,
        "diff_engine": infra.diff_engine,
    }
