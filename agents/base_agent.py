from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import structlog

from context_files.manager import ContextFileManager
from context_management.context_window_manager import ContextWindowManager
from interpret.gate import check_gate
from interpret.record import InterpretRecord
from memory.memory_archiver import MemoryArchiver
from memory.memory_context_builder import MemoryContextBuilder
from model_router.router import ModelRouter
from workspace.bridge import WorkspaceBridge
from workspace.diff_engine import DiffEngine

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Shared skeleton for all 14 SDLC agents.

    Subclasses implement _interpret() and _execute() only.
    Everything else — context building, HITL gate, archiving,
    context file writing — is handled here.

    Loop: ContextWindowManager → memory read → _interpret (L1) →
          gate check → _execute → ContextFileManager (L13) → MemoryArchiver
    """

    def __init__(
        self,
        name: str,
        context_window_manager: ContextWindowManager,
        model_router: ModelRouter,
        memory_archiver: MemoryArchiver,
        memory_context_builder: MemoryContextBuilder,
        context_file_manager: ContextFileManager,
        workspace_bridge: WorkspaceBridge,
        diff_engine: DiffEngine,
    ) -> None:
        self.name = name
        self.cwm = context_window_manager
        self.model_router = model_router
        self.memory_archiver = memory_archiver
        self.memory_ctx_builder = memory_context_builder
        self.cfm = context_file_manager
        self.workspace = workspace_bridge
        self.diff_engine = diff_engine

    async def run(self, state: dict[str, object]) -> dict[str, object]:
        """Full agent execution cycle.

        Returns state with interpret_log updated.
        Does NOT execute unless human_confirmation == '100% GO'.
        """
        # Step 1: Build ContextPacket — emits L11 InterpretRecord
        packet = await self.cwm.build_packet(self.name, state)

        # Step 2: Read memory layers per AgentContextSpec
        memory_context = await self.memory_ctx_builder.build(
            query=str(state.get("user_prompt", "")),
            project_id=str(state.get("mcp_session_id", "default")),
        )

        # Step 3: Generate interpretation — emits L1 InterpretRecord
        interpretation = await self._interpret(packet, memory_context, state)
        interpret_log = list(state.get("interpret_log", []) or [])
        interpret_log.append(interpretation.model_dump())
        state["interpret_log"] = interpret_log
        # displayed_interpretation: always the CURRENT one — not a stack
        state["displayed_interpretation"] = interpretation.action
        state["interpret_round"] = int(state.get("interpret_round", 0) or 0) + 1

        # Step 4: Gate check — execute only on exact "100% GO"
        if not check_gate(str(state.get("human_confirmation", ""))):
            logger.info(
                "base_agent.awaiting_confirmation",
                agent=self.name,
                round=state["interpret_round"],
            )
            return state

        # Step 5: Execute — only reached after gate passes
        logger.info("base_agent.executing", agent=self.name)
        state = await self._execute(state, packet, memory_context)

        # Step 6: Write context files — emits L13 InterpretRecord
        try:
            workspace_ctx = await self.workspace.get_context()
            workspace_root = workspace_ctx.root_path
        except Exception:
            workspace_root = "."
        await self.cfm.write_all(
            project_id=str(state.get("mcp_session_id", "default")),
            workspace_path=workspace_root,
            current_phase=self._phase_name(),
            prd_summary=str(state.get("prd", ""))[:500],
            architecture_summary=str(state.get("rfc", ""))[:300],
        )

        # Step 7: Archive to all 5 memory layers
        await self.memory_archiver.archive(state)  # type: ignore[arg-type]

        # Step 8: Reset confirmation and displayed interpretation for next agent
        state["human_confirmation"] = ""
        state["displayed_interpretation"] = ""

        logger.info("base_agent.complete", agent=self.name)
        return state

    @abstractmethod
    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Generate interpretation of what this agent will do. Emits L1."""
        ...

    @abstractmethod
    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Perform the actual SDLC action. Only called after 100% GO."""
        ...

    def _phase_name(self) -> str:
        return self.name.replace("agent_", "").replace("_", " ")

    def _emit_l1_record(
        self,
        component: str,
        action: str,
        inputs: dict[str, object],
        expected_outputs: dict[str, object],
        external_calls: list[str],
        model_selected: str | None,
        files_write: list[str] | None = None,
    ) -> InterpretRecord:
        """Helper to emit L1 (agent layer) InterpretRecord."""
        record = InterpretRecord(
            layer="agent",
            component=component,
            action=action,
            inputs=inputs,
            expected_outputs=expected_outputs,
            files_it_will_read=[],
            files_it_will_write=files_write or [],
            external_calls=external_calls,
            model_selected=model_selected,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=files_write or [],
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "interpret_record.agent",
            layer=record.layer,
            component=component,
            action=action,
        )
        return record