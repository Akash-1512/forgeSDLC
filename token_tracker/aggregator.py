from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import structlog

from token_tracker.record import TokenRecord

logger = structlog.get_logger()


class TokenAggregator:
    """Aggregates TokenRecords for UI consumption (status bar, sidebar, widget).

    All methods accept a list of TokenRecord dicts (from state) or TokenRecord
    objects and return summary dicts.
    """

    def _to_records(
        self, raw: list[dict[str, object] | TokenRecord]
    ) -> list[TokenRecord]:
        result: list[TokenRecord] = []
        for item in raw:
            if isinstance(item, TokenRecord):
                result.append(item)
            else:
                result.append(TokenRecord.model_validate(item))
        return result

    def by_agent(
        self, raw: list[dict[str, object] | TokenRecord]
    ) -> dict[str, dict[str, float]]:
        """Group totals by agent name."""
        records = self._to_records(raw)
        groups: dict[str, dict[str, float]] = defaultdict(
            lambda: {"input_tokens": 0.0, "output_tokens": 0.0, "cost_usd": 0.0, "calls": 0.0}
        )
        for rec in records:
            g = groups[rec.agent]
            g["input_tokens"] += rec.input_tokens
            g["output_tokens"] += rec.output_tokens
            g["cost_usd"] += rec.cost_usd
            g["calls"] += 1
        return dict(groups)

    def by_model(
        self, raw: list[dict[str, object] | TokenRecord]
    ) -> dict[str, dict[str, float]]:
        """Group totals by model string."""
        records = self._to_records(raw)
        groups: dict[str, dict[str, float]] = defaultdict(
            lambda: {"input_tokens": 0.0, "output_tokens": 0.0, "cost_usd": 0.0, "calls": 0.0}
        )
        for rec in records:
            g = groups[rec.model]
            g["input_tokens"] += rec.input_tokens
            g["output_tokens"] += rec.output_tokens
            g["cost_usd"] += rec.cost_usd
            g["calls"] += 1
        return dict(groups)

    def by_provider(
        self, raw: list[dict[str, object] | TokenRecord]
    ) -> dict[str, dict[str, float]]:
        """Group totals by provider."""
        records = self._to_records(raw)
        groups: dict[str, dict[str, float]] = defaultdict(
            lambda: {"input_tokens": 0.0, "output_tokens": 0.0, "cost_usd": 0.0, "calls": 0.0}
        )
        for rec in records:
            g = groups[rec.provider]
            g["input_tokens"] += rec.input_tokens
            g["output_tokens"] += rec.output_tokens
            g["cost_usd"] += rec.cost_usd
            g["calls"] += 1
        return dict(groups)

    def total_cost(
        self, raw: list[dict[str, object] | TokenRecord]
    ) -> float:
        """Sum of all cost_usd values."""
        return sum(r.cost_usd for r in self._to_records(raw))

    def total_tokens(
        self, raw: list[dict[str, object] | TokenRecord]
    ) -> int:
        """Sum of all input + output tokens."""
        records = self._to_records(raw)
        return sum(r.input_tokens + r.output_tokens for r in records)