from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord
from tools.security_tools import (
    BanditRunner,
    DASTRunner,
    PipAuditRunner,
    SecurityFinding,
    SecurityFindings,
    SemgrepRunner,
)

logger = structlog.get_logger()

_STRIDE_MODEL = "o3-mini"  # Responses API — NOT Chat Completions


class SecurityAgent(BaseAgent):
    """Agent 5b — SAST + DAST + STRIDE + detect-secrets. Security gate blocks Agent 8.

    Model: o3-mini for STRIDE (Responses API via OpenAIReasoningAdapter)
           gpt-5.4-mini for explanations
    Gate: HIGH or CRITICAL finding → state["security_gate"]["blocked"] = True
    threat_model.md written via DiffEngine (not Path.write_text directly)
    """

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        dast_status = (
            "enabled — uvicorn on port 18080"
            if os.getenv("RUN_DAST", "false").lower() == "true"
            else "disabled — set RUN_DAST=true to enable (not CI-safe)"
        )
        return self._emit_l1_record(
            component="SecurityAgent",
            action=(
                f"SECURITY SCAN PLAN\n"
                f"SAST: bandit + semgrep (p/python + p/security)\n"
                f"Dependencies: pip-audit\n"
                f"Secrets: detect-secrets\n"
                f"DAST: {dast_status}\n"
                f"STRIDE: o3-mini threat model of RFC\n"
                f"Gate: HIGH/CRITICAL findings block Agent 8 (deployment)"
            ),
            inputs={
                "workspace": str(
                    (state.get("workspace_context") or {}).get("root_path", ".")
                    if isinstance(state.get("workspace_context"), dict)
                    else "."
                ),
            },
            expected_outputs={
                "security_findings": "SecurityFindings",
                "security_gate": "SecurityGate",
            },
            external_calls=["bandit", "semgrep", "pip-audit", "o3-mini"],
            model_selected=_STRIDE_MODEL,
            files_write=["docs/security/threat_model.md"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Run all security tools and compute gate status."""
        workspace_ctx = await self.workspace.get_context()
        code_path = workspace_ctx.root_path

        # SAST tools
        bandit = BanditRunner()
        semgrep_runner = SemgrepRunner()
        pip_audit = PipAuditRunner()
        dast = DASTRunner()

        bandit_findings = await bandit.run(code_path)
        semgrep_findings = await semgrep_runner.run(code_path)
        pip_findings = await pip_audit.run(code_path)
        dast_findings = await dast.run(code_path)

        # detect-secrets
        secrets_findings = await self._run_detect_secrets(code_path)

        # STRIDE via o3-mini (Responses API)
        threat_model_path = await self._run_stride(state)

        # Aggregate and determine gate status
        all_findings = (
            bandit_findings + semgrep_findings + pip_findings
            + dast_findings + secrets_findings
        )
        gate_blocked = any(
            f.severity in ("CRITICAL", "HIGH") for f in all_findings
        )

        findings_obj = SecurityFindings(
            bandit_findings=bandit_findings,
            semgrep_findings=semgrep_findings,
            pip_audit_findings=pip_findings,
            dast_findings=dast_findings,
            detect_secrets_findings=secrets_findings,
            threat_model_path=threat_model_path,
            gate_blocked=gate_blocked,
        )

        state["security_findings"] = findings_obj.model_dump()
        state["security_gate"] = {
            "blocked": gate_blocked,
            "reason": (
                f"{sum(1 for f in all_findings if f.severity in ('CRITICAL', 'HIGH'))} "
                f"HIGH/CRITICAL findings — deployment blocked until resolved"
                if gate_blocked else None
            ),
        }

        logger.info(
            "agent_5b.executed",
            gate_blocked=gate_blocked,
            total_findings=len(all_findings),
            threat_model=threat_model_path,
        )
        return state

    async def _run_stride(self, state: dict[str, object]) -> str | None:
        """STRIDE threat modelling via o3-mini (Responses API).

        Uses OpenAIReasoningAdapter — client.responses.create (NOT Chat Completions).
        Writes result to docs/security/threat_model.md via DiffEngine.
        """
        rfc = str(state.get("rfc", ""))
        if not rfc:
            logger.info("agent_5b.stride_skipped", reason="no RFC in state")
            return None

        adapter = await self.model_router.route(
            agent="agent_5b_security",      # → o3-mini via AGENT_MODELS catalog
            task_type="security_reasoning",
            estimated_tokens=int(len(rfc.split()) * 2),
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd", 0.0) or 0.0),
            budget_total=float(state.get("budget_remaining_usd", 999.0) or 999.0),
        )

        response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(content=(
                    "You are a security architect. Run STRIDE threat analysis. "
                    "For each category (Spoofing, Tampering, Repudiation, "
                    "Information Disclosure, Denial of Service, Elevation of Privilege): "
                    "identify specific threats and mitigations for this architecture. "
                    "Output as structured Markdown."
                )),
                HumanMessage(content=f"RFC:\n{rfc[:6000]}"),
            ]
        )

        content = str(response.content) if response.content else ""
        threat_model = (
            f"<!-- Generated by forgeSDLC Agent 5b STRIDE — "
            f"{datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} -->\n\n"
            + content
        )

        # Write via DiffEngine — emits L3 InterpretRecord, creates .forgesdlc.bak
        path = "docs/security/threat_model.md"
        diff = await self.diff_engine.generate_diff(
            path, threat_model, "Agent 5b: STRIDE threat model"
        )
        await self.diff_engine.apply_diff(diff)
        return path

    async def _run_detect_secrets(self, code_path: str) -> list[SecurityFinding]:
        """Run detect-secrets scan on workspace."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "detect-secrets", "scan", code_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            data = json.loads(stdout.decode(errors="replace"))
            findings: list[SecurityFinding] = []
            for filepath, secrets in data.get("results", {}).items():
                for secret in secrets:
                    line_num = secret.get("line_number")
                    findings.append(SecurityFinding(
                        tool="detect_secrets",
                        rule="potential_secret",
                        severity="HIGH",
                        file=str(filepath),
                        line=int(line_num) if line_num and int(line_num) >= 1 else None,
                        description=(
                            f"Potential {secret.get('type', 'secret')} detected"
                        ),
                        fix_suggestion=(
                            "Move to environment variable or secrets manager"
                        ),
                        blocking=True,
                    ))
            return findings
        except Exception as exc:
            logger.warning("detect_secrets.failed", error=str(exc))
            return []