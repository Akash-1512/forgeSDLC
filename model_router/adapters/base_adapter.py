from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage


@runtime_checkable  # enables isinstance(adapter, BaseLLMAdapter) in tests
class BaseLLMAdapter(Protocol):
    """Protocol for all forgeSDLC internal LLM adapters.

    ALL adapters must implement this interface — no **kwargs anywhere.
    Explicit named parameters only (MAANG rule).

    @runtime_checkable allows isinstance() checks without ABC inheritance.
    Without this decorator, isinstance(adapter, BaseLLMAdapter) raises TypeError.
    """

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        stop: list[str] | None = None,
    ) -> AIMessage:
        """Invoke the model and return a complete response."""
        ...

    async def astream(
        self,
        messages: list[BaseMessage],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> AsyncIterator[AIMessageChunk]:
        """Stream the model response chunk by chunk."""
        ...

    async def afim(
        self,
        prefix: str,
        suffix: str,
        *,
        max_tokens: int = 512,
    ) -> str:
        """Fill-in-the-middle completion.

        PSM FIM: codestral implements natively.
        All other adapters raise NotImplementedError.
        """
        ...

    @property
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @property
    def context_window(self) -> int:
        """Return the model's context window in tokens."""
        ...

    @property
    def cost_per_1k_input_tokens(self) -> float:
        """Return cost in USD per 1000 input tokens."""
        ...

    @property
    def cost_per_1k_output_tokens(self) -> float:
        """Return cost in USD per 1000 output tokens."""
        ...
