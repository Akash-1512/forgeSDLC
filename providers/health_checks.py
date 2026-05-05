from __future__ import annotations

import asyncio

import structlog

from orchestrator.constants import HEALTH_CHECK_TIMEOUT_SECONDS

logger = structlog.get_logger()


async def check_postgresql(url: str) -> bool:
    """Return True if PostgreSQL is reachable at the given URL."""
    try:
        import asyncpg  # noqa: PLC0415

        conn = await asyncio.wait_for(
            asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://")),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        await conn.close()
        return True
    except Exception as exc:
        logger.debug("health_check.postgresql_failed", error=str(exc))
        return False


async def check_chromadb(path: str) -> bool:
    """Return True if ChromaDB PersistentClient can open at path."""
    try:
        import chromadb  # noqa: PLC0415

        chromadb.PersistentClient(path=path)
        return True
    except Exception as exc:
        logger.debug("health_check.chromadb_failed", error=str(exc))
        return False


async def check_ollama() -> bool:
    """Return True if local Ollama is running on port 11434."""
    try:
        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as client:
            r = await client.get("http://localhost:11434/api/tags")
            return r.status_code == 200
    except Exception:
        return False
