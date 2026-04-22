from __future__ import annotations

"""Smoke test — connects to forgeSDLC MCP server on localhost:8080,
lists all 11 tools, calls each one, and exits 0 on success.

Run after starting the server in a separate terminal:
    python -m mcp_server.server

Then in another terminal:
    python scripts/mcp_test_client.py
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

BASE_URL = "http://localhost:8080/mcp"

TOOL_CALLS = [
    ("gather_requirements", {"prompt": "build a REST API", "project_id": "smoke-test"}),
    ("design_architecture", {"project_id": "smoke-test", "prd": "stub prd"}),
    ("recall_context", {"query": "tech stack", "project_id": "smoke-test"}),
    (
        "save_decision",
        {"decision": "use postgres", "rationale": "scale", "project_id": "smoke-test"},
    ),
    ("route_code_generation", {"project_id": "smoke-test", "task": "write models", "context": ""}),
    ("run_security_scan", {"project_id": "smoke-test", "target_path": "./src"}),
    ("generate_cicd", {"project_id": "smoke-test", "stack": "fastapi"}),
    ("deploy_project", {"project_id": "smoke-test", "environment": "staging"}),
    ("setup_monitoring", {"project_id": "smoke-test", "deployment_url": "https://example.com"}),
    ("generate_docs", {"project_id": "smoke-test", "scope": "full"}),
    ("track_progress", {"project_id": "smoke-test"}),
]


async def main() -> None:
    print(f"Connecting to forgeSDLC MCP server at {BASE_URL} ...")

    async with streamablehttp_client(BASE_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. List tools
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"Tools registered: {len(tool_names)}")
            for name in tool_names:
                print(f"  ✓ {name}")

            if len(tool_names) != 11:
                print(f"FAIL: expected 11 tools, got {len(tool_names)}", file=sys.stderr)
                sys.exit(1)

            # 2. Call each tool
            print("\nCalling all 11 stubs ...")
            for tool, args in TOOL_CALLS:
                result = await session.call_tool(tool, args)
                # result.content is a list of TextContent/etc
                content = result.content[0].text if result.content else ""
                import json

                try:
                    parsed = json.loads(content)
                    status = parsed.get("status")
                except Exception:
                    status = None
                mark = "✓" if status == "stub" else "✗"
                print(f"  {mark} {tool} → status={status}")
                if status != "stub":
                    print(f"FAIL: {tool} did not return stub status", file=sys.stderr)
                    sys.exit(1)

    print("\nAll 11 stubs responded correctly. exit 0")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
