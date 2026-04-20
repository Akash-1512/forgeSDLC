from __future__ import annotations

from datetime import datetime, timezone

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord

logger = structlog.get_logger()

_MODEL = "gemini-3.1-pro-preview"  # selected by ModelRouter long-context router


class IntegrationAgent(BaseAgent):
    """Agent 11 — cross-service integration tests. Multi-service only.

    Model: gemini-3.1-pro-preview — selected by ModelRouter's LongContextRouter
           when estimated_tokens > 100_000. NOT hardcoded in this agent.
           Multi-service combined codebase = large context → long-context router fires.
    Fires ONLY when architecture_type == "multi_service".
    Silent skip on monolith — no interpret_log entries added.
    """

    _skip_key = "agent_11_integration"

    async def run(self, state: dict[str, object]) -> dict[str, object]:
        """Override: silent skip on monolith. No super() call on skip path."""
        arch_type = str(
            (state.get("service_graph") or {}).get("architecture_type", "monolith")
        )
        if arch_type != "multi_service":
            # Silent skip — NO interpret_log entries. Audit marker only.
            state[f"{self._skip_key}_skipped"] = True
            logger.info("agent_11.skipped", reason="monolith architecture")
            return state
        return await super().run(state)

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        services = list((state.get("service_graph") or {}).get("services", []) or [])
        service_names = [str(s.get("name", "")) for s in services if isinstance(s, dict)]

        return self._emit_l1_record(
            component="IntegrationAgent",
            action=(
                f"CROSS-SERVICE INTEGRATION TESTS\n"
                f"Services: {service_names}\n"
                f"Model: {_MODEL} (1M context — full multi-service codebase)\n"
                f"Tests: API contract, async event, database transaction isolation"
            ),
            inputs={"service_count": len(services)},
            expected_outputs={"integration_tests": "tests/integration/test_cross_service.py"},
            external_calls=[_MODEL],
            model_selected=_MODEL,
            files_write=["tests/integration/test_cross_service.py"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Generate cross-service integration tests via gemini (long-context router)."""
        # ModelRouter selects gemini via long-context router — not hardcoded here
        adapter = await self.model_router.route(
            agent="agent_11_integration",    # AGENT_MODELS → gemini-3.1-pro-preview
            task_type="integration_testing",
            estimated_tokens=150_000,         # multi-service = large combined codebase
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd", 0.0) or 0.0),
            budget_total=float(state.get("budget_remaining_usd", 999.0) or 999.0),
        )

        services = list((state.get("service_graph") or {}).get("services", []) or [])
        rfc = str(state.get("rfc", ""))

        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(content=(
                    "Generate cross-service integration tests for a multi-service system. "
                    "Include: API response schema validation between services, "
                    "async event consumer tests, database transaction isolation tests. "
                    "Use pytest with asyncio_mode=auto."
                )),
                HumanMessage(content=(
                    f"Services: {services}\n\n"
                    f"RFC:\n{rfc[:4000]}"
                )),
            ]
        )

        content = str(response.content) if response.content else ""
        diff = await self.diff_engine.generate_diff(
            "tests/integration/test_cross_service.py",
            content,
            "Agent 11: cross-service integration tests",
        )
        await self.diff_engine.apply_diff(diff)

        logger.info("agent_11.executed", services=len(services))
        return state