#!/usr/bin/env python3
import asyncio
import httpx
import json
import sys
import time

SERVER = "http://localhost:8080"
H = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


async def mcp_init(client):
    r = await client.post(
        f"{SERVER}/mcp",
        headers=H,
        json={
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "demo", "version": "1.0"},
                "capabilities": {},
            },
        },
    )
    return r.headers.get("mcp-session-id", "")


async def mcp_call(client, sid, tool, args):
    r = await client.post(
        f"{SERVER}/mcp",
        headers={**H, "mcp-session-id": sid},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        },
    )
    for line in r.text.splitlines():
        if line.startswith("data:"):
            d = json.loads(line[5:])
            c = d.get("result", {}).get("content", [{}])
            t = c[0].get("text", "") if c else ""
            try:
                return json.loads(t)
            except Exception:
                return {"raw": t}
    return {}


async def demo():
    print("=" * 60)
    print("  forgeSDLC Cross-Tool Memory Demo")
    print("=" * 60)

    # Health check
    try:
        r = httpx.get(f"{SERVER}/mcp", timeout=2,
                      headers={"Accept": "application/json, text/event-stream"})
        if r.status_code not in (200, 400, 405, 406, 422):
            print(f"Server returned unexpected status {r.status_code}")
            return 1
        print(f"Server OK at {SERVER}")
    except Exception as e:
        print(f"Server not running: {e}")
        print("Start with: python -m mcp_server.server --transport streamable-http --port 8080")
        return 1

    project_id = f"demo-{int(time.time())}"
    print(f"Project: {project_id}")

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: save_decision
        print("\nSTEP 1 - Cursor saves an architecture decision")
        sid1 = await mcp_init(client)
        r1 = await mcp_call(client, sid1, "save_decision", {
            "decision": "Use PostgreSQL with asyncpg",
            "rationale": "ACID compliance and async support",
            "project_id": project_id,
        })
        print("save_decision result:", str(r1)[:120])
        await asyncio.sleep(1)

        # Step 2: recall_context (fresh session)
        print("\nSTEP 2 - Claude Code recalls (new session)")
        sid2 = await mcp_init(client)
        r2 = await mcp_call(client, sid2, "recall_context", {
            "query": "What database should I use?",
            "project_id": project_id,
        })
        mem = r2.get("org_memory", [])
        print(f"Recalled {len(mem)} entries")
        for e in mem[:3]:
            print(" -", str(e.get("content", ""))[:100])

        found = any("PostgreSQL" in str(e.get("content", "")) for e in mem)
        print("\n" + "=" * 60)
        if found:
            print("Cross-tool memory: WORKS")
            print("Decision saved in Step 1 retrieved in Step 2")
        else:
            print("Decision not found in recall yet")
        print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(demo()))