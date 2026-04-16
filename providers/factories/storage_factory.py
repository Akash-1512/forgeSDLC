from __future__ import annotations

import os

import structlog

from orchestrator.constants import LOCAL_DB_URL

logger = structlog.get_logger()


def get_db_url() -> str:
    """Return the active database URL — always PostgreSQL.

    Reads DATABASE_URL env var; falls back to LOCAL_DB_URL (local Docker default).
    Raises immediately if the URL is not PostgreSQL — no silent SQLite fallback.
    """
    url = os.getenv("DATABASE_URL", LOCAL_DB_URL)
    if not url.startswith("postgresql"):
        raise ValueError(
            f"DATABASE_URL must be a PostgreSQL URL. Got: {url[:40]!r}\n"
            "Run local DB:  "
            "docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=forgesdlc "
            "--name forgesdlc-db postgres:16"
        )
    logger.debug("storage_factory.get_db_url", url=url[:40])
    return url


def get_db_engine() -> object:
    """Create and return an async SQLAlchemy engine for PostgreSQL."""
    from sqlalchemy.ext.asyncio import create_async_engine

    url = get_db_url()
    engine = create_async_engine(url, pool_size=5, max_overflow=10)
    logger.info("storage_factory.engine_created", url=url[:40])
    return engine