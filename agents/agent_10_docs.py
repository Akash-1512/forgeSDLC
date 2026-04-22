from __future__ import annotations

from datetime import UTC, datetime

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord
from subscription.byok_manager import BYOKManager

logger = structlog.get_logger()

_README_SECTIONS = [
    "Quick Start",
    "Installation",
    "Usage",
    "Architecture",
    "API Reference",
    "Known Limitations",
    "Development",
    "Contributing",
    "License",
]

_ATTRIBUTION = "\n\n---\nBuilt with forgeSDLC — https://github.com/Akash-1512/forgesdlc"


class DocsAgent(BaseAgent):
    """Agent 10 — final single-service agent. Generates documentation and completes pipeline.

    Model: claude-sonnet-4-6 (BYOK) | gpt-5.4-mini (default) → groq
    Generates: README.md + CHANGELOG.md
    Saves ProjectContextGraph to Layer 3 (emits L6 InterpretRecord)
    Final ContextFileManager update with complete project state
    Comprehensive MemoryArchiver write across all 5 layers
    Attribution "Built with forgeSDLC" always present — unconditional append.
    """

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Preview docs generation. Emits L1 InterpretRecord."""
        byok = BYOKManager()
        model = "claude-sonnet-4-6" if byok.has_key("anthropic") else "gpt-5.4-mini"

        return self._emit_l1_record(
            component="DocsAgent",
            action=(
                f"DOCUMENTATION GENERATION\n"
                f"Model: {model} {'(BYOK)' if 'claude' in model else ''}\n"
                f"Files: README.md + CHANGELOG.md\n"
                f"Known Limitations: from state (MEDIUM security + HITL rounds)\n"
                f"ProjectContextGraph: build + save to Layer 3 memory\n"
                f"Final memory archive: all 5 layers\n"
                f"Attribution: Built with forgeSDLC — always present"
            ),
            inputs={
                "model": model,
                "prd_length": len(str(state.get("prd", ""))),
            },
            expected_outputs={
                "readme": "README.md",
                "graph": "ProjectContextGraph",
            },
            external_calls=[model],
            model_selected=model,
            files_write=["README.md", "CHANGELOG.md"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Generate README, CHANGELOG, graph, and do final archive."""
        byok = BYOKManager()

        # Select agent key based on BYOK availability
        agent_key = "agent_10_docs_byok" if byok.has_key("anthropic") else "agent_10_docs"

        adapter = await self.model_router.route(
            agent=agent_key,
            task_type="documentation",
            estimated_tokens=int(len(str(state.get("prd", "")).split()) * 3),
            subscription_tier=str(state.get("subscription_tier", "free")),
            budget_used=float(state.get("budget_used_usd", 0.0) or 0.0),
            budget_total=float(state.get("budget_remaining_usd", 999.0) or 999.0),
        )

        # Step 1: Generate README
        known_limitations = self._build_known_limitations(state)
        readme_response = await adapter.ainvoke(  # type: ignore[union-attr]
            [
                SystemMessage(
                    content=(
                        "Generate a comprehensive README.md for this project. "
                        "Include sections in order: project name + 2-line description, "
                        "Quick Start, Installation, Usage, Architecture, API Reference, "
                        "Known Limitations, Development, Contributing, License. "
                        "Use clear Markdown. Do not add any attribution footer."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Project PRD:\n{str(state.get('prd', ''))[:2000]}\n\n"
                        f"Tech stack (ADR):\n{str(state.get('adr', ''))[:500]}\n\n"
                        f"Known Limitations:\n{known_limitations}\n\n"
                        f"Deployment URL: {state.get('deployment_url', 'not deployed')}"
                    )
                ),
            ]
        )

        readme_content = str(readme_response.content) if readme_response.content else ""

        # Attribution: always appended unconditionally — model output is irrelevant
        if "Built with forgeSDLC" not in readme_content:
            readme_content += _ATTRIBUTION

        # Write README via DiffEngine (L3 InterpretRecord, .forgesdlc.bak)
        workspace_path = "."
        try:
            wctx = await self.workspace.get_context()
            workspace_path = wctx.root_path
        except Exception:
            pass

        import os  # noqa: PLC0415

        readme_path = os.path.join(workspace_path, "README.md")
        diff = await self.diff_engine.generate_diff(
            readme_path, readme_content, "Agent 10: project README"
        )
        await self.diff_engine.apply_diff(diff)

        # Step 2: Generate CHANGELOG
        arch_type = str((state.get("service_graph") or {}).get("architecture_type", "Service"))
        changelog = (
            f"# Changelog\n\n"
            f"## [0.1.0] — {datetime.now(tz=UTC).strftime('%Y-%m-%d')}\n\n"
            f"### Added\n"
            f"- Initial release generated by forgeSDLC\n"
            f"- {arch_type} architecture\n"
            f"- Deployment to {state.get('deployment_url', 'local')}\n"
        )
        changelog_path = os.path.join(workspace_path, "CHANGELOG.md")
        changelog_diff = await self.diff_engine.generate_diff(
            changelog_path, changelog, "Agent 10: initial changelog"
        )
        await self.diff_engine.apply_diff(changelog_diff)

        # Step 3: Build and save ProjectContextGraph to Layer 3 (emits L6)
        await self._save_project_context_graph(state, workspace_path)

        # Step 4: Final ContextFileManager update with complete project state
        await self.cfm.write_all(
            project_id=str(state.get("mcp_session_id", "default")),
            workspace_path=workspace_path,
            current_phase="complete",
            prd_summary=str(state.get("prd", ""))[:500],
            architecture_summary=str(state.get("rfc", ""))[:300],
        )

        # Step 5: Comprehensive MemoryArchiver write — all 5 layers
        await self.memory_archiver.archive(state)  # type: ignore[arg-type]

        logger.info(
            "agent_10.executed",
            readme_path=readme_path,
            changelog_path=changelog_path,
            attribution_present="Built with forgeSDLC" in readme_content,
        )
        return state

    def _build_known_limitations(self, state: dict[str, object]) -> str:
        """Generate Known Limitations section from state. Never hardcoded."""
        limitations: list[str] = []

        # Source 1: MEDIUM security findings (advisory, non-blocking)
        security = dict(state.get("security_findings") or {})
        all_findings = (
            list(security.get("bandit_findings", []) or [])
            + list(security.get("semgrep_findings", []) or [])
            + list(security.get("pip_audit_findings", []) or [])
        )
        medium_findings = [
            f for f in all_findings if isinstance(f, dict) and f.get("severity") == "MEDIUM"
        ]
        for finding in medium_findings[:3]:
            desc = str(finding.get("description", "See security report"))
            limitations.append(f"- Known security advisory: {desc}")

        # Source 2: HITL correction rounds > 2 (areas AI struggled with)
        interpret_rounds = int(state.get("interpret_round", 0) or 0)
        if interpret_rounds > 2:
            limitations.append(
                f"- Architecture complexity: this project required {interpret_rounds} "
                f"interpretation rounds — some edge cases may need manual review."
            )

        if not limitations:
            limitations.append("- No known limitations identified during generation.")

        return "\n".join(limitations)

    async def _save_project_context_graph(
        self, state: dict[str, object], workspace_path: str
    ) -> None:
        """Build ProjectContextGraph and save to Layer 3. Emits L6 InterpretRecord."""
        from memory.project_context_graph import (
            ProjectContextGraphStore,  # noqa: PLC0415
        )
        from memory.schemas import ProjectContextGraph, ServiceNode  # noqa: PLC0415

        service_graph = dict(state.get("service_graph") or {})
        raw_services = list(service_graph.get("services", []) or [])

        services: list[ServiceNode] = []
        for svc in raw_services:
            if isinstance(svc, dict):
                services.append(
                    ServiceNode(
                        name=str(svc.get("name", "main")),
                        responsibility=str(svc.get("responsibility", "")),
                        exposes=list(svc.get("exposes", []) or []),
                        depends_on=list(svc.get("depends_on", []) or []),
                        owns_data=bool(svc.get("owns_data", True)),
                        database=svc.get("database"),
                    )
                )

        if not services:
            services = [
                ServiceNode(
                    name="main",
                    responsibility="Primary application service",
                    exposes=[],
                    depends_on=[],
                    owns_data=True,
                    database=None,
                )
            ]

        monitoring = dict(state.get("monitoring_config") or {})
        slo_defs = list(monitoring.get("slo_definitions", []) or [])

        graph = ProjectContextGraph(
            project_id=str(state.get("mcp_session_id", "default")),
            repo_url=None,
            services=services,
            api_contracts=(
                ["docs/architecture/openapi.yaml"] if state.get("deployment_url") else []
            ),
            architectural_decisions=[str(state.get("adr", ""))[:200]],
            dependencies=[],
            env_var_names=[],
            deployment_config={
                "url": state.get("deployment_url"),
                "target": "render" if state.get("deployment_url") else "local",
            },
            slo_definitions=[str(s) for s in slo_defs],
            workspace_path=workspace_path,
            last_updated=datetime.now(tz=UTC),
        )

        store = ProjectContextGraphStore()
        await store.save_graph(graph)  # emits L6 InterpretRecord (layer="memory")
        state["project_context_graph"] = graph.model_dump()
        logger.info(
            "agent_10.graph_saved",
            project_id=graph.project_id,
            services=len(services),
        )

    def _extract_key_decisions(self, state: dict[str, object]) -> list[str]:
        adr = str(state.get("adr", ""))
        decisions: list[str] = []
        for line in adr.splitlines():
            stripped = line.strip("# ").strip()
            if stripped and ("##" in line or "decision" in line.lower()):
                decisions.append(stripped)
        return decisions[:5]

    def _extract_security_rules(self, state: dict[str, object]) -> list[str]:
        security = dict(state.get("security_findings") or {})
        high_findings = [
            f
            for findings in [
                list(security.get("bandit_findings", []) or []),
                list(security.get("semgrep_findings", []) or []),
            ]
            for f in findings
            if isinstance(f, dict) and f.get("severity") == "HIGH"
        ]
        return [str(f.get("description", ""))[:100] for f in high_findings[:3]]
