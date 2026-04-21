from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord

logger = structlog.get_logger()

_MODEL = "groq/llama-3.3-70b-versatile"


class ServiceDecompositionAgent(BaseAgent):
    """Agent 0 — decides monolith vs multi-service architecture.

    Model: groq/llama-3.3-70b-versatile (free backbone)
    Memory reads: Layer 3 (ProjectContextGraphs), Layer 4 (UserPreferences)
    Output: state["service_graph"] populated
    """

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Analyse scope and decide architecture type. Emits L1 InterpretRecord."""
        adapter = await self.model_router.route(
            agent="agent_0_decompose",
            task_type="analysis",
            estimated_tokens=500,
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd", 0.0) or 0.0),
            budget_total=float(state.get("budget_remaining_usd", 999.0) or 999.0),
        )
        prompt = (
            "Analyse this project request and determine if it needs a single "
            "monolithic service or multiple microservices.\n\n"
            f"Request: {state.get('user_prompt', '')}\n\n"
            "Respond ONLY with JSON (no markdown):\n"
            '{"architecture_type": "monolith" or "multi_service", '
            '"reasoning": "2-3 sentences", '
            '"services": ["service1", "service2"] or [], '
            '"confidence": "HIGH" or "MEDIUM"}'
        )
        response = await adapter.ainvoke(
            [
                SystemMessage(content="You are a senior software architect."),
                HumanMessage(content=prompt),
            ]
        )
        raw = str(response.content).strip()
        # Store raw for execute step
        state["_agent0_raw"] = raw

        return self._emit_l1_record(
            component="ServiceDecompositionAgent",
            action=f"Analysing scope: {str(state.get('user_prompt', ''))[:60]}",
            inputs={"user_prompt": state.get("user_prompt", "")},
            expected_outputs={"service_graph": "dict with architecture_type and services"},
            external_calls=[_MODEL],
            model_selected=_MODEL,
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Parse decomposition result and populate state["service_graph"]."""
        raw = str(state.get("_agent0_raw", ""))
        try:
            # Strip markdown fences if present
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw.strip())
            architecture_type = data.get("architecture_type", "monolith")
            services = data.get("services", [])
            reasoning = data.get("reasoning", "")
            confidence = data.get("confidence", "MEDIUM")
        except (json.JSONDecodeError, KeyError, IndexError):
            # Fallback: default to monolith
            architecture_type = "monolith"
            services = []
            reasoning = "Could not parse LLM response — defaulting to monolith."
            confidence = "MEDIUM"
            logger.warning("agent_0.parse_failed", raw=raw[:100])

        state["service_graph"] = {
            "architecture_type": architecture_type,
            "services": services,
            "reasoning": reasoning,
            "confidence": confidence,
            "generated_by": "agent_0_decompose",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        logger.info(
            "agent_0.executed",
            architecture_type=architecture_type,
            services=services,
            confidence=confidence,
        )
        return state
