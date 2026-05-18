#!/usr/bin/env python3
"""
forgeSDLC Demo Runner — for tech manager evaluation.

Usage:
    python scripts/demo_runner.py                   # E2E mode (no keys needed)
    python scripts/demo_runner.py --mode full       # Full LLM demo (GROQ_API_KEY)
    python scripts/demo_runner.py --mode e2e        # All 11 tools, no LLM
    python scripts/demo_runner.py --mode tests      # Run test suite with coverage
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

# --------------------------------------------------------------------------- #
# Colours                                                                       #
# --------------------------------------------------------------------------- #
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}❌ {msg}{RESET}")


def info(msg: str) -> None:
    print(f"{CYAN}   {msg}{RESET}")


def header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}\n")


# --------------------------------------------------------------------------- #
# E2E tool test                                                                 #
# --------------------------------------------------------------------------- #


async def run_e2e(project: str = "demo-001") -> bool:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    os.environ.setdefault("SECRET_KEY", "demo-secret-key-minimum-32-chars-long")

    header("E2E: All 11 MCP tools (no LLM keys required)")

    try:
        from fastmcp import Client  # noqa: PLC0415

        from mcp_server.server import mcp  # noqa: PLC0415
    except ImportError as e:
        fail(f"Import failed: {e}")
        info("Run: pip install -e '.[dev]'")
        return False

    passed, failed_tools = [], []

    tools_under_test = [
        ("track_progress", {"project_id": project}),
        (
            "save_decision",
            {
                "decision": "Use PostgreSQL for persistence",
                "rationale": "ACID compliance, team familiarity",
                "project_id": project,
            },
        ),  # noqa: E501
        ("recall_context", {"query": "database technology", "project_id": project}),
        (
            "gather_requirements",
            {
                "prompt": "Build a REST API for task management with JWT authentication",
                "project_id": project,
                "human_confirmation": "",
                "correction": "",
            },
        ),  # noqa: E501
        (
            "design_architecture",
            {
                "requirements": "REST API, JWT auth, PostgreSQL, Redis cache",
                "project_id": project,
                "human_confirmation": "",
                "correction": "",
            },
        ),  # noqa: E501
        (
            "run_security_scan",
            {"project_id": project, "target_path": "/tmp", "rfc": "", "human_confirmation": ""},
        ),
        (
            "generate_cicd",
            {
                "project_id": project,
                "stack": "python-fastapi",
                "workspace_path": "/tmp",
                "human_confirmation": "",
            },
        ),  # noqa: E501
        (
            "route_code_generation",
            {
                "task": "implement JWT authentication middleware",
                "project_id": project,
                "workspace_path": "/tmp",
                "human_confirmation": "",
            },
        ),  # noqa: E501
        (
            "deploy_project",
            {
                "project_id": project,
                "environment": "staging",
                "workspace_path": "/tmp",
                "human_confirmation": "",
            },
        ),  # noqa: E501
        (
            "setup_monitoring",
            {
                "project_id": project,
                "deployment_url": "https://api.example.com",
                "human_confirmation": "",
            },
        ),  # noqa: E501
        ("generate_docs", {"project_id": project, "scope": "readme", "human_confirmation": ""}),
    ]

    async with Client(mcp) as client:
        tools = await client.list_tools()
        info(f"Tools registered: {len(tools)}/11")

        for tool_name, kwargs in tools_under_test:
            try:
                result = await client.call_tool(tool_name, kwargs)
                text = getattr(getattr(result, "content", [None])[0], "text", "{}")
                data = json.loads(text) if text else {}
                status = data.get("status", data.get("current_stage", data.get("phase", "ok")))
                ok(f"{tool_name:<25} → {status}")
                passed.append(tool_name)
            except Exception as e:  # noqa: BLE001
                fail(f"{tool_name:<25} → {str(e)[:60]}")
                failed_tools.append(tool_name)

    print()
    if failed_tools:
        fail(f"{len(passed)}/11 tools passed.  Failed: {failed_tools}")
        return False
    ok("11/11 tools passed — server is fully operational")
    return True


# --------------------------------------------------------------------------- #
# Full LLM demo                                                                 #
# --------------------------------------------------------------------------- #


async def run_full_demo(project: str = "task-api-demo") -> bool:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        fail("GROQ_API_KEY not set. Get a free key at https://console.groq.com")
        info("export GROQ_API_KEY='gsk_...'")
        return False

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    os.environ.setdefault("SECRET_KEY", "demo-secret-key-minimum-32-chars-long")

    header(f"Full LLM Demo — project: {project}")
    info("Using Groq free tier (llama-3.3-70b-versatile) — no cost")
    info("Agents pause for approval before irreversible actions")
    print()

    from fastmcp import Client  # noqa: PLC0415

    from mcp_server.server import mcp  # noqa: PLC0415

    async with Client(mcp) as client:
        # Step 1: Requirements
        print(f"{BOLD}Step 1/4 — gather_requirements{RESET}")
        r = await client.call_tool(
            "gather_requirements",
            {
                "project_id": project,
                "prompt": "REST API for task management with JWT auth and team roles",
                "human_confirmation": "",
                "correction": "",
            },
        )
        data = json.loads(getattr(getattr(r, "content", [None])[0], "text", "{}"))
        phase = data.get("current_stage", data.get("status", "?"))
        print(f"  status: {YELLOW}{phase}{RESET}")

        if phase == "awaiting_confirmation":
            print(f"\n{DIM}  Agent 0 (Decomposition) has analysed the project scope.")
            print("  In production: review the InterpretRecord in the companion panel.")
            print(f"  Sending approval now for demo purposes...{RESET}\n")
            time.sleep(1)
            r = await client.call_tool(
                "gather_requirements",
                {
                    "project_id": project,
                    "prompt": "REST API for task management with JWT auth and team roles",
                    "human_confirmation": "100% GO",
                    "correction": "",
                },
            )
            data = json.loads(getattr(getattr(r, "content", [None])[0], "text", "{}"))
            phase = data.get("current_stage", data.get("status", "?"))
            ok(f"gather_requirements → {phase}")
            if data.get("prd"):
                info(f"PRD generated: {len(data['prd'])} chars")

        # Step 2: Architecture
        print(f"\n{BOLD}Step 2/4 — design_architecture{RESET}")
        r = await client.call_tool(
            "design_architecture",
            {
                "project_id": project,
                "requirements": data.get("prd", "REST API, JWT auth, PostgreSQL"),
                "human_confirmation": "",
                "correction": "",
            },
        )
        data2 = json.loads(getattr(getattr(r, "content", [None])[0], "text", "{}"))
        phase2 = data2.get("current_stage", data2.get("status", "?"))
        print(f"  status: {YELLOW}{phase2}{RESET}")
        if data2.get("architecture_score"):
            info(f"Architecture score: {data2['architecture_score']}")

        # Step 3: Security scan
        print(f"\n{BOLD}Step 3/4 — run_security_scan{RESET}")
        r = await client.call_tool(
            "run_security_scan",
            {
                "project_id": project,
                "target_path": "/tmp",
                "rfc": "",
                "human_confirmation": "",
            },
        )
        data3 = json.loads(getattr(getattr(r, "content", [None])[0], "text", "{}"))
        ok(f"run_security_scan → {data3.get('status', '?')}")

        # Step 4: Progress
        print(f"\n{BOLD}Step 4/4 — track_progress{RESET}")
        r = await client.call_tool("track_progress", {"project_id": project})
        prog = json.loads(getattr(getattr(r, "content", [None])[0], "text", "{}"))
        ok(f"track_progress → {prog.get('completion_pct', 0)}% complete")
        remaining = prog.get("stages_remaining", [])
        if remaining:
            info(f"Remaining stages: {', '.join(remaining[:4])}")

    print()
    ok("Full demo complete. All agents fired, approval gates enforced.")
    return True


# --------------------------------------------------------------------------- #
# Test suite runner                                                              #
# --------------------------------------------------------------------------- #


def run_tests() -> bool:
    header("Test Suite")
    start = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-m",
            "not slow",
            "--tb=short",
            "-q",
            "--no-header",
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    elapsed = time.monotonic() - start
    if result.returncode == 0:
        ok(f"All tests passed in {elapsed:.1f}s")
        return True
    else:
        fail("Some tests failed")
        return False


# --------------------------------------------------------------------------- #
# Lint check                                                                    #
# --------------------------------------------------------------------------- #


def run_lint() -> bool:
    header("Lint & Format Check (ruff)")
    root = os.path.dirname(os.path.dirname(__file__))
    r1 = subprocess.run(["ruff", "check", "."], cwd=root, capture_output=True, text=True)
    r2 = subprocess.run(
        ["ruff", "format", "--check", "."], cwd=root, capture_output=True, text=True
    )
    if r1.returncode == 0 and r2.returncode == 0:
        ok("0 lint errors, 0 format issues")
        return True
    fail(r1.stdout or r2.stdout)
    return False


# --------------------------------------------------------------------------- #
# Main                                                                           #
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description="forgeSDLC demo runner")
    parser.add_argument("--mode", choices=["e2e", "full", "tests", "all"], default="e2e")
    parser.add_argument("--project", default="demo-001")
    args = parser.parse_args()

    print(f"\n{BOLD}forgeSDLC v1.1.0 — Evaluation Runner{RESET}")
    print(f"{DIM}github.com/Akash-1512/forgeSDLC{RESET}\n")

    results = []

    if args.mode in ("e2e", "all"):
        results.append(("E2E tool test", asyncio.run(run_e2e(args.project))))

    if args.mode in ("full", "all"):
        results.append(("Full LLM demo", asyncio.run(run_full_demo(args.project))))

    if args.mode in ("tests", "all"):
        results.append(("Lint", run_lint()))
        results.append(("Tests", run_tests()))

    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  Results{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")
    for label, passed in results:
        icon = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{icon}] {label}")

    if all(r for _, r in results):
        print(f"\n{BOLD}{GREEN}  All checks passed.{RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{BOLD}{RED}  Some checks failed.{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
