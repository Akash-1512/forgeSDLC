from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.docs_fetcher import _CACHE_TTL_HOURS, DocsFetcher


@pytest.mark.asyncio
async def test_docs_fetcher_emits_l7_interpret_record_before_fetch(
    tmp_path: Path,
) -> None:
    from interpret.record import InterpretRecord

    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "DocsFetcher":
            emitted.append(str(kwargs.get("layer", "")))

    mock_response = MagicMock()
    mock_response.text = "content"
    mock_response.raise_for_status = MagicMock()

    with (
        patch.object(InterpretRecord, "__init__", capturing_init),
        patch("httpx.AsyncClient") as mock_client,
    ):
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_response))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        fetcher = DocsFetcher()
        await fetcher.fetch("https://example.com/doc", "test")

    assert "docs_fetcher" in emitted


@pytest.mark.asyncio
async def test_docs_fetcher_emits_l7_even_on_cache_hit(tmp_path: Path) -> None:
    """L7 must fire BEFORE the cache check — even cache hits are recorded."""
    from interpret.record import InterpretRecord

    emitted: list[str] = []
    original_init = InterpretRecord.__init__

    def capturing_init(self: InterpretRecord, **kwargs: object) -> None:
        original_init(self, **kwargs)
        if kwargs.get("component") == "DocsFetcher":
            emitted.append(str(kwargs.get("layer", "")))

    # Pre-populate cache
    fetcher = DocsFetcher()
    url = "https://example.com/cached"
    cache_data = {
        "url": url,
        "content": "cached content",
        "cached_at": datetime.now(tz=UTC).isoformat(),
    }
    cache_path = Path(fetcher._cache_path(url))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    with patch.object(InterpretRecord, "__init__", capturing_init):
        result = await fetcher.fetch(url, "cached test")

    assert "docs_fetcher" in emitted
    assert result == "cached content"

    # cleanup
    cache_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_docs_fetcher_returns_cached_content_within_24h() -> None:
    fetcher = DocsFetcher()
    url = "https://example.com/cache-test"
    expected = "fresh cached content"

    cache_data = {
        "url": url,
        "content": expected,
        "cached_at": datetime.now(tz=UTC).isoformat(),
    }
    cache_path = Path(fetcher._cache_path(url))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock()
        result = await fetcher.fetch(url)

    assert result == expected
    # httpx should NOT have been called
    mock_client.return_value.__aenter__.assert_not_called()

    cache_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_docs_fetcher_refetches_after_24h_cache_expiry() -> None:
    fetcher = DocsFetcher()
    url = "https://example.com/expired"
    old_content = "old content"
    new_content = "fresh content"

    # Write expired cache entry
    cache_data = {
        "url": url,
        "content": old_content,
        "cached_at": (datetime.now(tz=UTC) - timedelta(hours=_CACHE_TTL_HOURS + 1)).isoformat(),
    }
    cache_path = Path(fetcher._cache_path(url))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.text = new_content
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(return_value=mock_response))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetcher.fetch(url)

    assert result == new_content
    cache_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_docs_fetcher_returns_empty_string_on_network_failure() -> None:
    fetcher = DocsFetcher()
    url = "https://example.com/network-fail"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(get=AsyncMock(side_effect=Exception("connection refused")))
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetcher.fetch(url)

    assert result == ""
