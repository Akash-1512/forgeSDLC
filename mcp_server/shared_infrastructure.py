"""
Shared infrastructure factory used by all MCP tool handlers.

All 8 tool files import from here rather than constructing their own components.
Any change to the infrastructure stack only needs to happen in one place.

Usage:
    from mcp_server.shared_infrastructure import build_infrastructure, build_agent_kwargs

    infra = build_infrastructure()
    kwargs = build_agent_kwargs(infra)
    agent = MyAgent(name="agent_N", **kwargs)
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

    # ContextCompressor uses a module-level ModelRouter singleton
    compressor = ContextCompressor()

    cwm = ContextWindowManager(
        estimator=estimator,
        compressor=compressor,
        specs=AGENT_CONTEXT_SPECS,
    )

    # Stores are singletons — reuses existing engine pools
    l1, l2, l3, l4, l5 = _get_stores()
    memory_archiver = MemoryArchiver(l1, l2, l3, l4, l5)

    # MemoryContextBuilder fetches singletons — no new engines
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
