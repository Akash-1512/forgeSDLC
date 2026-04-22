from __future__ import annotations

import os
from collections.abc import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()

# CRITICAL: o3-mini and gpt-5.4-pro use the Responses API, NOT Chat Completions.
# - Endpoint method: client.responses.create (NOT client.chat.completions.create)
# - Token param: max_output_tokens (NOT max_tokens)
# - Input param: input=[...] (NOT messages=[...])
# Getting this wrong produces a cryptic OpenAI 400 error.

_MODEL_METADATA: dict[str, dict[str, object]] = {
    "o3-mini": {
        "context_window": 200_000,
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.012,
    },
    "gpt-5.4-pro": {
        "context_window": 128_000,
        "cost_per_1k_input": 0.01,
        "cost_per_1k_output": 0.03,
    },
}


class OpenAIReasoningAdapter:
    """OpenAI Responses API — o3-mini (Security STRIDE) and gpt-5.4-pro.

    Uses client.responses.create — NOT client.chat.completions.create.
    Different endpoint, different parameter names.
    Agent 5b (Security) uses o3-mini via this adapter.
    """

    def __init__(self, model: str = "o3-mini") -> None:
        self._model = model
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        meta = _MODEL_METADATA.get(model, _MODEL_METADATA["o3-mini"])
        self._context_window = int(meta["context_window"])
        self._cost_input = float(meta["cost_per_1k_input"])
        self._cost_output = float(meta["cost_per_1k_output"])

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: list[str] | None = None,
    ) -> AIMessage:
        from openai import AsyncOpenAI  # noqa: PLC0415

        client = AsyncOpenAI(api_key=self._api_key)

        # Responses API: input=[...], max_output_tokens=N (NOT max_tokens)
        response = await client.responses.create(
            model=self._model,
            input=[{"role": self._map_role(m.type), "content": str(m.content)} for m in messages],
            max_output_tokens=max_tokens,  # NOT max_tokens — Responses API param
        )
        content = response.output_text or ""
        logger.info(
            "openai_reasoning_adapter.ainvoke",
            model=self._model,
            chars=len(content),
        )
        return AIMessage(content=content)

    async def astream(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AsyncIterator[AIMessageChunk]:
        response = await self.ainvoke(messages, max_tokens=max_tokens)

        async def _gen() -> AsyncIterator[AIMessageChunk]:
            yield AIMessageChunk(content=str(response.content))

        return _gen()

    async def afim(self, prefix: str, suffix: str, *, max_tokens: int = 512) -> str:
        raise NotImplementedError("Reasoning models do not support FIM. Use CodestralAdapter.")

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return self._context_window

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return self._cost_input

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return self._cost_output

    def _map_role(self, role: str) -> str:
        return {"human": "user", "ai": "assistant", "system": "system"}.get(role, "user")
