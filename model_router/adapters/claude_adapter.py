from __future__ import annotations

import os
from typing import AsyncIterator

import structlog
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from orchestrator.exceptions import ForgeSDLCError
from subscription.byok_manager import BYOKManager

logger = structlog.get_logger()

# Models retired as of April 2026 — raise immediately if selected
RETIRED_MODELS: frozenset[str] = frozenset({
    "claude-3-5-sonnet-20241022",
    "claude-3-5-sonnet-20240620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
})


class ClaudeNotConfiguredError(ForgeSDLCError):
    """Raised when Claude is requested but no Anthropic BYOK key is set."""


class ClaudeAdapter:
    """Anthropic Claude — BYOK only, never a built-in default.

    Raises ClaudeNotConfiguredError if no Anthropic key is stored in keychain.
    Raises ValueError if a retired model is requested.
    See legal/cursor_api_review.md for ToS context on BYOK adapters.
    """

    def __init__(
        self,
        byok_manager: BYOKManager,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self.assert_model_not_retired(model)
        key = byok_manager.get_key("anthropic")
        if not key:
            raise ClaudeNotConfiguredError(
                "Claude requires BYOK. Open Settings → API Keys and add "
                "your Anthropic API key. Read Anthropic's ToS before enabling. "
                "See subscription/anthropic_tos_warning.py for the required flow."
            )
        import anthropic  # noqa: PLC0415
        self._client = anthropic.AsyncAnthropic(api_key=key)
        self._model = model
        logger.info("claude_adapter.init", model=model)

    @classmethod
    def assert_model_not_retired(cls, model: str) -> None:
        """Raise ValueError immediately for retired Claude models."""
        if model in RETIRED_MODELS:
            raise ValueError(
                f"Model '{model}' is retired. Use claude-sonnet-4-6 instead. "
                f"Retired models: {sorted(RETIRED_MODELS)}"
            )

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: list[str] | None = None,
    ) -> AIMessage:
        system_content = ""
        user_messages: list[dict[str, str]] = []

        for m in messages:
            if m.type == "system":
                system_content = str(m.content)
            else:
                role = "user" if m.type == "human" else "assistant"
                user_messages.append({"role": role, "content": str(m.content)})

        kwargs: dict[str, object] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": user_messages,
        }
        if system_content:
            kwargs["system"] = system_content
        if stop:
            kwargs["stop_sequences"] = stop

        response = await self._client.messages.create(**kwargs)  # type: ignore[arg-type]
        content = response.content[0].text if response.content else ""
        logger.info("claude_adapter.ainvoke", model=self._model, chars=len(content))
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
            "Claude does not support FIM. Use CodestralAdapter for FIM tasks."
        )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return 200_000  # claude-sonnet-4-6

    @property
    def cost_per_1k_input_tokens(self) -> float:
        return 0.003  # claude-sonnet-4-6

    @property
    def cost_per_1k_output_tokens(self) -> float:
        return 0.015