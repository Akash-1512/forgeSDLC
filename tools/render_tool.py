from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import structlog

from interpret.record import InterpretRecord
from orchestrator.constants import HEALTH_CHECK_TIMEOUT_SECONDS
from orchestrator.exceptions import ForgeSDLCError

logger = structlog.get_logger()


class RenderTool:
    """Wraps the Render deploy webhook and health polling.

    Emits InterpretRecord Layer 8 (tool) before EVERY API call.
    trigger_deploy: reversible=False — deployment is irreversible.
    wait_for_health: reversible=True — health check doesn't change state.
    wait_for_health(url=None): returns True immediately (local Docker case).
    """

    async def trigger_deploy(self) -> str:
        """Trigger deployment via Render webhook. Returns deploy response text."""
        hook_url = os.getenv("RENDER_DEPLOY_HOOK_URL", "")
        if not hook_url:
            raise ForgeSDLCError(
                "RENDER_DEPLOY_HOOK_URL not set. "
                "Add it from Render service settings → Deploy Hooks."
            )

        # Emit L8 BEFORE the API call — deployment is irreversible
        InterpretRecord(
            layer="tool",
            component="RenderTool",
            action="Triggering Render deployment via webhook",
            inputs={"hook_url": hook_url[:40] + "..."},
            expected_outputs={"deploy_id": "str"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[hook_url],
            model_selected=None,
            tool_delegated_to=None,
            reversible=False,  # deployment is irreversible until manually rolled back
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info("render_tool.trigger_deploy", hook_url=hook_url[:40])

        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as client:
            r = await client.post(hook_url)
            r.raise_for_status()
            return r.text

    async def wait_for_health(self, url: str | None, timeout_seconds: int = 60) -> bool:
        """Poll {url}/health every 10s until 200 or timeout.

        Returns True if healthy within timeout.
        Returns False on timeout.
        Returns True immediately when url is None (local Docker — no public URL).
        Emits L8 InterpretRecord before polling begins.
        """
        # Emit L8 BEFORE polling (even for None URL — audit trail completeness)
        InterpretRecord(
            layer="tool",
            component="RenderTool",
            action=f"Polling health: {url}/health" if url else "Health check skipped (no URL)",
            inputs={"url": url, "timeout": timeout_seconds},
            expected_outputs={"healthy": "bool"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=[f"{url}/health"] if url else [],
            model_selected=None,
            tool_delegated_to=None,
            reversible=True,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )

        if not url:
            logger.info("render_health_check_skipped", reason="no deployment URL — local Docker")
            return True  # Local Docker — no public URL, no health check needed

        logger.info("render_health_polling", url=url, timeout=timeout_seconds)
        deadline = asyncio.get_event_loop().time() + timeout_seconds

        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient() as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await client.get(f"{url}/health", timeout=5)
                    if r.status_code == 200:
                        logger.info("render_health_ok", url=url)
                        return True
                except Exception:
                    pass
                await asyncio.sleep(10)

        logger.warning("render_health_timeout", url=url, timeout=timeout_seconds)
        return False
