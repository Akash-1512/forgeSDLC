from __future__ import annotations

import os
from typing import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_MODEL_METADATA: dict[str, dict[str, object]] = {
    "groq/llama-3.3-70b-specdec": {
        "context_window": 128_000,
        "cost_per_1k_input": 0.00059,
        "cost_per_1k_output": 0.00079,
    },
    "groq/llama-3.1-8b-instant": {
        "context_window": 131_072,
        "cost_per_1k_input": 0.00005,
        "cost_per_1k_output": 0.00008,
    },
}


class GroqAdapter:
    """Groq LPU inference — free orchestration backbone.

    Free tier: 30 req/min. Paid Developer tier required for commercial use.
    Always available as final fallback in ModelRouter.
    """

    def __init__(self, model: str = "groq/llama-3.3-70b-specdec") -> None:
        self._model = model
        self._api_key = os.getenv("GROQ_API_KEY", "")
        meta = _MODEL_METADATA.get(model, _MODEL_METADATA["groq/llama-3.3-70b-specdec"])
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
        import httpx  # noqa: PLC0415

        payload: dict[str, object] = {
            "model": self._model.replace("groq/", ""),
            "messages": [
                {"role": self._map_role(m.type), "content": str(m.content)}
                for m in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{_GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"] or ""
            logger.info("groq_adapter.ainvoke", model=self._model, chars=len(content))
            return AIMessage(content=content)

    async def astream(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AsyncIterator[AIMessageChunk]:
        # Stub — full streaming wired in Session 17 (companion panel)
        response = await self.ainvoke(messages, max_tokens=max_tokens, temperature=temperature)
        async def _gen() -> AsyncIterator[AIMessageChunk]:
            yield AIMessageChunk(content=str(response.content))
        return _gen()

    async def afim(self, prefix: str, suffix: str, *, max_tokens: int = 512) -> str:
        raise NotImplementedError(
            "Groq does not support FIM. Use CodestralAdapter for FIM tasks."
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