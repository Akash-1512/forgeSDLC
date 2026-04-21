from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_security_scan_returns_gate_blocked_false_for_clean_code(
    tmp_path: Path,
) -> None:
    from fastmcp import Context
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.report_progress = AsyncMock()

    infra_tuple = (
        MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )

    async def fake_agent_run(state: dict) -> dict:
        state["security_findings"] = {
            "bandit_findings": [],
            "semgrep_findings": [],
            "pip_audit_findings": [],
            "dast_findings": [],
            "detect_secrets_findings": [],
            "threat_model_path": None,
            "gate_blocked": False,
        }
        state["security_gate"] = {"blocked": False, "reason": None}
        state["human_confirmation"] = ""
        return state

    with (
        patch(
            "mcp_server.tools.security_tool._build_security_infrastructure",
            return_value=infra_tuple,
        ),
        patch(
            "mcp_server.tools.security_tool._build_security_agent",
        ) as mock_build,
    ):
        from agents.agent_5b_security import SecurityAgent
        mock_agent = MagicMock(spec=SecurityAgent)
        mock_agent.run = AsyncMock(side_effect=fake_agent_run)
        mock_build.return_value = mock_agent

        from mcp_server.tools.security_tool import run_security_scan
        result = await run_security_scan(
            project_id=f"test-clean-{tmp_path.name}",
            ctx=mock_ctx,
            target_path=str(tmp_path),
            human_confirmation="100% GO",
        )

    assert result["status"] == "complete"
    assert result["gate_blocked"] is False


@pytest.mark.asyncio
async def test_run_security_scan_gate_blocked_stored_in_state(
    tmp_path: Path,
) -> None:
    from fastmcp import Context
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.report_progress = AsyncMock()

    infra_tuple = (
        MagicMock(), MagicMock(), MagicMock(),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )

    async def fake_agent_run_blocked(state: dict) -> dict:
        state["security_findings"] = {
            "bandit_findings": [{"severity": "HIGH", "tool": "bandit", "rule": "B101",
                                  "file": "main.py", "line": 5,
                                  "description": "hardcoded password",
                                  "fix_suggestion": None, "blocking": True}],
            "semgrep_findings": [],
            "pip_audit_findings": [],
            "dast_findings": [],
            "detect_secrets_findings": [],
            "threat_model_path": None,
            "gate_blocked": True,
        }
        state["security_gate"] = {
            "blocked": True,
            "reason": "1 HIGH/CRITICAL findings — deployment blocked",
        }
        state["human_confirmation"] = ""
        return state

    with (
        patch(
            "mcp_server.tools.security_tool._build_security_infrastructure",
            return_value=infra_tuple,
        ),
        patch(
            "mcp_server.tools.security_tool._build_security_agent",
        ) as mock_build,
    ):
        from agents.agent_5b_security import SecurityAgent
        mock_agent = MagicMock(spec=SecurityAgent)
        mock_agent.run = AsyncMock(side_effect=fake_agent_run_blocked)
        mock_build.return_value = mock_agent

        from mcp_server.tools.security_tool import run_security_scan
        result = await run_security_scan(
            project_id=f"test-blocked-{tmp_path.name}",
            ctx=mock_ctx,
            target_path=str(tmp_path),
            human_confirmation="100% GO",
        )

    assert result["status"] == "complete"
    assert result["gate_blocked"] is True
    assert "blocked" in result["instructions"].lower()