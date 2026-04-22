from __future__ import annotations

import csv
import io
from pathlib import Path

import structlog

from token_tracker.record import TokenRecord

logger = structlog.get_logger()

_FIELDS = [
    "record_id",
    "timestamp",
    "trace_id",
    "agent",
    "task",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "latency_ms",
    "api_key_source",
    "subscription_tier",
    "fim_call",
    "session_id",
    "run_id",
    "tool_delegated_to",
]


class TokenExporter:
    """Exports session token records to CSV for billing and debugging."""

    def to_csv_string(self, raw: list[dict[str, object] | TokenRecord]) -> str:
        """Return CSV as a string (for MCP tool response or clipboard)."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in raw:
            row = item.model_dump() if isinstance(item, TokenRecord) else dict(item)
            writer.writerow(row)
        return output.getvalue()

    def to_csv_file(
        self,
        raw: list[dict[str, object] | TokenRecord],
        output_path: str | Path,
    ) -> Path:
        """Write CSV to disk. Returns the written path."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_csv_string(raw), encoding="utf-8")
        logger.info("token_exporter.csv_written", path=str(path), rows=len(raw))
        return path
