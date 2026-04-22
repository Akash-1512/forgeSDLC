from __future__ import annotations

from datetime import UTC, datetime

import structlog

from context_management.context_compressor import ContextCompressor
from context_management.context_packet import AgentContextSpec, ContextPacket
from context_management.token_estimator import TokenEstimator
from interpret.record import InterpretRecord
from orchestrator.exceptions import ForgeSDLCError

logger = structlog.get_logger()


class ContextWindowManager:
    """Builds ContextPacket for each agent before it runs.

    Emits InterpretRecord Layer 11 (context_window_manager) before every build.
    Respects max_context_tokens per agent spec.

    EXCLUDED = ABSENT invariant:
    Excluded fields are never added to included_fields or compressed_fields.
    They are completely absent from the packet — not None, not [], not compressed stubs.
    The excluded_fields list in ContextPacket is stored for audit only.
    """

    def __init__(
        self,
        estimator: TokenEstimator,
        compressor: ContextCompressor,
        specs: dict[str, AgentContextSpec],
    ) -> None:
        self._est = estimator
        self._cmp = compressor
        self._specs = specs

    async def build_packet(
        self,
        agent_name: str,
        state: dict[str, object],
    ) -> ContextPacket:
        """Build a trimmed, agent-specific ContextPacket from SDLCState."""
        spec = self._specs.get(agent_name)
        if spec is None:
            raise ForgeSDLCError(
                f"No AgentContextSpec found for agent '{agent_name}'. "
                f"Available agents: {sorted(self._specs.keys())}"
            )

        # Emit InterpretRecord Layer 11 BEFORE building packet
        self._emit_record(agent_name, spec)

        original_tokens = self._est.estimate_state(state)
        included: dict[str, object] = {}
        compressed: dict[str, str] = {}
        compression_applied = False
        compression_model: str | None = None

        # Step 1: Required fields — always included at full size
        # Follow priority_order for the required fields that appear there
        added: set[str] = set()
        for field in spec.priority_order:
            if field in spec.required_fields and field in state:
                included[field] = state[field]
                added.add(field)
        # Add any required fields not in priority_order
        for field in spec.required_fields:
            if field not in added and field in state:
                included[field] = state[field]
                added.add(field)

        # Step 2: Optional fields — include if within token budget; compress if large
        for field in spec.optional_fields:
            # EXCLUDED wins over OPTIONAL — skip if excluded
            if field in spec.excluded_fields:
                continue
            if field not in state:
                continue

            value = state[field]
            field_tokens = self._est.estimate(str(value))
            current_tokens = self._est.estimate_dict(included)

            if current_tokens + field_tokens <= spec.max_context_tokens:
                included[field] = value
            elif field_tokens > spec.summarise_threshold_tokens:
                # Compress large optional fields that exceed threshold
                summary = await self._cmp.compress(str(value), field)
                compressed[field] = summary
                compression_applied = True
                compression_model = "groq/llama-3.1-8b-instant"

        # Step 3: Excluded fields are NOT added — completely absent from packet.
        # No loop needed — absence is achieved by never adding them above.

        total_tokens = self._est.estimate_dict(included)
        logger.info(
            "context_window_manager.packet_built",
            agent=agent_name,
            included=list(included.keys()),
            compressed=list(compressed.keys()),
            excluded_count=len(spec.excluded_fields),
            total_tokens=total_tokens,
            compression_applied=compression_applied,
        )

        return ContextPacket(
            agent_name=agent_name,
            included_fields=included,
            compressed_fields=compressed,
            excluded_fields=spec.excluded_fields,  # audit trail only
            total_tokens_estimated=total_tokens,
            compression_applied=compression_applied,
            compression_model=compression_model,
            original_state_tokens=original_tokens,
        )

    def _emit_record(self, agent_name: str, spec: AgentContextSpec) -> InterpretRecord:
        record = InterpretRecord(
            layer="context_window_manager",
            component="ContextWindowManager",
            action=f"building ContextPacket for {agent_name}",
            inputs={
                "agent": agent_name,
                "max_tokens": spec.max_context_tokens,
                "required_fields": spec.required_fields,
            },
            expected_outputs={"context_packet": "ContextPacket"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.context_window_manager",
            layer=record.layer,
            agent=agent_name,
        )
        return record
