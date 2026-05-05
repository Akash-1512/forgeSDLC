from __future__ import annotations

# ---------------------------------------------------------------------------
# Gate — internal only, sent by [✅ Approve] button, never shown to users
# ---------------------------------------------------------------------------
HUMAN_CONFIRMATION_PHRASE: str = "100% GO"

# ---------------------------------------------------------------------------
# Retry / backoff
# ---------------------------------------------------------------------------
EXPONENTIAL_BACKOFF_BASE: float = 2.0
EXPONENTIAL_BACKOFF_MAX_SECONDS: float = 60.0

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------
HEALTH_CHECK_TIMEOUT_SECONDS: int = 5

# ---------------------------------------------------------------------------
# Budget thresholds (fraction of total budget)
# ---------------------------------------------------------------------------
BUDGET_WARN_THRESHOLD: float = 0.50
BUDGET_OPTIMISE_THRESHOLD: float = 0.80
BUDGET_ALERT_THRESHOLD: float = 0.90

# ---------------------------------------------------------------------------
# Context / token management
# ---------------------------------------------------------------------------
CONTEXT_COMPRESS_THRESHOLD_TOKENS: int = 2_000
LONG_CONTEXT_ROUTE_THRESHOLD_TOKENS: int = 100_000
TOKEN_ESTIMATE_WORDS_MULTIPLIER: float = 1.33

# ---------------------------------------------------------------------------
# Task types
# ---------------------------------------------------------------------------
FIM_TASK_TYPE: str = "fim"

# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
MCP_SERVER_PORT: int = 8080
import os as _os

# Fix #51: bind localhost by default — prevents LAN exposure without authentication.
# Set MCP_SERVER_HOST=0.0.0.0 only if you need LAN/Docker access AND have auth configured.
MCP_SERVER_HOST: str = _os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_TOOL_TIMEOUT_SECONDS: int = 300

# ---------------------------------------------------------------------------
# Database — PostgreSQL everywhere (local Docker postgres:16)
# SQLite is used only by LangGraph HITL checkpointing internally
# ---------------------------------------------------------------------------
import os as _os

# Fix #7: never hardcode DB credentials in source.
# LOCAL_DB_URL is only used as a last-resort fallback when DATABASE_URL is not set.
# The password here is a placeholder — set DATABASE_URL in .env for real credentials.
LOCAL_DB_URL: str = _os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:changeme@localhost:5432/forgesdlc",
)