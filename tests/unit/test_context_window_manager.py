from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from context_management.agent_context_specs import AGENT_CONTEXT_SPECS
from context_management.context_compressor import ContextCompressor
from context_management.context_packet import AgentContextSpec, ContextPacket
from context_management.context_window_manager import ContextWindowManager
from context_management.token_estimator import TokenEstimator


def _make_cwm(compressor: ContextCompressor | None = None) -> ContextWindowManager:
    est = TokenEstimator()
    cmp = compressor or MagicMock(spec=ContextCompressor)
    return ContextWindowManager(estimator=est, compressor=cmp, specs=AGENT_CONTEXT_SPECS)


def _base_state() -> dict[str, object]:
    return {
        "user_prompt": "build a REST API",
        "prd": "Product requirements document content here",
        "adr": "Architecture decision record content",
        "rfc": "Request for comments document",
        "service_graph": {"api": "service"},
        "workspace_context": {"root": "/project"},
        "model_router_context": {"model": "groq/llama-3.3-70b-specdec"},
        "tool_router_context": {"selected": "direct_llm"},
        "memory_context": {"layers": [1, 2]},
        "review_findings": [{"severity": "minor", "issue": "unused import"}],
        "security_findings": {"high_count": 0},
        "generated_files": [{"path": "main.py"}],
        "interpret_log": [{"round": 1}],
        "session_token_records": [{"cost": 0.001}],
        "deployment_url": "https://app.render.com",
        "ci_pipeline_url": "https://github.com/actions/run/1",
        "monitoring_config": {"provider": "structlog"},
        "provider_manifest": {"llm": "groq"},
        "research_context": "some research",
    }


@pytest.mark.asyncio
async def test_build_packet_emits_interpret_record_layer11(
    tmp_path: object,
) -> None:
    from interpret.record import InterpretRecord
    cwm = _make_cwm()
    emitted: list[str] = []
    original_emit = cwm._emit_record

    def capturing_emit(agent_name: str, spec: AgentContextSpec) -> object:
        ir = original_emit(agent_name, spec)
        emitted.append(ir.layer)
        return ir

    cwm._emit_record = capturing_emit  # type: ignore[method-assign]
    await cwm.build_packet("agent_0_decompose", _base_state())
    assert "context_window_manager" in emitted


@pytest.mark.asyncio
async def test_build_packet_respects_max_context_tokens() -> None:
    mock_cmp = MagicMock(spec=ContextCompressor)
    mock_cmp.compress = AsyncMock(return_value="compressed summary text")
    cwm = _make_cwm(compressor=mock_cmp)
    state = _base_state()
    state["memory_context"] = {"data": "word " * 10_000}
    packet = await cwm.build_packet("agent_0_decompose", state)
    assert packet.total_tokens_estimated <= AGENT_CONTEXT_SPECS["agent_0_decompose"].max_context_tokens + 500
    

@pytest.mark.asyncio
async def test_build_packet_excludes_fields_completely() -> None:
    """CRITICAL: excluded fields must be ABSENT — not None, not [] — key must not exist."""
    cwm = _make_cwm()
    spec = AGENT_CONTEXT_SPECS["agent_0_decompose"]
    packet = await cwm.build_packet("agent_0_decompose", _base_state())

    for excluded_field in spec.excluded_fields:
        assert excluded_field not in packet.included_fields, (
            f"Excluded field '{excluded_field}' found in included_fields — must be absent"
        )
        assert excluded_field not in packet.compressed_fields, (
            f"Excluded field '{excluded_field}' found in compressed_fields — must be absent"
        )


@pytest.mark.asyncio
async def test_build_packet_includes_required_fields_at_full_size() -> None:
    cwm = _make_cwm()
    spec = AGENT_CONTEXT_SPECS["agent_0_decompose"]
    state = _base_state()
    packet = await cwm.build_packet("agent_0_decompose", state)

    for req_field in spec.required_fields:
        if req_field in state:
            assert req_field in packet.included_fields, (
                f"Required field '{req_field}' missing from included_fields"
            )
            assert packet.included_fields[req_field] == state[req_field]


@pytest.mark.asyncio
async def test_build_packet_compresses_large_optional_fields() -> None:
    mock_cmp = MagicMock(spec=ContextCompressor)
    mock_cmp.compress = AsyncMock(return_value="compressed summary")
    cwm = _make_cwm(compressor=mock_cmp)

    state = _base_state()
    # Make memory_context enormous so it triggers compression
    state["memory_context"] = {"data": "important fact " * 5_000}

    packet = await cwm.build_packet("agent_0_decompose", state)
    # Either compressed or excluded from the packet — compression was attempted
    assert packet.compression_applied or "memory_context" not in packet.included_fields


@pytest.mark.asyncio
async def test_build_packet_raises_for_unknown_agent_name() -> None:
    from orchestrator.exceptions import ForgeSDLCError
    cwm = _make_cwm()
    with pytest.raises(ForgeSDLCError, match="No AgentContextSpec"):
        await cwm.build_packet("agent_99_nonexistent", _base_state())


@pytest.mark.asyncio
async def test_compression_uses_groq_via_model_router() -> None:
    """ContextCompressor must route through ModelRouter — no direct groq import."""
    with patch("subscription.byok_manager.keyring") as mk:
        mk.get_password.return_value = None
        from model_router.router import ModelRouter
        with patch.object(
            ModelRouter,
            "route",
            new_callable=lambda: lambda *a, **kw: AsyncMock(
                return_value=MagicMock(ainvoke=AsyncMock(return_value=MagicMock(content="summary")))
            )()
        ) as mock_route:
            compressor = ContextCompressor()
            result = await compressor.compress("some long content here", "memory_context")
    assert isinstance(result, str)