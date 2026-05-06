from __future__ import annotations

import asyncio

import structlog

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment,misc]

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

try:
    from starlette.requests import Request
    from starlette.responses import JSONResponse
except ImportError:
    Request = object  # type: ignore[misc,assignment]
    JSONResponse = None  # type: ignore[assignment,misc]

# Guard: FastMCP may be None when fastmcp is not installed (e.g. in test environments).
# In production, pip install forgesdlc-mcp installs fastmcp as a runtime dependency.
if FastMCP is None:
    raise ImportError(
        "fastmcp is required to run the forgeSDLC MCP server. Install it: pip install forgesdlc-mcp"
    )

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


# Register MCP prompts — surfaced to clients as slash-commands
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


# Register MCP resources — project artefacts readable via resource URI
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


# Health check endpoint for smithery.yaml and Electron polling
@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Health check endpoint. Returns 200 when server is ready."""
    return JSONResponse({"status": "ok", "version": "1.1.0", "transport": TRANSPORT})


@mcp.custom_route("/auth/token", methods=["POST"])
async def create_token(request: Request) -> JSONResponse:
    """Issue a JWT session token with a tier claim.

    Issues a signed JWT with a tier claim via session_manager.
    Returns the Anthropic ToS warning for tiers that include Claude BYOK.

    Clients (Electron, Claude Desktop) POST:
        {"user_id": "...", "tier": "free|pro|enterprise", "tos_confirmed": true}
    and receive a signed JWT to set as FORGESDLC_SESSION_TOKEN.

    SECRET_KEY must be set in environment for this to work.
    """
    try:
        import json as _json  # noqa: PLC0415

        body = await request.body()  # type: ignore[union-attr]
        data = _json.loads(body)
        user_id = str(data.get("user_id", "default"))
        tier = str(data.get("tier", "free"))
        tos_confirmed = data.get("tos_confirmed", False) is True

        if tier not in {"free", "pro", "enterprise"}:
            msg = f"Invalid tier: {tier!r}. Must be free, pro, or enterprise."
            return JSONResponse({"error": msg})

        # Surface Anthropic ToS for tiers that include Claude BYOK
        anthropic_tos: dict[str, object] = {}
        if tier in {"pro", "enterprise"}:
            from subscription.anthropic_tos_warning import (
                AnthropicTosWarning,  # noqa: PLC0415
            )

            tos = AnthropicTosWarning()
            anthropic_tos = {
                "warning": tos.get_warning_text(),
                "confirmed": tos_confirmed,
                "required": True,
            }

        from subscription.session_manager import create_session_token  # noqa: PLC0415

        token = create_session_token(user_id=user_id, tier=tier)
        logger.info("auth.token_issued", user_id=user_id, tier=tier, tos_confirmed=tos_confirmed)
        return JSONResponse(
            {
                "token": token,
                "user_id": user_id,
                "tier": tier,
                "anthropic_tos": anthropic_tos,
            }
        )
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc), "hint": "Set SECRET_KEY environment variable"})


async def _startup() -> None:
    """Initialise database tables, run health checks, log provider status.

    Only initialises the three PostgreSQL stores — OrgMemory (Layer 2) loads
    its embeddings model lazily on first use, not at startup.
    """
    from memory.pipeline_history_store import PipelineHistoryStore  # noqa: PLC0415
    from memory.post_mortem_records import PostMortemStore  # noqa: PLC0415
    from memory.user_preference_profile import UserPreferenceStore  # noqa: PLC0415

    try:
        await PipelineHistoryStore().init_db()
        await UserPreferenceStore().init_db()
        await PostMortemStore().init_db()
        logger.info("forgesdlc.startup.db_tables_ready")
    except Exception as exc:
        logger.error("forgesdlc.startup.db_init_failed", error=str(exc))
        logger.warning(
            "forgesdlc.startup.continuing_without_db",
            hint="Start PostgreSQL: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=changeme postgres:16",  # noqa: E501
        )

    # Run provider health checks on startup
    try:
        import os as _os  # noqa: PLC0415

        from memory.organizational_memory import _DEFAULT_CHROMA_PATH  # noqa: PLC0415
        from orchestrator.constants import LOCAL_DB_URL  # noqa: PLC0415
        from providers.health_checks import (  # noqa: PLC0415
            check_chromadb,
            check_postgresql,
        )

        pg_ok = await check_postgresql(_os.getenv("DATABASE_URL", LOCAL_DB_URL))
        chroma_ok = await check_chromadb(_DEFAULT_CHROMA_PATH)
        logger.info(
            "forgesdlc.startup.health_checks",
            postgresql=pg_ok,
            chromadb=chroma_ok,
        )
        if not pg_ok:
            logger.warning(
                "forgesdlc.startup.postgresql_unhealthy",
                hint="Layer 1/4/5 memory will not persist. Start DB: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=changeme postgres:16",  # noqa: E501
            )
        if not chroma_ok:
            logger.warning(
                "forgesdlc.startup.chromadb_unhealthy",
                hint="Layer 2 (semantic memory) will not persist. Check chroma_db/ directory permissions.",  # noqa: E501
            )
    except Exception as exc:
        logger.warning("forgesdlc.startup.health_checks_failed", error=str(exc))

    # Log provider resolution table
    try:
        from providers.resolver import ProviderResolver  # noqa: PLC0415

        ProviderResolver().log_table()
    except Exception as exc:
        logger.warning("forgesdlc.startup.provider_resolution_failed", error=str(exc))


def main() -> None:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="forgeSDLC MCP server")
    parser.add_argument(
        "--transport",
        default=TRANSPORT,
        choices=["streamable-http", "stdio"],
        help="MCP transport (default: streamable-http)",
    )
    parser.add_argument(
        "--port", type=int, default=PORT, help=f"HTTP port (default: {PORT}, streamable-http only)"
    )
    parser.add_argument("--host", default=HOST, help=f"Bind host (default: {HOST})")
    args = parser.parse_args()

    logger.info(
        "forgeSDLC MCP server starting", transport=args.transport, host=args.host, port=args.port
    )
    asyncio.run(_startup())
    mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
