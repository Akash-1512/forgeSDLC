import asyncio
import json

import httpx

BASE = "http://localhost:8080"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

async def call(client, sid, args):
    r = await client.post(f"{BASE}/mcp",
        headers={**H, "mcp-session-id": sid},
        json={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
            "name": "gather_requirements", "arguments": args}})
    for line in r.text.splitlines():
        if line.startswith("data:"):
            d = json.loads(line[5:])
            text = d.get("result",{}).get("content",[{}])[0].get("text","")
            return json.loads(text) if text.startswith("{") else {"raw": text[:200]}
    return {}

async def test():
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{BASE}/mcp", headers=H,
            json={"jsonrpc":"2.0","id":0,"method":"initialize","params":{
                "protocolVersion":"2024-11-05",
                "clientInfo":{"name":"test","version":"1.0"},"capabilities":{}}})
        sid = r.headers.get("mcp-session-id","")
        print("Session:", sid[:16])

        # Call 1: interpret
        r1 = await call(client, sid, {"prompt": "Build a todo REST API with PostgreSQL", "project_id": "hitl-fresh-01"})
        print("Call 1 status:", r1.get("status"), "stage:", r1.get("stage"))

        # Call 2: approve
        r2 = await call(client, sid, {"prompt": "Build a todo REST API with PostgreSQL", "project_id": "hitl-fresh-01", "human_confirmation": "100% GO"})
        print("Call 2 status:", r2.get("status"), "stage:", r2.get("stage"))
        if r2.get("raw"):
            print("Call 2 raw:", r2["raw"])

asyncio.run(test())
