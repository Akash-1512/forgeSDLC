from __future__ import annotations

import os
from typing import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

_MODEL_METADATA: dict[str, dict[str, object]] = {
    "gemini-3.1-pro-preview": {
        "context_window": 1_000_000,
        "cost_per_1k_input": 0.00125,
        "cost_per_1k_output": 0.005,
    },
    "gemini-3-flash-preview": {
        "context_window": 1_000_000,
        "cost_per_1k_input": 0.000075,
        "cost_per_1k_output": 0.0003,
    },
}


class GeminiAdapter:
    """Google Gemini — 1M context window for long-context routing.

    gemini-3.1-pro-preview: Agent 11 (Integration) + long-context fallback.
    gemini-3-flash-preview: Free tier Gemini option.
    gemini-3-pro-preview was SHUT DOWN March 9 2026 — do not use.
    """

    def __init__(self, model: str = "gemini-3.1-pro-preview") -> None:
        self._model = model
        self._api_key = os.getenv("GOOGLE_API_KEY", "")
        meta = _MODEL_METADATA.get(model, _MODEL_METADATA["gemini-3.1-pro-preview"])
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

        contents = [
            {"role": self._map_role(m.type), "parts": [{"text": str(m.content)}]}
            for m in messages
            if m.type != "system"
        ]
        system_text = " ".join(
            str(m.content) for m in messages if m.type == "system"
        )
        payload: dict[str, object] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{_GEMINI_BASE_URL}/models/{self._model}:generateContent"
                f"?key={self._api_key}",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            logger.info("gemini_adapter.ainvoke", model=self._model, chars=len(content))
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
        raise NotImplementedError("Gemini does not support FIM. Use CodestralAdapter.")

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
        return {"human": "user", "ai": "model", "system": "user"}.get(role, "user")