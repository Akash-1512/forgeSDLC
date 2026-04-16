from __future__ import annotations

from typing import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()

_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaAdapter:
    """Local Ollama inference — devstral (Apache 2.0) and deepseek-coder-v2.

    Used as FIM fallback when MISTRAL_CODESTRAL_KEY is not set.
    devstral: Apache 2.0 — safe for commercial use, self-hosted.
    Requires Ollama running locally: https://ollama.ai
    """

    def __init__(self, model: str = "devstral") -> None:
        self._model = model

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
                {"role": self._map_role(m.type), "content": str(m.content)}
                for m in messages
            ],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if stop:
            payload["options"] = {**dict(payload["options"]), "stop": stop}  # type: ignore[arg-type]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{_OLLAMA_BASE_URL}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            logger.info("ollama_adapter.ainvoke", model=self._model, chars=len(content))
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
        """FIM via Ollama generate endpoint with PSM format."""
        import httpx  # noqa: PLC0415

        prompt = f"<PRE>{prefix}<SUF>{suffix}<MID>"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{_OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return 32_768  # devstral default

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return 0.0  # local — no API cost

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return 0.0

    def _map_role(self, role: str) -> str:
        return {"human": "user", "ai": "assistant", "system": "system"}.get(role, "user")