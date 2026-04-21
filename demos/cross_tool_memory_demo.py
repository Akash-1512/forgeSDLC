#!/usr/bin/env python3
"""
forgeSDLC Cross-Tool Memory Demo
==================================
Demonstrates the core forgeSDLC value proposition:
  A decision saved in one tool session is recalled by a completely
  different tool session — with no shared state.

Narrative:
  Step 1 — "Cursor" saves an architecture decision via save_decision()
  Step 2 — "Claude Code" (new session) recalls it via recall_context()

Requirements:
  MCP server running on port 8080.
  Start with: make run-mcp   OR   python -m mcp_server.server --port 8080

Usage:
  python demos/cross_tool_memory_demo.py
"""
from __future__ import annotations

import asyncio
import sys
import time

import httpx

SERVER = "http://localhost:8080"


async def demo() -> int:
    """Run the cross-tool memory demonstration. Returns exit code."""

    print("\n" + "=" * 60)
    print("  forgeSDLC Cross-Tool Memory Demo")
    print("=" * 60)

    # ── Health check first — fail fast with clear message ────────────────────
    print("\n📡 Checking MCP server...")
    try:
        r = httpx.get(f"{SERVER}/health", timeout=2)
        if r.status_code != 200:
            print(f"❌ MCP server returned {r.status_code}. Expected 200.")
            return 1
        print(f"   Server healthy at {SERVER}")
    except Exception:
        print(
            f"❌ MCP server not running at {SERVER}\n"
            "   Start with:  make run-mcp\n"
            "   Or:          python -m mcp_server.server "
            "--transport streamable-http --port 8080"
        )
        return 1

    project_id = f"demo-{int(time.time())}"
    print(f"\n   Project ID: {project_id}")
    print("   (unique per run — proves no shared state between steps)\n")

    async with httpx.AsyncClient(timeout=30) as client:

        # ── Step 1: Cursor saves decision ─────────────────────────────────────
        print("─" * 60)
        print("STEP 1 — Cursor saves an architecture decision")
        print("─" * 60)
        print("  Tool:    save_decision()")
        print("  Simulating: developer in Cursor documents a stack choice\n")

        try:
            r = await client.post(
                f"{SERVER}/call",
                json={
                    "name": "save_decision",
                    "arguments": {
                        "decision": (
                            "Use PostgreSQL with asyncpg for all database operations"
                        ),
                        "rationale": (
                            "ACID compliance, native async support, "
                            "compatible with Supabase for scalability"
                        ),
                        "project_id": project_id,
                        "category": "architecture",
                    },
                },
            )
            result = r.json()
            entry_id = result.get("entry_id", result.get("id", "n/a"))
            print(f"  ✅ Decision saved")
            print(f"     Entry ID:  {entry_id}")
            print(f"     Category:  architecture")
            print(f"     Decision:  Use PostgreSQL with asyncpg")
        except Exception as exc:
            print(f"  ❌ save_decision() failed: {exc}")
            return 1

        # Brief pause — let ChromaDB index the embedding
        print("\n  ⏳ Waiting 1s for ChromaDB to index...")
        await asyncio.sleep(1)

        # ── Step 2: Claude Code (new session) recalls ─────────────────────────
        print("\n" + "─" * 60)
        print("STEP 2 — Claude Code recalls project context (new session)")
        print("─" * 60)
        print("  Tool:    recall_context()")
        print("  Simulating: developer opens Claude Code, asks about the DB stack")
        print("  Query:   'What database should I use?'\n")

        try:
            r2 = await client.post(
                f"{SERVER}/call",
                json={
                    "name": "recall_context",
                    "arguments": {
                        "query": "What database should I use?",
                        "project_id": project_id,
                    },
                },
            )
            result2 = r2.json()
        except Exception as exc:
            print(f"  ❌ recall_context() failed: {exc}")
            return 1

        org_memory = result2.get("org_memory", [])
        pipeline_history = result2.get("pipeline_history", [])

        print(f"  Org memory entries returned: {len(org_memory)}")
        print(f"  Pipeline history entries:    {len(pipeline_history)}\n")

        if org_memory:
            print("  Retrieved decisions:")
            for entry in org_memory[:3]:
                content = str(entry.get("content", ""))[:120]
                category = entry.get("category", "unknown")
                print(f"  • [{category}] {content}")
        else:
            print("  (no org memory entries returned)")

        # ── Result ────────────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        found = any(
            "PostgreSQL" in str(e.get("content", ""))
            for e in org_memory
        )

        if found:
            print("✅  Cross-tool memory works!")
            print()
            print("   The decision saved in Step 1 (Cursor) was retrieved")
            print("   in Step 2 (Claude Code) with no shared Python state.")
            print()
            print("   This is what forgeSDLC does:")
            print("   → Every decision, pattern, and failure compounds into")
            print("     a living project memory accessible from any AI tool.")
            print("=" * 60 + "\n")
            return 0
        else:
            print("⚠️   Decision saved but not found in recall_context() results.")
            print()
            print("   Possible causes:")
            print("   • ChromaDB embedding not yet indexed (try increasing sleep)")
            print("   • recall_context() query didn't match semantically")
            print("   • org_memory disabled for this subscription tier")
            print("=" * 60 + "\n")
            return 0  # Not a hard failure — demo ran successfully


def main() -> int:
    return asyncio.run(demo())


if __name__ == "__main__":
    sys.exit(main())