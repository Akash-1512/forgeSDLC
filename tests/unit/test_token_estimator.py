from __future__ import annotations

import inspect

import pytest

from context_management.token_estimator import TokenEstimator


def test_estimate_returns_zero_for_empty_string() -> None:
    est = TokenEstimator()
    assert est.estimate("") == 0
    assert est.estimate("   ") == 0


def test_estimate_uses_word_count_times_1_33() -> None:
    est = TokenEstimator()
    # "hello world foo" = 3 words → int(3 * 1.33) = 3
    result = est.estimate("hello world foo")
    assert result == int(3 * 1.33)


def test_estimate_dict_converts_to_string_first() -> None:
    est = TokenEstimator()
    data = {"key": "value one two three"}
    result = est.estimate_dict(data)
    assert result == est.estimate(str(data))
    assert result > 0


def test_token_estimator_never_calls_external_api() -> None:
    """TokenEstimator must not import tiktoken, transformers, or any tokenizer."""
    import context_management.token_estimator as module

    source = inspect.getsource(module)
    forbidden = ["tiktoken", "transformers", "tokenizer", "openai", "anthropic", "httpx"]
    for term in forbidden:
        assert term not in source, (
            f"TokenEstimator imports or references '{term}' — "
            "it must use only word count × 1.33, zero external API calls."
        )