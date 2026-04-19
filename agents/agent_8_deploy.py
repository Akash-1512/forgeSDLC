from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import structlog

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord
from orchestrator.exceptions import ForgeSDLCError
from tools.render_tool import RenderTool

logger = structlog.get_logger()

_MODEL = "gpt-5.4-mini"


class DeployAgent(BaseAgent):
    """Agent 8 — deployment to Render or local Docker.

    hard_gate = True — companion panel shows red border (Session 17).
    Security gate pre-check runs BEFORE interpret_node.
    Overrides BaseAgent.run() to add the pre-check.
    Cold start warning ALWAYS appears in interpret — content varies by tier.
    Writes PostMortem to Layer 5 on deployment failure.
    Dockerfile: multi-stage, non-root UID 1000, HEALTHCHECK on /health.
    """

    hard_gate: bool = True  # Session 17 Desktop reads this for red border UI

    async def run(self, state: dict[str, object]) -> dict[str, object]:
        """Override: security gate pre-check before calling super().run().

        If security gate is blocked: return state immediately.
        super().run() is NOT called — interpret_node is never reached.
        """
        gate = dict(state.get("security_gate") or {})
        if gate.get("blocked", False):
            reason = str(gate.get("reason", "Security findings not resolved"))
            logger.warning("agent_8.blocked_by_security_gate", reason=reason)
            state["deploy_blocked"] = True
            state["deploy_blocked_reason"] = (
                "Security gate not cleared. Run run_security_scan() and "
                "resolve all HIGH/CRITICAL findings before deployment."
            )
            return state

        # Gate clear — proceed with normal BaseAgent lifecycle
        return await super().run(state)

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Preview deployment. Cold start warning ALWAYS present. Emits L1."""
        render_hook = os.getenv("RENDER_DEPLOY_HOOK_URL", "")

        if render_hook:
            is_paid = os.getenv("RENDER_TIER", "free").lower() != "free"
            cold_start_line = (
                "✅ Cold start: none (Render Starter — always-on)"
                if is_paid
                else "⚠️  Cold start: 30-60s after 15min idle (Render free tier)"
            )
            target = "Render"
        else:
            cold_start_line = "🐳 Cold start: N/A — Local Docker deployment"
            target = "Docker local"

        # Past failures from Layer 5 memory
        past_failures: list[object] = []
        if memory_context and hasattr(memory_context, "past_failures"):
            past_failures = list(memory_context.past_failures or [])
        failure_summary = (
            f"{len(past_failures)} past deployment failure(s) on record."
            if past_failures
            else "No past deployment failures."
        )

        record = InterpretRecord(
            layer="agent",
            component="DeployAgent",
            action=(
                f"⚠️  DEPLOYMENT — IRREVERSIBLE UNTIL MANUALLY ROLLED BACK\n"
                f"Target: {target}\n"
                f"{cold_start_line}\n"
                f"Dockerfile: multi-stage, non-root UID 1000, HEALTHCHECK /health\n"
                f"Post-deploy health check: /health → 200 within 60s\n"
                f"Security gate: CLEARED ✅\n"
                f"Past deployments: {failure_summary}\n"
                f"⚠️  THIS IS AN ARCHITECTURAL COMMITMENT. Review carefully."
            ),
            inputs={"target": target},
            expected_outputs={"deployment_url": "str | None"},
            files_it_will_read=[],
            files_it_will_write=["Dockerfile"],
            external_calls=["render_webhook" if render_hook else "docker"],
            model_selected=_MODEL,
            tool_delegated_to=None,
            reversible=False,
            workspace_files_affected=["Dockerfile"],
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "interpret_record.agent",
            layer=record.layer,
            component="DeployAgent",
            target=target,
        )
        return record

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Generate Dockerfile and deploy. Writes PostMortem on failure."""
        try:
            # Step 1: Generate Dockerfile via DiffEngine (L3 InterpretRecord)
            dockerfile = self._generate_dockerfile(state)
            workspace_path = "."
            try:
                wctx = await self.workspace.get_context()
                workspace_path = wctx.root_path
            except Exception:
                pass

            import os as _os  # noqa: PLC0415
            dockerfile_path = _os.path.join(workspace_path, "Dockerfile")
            diff = await self.diff_engine.generate_diff(
                filepath=dockerfile_path,
                new_content=dockerfile,
                reason="Agent 8: production Dockerfile",
            )
            await self.diff_engine.apply_diff(diff)

            # Step 2: Deploy
            render_hook = os.getenv("RENDER_DEPLOY_HOOK_URL", "")
            if render_hook:
                render = RenderTool()
                await render.trigger_deploy()
                deployment_url = os.getenv("RENDER_SERVICE_URL")
                healthy = await render.wait_for_health(
                    deployment_url, timeout_seconds=60
                )
                if not healthy:
                    raise ForgeSDLCError(
                        "Deployment health check failed after 60s. "
                        "Check Render logs for startup errors."
                    )
            else:
                deployment_url = None
                logger.info(
                    "agent_8.local_docker",
                    reason="RENDER_DEPLOY_HOOK_URL not set",
                )

            state["deployment_url"] = deployment_url
            logger.info("agent_8.deployment_success", url=deployment_url)
            return state

        except Exception as exc:
            logger.error("agent_8.deployment_failed", error=str(exc))
            await self._write_post_mortem(state, str(exc))
            state["deployment_url"] = None
            raise

    def _generate_dockerfile(self, state: dict[str, object]) -> str:
        """Generate a production-ready multi-stage Dockerfile.

        Rules:
        - Multi-stage: builder + runtime stages
        - Non-root user: UID 1000 (appuser)
        - useradd BEFORE COPY . . (files can be chowned to appuser)
        - HEALTHCHECK on /health
        - Python 3.12-slim base
        """
        return """\
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN useradd --uid 1000 --create-home --shell /bin/bash appuser
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

    async def _write_post_mortem(
        self, state: dict[str, object], error: str
    ) -> None:
        """Write deployment failure to Layer 5 (PostMortemStore)."""
        try:
            from memory.post_mortem_records import PostMortemStore  # noqa: PLC0415
            from memory.schemas import PostMortem  # noqa: PLC0415

            store = PostMortemStore()
            pm = PostMortem(
                post_mortem_id=str(uuid4()),
                run_id=str(state.get("trace_id", "unknown")),
                failure_type="deployment",
                agent_that_failed="agent_8_deploy",
                root_cause=error[:500],
                resolution="Manual investigation required",
                prevention_rule=(
                    "Check RENDER_DEPLOY_HOOK_URL and service health before deploy"
                ),
                stack_context=str(state.get("adr", ""))[:200],
                tool_involved=None,
                timestamp=datetime.now(tz=timezone.utc),
            )
            await store.save_post_mortem(pm)
            logger.info("agent_8.post_mortem_written", error=error[:80])
        except Exception as pm_exc:
            logger.warning("agent_8.post_mortem_failed", error=str(pm_exc))