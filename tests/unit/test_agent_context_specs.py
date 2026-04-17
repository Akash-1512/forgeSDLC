from __future__ import annotations

import pytest

from context_management.agent_context_specs import AGENT_CONTEXT_SPECS, print_spec_table
from context_management.context_packet import AgentContextSpec
import pydantic


def test_all_14_agents_have_specs() -> None:
    expected = {
        "agent_0_decompose", "agent_1_requirements", "agent_2_stack",
        "agent_3_architecture", "agent_4_tool_router", "agent_5_coord_review",
        "agent_5b_security", "agent_6_test_coord", "agent_7_cicd",
        "agent_8_deploy", "agent_9_monitor", "agent_10_docs",
        "agent_11_integration", "agent_12_contracts", "agent_13_platform",
    }
    assert set(AGENT_CONTEXT_SPECS.keys()) == expected
    assert len(AGENT_CONTEXT_SPECS) == 15  # 14 numbered + agent_5b


def test_model_router_context_required_for_all_14_agents() -> None:
    for agent_name, spec in AGENT_CONTEXT_SPECS.items():
        assert "model_router_context" in spec.required_fields, (
            f"Agent '{agent_name}' is missing 'model_router_context' in required_fields"
        )


def test_tool_router_context_required_for_agent_4() -> None:
    spec = AGENT_CONTEXT_SPECS["agent_4_tool_router"]
    assert "tool_router_context" in spec.required_fields


def test_tool_router_context_required_for_agent_6() -> None:
    spec = AGENT_CONTEXT_SPECS["agent_6_test_coord"]
    assert "tool_router_context" in spec.required_fields


def test_tool_router_context_not_required_for_other_agents() -> None:
    """Only Agent 4 and Agent 6 delegate via ToolRouter — others must not require it."""
    delegation_agents = {"agent_4_tool_router", "agent_6_test_coord", "agent_5_coord_review"}
    for agent_name, spec in AGENT_CONTEXT_SPECS.items():
        if agent_name not in delegation_agents:
            assert "tool_router_context" not in spec.required_fields, (
                f"Agent '{agent_name}' should NOT require tool_router_context"
            )


def test_excluded_cannot_overlap_required_raises_validation_error() -> None:
    """Pydantic v2 cross-field validator must raise when required ∩ excluded ≠ ∅."""
    with pytest.raises(pydantic.ValidationError, match="overlap"):
        AgentContextSpec(
            agent_name="bad_spec",
            required_fields=["prd", "model_router_context"],
            optional_fields=[],
            excluded_fields=["prd"],  # overlap with required!
            max_context_tokens=8_000,
            summarise_threshold_tokens=2_000,
            memory_layers=[],
            priority_order=["prd"],
        )


def test_agent_11_max_tokens_is_20000() -> None:
    """Agent 11 uses gemini-3.1-pro-preview (1M context) — 20K budget."""
    spec = AGENT_CONTEXT_SPECS["agent_11_integration"]
    assert spec.max_context_tokens == 20_000


def test_agent_9_max_tokens_is_6000_not_20000() -> None:
    """Agent 9 (Monitor) has the tightest budget — 6K tokens."""
    spec = AGENT_CONTEXT_SPECS["agent_9_monitor"]
    assert spec.max_context_tokens == 6_000
    assert spec.max_context_tokens != 20_000


def test_print_spec_table_outputs_all_14_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_spec_table()
    captured = capsys.readouterr()
    for agent_name in AGENT_CONTEXT_SPECS:
        assert agent_name in captured.out, (
            f"Agent '{agent_name}' missing from print_spec_table output"
        )