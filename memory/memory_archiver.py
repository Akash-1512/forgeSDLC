from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog

from interpret.record import InterpretRecord
from memory.organizational_memory import OrgMemory
from memory.pipeline_history_store import PipelineHistoryStore
from memory.post_mortem_records import PostMortemStore
from memory.project_context_graph import ProjectContextGraphStore
from memory.schemas import OrgMemoryEntry, PipelineRunRecord, PostMortem
from memory.user_preference_profile import UserPreferenceStore
from orchestrator.state import SDLCState

logger = structlog.get_logger()


class MemoryArchiver:
    """Runs after every completed SDLC pipeline.

    Writes to all 5 memory layers in sequence.
    Emits InterpretRecord(layer="memory") before writing to each layer.

    Layer 2 fact extraction is rule-based in this session — no LLM calls.
    _archive_layer2 now uses groq/llama-3.1-8b-instant via ModelRouter.
    using groq/llama-3.1-8b-instant for fact summarisation.
    """

    def __init__(
        self,
        layer1: PipelineHistoryStore,
        layer2: OrgMemory,
        layer3: ProjectContextGraphStore,
        layer4: UserPreferenceStore,
        layer5: PostMortemStore,
    ) -> None:
        self.l1 = layer1
        self.l2 = layer2
        self.l3 = layer3
        self.l4 = layer4
        self.l5 = layer5

    async def archive(self, state: SDLCState) -> None:
        """Archive learnings from a completed pipeline run to all 5 layers.

        Individual layer failures (e.g. database unavailable) are caught and
        logged — archival is best-effort and must never block the pipeline.
        """
        self._emit_archiver_record(state)

        for layer_fn, label in [
            (self._archive_layer1, "layer1"),
            (self._archive_layer2, "layer2"),
            (self._archive_layer3, "layer3"),
            (self._archive_layer4, "layer4"),
        ]:
            try:
                await layer_fn(state)
            except OSError as exc:
                logger.warning(
                    f"memory_archiver.{label}_skipped",
                    reason="database unavailable",
                    error=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 — archival is best-effort, must not block pipeline
                logger.warning("memory_archiver.layer_failed", layer=label, error=str(exc))

        if state.get("failure_type"):
            try:
                await self._archive_layer5(state)
            except OSError as exc:
                logger.warning(
                    "memory_archiver.layer5_skipped", reason="database unavailable", error=str(exc)
                )
        else:
            logger.info("memory_archiver.layer5_skipped", reason="no failure_type in state")

    # ------------------------------------------------------------------ L1

    async def _archive_layer1(self, state: SDLCState) -> None:
        # Extract a short stack label from the ADR header line
        # ADR typically starts with "# ADR-NNN: FastAPI + PostgreSQL + Redis"
        # Extract just the stack part after the colon for the stack_chosen field
        adr_text = str(state.get("adr") or "")
        stack_chosen: str | None = None
        if adr_text:
            first_line = adr_text.strip().splitlines()[0] if adr_text.strip() else ""
            if ":" in first_line:
                # "# ADR-NNN: FastAPI + PostgreSQL" → "FastAPI + PostgreSQL"
                stack_chosen = first_line.split(":", 1)[1].strip()[:100]
            elif first_line:
                stack_chosen = first_line.lstrip("#").strip()[:100]

        # Use trace_id as run_id so Layer 5 post-mortems can link back to this pipeline run
        run_id = str(state.get("trace_id") or uuid4())

        record = PipelineRunRecord(
            run_id=run_id,
            timestamp=datetime.now(tz=UTC),
            project_id=state.get("mcp_session_id") or "default",
            user_prompt=state.get("user_prompt") or "",
            stack_chosen=stack_chosen,
            deployment_success=state.get("deployment_url") is not None,
            cost_total_usd=state.get("budget_used_usd") or 0.0,
            hitl_rounds=state.get("interpret_round") or 0,
            human_corrections=state.get("human_corrections") or [],
            lessons_learned=[],
            tool_delegated_to=state.get("tool_delegated_to"),
            workspace_path=str((state.get("workspace_context") or {}).get("root_path", ".")),
        )
        await self.l1.save_run(record)  # l1 emits InterpretRecord before write
        logger.info(
            "memory_archiver.layer1_archived",
            run_id=record.run_id,
            stack_chosen=stack_chosen,
        )

    # ------------------------------------------------------------------ L2

    async def _archive_layer2(self, state: SDLCState) -> None:
        """LLM-based fact extraction via groq/llama-3.1-8b-instant.

        TODO resolved — now uses ModelRouter.route(context_compressor)
        which maps to groq/llama-3.1-8b-instant (always free, no exceptions).
        Produces higher-quality, categorised facts vs the previous rule-based approach.
        """
        project_id = state.get("mcp_session_id") or "default"
        run_id = str(uuid4())

        try:
            import json  # noqa: PLC0415

            from langchain_core.messages import HumanMessage  # noqa: PLC0415

            from model_router.router import ModelRouter  # noqa: PLC0415

            router = ModelRouter()
            adapter = await router.route(
                agent="context_compressor",  # → groq/llama-3.1-8b-instant always free
                task_type="extraction",
                estimated_tokens=500,
                subscription_tier=str(state.get("subscription_tier") or "free"),
                budget_used=float(state.get("budget_used_usd") or 0.0),
                budget_total=float(state.get("budget_remaining_usd") or 0.0),
            )

            prompt = (
                "Extract 3-5 learnable facts from this SDLC pipeline run. "
                "Each fact should be 1-2 sentences. "
                "Categories must be one of: architecture, security, pattern, failure, preference.\n\n"  # noqa: E501
                f"PRD: {str(state.get('prd', ''))[:300]}\n"
                f"ADR: {str(state.get('adr', ''))[:300]}\n"
                f"Security findings: {state.get('security_findings', {})}\n"
                f"Human corrections: {state.get('human_corrections', [])}\n\n"
                "Output ONLY valid JSON array, no markdown:\n"
                '[{"content": "...", "category": "architecture"}]'
            )

            response = await adapter.ainvoke([HumanMessage(content=prompt)])
            raw = str(response.content).strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            facts_data: list[dict[str, str]] = json.loads(raw)
            valid_categories = {
                "architecture",
                "security",
                "pattern",
                "failure",
                "preference",
            }

            for item in facts_data[:5]:
                content = str(item.get("content", "")).strip()
                category = str(item.get("category", "pattern")).strip()
                if not content:
                    continue
                if category not in valid_categories:
                    category = "pattern"
                entry = OrgMemoryEntry(
                    entry_id=str(uuid4()),
                    project_id=project_id,
                    content=content,
                    category=category,  # type: ignore[arg-type]
                    source_run_id=run_id,
                    timestamp=datetime.now(tz=UTC),
                )
                await self.l2.upsert(entry)

            logger.info(
                "memory_archiver.layer2_archived_llm",
                project_id=project_id,
                facts_extracted=len(facts_data),
            )

        except Exception as exc:
            # Fallback to rule-based extraction if LLM fails
            logger.warning(
                "memory_archiver.layer2_llm_failed_fallback",
                error=str(exc),
                project_id=project_id,
            )
            facts: list[str] = []
            if state.get("prd"):
                facts.append(f"REQUIREMENTS: {str(state['prd'])[:200]}")
            if state.get("adr"):
                facts.append(f"DECISION: {str(state['adr'])[:200]}")
            security = state.get("security_findings") or {}
            if isinstance(security, dict) and security.get("high_count", 0) > 0:
                facts.append(f"SECURITY: {security['high_count']} HIGH findings in this run")
            for correction in state.get("human_corrections") or []:
                if correction:
                    facts.append(f"CORRECTION: {str(correction)[:150]}")
            for fact in facts[:5]:
                entry = OrgMemoryEntry(
                    entry_id=str(uuid4()),
                    project_id=project_id,
                    content=fact,
                    category=self._classify_fact(fact),  # type: ignore[arg-type]
                    source_run_id=run_id,
                    timestamp=datetime.now(tz=UTC),
                )
                await self.l2.upsert(entry)

        # duplicated after try/except, reassigning facts=[] and iterating empty list.
        # LLM path (try block) and fallback rule-based path (except block) are sufficient.

    # ------------------------------------------------------------------ L3

    async def _archive_layer3(self, state: SDLCState) -> None:
        """Update project graph if workspace context contains graph data.

        workspace_context is stored as a plain dict via model_dump().
        project_graph field added to WorkspaceContext in v1.1.0 (H11 fix).
        Reconstruct ProjectContextGraph object before passing to l3.save_graph().
        """
        graph_data = (state.get("workspace_context") or {}).get("project_graph")
        if graph_data is None:
            logger.info(
                "memory_archiver.layer3_skipped",
                reason="no project_graph in workspace_context",
            )
            return

        # Reconstruct the Pydantic model from the stored dict
        try:
            from memory.schemas import ProjectContextGraph  # noqa: PLC0415

            if isinstance(graph_data, dict):
                graph_obj = ProjectContextGraph.model_validate(graph_data)
            elif isinstance(graph_data, ProjectContextGraph):
                graph_obj = graph_data
            else:
                logger.warning(
                    "memory_archiver.layer3_invalid_graph_type",
                    type=type(graph_data).__name__,
                )
                return
        except Exception as exc:
            logger.warning("memory_archiver.layer3_graph_parse_failed", error=str(exc))
            return

        # l3 emits InterpretRecord before write
        await self.l3.save_graph(graph_obj)
        logger.info("memory_archiver.layer3_archived", project_id=graph_obj.project_id)

    # ------------------------------------------------------------------ L4

    async def _archive_layer4(self, state: SDLCState) -> None:
        """Update tool preference from ToolRouter delegation signal."""
        tool = state.get("tool_delegated_to")
        if not tool:
            logger.info("memory_archiver.layer4_skipped", reason="no tool_delegated_to in state")
            return
        # Use session ID as user key so preferences are per-session, not global
        user_id = str(state.get("mcp_session_id") or "default")
        # l4 emits InterpretRecord before write inside update_tool_preference
        await self.l4.update_tool_preference(user_id, tool)
        logger.info("memory_archiver.layer4_archived", tool=tool)

    # ------------------------------------------------------------------ L5

    async def _archive_layer5(self, state: SDLCState) -> None:
        """Write post-mortem when pipeline failed."""
        # run_id = trace_id links this post-mortem to the Layer 1 pipeline_run row
        run_id = str(state.get("trace_id") or uuid4())
        pm = PostMortem(
            post_mortem_id=str(uuid4()),
            run_id=run_id,
            failure_type=state.get("failure_type", "architecture"),  # type: ignore[arg-type]
            agent_that_failed=state.get("failed_agent") or "unknown",
            root_cause=state.get("failure_root_cause") or "unknown",
            resolution=state.get("failure_resolution") or "none",
            prevention_rule=state.get("failure_prevention") or "none",
            stack_context=state.get("adr") or "",
            tool_involved=state.get("tool_delegated_to"),
            timestamp=datetime.now(tz=UTC),
        )
        await self.l5.save_post_mortem(pm)  # l5 emits InterpretRecord before write
        logger.info(
            "memory_archiver.layer5_archived",
            failure_type=pm.failure_type,
            tool_involved=pm.tool_involved,
        )

    # ------------------------------------------------------------------ helpers

    def _classify_fact(self, fact: str) -> str:
        if fact.startswith("DECISION"):
            return "architecture"
        if fact.startswith("SECURITY"):
            return "security"
        if fact.startswith("CORRECTION"):
            return "pattern"
        if fact.startswith("REQUIREMENTS"):
            return "pattern"
        return "pattern"

    def _emit_archiver_record(self, state: SDLCState) -> InterpretRecord:
        record = InterpretRecord(
            layer="memory",
            component="MemoryArchiver",
            action="archive: writing all 5 memory layers after pipeline completion",
            inputs={"project_id": state.get("mcp_session_id") or "default"},
            expected_outputs={"layers_written": "list[str]"},
            files_it_will_read=[],
            files_it_will_write=[],
            external_calls=["postgresql", "chromadb_local", "filesystem"],
            model_selected=None,
            tool_delegated_to=None,
            reversible=False,
            workspace_files_affected=[],
            timestamp=datetime.now(tz=UTC),
        )
        logger.info(
            "interpret_record.memory",
            action=record.action,
            layer=record.layer,
        )
        return record
