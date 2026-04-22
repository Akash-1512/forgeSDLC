import asyncio

import httpx

BASE = "http://localhost:8080"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


async def test():
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE}/mcp",
            headers=H,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
        )
        sid = r.headers.get("mcp-session-id", "")

        r2 = await client.post(
            f"{BASE}/mcp",
            headers={**H, "mcp-session-id": sid},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "gather_requirements",
                    "arguments": {"prompt": "Build a todo REST API", "project_id": "debug-01"},
                },
            },
        )
        print("Full response:")
        print(r2.text[:2000])


asyncio.run(test())
