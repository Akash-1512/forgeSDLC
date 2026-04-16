from __future__ import annotations

from orchestrator.constants import (
    HUMAN_CONFIRMATION_PHRASE,
    LOCAL_DB_URL,
    MCP_SERVER_PORT,
)


def test_human_confirmation_phrase_is_100_percent_go() -> None:
    assert HUMAN_CONFIRMATION_PHRASE == "100% GO"


def test_mcp_server_port_is_8080() -> None:
    assert MCP_SERVER_PORT == 8080


def test_local_db_url_contains_postgres() -> None:
    assert "postgres" in LOCAL_DB_URL