from __future__ import annotations

from orchestrator.constants import MCP_SERVER_HOST, MCP_SERVER_PORT

# Streamable HTTP is the primary transport for Cursor / Claude Code / Copilot.
# stdio is available for local CLI usage.
TRANSPORT = "streamable-http"
HOST = MCP_SERVER_HOST
PORT = MCP_SERVER_PORT
