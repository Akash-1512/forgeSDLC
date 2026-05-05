from __future__ import annotations

import asyncio

import structlog
from fastmcp import FastMCP

from mcp_server.prompts.sdlc_prompts import (
    get_architecture_prompt,
    get_requirements_prompt,
    get_review_prompt,
)
from mcp_server.resources.project_resources import (
    get_project_adr,
    get_project_memory,
    get_project_prd,
)
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

logger = structlog.get_logger()

mcp = FastMCP(
    name="forgesdlc",
    version="1.1.0",
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

# H14 Fix: Register MCP prompts — surfaced to MCP clients as slash-commands / templates
@mcp.prompt()
def requirements_prompt(project_description: str = "") -> str:
    """Structured PRD generation prompt for requirements gathering."""
    return get_requirements_prompt(project_description)


@mcp.prompt()
def architecture_prompt(prd_summary: str = "") -> str:
    """RFC + ADR generation prompt for architecture design."""
    return get_architecture_prompt(prd_summary)


@mcp.prompt()
def review_prompt(files_summary: str = "") -> str:
    """5-pass code review prompt template."""
    return get_review_prompt(files_summary)


# H14 Fix: Register MCP resources — project artefacts readable via URI
@mcp.resource("project://{project_id}/prd")
async def resource_prd(project_id: str) -> str:
    """PRD document for a project (from checkpoint)."""
    return await get_project_prd(project_id)


@mcp.resource("project://{project_id}/adr")
async def resource_adr(project_id: str) -> str:
    """ADR document for a project (from checkpoint)."""
    return await get_project_adr(project_id)


@mcp.resource("project://{project_id}/memory")
async def resource_memory(project_id: str) -> str:
    """Layer 2 organisational memory for a project."""
    return await get_project_memory(project_id)


# Fix #6: /health endpoint — required by smithery.yaml and server_manager.js polling
@mcp.custom_route("/health", methods=["GET"])
async def health(_request: object) -> dict[str, object]:
    """Health check endpoint. Returns 200 when server is ready."""
    return {"status": "ok", "version": "1.1.0", "transport": TRANSPORT}


async def _startup() -> None:
    """Initialise database tables and log provider status on server startup."""
    # Fix #112: create all PostgreSQL tables on startup (idempotent)
    from memory.pipeline_history_store import PipelineHistoryStore
    from memory.post_mortem_records import PostMortemStore
    from memory.user_preference_profile import UserPreferenceStore

    try:
        await PipelineHistoryStore().init_db()
        await UserPreferenceStore().init_db()
        await PostMortemStore().init_db()
        logger.info("forgesdlc.startup.db_tables_ready")
    except Exception as exc:
        logger.error("forgesdlc.startup.db_init_failed", error=str(exc))
        logger.warning(
            "forgesdlc.startup.continuing_without_db",
            hint="Start PostgreSQL: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=changeme postgres:16",
        )

    # Fix #53: log provider resolution table at startup
    try:
        from providers.resolver import ProviderResolver
        ProviderResolver().print_table()
    except Exception as exc:
        logger.warning("forgesdlc.startup.provider_resolution_failed", error=str(exc))


def main() -> None:
    # Fix #14: single source of truth — PORT from transport.py only
    logger.info("forgeSDLC MCP server starting", port=PORT, transport=TRANSPORT)
    asyncio.run(_startup())
    mcp.run(transport=TRANSPORT, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
