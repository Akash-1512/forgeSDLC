from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

from interpret.record import InterpretRecord

logger = structlog.get_logger()

_CACHE_DIR = Path("./data/docs_cache")
_CACHE_TTL_HOURS = 24


class DocsFetcher:
    """Fetches documentation URLs with 24h filesystem cache.

    Emits InterpretRecord Layer 7 (docs_fetcher) before EVERY fetch —
    including cache hits. This ensures the audit trail shows every fetch
    attempt regardless of whether a network call was made.
    """

    async def fetch(self, url: str, description: str = "") -> str:
        """Fetch URL content. Returns cached result if < 24h old.

        L7 InterpretRecord is emitted FIRST — before the cache check.
        """
        # Emit L7 BEFORE any cache check (even cache hits must be recorded)
        InterpretRecord(
            layer="docs_fetcher",
            component="DocsFetcher",
            action=f"Fetching: {url[:80]}",
            inputs={"url": url, "description": description},
            expected_outputs={"content": "str"},
            files_it_will_read=[self._cache_path(url)],
            files_it_will_write=[self._cache_path(url)],
            external_calls=[url],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info("docs_fetcher.fetch", url=url[:60], description=description)

        # Check cache — return immediately if fresh
        cached = self._read_cache(url)
        if cached is not None:
            logger.info("docs_fetcher.cache_hit", url=url[:60])
            return cached

        # Fetch from network
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, follow_redirects=True)
                r.raise_for_status()
                content = r.text
        except Exception as exc:
            logger.warning("docs_fetcher.failed", url=url[:60], error=str(exc))
            return ""

        self._write_cache(url, content)
        logger.info("docs_fetcher.fetched", url=url[:60], length=len(content))
        return content

    def _cache_path(self, url: str) -> str:
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        return str(_CACHE_DIR / f"{key}.json")

    def _read_cache(self, url: str) -> str | None:
        p = Path(self._cache_path(url))
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data["cached_at"])
            # Make timezone-aware if naive
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=UTC)
            now = datetime.now(tz=UTC)
            if now - cached_at < timedelta(hours=_CACHE_TTL_HOURS):
                return str(data["content"])
        except Exception as exc:
            logger.debug("docs_fetcher.cache_read_error", error=str(exc))
        return None

    def _write_cache(self, url: str, content: str) -> None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = Path(self._cache_path(url))
        p.write_text(
            json.dumps(
                {
                    "url": url,
                    "content": content,
                    "cached_at": datetime.now(tz=UTC).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        logger.debug("docs_fetcher.cached", url=url[:60])
