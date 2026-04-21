from __future__ import annotations

import os
from typing import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

logger = structlog.get_logger()


class AzureOpenAIAdapter:
    """Azure OpenAI — production path for enterprise deployments.

    Required env vars:
      AZURE_OPENAI_API_KEY
      AZURE_OPENAI_ENDPOINT   (e.g. https://<resource>.openai.azure.com/)
      AZURE_OPENAI_DEPLOYMENT (deployment name — often same as model)
      AZURE_OPENAI_API_VERSION (default: 2024-12-01-preview)
    """

    def __init__(self, deployment: str | None = None) -> None:
        self._endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self._api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self._deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
        self._api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: list[str] | None = None,
    ) -> AIMessage:
        from openai import AsyncAzureOpenAI  # noqa: PLC0415

        client = AsyncAzureOpenAI(
            api_key=self._api_key,
            azure_endpoint=self._endpoint,
            api_version=self._api_version,
        )
        payload: dict[str, object] = {
            "model": self._deployment,
            "messages": [
                {"role": self._map_role(m.type), "content": str(m.content)}
                for m in messages
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop

        response = await client.chat.completions.create(**payload)  # type: ignore[arg-type]
        content = response.choices[0].message.content or ""
        logger.info("azure_adapter.ainvoke", deployment=self._deployment, chars=len(content))
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
        raise NotImplementedError("Azure OpenAI does not support FIM. Use CodestralAdapter.")

    @property
    def model_name(self) -> str:
        return self._deployment

    @property
    def context_window(self) -> int:
        return 128_000

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return 0.005

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return 0.015

    def _map_role(self, role: str) -> str:
        return {"human": "user", "ai": "assistant", "system": "system"}.get(role, "user")