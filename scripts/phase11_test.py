import asyncio
import json

import httpx

BASE = "http://localhost:8080"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


async def test():
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{BASE}/mcp",
            headers=H,
            json={
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "hitl-test", "version": "1.0"},
                    "capabilities": {},
                },
            },
        )
        sid = r.headers.get("mcp-session-id", "")
        print("Session:", sid[:16])

        r2 = await client.post(
            f"{BASE}/mcp",
            headers={**H, "mcp-session-id": sid},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "gather_requirements",
                    "arguments": {
                        "prompt": "Build a todo REST API with PostgreSQL",
                        "project_id": "live-hitl-01",
                        "human_confirmation": "100% GO",
                    },
                },
            },
        )
        for line in r2.text.splitlines():
            if line.startswith("data:"):
                result = json.loads(line[5:])
                content = result.get("result", {}).get("content", [{}])
                text = content[0].get("text", "") if content else ""
                data = json.loads(text) if text.startswith("{") else {}
                print("Status:", data.get("status"))
                print("Stage:", data.get("stage", "n/a"))
                disp = data.get("displayed_interpretation", "")
                print("Interpretation:", str(disp)[:150])
                break


asyncio.run(test())
