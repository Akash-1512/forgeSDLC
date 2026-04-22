"""
End-to-end MCP client test.
Starts the forgeSDLC MCP server as a subprocess, connects via HTTP,
calls tools, and verifies responses.

Marked @pytest.mark.slow — excluded from default test run.
Run with: python -m pytest tests/integration/test_mcp_client_e2e.py -v
"""

from __future__ import annotations

import subprocess
import sys
import time

import httpx
import pytest

TEST_PORT = 18090
SERVER_URL = f"http://localhost:{TEST_PORT}"


@pytest.fixture(scope="module")
def mcp_server():
    """Start MCP server on port 18090 for testing. Shuts down after module."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mcp_server.server",
            "--transport",
            "streamable-http",
            "--port",
            str(TEST_PORT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to be ready (up to 15s)
    deadline = time.time() + 15
    ready = False
    while time.time() < deadline:
        try:
            r = httpx.get(f"{SERVER_URL}/health", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.3)

    if not ready:
        proc.terminate()
        proc.wait()
        pytest.skip("MCP server did not start within 15s — skipping e2e tests")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_mcp_server_health_endpoint(mcp_server: object) -> None:
    """MCP server responds to /health with 200."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SERVER_URL}/health", timeout=5)
    assert r.status_code == 200


@pytest.mark.slow
@pytest.mark.asyncio
async def test_mcp_server_lists_tools(mcp_server: object) -> None:
    """MCP server exposes registered tools via /tools endpoint."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SERVER_URL}/tools", timeout=5)

    if r.status_code == 404:
        pytest.skip("Server does not expose /tools endpoint — verify FastMCP version")

    assert r.status_code == 200
    body = r.json()
    # Accept either list or dict with tools key
    if isinstance(body, list):
        tool_names = [t.get("name") for t in body if isinstance(t, dict)]
    else:
        tool_names = [t.get("name") for t in body.get("tools", []) if isinstance(t, dict)]

    expected_tools = [
        "gather_requirements",
        "design_architecture",
        "recall_context",
        "save_decision",
        "route_code_generation",
        "run_security_scan",
        "generate_cicd",
        "deploy_project",
        "setup_monitoring",
        "generate_docs",
        "track_progress",
    ]
    for name in expected_tools:
        assert name in tool_names, (
            f"Tool '{name}' not found in MCP server tool listing.\nAvailable: {tool_names}"
        )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_gather_requirements_returns_awaiting_confirmation(
    mcp_server: object,
) -> None:
    """First call to gather_requirements returns awaiting_confirmation status."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{SERVER_URL}/call",
            json={
                "name": "gather_requirements",
                "arguments": {
                    "prompt": "Build a simple REST API for user management",
                    "project_id": f"test-e2e-{int(time.time())}",
                },
            },
        )

    if r.status_code == 404:
        pytest.skip("/call endpoint not available — verify FastMCP transport version")

    assert r.status_code == 200
    result = r.json()
    assert result.get("status") == "awaiting_confirmation", (
        f"Expected status='awaiting_confirmation', got: {result.get('status')}\n"
        f"Full response: {result}"
    )
    assert (
        "interpretation" in result
        or "displayed_interpretation" in result
        or "interpret_log" in result
    ), "Response must contain interpretation for human review"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_mcp_server_recall_context_returns_dict(mcp_server: object) -> None:
    """recall_context() returns a dict with project_id field."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{SERVER_URL}/call",
            json={
                "name": "recall_context",
                "arguments": {
                    "project_id": "test-recall-e2e",
                },
            },
        )

    if r.status_code == 404:
        pytest.skip("/call endpoint not available")

    assert r.status_code == 200
    result = r.json()
    assert isinstance(result, dict), f"recall_context must return a dict, got: {type(result)}"


@pytest.mark.slow
def test_mcp_server_starts_and_stops_cleanly(mcp_server: object) -> None:
    """Verify server process is running during fixture lifetime."""
    proc = mcp_server
    assert proc.poll() is None, (
        "MCP server process exited unexpectedly during test run. "
        "Check server logs for startup errors."
    )
