from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog

from token_tracker.record import TokenRecord

logger = structlog.get_logger()


class TokenTracker:
    """Records every internal ModelRouter LLM call.

    Appends TokenRecord to state['session_token_records'].
    Does NOT record ToolRouter delegations — those are billed to the
    developer's own subscriptions and never appear here.
    """

    def record(
        self,
        state: dict[str, object],
        agent: str,
        task: str,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: int,
        api_key_source: str,
        fim_call: bool = False,
        tool_delegated_to: str | None = None,
    ) -> TokenRecord:
        """Create and append a TokenRecord to state."""
        rec = TokenRecord(
            record_id=str(uuid4()),
            timestamp=datetime.now(tz=UTC),
            trace_id=str(state.get("trace_id") or uuid4()),
            agent=agent,
            task=task,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            api_key_source=api_key_source,  # type: ignore[arg-type]
            subscription_tier=str(state.get("subscription_tier") or "free"),
            fim_call=fim_call,
            session_id=str(state.get("mcp_session_id") or "default"),
            run_id=None,
            tool_delegated_to=tool_delegated_to,
        )

        records: list[dict[str, object]] = list(state.get("session_token_records") or [])
        records.append(rec.model_dump())
        state["session_token_records"] = records  # type: ignore[index]

        logger.info(
            "token_tracker.recorded",
            agent=agent,
            model=model,
            cost_usd=cost_usd,
            tokens=input_tokens + output_tokens,
        )
        return rec
