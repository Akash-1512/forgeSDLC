from __future__ import annotations

"""Smoke test — connects to forgeSDLC MCP server on localhost:8080,
lists all 11 tools, calls each one, and exits 0 on success.

Run after `forgesdlc` server is started in a separate terminal:
    uv run forgesdlc

Then in another terminal:
    uv run python scripts/mcp_test_client.py
"""

import asyncio
import sys

import httpx

BASE_URL = "http://localhost:8080"

TOOL_CALLS = [
    ("gather_requirements", {"prompt": "build a REST API", "project_id": "smoke-test"}),
    ("design_architecture", {"project_id": "smoke-test", "prd": "stub prd"}),
    ("recall_context", {"project_id": "smoke-test", "query": "tech stack"}),
    ("save_decision", {"project_id": "smoke-test", "decision": "use postgres", "rationale": "scale"}),
    ("route_code_generation", {"project_id": "smoke-test", "task": "write models", "context": ""}),
    ("run_security_scan", {"project_id": "smoke-test", "target_path": "./src"}),
    ("generate_cicd", {"project_id": "smoke-test", "stack": "fastapi"}),
    ("deploy_project", {"project_id": "smoke-test", "environment": "staging"}),
    ("setup_monitoring", {"project_id": "smoke-test", "deployment_url": "https://example.com"}),
    ("generate_docs", {"project_id": "smoke-test", "scope": "full"}),
    ("track_progress", {"project_id": "smoke-test"}),
]


async def call_tool(
    client: httpx.AsyncClient, tool: str, arguments: dict[str, object]
) -> dict[str, object]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    response = await client.post("/mcp", json=payload)
    response.raise_for_status()
    return response.json()  # type: ignore[return-value]


async def list_tools(client: httpx.AsyncClient) -> list[str]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    response = await client.post("/mcp", json=payload)
    response.raise_for_status()
    data = response.json()
    tools: list[str] = [t["name"] for t in data.get("result", {}).get("tools", [])]
    return tools


async def main() -> None:
    print(f"Connecting to forgeSDLC MCP server at {BASE_URL} ...")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. List tools
        tools = await list_tools(client)
        print(f"Tools registered: {len(tools)}")
        for name in tools:
            print(f"  ✓ {name}")

        if len(tools) != 11:
            print(f"FAIL: expected 11 tools, got {len(tools)}", file=sys.stderr)
            sys.exit(1)

        # 2. Call each tool
        print("\nCalling all 11 stubs ...")
        for tool, args in TOOL_CALLS:
            result = await call_tool(client, tool, args)
            content = result.get("result", {})
            status = content.get("status") if isinstance(content, dict) else None
            mark = "✓" if status == "stub" else "✗"
            print(f"  {mark} {tool} → status={status}")
            if status != "stub":
                print(f"FAIL: {tool} did not return stub status", file=sys.stderr)
                sys.exit(1)

    print("\nAll 11 stubs responded correctly. exit 0")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())