"""Shared pytest fixtures for all test suites."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_model_router():
    """A ModelRouter that routes to a mock adapter."""
    router = MagicMock()
    adapter = MagicMock()
    adapter.ainvoke = AsyncMock(return_value=MagicMock(content="mock response"))
    adapter.model_name = "groq/llama-3.3-70b-versatile"
    adapter.inner = adapter
    router.route = AsyncMock(return_value=adapter)
    return router


@pytest.fixture
def mock_archiver():
    """A MemoryArchiver with all methods mocked."""
    archiver = MagicMock()
    archiver.archive = AsyncMock()
    return archiver


@pytest.fixture
def mock_memory_builder():
    """A MemoryContextBuilder that returns an empty context."""
    from datetime import datetime

    builder = MagicMock()

    async def _build(query: str = "", project_id: str = "default") -> object:
        from memory.memory_context_builder import MemoryContext  # noqa: PLC0415

        return MemoryContext(
            project_id=project_id,
            query=query,
            similar_runs=[],
            relevant_patterns=[],
            project_graph=None,
            user_preferences=None,
            past_failures=[],
            layers_queried=[],
            assembled_at=datetime.now(tz=UTC).isoformat(),
        )

    builder.build = _build
    return builder


@pytest.fixture
def mock_cwm():
    """A ContextWindowManager that returns a minimal packet."""
    cwm = MagicMock()
    cwm.build_packet = AsyncMock(return_value=MagicMock())
    return cwm


@pytest.fixture
def mock_workspace():
    """A WorkspaceBridge with a minimal context."""
    bridge = MagicMock()
    ctx = MagicMock()
    ctx.root_path = "/tmp/test_workspace"
    bridge.get_context = AsyncMock(return_value=ctx)
    bridge.start = AsyncMock()
    return bridge


@pytest.fixture
def mock_cfm():
    """A ContextFileManager that does nothing."""
    cfm = MagicMock()
    cfm.write_all = AsyncMock(return_value=[])
    return cfm


@pytest.fixture
def mock_diff_engine():
    """A DiffEngine that does nothing."""
    engine = MagicMock()
    engine.apply_diff = AsyncMock()
    engine.generate_diff = AsyncMock(return_value=MagicMock())
    return engine


@pytest.fixture
def base_state() -> dict:
    """Minimal valid SDLCState for unit tests."""
    return {
        "user_prompt": "build a REST API",
        "mcp_session_id": "test-project-1",
        "human_confirmation": "",
        "human_corrections": [],
        "displayed_interpretation": "",
        "interpret_round": 0,
        "interpret_log": [],
        "trace_id": "test-trace-id",
        "mode": "mcp",
        "service_graph": None,
        "prd": "",
        "adr": "",
        "rfc": "",
        "generated_files": [],
        "review_findings": [],
        "security_findings": None,
        "security_gate": None,
        "test_coverage": 0.0,
        "ci_pipeline_url": "",
        "deployment_url": None,
        "monitoring_config": None,
        "project_context_graph": None,
        "budget_used_usd": 0.0,
        "budget_remaining_usd": 0.0,
        "subscription_tier": "free",
        "session_token_records": [],
        "tool_delegated_to": None,
        "workspace_context": None,
        "memory_context": None,
        "arch_validation": None,
        "deploy_blocked": False,
        "deploy_blocked_reason": "",
        "hitl_required": False,
        "hitl_reason": "",
        "slo_definitions": [],
        "tool_router_context": None,
        "model_router_context": None,
    }
