from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord
from tool_router.router import ToolRouter

logger = structlog.get_logger()

_COVERAGE_THRESHOLD = 80.0
_MAX_RETRIES = 3


class TestCoordinatorAgent(BaseAgent):
    """Agent 6 — delegates test generation via ToolRouter, owns 80% coverage gate.

    Coverage measured via pytest subprocess using sys.executable (not "python").
    3 auto-retries with uncovered lines before HITL escalation.
    tool_router_context REQUIRED in AgentContextSpec (Session 08 — verified in tests).
    """

    def __init__(self, tool_router: ToolRouter, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._tool_router = tool_router

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Preview test gen delegation. Emits L1 InterpretRecord."""
        from tool_router.context import AvailableTool  # noqa: PLC0415

        available_tools = await self._tool_router.detect_available_tools()
        selected = available_tools[0] if available_tools else AvailableTool.DIRECT_LLM
        retry_count = int(state.get("test_retry_count", 0) or 0)
        current_coverage = float(state.get("test_coverage", 0.0) or 0.0)

        record = InterpretRecord(
            layer="agent",
            component="TestCoordinatorAgent",
            action=(
                f"TEST GENERATION + COVERAGE GATE\n"
                f"Delegate to: {selected.value}\n"
                f"Target: 80% line coverage\n"
                f"Current coverage: {current_coverage:.1f}%\n"
                f"Retry: {retry_count}/{_MAX_RETRIES}\n"
                f"Context: AGENTS.md + RFC (test patterns, expected behaviour)"
            ),
            inputs={
                "selected_tool": selected.value,
                "retry": retry_count,
                "current_coverage": current_coverage,
            },
            expected_outputs={
                "test_files": "list[str]",
                "coverage": "float",
            },
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[selected.value, "pytest subprocess"],
            model_selected=None,  # delegates — no internal LLM for test gen
            tool_delegated_to=selected.value,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.agent",
            layer=record.layer,
            component="TestCoordinatorAgent",
            retry=retry_count,
        )
        return record

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Delegate test generation then measure and gate on coverage."""
        workspace_ctx = await self.workspace.get_context()
        workspace_root = workspace_ctx.root_path

        # Write context files before delegation
        await self.cfm.write_all(
            project_id=str(state.get("mcp_session_id", "default")),
            workspace_path=workspace_root,
            current_phase="testing",
            prd_summary=str(state.get("prd", ""))[:500],
            architecture_summary=str(state.get("rfc", ""))[:300],
        )

        retry_count = int(state.get("test_retry_count", 0) or 0)
        task = self._build_test_task(state, retry_count)

        # Delegate test generation via ToolRouter (emits L5 InterpretRecord)
        await self._tool_router.route(
            task=task,
            context=str(state.get("rfc", "")),
            project_id=str(state.get("mcp_session_id", "default")),
            workspace_path=workspace_root,
        )

        # Measure coverage using sys.executable — not hardcoded "python"
        coverage = await self._measure_coverage(workspace_root, sys.executable)
        state["test_coverage"] = coverage

        if coverage < _COVERAGE_THRESHOLD:
            if retry_count < _MAX_RETRIES:
                state["test_retry_count"] = retry_count + 1
                uncovered = await self._get_uncovered_lines(workspace_root, sys.executable)
                state["test_uncovered_lines"] = uncovered
                state["test_retry_needed"] = True
                logger.warning(
                    "agent_6.coverage_below_threshold",
                    coverage=coverage,
                    threshold=_COVERAGE_THRESHOLD,
                    retry=retry_count + 1,
                )
            else:
                # Max retries exceeded — HITL escalation
                state["hitl_required"] = True
                state["hitl_reason"] = (
                    f"Test coverage {coverage:.1f}% below 80% threshold "
                    f"after {_MAX_RETRIES} re-delegations."
                )
                state["test_retry_needed"] = False
                logger.error(
                    "agent_6.hitl_escalation",
                    coverage=coverage,
                    retries=_MAX_RETRIES,
                )
        else:
            state["test_retry_needed"] = False
            logger.info("agent_6.coverage_met", coverage=coverage)

        return state

    def _build_test_task(self, state: dict[str, object], retry_count: int) -> str:
        """Build the test generation task string for ToolRouter."""
        base = (
            "Generate comprehensive test suite for the code in this project. "
            "Follow patterns in AGENTS.md. Create 4 test categories per module: "
            "happy path, edge cases, failures, regression. "
            "Naming: test_[what]_[condition]_[expected_outcome]. "
            "Use pytest with asyncio_mode=auto. "
            "Target: 80% line coverage. All external calls must be mocked."
        )
        if retry_count > 0:
            uncovered = list(state.get("test_uncovered_lines", []) or [])
            if uncovered:
                lines_str = "\n".join(f"  - {line}" for line in uncovered[:20])
                base += (
                    f"\n\nFix required: please add tests for these uncovered lines:\n{lines_str}"
                )
        return base

    async def _measure_coverage(self, workspace_path: str, python_exe: str) -> float:
        """Run pytest with coverage and return percent_covered float."""
        try:
            proc = await asyncio.create_subprocess_exec(
                python_exe,
                "-m",
                "pytest",
                "--cov=.",
                "--cov-report=json",
                "-q",
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except Exception as exc:
            logger.warning("agent_6.coverage_subprocess_failed", error=str(exc))
            return 0.0

        cov_file = Path(workspace_path) / "coverage.json"
        if cov_file.exists():
            try:
                data = json.loads(cov_file.read_text(encoding="utf-8"))
                return float(data.get("totals", {}).get("percent_covered", 0.0))
            except Exception as exc:
                logger.warning("agent_6.coverage_parse_failed", error=str(exc))
        return 0.0

    async def _get_uncovered_lines(self, workspace_path: str, python_exe: str) -> list[str]:
        """Parse coverage.json to find uncovered lines for retry task."""
        cov_file = Path(workspace_path) / "coverage.json"
        uncovered: list[str] = []
        if cov_file.exists():
            try:
                data = json.loads(cov_file.read_text(encoding="utf-8"))
                for filepath, info in data.get("files", {}).items():
                    missing = info.get("missing_lines", [])
                    if missing:
                        uncovered.append(f"{filepath}: lines {missing[:5]}")
            except Exception as exc:
                logger.warning("agent_6.uncovered_parse_failed", error=str(exc))
        return uncovered[:10]  # cap at 10 for task readability
