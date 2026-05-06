from __future__ import annotations

import ast as ast_module
import asyncio
import json
import re
from datetime import UTC, datetime

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord

logger = structlog.get_logger()

_MODEL = "gpt-4o-mini"


class CoordinatedReview(BaseAgent):
    """Agent 5 — validates code produced by Agent 4's tool delegation.

    Runs 5 passes on generated code:
    Pass 1: Correctness (LLM)
    Pass 2: Security — OWASP Top 10 (LLM)
    Pass 3: Performance (LLM)
    Pass 4: MAANG Standards — DETERMINISTIC, zero LLM, AST-based
    Pass 5: Error Handling (LLM)

    BLOCKING findings → sets trigger_agent_4_retry=True (max 2 times).
    At max 2 delegations → HITL escalation.
    """

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Preview 5-pass review. Emits L1 InterpretRecord."""
        generated = list(state.get("generated_files", []) or [])
        file_count = len(generated)
        tool_used = str(state.get("tool_delegated_to", "unknown tool"))

        record = InterpretRecord(
            layer="agent",
            component="CoordinatedReview",
            action=(
                f"CODE REVIEW — {file_count} file(s) from {tool_used}\n"
                f"Passes: correctness | security | performance | "
                f"MAANG standards (deterministic) | error handling\n"
                f"BLOCKING findings will re-delegate to Agent 4 (max 2 retries)"
            ),
            inputs={
                "files": file_count,
                "tool_used": tool_used,
            },
            expected_outputs={"review_findings": "list[ReviewFinding]"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[_MODEL],
            model_selected=_MODEL,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.agent",
            layer=record.layer,
            component="CoordinatedReview",
            files=file_count,
        )
        return record

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Run all 5 passes on generated files."""
        generated = list(state.get("generated_files", []) or [])
        all_findings: list[dict[str, object]] = []
        delegation_count = int(state.get("review_delegation_count", 0) or 0)

        for file_info in generated:
            code = str(file_info.get("content", ""))
            # Extract filepath for language detection in Pass 4
            filepath = str(file_info.get("filepath") or file_info.get("path") or "")

            # Run all LLM passes concurrently — ~8s sequential becomes ~2s parallel.
            # Pass 4 (MAANG Standards) is deterministic/synchronous — run separately.
            # Sequential: ~8s per file (4 × 2s LLM latency).
            # Parallel:   ~2s per file (all 4 overlap).
            (
                findings_p1,
                findings_p2,
                findings_p3,
                findings_p5,
            ) = await asyncio.gather(
                self._pass_correctness(code, state),  # Pass 1: Correctness
                self._pass_security(code, state),  # Pass 2: OWASP Security
                self._pass_performance(code, state),  # Pass 3: Performance
                self._pass_error_handling(code, state),  # Pass 5: Error Handling
            )

            # Pass 4: MAANG Standards — deterministic AST (no await needed)

            findings_p4 = self._pass_maang_standards(code, filepath=filepath)

            all_findings.extend(findings_p1)
            all_findings.extend(findings_p2)
            all_findings.extend(findings_p3)
            all_findings.extend(findings_p4)
            all_findings.extend(findings_p5)

        blocking = [f for f in all_findings if f.get("severity") == "BLOCKING"]

        if blocking and delegation_count < 2:
            state["review_delegation_count"] = delegation_count + 1
            correction_notes = "\n".join(f"- {f['message']}" for f in blocking)
            state["review_corrections"] = correction_notes
            state["trigger_agent_4_retry"] = True
            logger.warning(
                "agent_5.blocking_findings_trigger_retry",
                delegation_count=delegation_count + 1,
                blocking_count=len(blocking),
            )
        elif blocking:
            # Max 2 delegations exceeded — escalate to HITL
            state["hitl_required"] = True
            state["hitl_reason"] = (
                f"Code review found {len(blocking)} BLOCKING issues after 2 Agent 4 re-delegations."
            )
            state["trigger_agent_4_retry"] = False
            logger.error(
                "agent_5.hitl_escalation",
                blocking_count=len(blocking),
            )
        else:
            state["trigger_agent_4_retry"] = False

        state["review_findings"] = all_findings
        logger.info(
            "agent_5.executed",
            total_findings=len(all_findings),
            blocking=len(blocking),
        )
        return state

    # ── Pass 4: DETERMINISTIC — zero LLM ────────────────────────────────────

    def _pass_maang_standards(self, code: str, filepath: str = "") -> list[dict[str, object]]:
        """Pass 4: Deterministic AST-based MAANG standards check. Zero LLM.

        Rules (Python only):
        - Function > 50 lines → BLOCKING
        - Missing return type hint → ADVISORY
        - Bare except → BLOCKING

        Non-Python files return an ADVISORY — AST rules only apply to Python.
        Previously silently returned [] for TypeScript/Go/Rust/SQL — now explicit.
        """
        findings: list[dict[str, object]] = []
        if not code or not code.strip():
            return findings

        # Detect language from file extension — AST rules only apply to Python
        is_python = filepath.endswith(".py") or not filepath  # default to Python if no path
        if not is_python:
            ext = filepath.rsplit(".", 1)[-1] if "." in filepath else "unknown"
            findings.append(
                {
                    "pass": 4,
                    "severity": "ADVISORY",
                    "message": (
                        f"Pass 4 (MAANG Standards): AST check skipped for .{ext} file. "
                        "AST-based rules only apply to Python. "
                        "Manual review recommended for function length and bare catch blocks."
                    ),
                    "file": filepath,
                    "line": None,
                }
            )
            return findings

        findings: list[dict[str, object]] = []
        if not code or not code.strip():
            return findings

        try:
            tree = ast_module.parse(code)
            for node in ast_module.walk(tree):
                if isinstance(node, (ast_module.FunctionDef, ast_module.AsyncFunctionDef)):
                    lines = (node.end_lineno or 0) - node.lineno
                    if lines > 50:
                        findings.append(
                            {
                                "pass": 4,
                                "severity": "BLOCKING",
                                "rule": "function_length",
                                "message": (
                                    f"Function '{node.name}' is {lines} lines (max 50). "
                                    "Split into smaller functions."
                                ),
                            }
                        )
                    if not node.returns:
                        findings.append(
                            {
                                "pass": 4,
                                "severity": "ADVISORY",
                                "rule": "type_hints",
                                "message": (f"Function '{node.name}' missing return type hint."),
                            }
                        )
                if isinstance(node, ast_module.ExceptHandler):  # noqa: SIM102
                    if node.type is None:
                        findings.append(
                            {
                                "pass": 4,
                                "severity": "BLOCKING",
                                "rule": "bare_except",
                                "message": "Bare 'except:' found. Use specific exception types.",
                            }
                        )
        except SyntaxError:
            pass

        return findings

    # ── Passes 1, 2, 3, 5: LLM-assisted ────────────────────────────────────

    async def _get_adapter(self, state: dict[str, object]) -> object:
        return await self.model_router.route(
            agent="agent_5_coord_review",
            task_type="review",
            estimated_tokens=2_000,
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd") or 0.0),
            budget_total=float(state.get("budget_remaining_usd") or 0.0),
        )

    def _parse_findings(self, raw: str, pass_num: int) -> list[dict[str, object]]:
        """Parse JSON findings from LLM response. Returns [] on parse failure."""
        try:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                return []
            findings = json.loads(match.group())
            return [{"pass": pass_num, **f} for f in findings if isinstance(f, dict)]
        except Exception:
            return []

    async def _pass_correctness(
        self, code: str, state: dict[str, object]
    ) -> list[dict[str, object]]:
        """Pass 1: Correctness — logic errors, off-by-one, race conditions."""
        adapter = await self._get_adapter(state)
        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(
                    content=(
                        "Review this code for correctness issues: logic errors, "
                        "off-by-one, race conditions, null pointer risks. "
                        'Respond ONLY as JSON array: [{"severity": "BLOCKING|ADVISORY", '
                        '"message": "..."}]. Empty array [] if none found.'
                    )
                ),
                HumanMessage(content=code[:4000]),
            ]
        )
        return self._parse_findings(str(response.content), pass_num=1)

    async def _pass_security(self, code: str, state: dict[str, object]) -> list[dict[str, object]]:
        """Pass 2: Security — OWASP Top 10 (injection, XSS, IDOR, etc.)."""
        adapter = await self._get_adapter(state)
        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(
                    content=(
                        "Review this code for OWASP Top 10 security vulnerabilities: "
                        "SQL injection, XSS, broken auth, IDOR, sensitive data exposure. "
                        'Respond ONLY as JSON array: [{"severity": "BLOCKING|ADVISORY", '
                        '"message": "..."}]. Empty array [] if none found.'
                    )
                ),
                HumanMessage(content=code[:4000]),
            ]
        )
        return self._parse_findings(str(response.content), pass_num=2)

    async def _pass_performance(
        self, code: str, state: dict[str, object]
    ) -> list[dict[str, object]]:
        """Pass 3: Performance — N+1 queries, missing indexes, blocking I/O."""
        adapter = await self._get_adapter(state)
        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(
                    content=(
                        "Review this code for performance issues: N+1 queries, "
                        "missing indexes, blocking I/O in async context, "
                        "O(n²) algorithms, unbounded memory growth. "
                        'Respond ONLY as JSON array: [{"severity": "BLOCKING|ADVISORY", '
                        '"message": "..."}]. Empty array [] if none found.'
                    )
                ),
                HumanMessage(content=code[:4000]),
            ]
        )
        return self._parse_findings(str(response.content), pass_num=3)

    async def _pass_error_handling(
        self, code: str, state: dict[str, object]
    ) -> list[dict[str, object]]:
        """Pass 5: Error handling — swallowed exceptions, missing fallbacks."""
        adapter = await self._get_adapter(state)
        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(
                    content=(
                        "Review this code for error handling issues: swallowed exceptions, "
                        "missing error boundaries, no retry logic for transient failures, "
                        "unhandled promise rejections. "
                        'Respond ONLY as JSON array: [{"severity": "BLOCKING|ADVISORY", '
                        '"message": "..."}]. Empty array [] if none found.'
                    )
                ),
                HumanMessage(content=code[:4000]),
            ]
        )
        return self._parse_findings(str(response.content), pass_num=5)
