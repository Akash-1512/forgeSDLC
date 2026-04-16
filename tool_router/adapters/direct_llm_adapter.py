from __future__ import annotations

import os

import structlog

from tool_router.context import AvailableTool, ToolResult

logger = structlog.get_logger()


class DirectLLMAdapter:
    """Always-available fallback — zero external tool dependency.

    Uses OpenAI API directly via OPENAI_API_KEY env var (BYOK — user's own key).
    Falls back to Groq if OPENAI_API_KEY is not set.

    TODO Session 06: replace direct openai import with ModelRouter.route()
    using the full provider fallback chain (Azure OpenAI → OpenAI → Groq → Ollama).
    """

    async def generate(
        self, task: str, context: str, workspace_path: str
    ) -> ToolResult:
        openai_key = os.getenv("OPENAI_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")

        if openai_key:
            return await self._generate_openai(task, context, openai_key)
        if groq_key:
            return await self._generate_groq(task, context, groq_key)

        # No API key available — return descriptive stub so route() never raises
        logger.warning(
            "direct_llm_adapter.no_api_key",
            hint="Set OPENAI_API_KEY or GROQ_API_KEY to enable DirectLLMAdapter",
        )
        return ToolResult(
            tool=AvailableTool.DIRECT_LLM,
            output=(
                "# DirectLLMAdapter: no API key configured.\n"
                "# Set OPENAI_API_KEY or GROQ_API_KEY to enable code generation.\n"
                f"# Task: {task[:200]}"
            ),
            files_written=[],
            success=False,
            stderr="No OPENAI_API_KEY or GROQ_API_KEY found in environment.",
        )

    async def _generate_openai(
        self, task: str, context: str, api_key: str
    ) -> ToolResult:
        # TODO Session 06: replace with ModelRouter.route()
        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(api_key=api_key)
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # TODO Session 06: via ModelRouter with gpt-5.4-mini
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a code generation assistant. "
                            f"Project context:\n{context}"
                        ),
                    },
                    {"role": "user", "content": task},
                ],
                max_tokens=4096,
            )
            code = response.choices[0].message.content or ""
            logger.info("direct_llm_adapter.openai_success", chars=len(code))
            return ToolResult(
                tool=AvailableTool.DIRECT_LLM,
                output=code,
                files_written=[],
                success=True,
                stderr=None,
            )
        except Exception as exc:
            logger.error("direct_llm_adapter.openai_error", error=str(exc))
            return ToolResult(
                tool=AvailableTool.DIRECT_LLM,
                output="",
                files_written=[],
                success=False,
                stderr=str(exc),
            )

    async def _generate_groq(
        self, task: str, context: str, api_key: str
    ) -> ToolResult:
        # TODO Session 06: replace with ModelRouter.route()
        import httpx  # noqa: PLC0415

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a code generation assistant.\nContext:\n{context}",
                },
                {"role": "user", "content": task},
            ],
            "max_tokens": 4096,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                code = data["choices"][0]["message"]["content"] or ""
                logger.info("direct_llm_adapter.groq_success", chars=len(code))
                return ToolResult(
                    tool=AvailableTool.DIRECT_LLM,
                    output=code,
                    files_written=[],
                    success=True,
                    stderr=None,
                )
        except Exception as exc:
            logger.error("direct_llm_adapter.groq_error", error=str(exc))
            return ToolResult(
                tool=AvailableTool.DIRECT_LLM,
                output="",
                files_written=[],
                success=False,
                stderr=str(exc),
            )