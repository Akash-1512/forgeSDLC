from __future__ import annotations

import os

import structlog

from tool_router.context import AvailableTool, ToolResult

logger = structlog.get_logger()


class DirectLLMAdapter:
    """Always-available fallback — zero external tool dependency.

    Session 06: replaced direct openai/groq imports with ModelRouter.route().
    Now respects subscription tier, budget constraints, and BYOK configuration.
    All calls appear in TokenRecords via ModelRouter's tracking.
    """

    async def generate(self, task: str, context: str, workspace_path: str) -> ToolResult:
        try:
            from langchain_core.messages import (  # noqa: PLC0415
                HumanMessage,
                SystemMessage,
            )

            from model_router.router import ModelRouter  # noqa: PLC0415

            router = ModelRouter()
            adapter = await router.route(
                agent="context_compressor",  # groq/llama-3.1-8b-instant — always free
                task_type="code_gen",
                estimated_tokens=int(len(task.split()) * 1.33) + 200,
                subscription_tier=os.getenv("FORGESDLC_TIER", "free"),
                budget_used=0.0,
                budget_total=999.0,  # no budget constraint for fallback path
            )
            response = await adapter.ainvoke(
                [
                    SystemMessage(
                        content=f"You are a code generation assistant.\nProject context:\n{context}"
                    ),
                    HumanMessage(content=task),
                ]
            )
            output = str(response.content) if response.content else ""
            logger.info("direct_llm_adapter.model_router_success", chars=len(output))
            return ToolResult(
                tool=AvailableTool.DIRECT_LLM,
                output=output,
                files_written=[],
                success=True,
                stderr=None,
            )
        except Exception as exc:
            logger.error("direct_llm_adapter.model_router_error", error=str(exc))
            return ToolResult(
                tool=AvailableTool.DIRECT_LLM,
                output="",
                files_written=[],
                success=False,
                stderr=str(exc),
            )
