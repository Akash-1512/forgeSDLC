from __future__ import annotations

from orchestrator.constants import TOKEN_ESTIMATE_WORDS_MULTIPLIER


class TokenEstimator:
    """Word count × TOKEN_ESTIMATE_WORDS_MULTIPLIER (1.33).

    NEVER calls an external API.
    NEVER imports tiktoken, transformers, or any tokenizer library.
    Fast, deterministic, good enough for budget and compression decisions.
    The approximation is intentional — exact token counts require API calls
    and introduce latency; 1.33× word count is accurate within ~10%.
    """

    def estimate(self, text: str) -> int:
        """Estimate token count for a string."""
        if not text or not text.strip():
            return 0
        words = len(text.split())
        return int(words * TOKEN_ESTIMATE_WORDS_MULTIPLIER)

    def estimate_dict(self, data: dict[str, object]) -> int:
        """Estimate token count for a dict by converting to string first."""
        return self.estimate(str(data))

    def estimate_state(self, state: dict[str, object]) -> int:
        """Estimate token count for the full SDLCState."""
        return self.estimate(str(state))
