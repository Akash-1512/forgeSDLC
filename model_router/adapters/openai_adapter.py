from __future__ import annotations

import os
from collections.abc import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()

_MODEL_METADATA: dict[str, dict[str, object]] = {
    "gpt-5.4": {
        "context_window": 128_000,
        "cost_per_1k_input": 0.005,
        "cost_per_1k_output": 0.015,
    },
    "gpt-5.4-mini": {
        "context_window": 128_000,
        "cost_per_1k_input": 0.00015,
        "cost_per_1k_output": 0.0006,
    },
}


class OpenAIAdapter:
    """OpenAI Chat Completions API — gpt-5.4, gpt-5.4-mini.

    Uses client.chat.completions.create — NOT the Responses API.
    For o3-mini and gpt-5.4-pro use OpenAIReasoningAdapter instead.
    """

    def __init__(self, model: str = "gpt-5.4-mini") -> None:
        self._model = model
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        meta = _MODEL_METADATA.get(model, _MODEL_METADATA["gpt-5.4-mini"])
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
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": self._map_role(m.type), "content": str(m.content)} for m in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop

        response = await client.chat.completions.create(**payload)  # type: ignore[arg-type]
        content = response.choices[0].message.content or ""
        logger.info("openai_adapter.ainvoke", model=self._model, chars=len(content))
        return AIMessage(content=content)

    async def astream(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AsyncIterator[AIMessageChunk]:
        response = await self.ainvoke(messages, max_tokens=max_tokens, temperature=temperature)

        async def _gen() -> AsyncIterator[AIMessageChunk]:
            yield AIMessageChunk(content=str(response.content))

        return _gen()

    async def afim(self, prefix: str, suffix: str, *, max_tokens: int = 512) -> str:
        raise NotImplementedError(
            "OpenAI Chat Completions does not support FIM. Use CodestralAdapter."
        )

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
