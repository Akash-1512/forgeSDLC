from __future__ import annotations

import structlog
from fastmcp import FastMCP

from mcp_server.tools.architecture_tool import design_architecture
from mcp_server.tools.cicd_tool import generate_cicd
from mcp_server.tools.code_generation_tool import route_code_generation
from mcp_server.tools.deploy_tool import deploy_project
from mcp_server.tools.docs_tool import generate_docs
from mcp_server.tools.memory_tool import recall_context, save_decision
from mcp_server.tools.monitor_tool import setup_monitoring
from mcp_server.tools.progress_tool import track_progress
from mcp_server.tools.requirements_tool import gather_requirements
from mcp_server.tools.security_tool import run_security_scan
from mcp_server.transport import HOST, PORT, TRANSPORT
from orchestrator.constants import MCP_SERVER_PORT

logger = structlog.get_logger()

mcp = FastMCP(
    name="forgesdlc",
    version="0.1.0",
    instructions=(
        "I am the SDLC intelligence layer for your AI coding tools. "
        "Use gather_requirements() to start any project. "
        "Use recall_context() to retrieve cross-session project memory. "
        "Use design_architecture() to validate architecture before coding."
    ),
)

# Register all 11 MCP tools
mcp.tool()(gather_requirements)
mcp.tool()(design_architecture)
mcp.tool()(recall_context)
mcp.tool()(save_decision)
mcp.tool()(route_code_generation)
mcp.tool()(run_security_scan)
mcp.tool()(generate_cicd)
mcp.tool()(deploy_project)
mcp.tool()(setup_monitoring)
mcp.tool()(generate_docs)
mcp.tool()(track_progress)


def main() -> None:
    logger.info("forgeSDLC MCP server starting", port=MCP_SERVER_PORT, transport=TRANSPORT)
    mcp.run(transport=TRANSPORT, host=HOST, port=PORT)


if __name__ == "__main__":
    main()