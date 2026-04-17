from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from architecture_intelligence.anti_pattern_detector import AntiPatternDetector
from architecture_intelligence.architecture_scorer import ArchitectureScorer
from architecture_intelligence.nfr_satisfiability import NFRSatisfiabilityChecker
from interpret.record import InterpretRecord

logger = structlog.get_logger()

_MODEL = "gpt-5.4"

_RFC_SYSTEM_PROMPT = """\
You are a senior software architect. Generate a detailed RFC (Request for Comments)
for the following project. Structure it as:

# RFC-001: System Design

## Overview
## Service Architecture
## API Contracts
## Data Model
## Security Considerations
## Deployment Topology
## Observability
## Architecture Diagram

Include a Mermaid diagram embedded as a fenced ```mermaid code block (NOT an image URL).
The diagram must be version-controllable and renderable in GitHub Markdown.
Format: Markdown."""


class ArchitectureAgent(BaseAgent):
    """Agent 3 — generates and validates system architecture.

    Model: gpt-5.4 (quality matters for architecture decisions)
    HardGate: hard_gate = True — companion panel shows red left border (Session 17)
    Validation: AntiPatternDetector + NFRSatisfiabilityChecker run BEFORE LLM
    Blocking: HIGH anti-pattern OR NFR failure → gate_blocked → execute cannot fire
    """

    hard_gate: bool = True  # Session 17 Desktop reads this for red border UI

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Run deterministic validation. Emits L1 InterpretRecord.

        Validation runs BEFORE any LLM call. If gate is blocked, sets
        state["human_confirmation"] = "" to prevent execute from firing.
        """
        detector = AntiPatternDetector()
        checker = NFRSatisfiabilityChecker()
        scorer = ArchitectureScorer()

        service_graph = dict(state.get("service_graph") or {"services": []})
        prd = str(state.get("prd", ""))
        rfc_draft = str(state.get("rfc", ""))  # use existing RFC on re-interpret rounds

        # All three: DETERMINISTIC, ZERO LLM CALLS
        ap_result = detector.detect(rfc_draft, service_graph)
        nfr_checks = checker.check(prd, rfc_draft)
        arch_score = scorer.score(rfc_draft)

        gate_blocked = not ap_result.all_clear or not checker.all_satisfied(nfr_checks)

        # Store validation results in state for audit and display
        state["arch_validation"] = {
            "anti_pattern_result": ap_result.model_dump(),
            "nfr_checks": [c.model_dump() for c in nfr_checks],
            "architecture_score": arch_score.model_dump(),
            "gate_blocked": gate_blocked,
        }

        # If gate is blocked, overwrite human_confirmation → check_gate("") = False
        if gate_blocked:
            state["human_confirmation"] = ""
            logger.warning(
                "agent_3.gate_blocked",
                high_count=ap_result.high_count,
                failed_nfrs=sum(1 for c in nfr_checks if not c.satisfied),
            )

        interpretation = self._format_interpretation(
            ap_result, nfr_checks, arch_score, gate_blocked
        )
        state["displayed_interpretation"] = interpretation

        return self._emit_l1_record(
            component="ArchitectureAgent",
            action=f"Architecture proposal: {interpretation[:100]}",
            inputs={
                "prd_length": len(prd),
                "services": len(service_graph.get("services") or []),
                "gate_blocked": gate_blocked,
                "high_count": ap_result.high_count,
            },
            expected_outputs={
                "rfc": "RFC-001-system-design.md",
                "arch_validation": "AntiPatternResult + NFRChecks + ArchScore",
            },
            external_calls=[_MODEL],
            model_selected=_MODEL,
            files_write=["docs/architecture/RFC-001-system-design.md"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Generate RFC via gpt-5.4 and write via DiffEngine. Only after gate passes."""
        adapter = await self.model_router.route(
            agent="agent_3_architecture",
            task_type="architecture",
            estimated_tokens=int(len(str(state.get("prd", "")).split()) * 3),
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd", 0.0) or 0.0),
            budget_total=float(state.get("budget_remaining_usd", 999.0) or 999.0),
        )

        response = await adapter.ainvoke(
            [
                SystemMessage(content=_RFC_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"PRD:\n{str(state.get('prd', ''))}\n\n"
                        f"ADR:\n{str(state.get('adr', ''))}\n\n"
                        f"Service Graph:\n{state.get('service_graph', {})}"
                    )
                ),
            ]
        )
        rfc_content = str(response.content) if response.content else ""

        # Add metadata header
        rfc_with_header = (
            f"<!-- Generated by forgeSDLC Agent 3 — "
            f"{datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} -->\n\n"
            + rfc_content
        )

        # Write RFC via DiffEngine — emits L3 InterpretRecord, creates .forgesdlc.bak
        workspace_path = "."
        try:
            wctx = await self.workspace.get_context()
            workspace_path = wctx.root_path
        except Exception:
            pass

        rfc_path = str(
            Path(workspace_path) / "docs" / "architecture" / "RFC-001-system-design.md"
        )
        diff = await self.diff_engine.generate_diff(
            filepath=rfc_path,
            new_content=rfc_with_header,
            reason="Agent 3: initial architecture RFC",
        )
        await self.diff_engine.apply_diff(diff)

        # Write openapi.yaml only when API service detected
        service_graph = dict(state.get("service_graph") or {})
        if self._has_api_service(service_graph):
            openapi_stub = self._generate_openapi_stub(state)
            openapi_path = str(
                Path(workspace_path) / "docs" / "architecture" / "openapi.yaml"
            )
            diff_api = await self.diff_engine.generate_diff(
                filepath=openapi_path,
                new_content=openapi_stub,
                reason="Agent 3: OpenAPI spec stub",
            )
            await self.diff_engine.apply_diff(diff_api)

        state["rfc"] = rfc_with_header
        logger.info("agent_3.executed", rfc_chars=len(rfc_with_header))
        return state

    # ------------------------------------------------------------------ helpers

    def _format_interpretation(
        self,
        ap_result: object,
        nfr_checks: list[object],
        score: object,
        blocked: bool,
    ) -> str:
        from architecture_intelligence.anti_pattern_detector import AntiPatternResult  # noqa: PLC0415
        from architecture_intelligence.architecture_scorer import ArchitectureScore  # noqa: PLC0415
        from architecture_intelligence.nfr_satisfiability import NFRCheck  # noqa: PLC0415

        ap = ap_result  # type: ignore[assignment]
        sc = score  # type: ignore[assignment]
        checks: list[NFRCheck] = nfr_checks  # type: ignore[assignment]

        lines = [
            "ARCHITECTURE PROPOSAL\n",
            f"Score: Scalability {sc.scalability}/10 | "  # type: ignore[attr-defined]
            f"Reliability {sc.reliability}/10 | "  # type: ignore[attr-defined]
            f"Security {sc.security}/10 | "  # type: ignore[attr-defined]
            f"Maintainability {sc.maintainability}/10 | "  # type: ignore[attr-defined]
            f"Cost {sc.cost}/10 | "  # type: ignore[attr-defined]
            f"Overall {sc.overall}/10\n",  # type: ignore[attr-defined]
        ]

        if ap.high_count > 0:  # type: ignore[attr-defined]
            lines.append(f"🚫 BLOCKED — {ap.high_count} HIGH anti-pattern(s):")  # type: ignore[attr-defined]
            for f in ap.findings:  # type: ignore[attr-defined]
                if f.blocking:
                    lines.append(f"  • Rule {f.rule}: {f.description}")
        else:
            lines.append("✅ No HIGH anti-patterns found")

        failed_nfrs = [c for c in checks if not c.satisfied]
        if failed_nfrs:
            lines.append(f"\n🚫 BLOCKED — {len(failed_nfrs)} NFR(s) not satisfied:")
            for c in failed_nfrs:
                lines.append(f"  • {c.nfr}: {c.failure_reason}")
        elif checks:
            lines.append("✅ All NFRs addressed")

        if blocked:
            lines.append(
                "\n⚠️  THIS IS AN ARCHITECTURAL COMMITMENT. "
                "Fix the blocking issues above, then click [✅ Approve]."
            )
        else:
            lines.append("\n⚠️  THIS IS AN ARCHITECTURAL COMMITMENT. Review carefully.")

        if ap.medium_count > 0:  # type: ignore[attr-defined]
            lines.append(f"\nAdvisory ({ap.medium_count} MEDIUM findings):")  # type: ignore[attr-defined]
            for f in ap.findings:  # type: ignore[attr-defined]
                if not f.blocking:
                    lines.append(f"  • {f.description}")

        return "\n".join(lines)

    def _has_api_service(self, service_graph: dict[str, object]) -> bool:
        """Return True if any service exposes REST/HTTP endpoints."""
        api_keywords = {"GET", "POST", "PUT", "DELETE", "/API", "REST", "HTTP"}
        for svc in list(service_graph.get("services") or []):
            exposed = " ".join(str(e) for e in (svc.get("exposes") or [])).upper()
            if any(kw in exposed for kw in api_keywords):
                return True
        return False

    def _generate_openapi_stub(self, state: dict[str, object]) -> str:
        """Generate a minimal OpenAPI 3.1 stub."""
        project = str(state.get("user_prompt", "API"))[:50]
        return f"""\
openapi: "3.1.0"
info:
  title: "{project}"
  version: "0.1.0"
  description: "Generated by forgeSDLC Agent 3"
paths: {{}}
components:
  schemas: {{}}
  securitySchemes: {{}}
"""