from __future__ import annotations

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord

logger = structlog.get_logger()

_MODEL = "gpt-5.4"


class ContractAgent(BaseAgent):
    """Agent 12 — Pact consumer-driven contract tests.

    Fires ONLY when BOTH conditions are true:
    1. architecture_type == "multi_service"
    2. service_graph["has_openapi"] == True (Agent 3 detected API services)

    Silent skip if either condition is absent — conservative default.
    Pact contracts require OpenAPI specs to be meaningful.
    """

    _skip_key = "agent_12_contracts"

    async def run(self, state: dict[str, object]) -> dict[str, object]:
        """Override: silent skip unless multi_service AND has_openapi."""
        service_graph = dict(state.get("service_graph") or {})
        arch_type = str(service_graph.get("architecture_type", "monolith"))
        has_openapi = bool(service_graph.get("has_openapi", False))

        if arch_type != "multi_service":
            state[f"{self._skip_key}_skipped"] = True
            logger.info("agent_12.skipped", reason="monolith architecture")
            return state

        if not has_openapi:
            state[f"{self._skip_key}_skipped"] = True
            logger.info("agent_12.skipped", reason="no openapi.yaml detected")
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
            component="ContractAgent",
            action=(
                f"PACT CONSUMER-DRIVEN CONTRACT TESTS\n"
                f"Services: {service_names}\n"
                f"Framework: pact-python\n"
                f"Tests: consumer expectations + provider verification\n"
                f"Output: tests/contracts/test_contracts.py"
            ),
            inputs={"service_count": len(services)},
            expected_outputs={"contract_tests": "tests/contracts/test_contracts.py"},
            external_calls=[_MODEL],
            model_selected=_MODEL,
            files_write=["tests/contracts/test_contracts.py"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Generate Pact consumer-driven contract tests."""
        adapter = await self.model_router.route(
            agent="agent_12_contracts",
            task_type="contract_testing",
            estimated_tokens=3_000,
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd", 0.0) or 0.0),
            budget_total=float(state.get("budget_remaining_usd", 999.0) or 999.0),
        )

        services = list((state.get("service_graph") or {}).get("services", []) or [])

        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(
                    content=(
                        "Generate Pact consumer-driven contract tests for these services. "
                        "Include consumer expectations and provider verification tests. "
                        "Write to tests/contracts/. Use Python pact-python library."
                    )
                ),
                HumanMessage(content=f"Services: {services}"),
            ]
        )

        content = str(response.content) if response.content else ""
        diff = await self.diff_engine.generate_diff(
            "tests/contracts/test_contracts.py",
            content,
            "Agent 12: Pact consumer-driven contracts",
        )
        await self.diff_engine.apply_diff(diff)

        logger.info("agent_12.executed", services=len(services))
        return state
