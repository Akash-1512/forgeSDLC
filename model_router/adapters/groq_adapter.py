from __future__ import annotations

import os
from typing import AsyncIterator

import httpx
import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from orchestrator.constants import EXPONENTIAL_BACKOFF_BASE, EXPONENTIAL_BACKOFF_MAX_SECONDS

logger = structlog.get_logger()


def _is_rate_limit(exc: BaseException) -> bool:
    """Return True for 429 rate limit and 503 service unavailable responses."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 503)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_MODEL_METADATA: dict[str, dict[str, object]] = {
    "groq/llama-3.3-70b-versatile": {
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

    def __init__(self, model: str = "groq/llama-3.3-70b-versatile") -> None:
        self._model = model
        self._api_key = os.getenv("GROQ_API_KEY", "")
        meta = _MODEL_METADATA.get(model, _MODEL_METADATA["groq/llama-3.3-70b-versatile"])
        self._context_window = int(meta["context_window"])
        self._cost_input = float(meta["cost_per_1k_input"])
        self._cost_output = float(meta["cost_per_1k_output"])

    @retry(
        retry=retry_if_exception(_is_rate_limit),
        wait=wait_exponential(multiplier=EXPONENTIAL_BACKOFF_BASE, max=EXPONENTIAL_BACKOFF_MAX_SECONDS),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def ainvoke(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: list[str] | None = None,
    ) -> AIMessage:


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
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            cost = (input_tokens * self._cost_input + output_tokens * self._cost_output) / 1000
            logger.info(
                "groq_adapter.ainvoke",
                model=self._model,
                chars=len(content),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=round(cost, 6),
            )
            return AIMessage(content=content)

    async def astream(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AsyncIterator[AIMessageChunk]:
        """Real token-by-token streaming via Groq SSE endpoint."""
        payload = {
            "model": self._model.replace("groq/", ""),
            "messages": [
                {"role": self._map_role(m.type), "content": str(m.content)}
                for m in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async def _stream_gen() -> AsyncIterator[AIMessageChunk]:
            import json as _json  # noqa: PLC0415
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = _json.loads(data_str)
                            delta = chunk["choices"][0]["delta"]
                            token = delta.get("content", "")
                            if token:
                                yield AIMessageChunk(content=token)
                        except (KeyError, _json.JSONDecodeError):
                            continue

        return _stream_gen()

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