from __future__ import annotations

# CRITICAL: NO import from model_router anywhere in this file.
# ast_checker.py CI test: grep for "model_router" → FAIL
# Agent 4 has NO internal LLM. AGENT_MODELS["agent_4_tool_router"] = None.
import ast as ast_module
from datetime import UTC, datetime

import structlog

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord
from tool_router.router import ToolRouter

logger = structlog.get_logger()


class ToolRouterAgent(BaseAgent):
    """Agent 4 — delegates code generation to external tools via ToolRouter.

    Has NO internal LLM. Never calls ModelRouter. Never imports model_router.
    ContextFileManager.write_all() ALWAYS called before ToolRouter.route().
    Max 2 auto-retries on BLOCKING MAANG violations before HITL escalation.
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
        """Detect available tools and preview delegation. Emits L1 InterpretRecord.

        model_selected=None — Agent 4 has no internal LLM.
        """
        from tool_router.context import AvailableTool  # noqa: PLC0415

        available_tools = await self._tool_router.detect_available_tools()
        selected = available_tools[0] if available_tools else AvailableTool.DIRECT_LLM
        task = self._build_task(state)

        record = InterpretRecord(
            layer="agent",
            component="ToolRouterAgent",
            action=(
                f"CODE GENERATION DELEGATION\n"
                f"Tool selected: {selected.value}\n"
                f"Context files to inject: AGENTS.md, CLAUDE.md, .cursorrules\n"
                f"Task: {task[:200]}"
            ),
            inputs={
                "task": task[:100],
                "selected_tool": selected.value,
                "available_tools": [t.value for t in available_tools],
            },
            expected_outputs={"tool_result": "ToolResult"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[selected.value],
            model_selected=None,  # NO model — delegation only
            tool_delegated_to=selected.value,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.agent",
            layer=record.layer,
            component="ToolRouterAgent",
            action=record.action[:60],
        )
        return record

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Execute code generation delegation.

        ORDER IS ENFORCED:
        1. ContextFileManager.write_all() — inject project context into workspace files
        2. ToolRouter.route() — delegate to Cursor/Claude Code/Devin/DirectLLM
        3. MAANG standards gate — deterministic AST check on output
        4. Auto-retry if BLOCKING violations (max 2 retries)
        """
        workspace_ctx = await self.workspace.get_context()
        workspace_root = workspace_ctx.root_path

        # Step 1: Write context files BEFORE delegation (ordering invariant)
        await self.cfm.write_all(
            project_id=str(state.get("mcp_session_id", "default")),
            workspace_path=workspace_root,
            current_phase="implementation",
            prd_summary=str(state.get("prd", ""))[:500],
            architecture_summary=str(state.get("rfc", ""))[:300],
        )

        # Step 2: Delegate via ToolRouter (emits L5 InterpretRecord)
        task = self._build_task(state)
        result = await self._tool_router.route(
            task=task,
            context=str(state.get("rfc", "")),
            project_id=str(state.get("mcp_session_id", "default")),
            workspace_path=workspace_root,
        )

        # Step 3: MAANG standards gate — deterministic, zero LLM
        violations = self._check_maang_standards(result.output)
        blocking = [v for v in violations if v["severity"] == "BLOCKING"]

        if blocking:
            retry_count = int(state.get("tool_retry_count", 0) or 0)
            if retry_count < 2:  # max 2 auto-retries
                state["tool_retry_count"] = retry_count + 1
                correction_notes = "\n".join(f"Fix required: {v['message']}" for v in blocking)
                logger.warning(
                    "agent_4.maang_violation_retry",
                    retry=retry_count + 1,
                    violations=len(blocking),
                )
                # Re-delegate with correction notes appended to task
                result = await self._tool_router.route(
                    task=f"{task}\n\n{correction_notes}",
                    context=str(state.get("rfc", "")),
                    project_id=str(state.get("mcp_session_id", "default")),
                    workspace_path=workspace_root,
                )
            else:
                # Max retries exceeded — escalate to HITL
                state["hitl_required"] = True
                state["hitl_reason"] = (
                    f"MAANG standards violations after 2 retries: "
                    f"{[v['message'] for v in blocking]}"
                )
                logger.error(
                    "agent_4.hitl_escalation",
                    violations=[v["message"] for v in blocking],
                )

        # Capture generated output
        if result.files_written:
            state["generated_files"] = [
                {"path": f, "content": result.output} for f in result.files_written
            ]
        else:
            state["generated_files"] = [{"path": "generated_code.py", "content": result.output}]
        state["tool_delegated_to"] = result.tool.value

        logger.info(
            "agent_4.executed",
            tool=result.tool.value,
            files=len(state["generated_files"]),
        )
        return state

    def _check_maang_standards(self, code: str) -> list[dict[str, str]]:
        """Deterministic MAANG standards check. Uses stdlib ast. Zero LLM.

        Rules:
        - Function > 50 lines → BLOCKING
        - Missing type hints → ADVISORY
        - Bare except → BLOCKING
        - File > 300 lines (non-Python) → BLOCKING
        """
        violations: list[dict[str, str]] = []
        if not code or not code.strip():
            return violations

        try:
            tree = ast_module.parse(code)
            for node in ast_module.walk(tree):
                if isinstance(node, (ast_module.FunctionDef, ast_module.AsyncFunctionDef)):
                    func_lines = (node.end_lineno or 0) - node.lineno
                    if func_lines > 50:
                        violations.append(
                            {
                                "severity": "BLOCKING",
                                "rule": "function_length",
                                "message": (
                                    f"Function '{node.name}' is {func_lines} lines "
                                    f"(max 50). Split into smaller functions."
                                ),
                            }
                        )
                    has_arg_annotations = any(a.annotation is not None for a in node.args.args)
                    if not node.returns and not has_arg_annotations:
                        violations.append(
                            {
                                "severity": "ADVISORY",
                                "rule": "type_hints",
                                "message": (f"Function '{node.name}' missing type hints."),
                            }
                        )
                if isinstance(node, ast_module.ExceptHandler):
                    if node.type is None:
                        violations.append(
                            {
                                "severity": "BLOCKING",
                                "rule": "bare_except",
                                "message": ("Bare 'except:' found. Use specific exception types."),
                            }
                        )
        except SyntaxError:
            lines = code.splitlines()
            if len(lines) > 300:
                violations.append(
                    {
                        "severity": "BLOCKING",
                        "rule": "file_length",
                        "message": (f"File is {len(lines)} lines (max 300). Split into modules."),
                    }
                )

        return violations

    def _build_task(self, state: dict[str, object]) -> str:
        """Build the task string for ToolRouter delegation."""
        base = (
            f"Generate implementation code for the following project.\n\n"
            f"Requirements (PRD):\n{str(state.get('prd', 'No PRD available'))[:500]}\n\n"
            f"Architecture (RFC):\n{str(state.get('rfc', 'No RFC available'))[:500]}\n\n"
            f"Stack decisions (ADR):\n{str(state.get('adr', 'No ADR available'))[:300]}\n\n"
            f"Follow all standards in AGENTS.md."
        )
        # Append review corrections if present from Agent 5
        corrections = str(state.get("review_corrections", "")).strip()
        if corrections:
            base = f"{base}\n\nCode review corrections required:\n{corrections}"
        return base
