from __future__ import annotations

import os

from orchestrator.constants import MCP_SERVER_HOST, MCP_SERVER_PORT

# Use stdio if env var set (for Claude Code / MCP clients that launch via subprocess)
TRANSPORT = os.environ.get("FORGESDLC_TRANSPORT", "streamable-http")
HOST = MCP_SERVER_HOST
PORT = MCP_SERVER_PORT
