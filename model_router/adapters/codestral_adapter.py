from __future__ import annotations

import os
from collections.abc import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()

# CRITICAL: Codestral FIM uses a DIFFERENT endpoint and key from Mistral chat.
# FIM endpoint:  codestral.mistral.ai  with MISTRAL_CODESTRAL_KEY
# Chat endpoint: api.mistral.ai        with MISTRAL_API_KEY
# Swapping these causes auth errors that look like network errors.
_CODESTRAL_BASE_URL = "https://codestral.mistral.ai/v1"


class CodestralAdapter:
    """Mistral Codestral — FIM specialist at codestral.mistral.ai.

    Uses MISTRAL_CODESTRAL_KEY (NOT MISTRAL_API_KEY — different key, different URL).
    FIM is the primary use case — companion panel InlineMode only.
    """

    def __init__(self, model: str = "codestral-latest") -> None:
        self._model = model
        self._api_key = os.getenv("MISTRAL_CODESTRAL_KEY", "")

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
            "model": self._model,
            "messages": [
                {"role": self._map_role(m.type), "content": str(m.content)} for m in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{_CODESTRAL_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"] or ""
            logger.info("codestral_adapter.ainvoke", model=self._model, chars=len(content))
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
        """PSM FIM — Codestral's primary capability."""
        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{_CODESTRAL_BASE_URL}/fim/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "prompt": prefix,
                    "suffix": suffix,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return 256_000

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return 0.0003

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return 0.0009

    def _map_role(self, role: str) -> str:
        return {"human": "user", "ai": "assistant", "system": "system"}.get(role, "user")
