"""
Verifies that check_gate() accepts EXACTLY "100% GO" and nothing else.
Covers: whitespace variants, case variants, similar strings, empty string,
        None input, numeric string, and common "approval" phrases.
"""

from __future__ import annotations

import pytest

from interpret.gate import check_gate

SHOULD_PASS = ["100% GO"]

SHOULD_FAIL = [
    "",
    " ",
    "100% go",  # wrong case
    "100%GO",  # missing space
    "100% GO ",  # trailing space
    " 100% GO",  # leading space
    " 100% GO ",  # both spaces
    "100 % GO",  # space before %
    "APPROVED",
    "approved",
    "yes",
    "YES",
    "ok",
    "OK",
    "ok go",
    "Let's go",
    "Confirmed",
    "confirm",
    "Go",
    "proceed",
    "100",
    "GO",
    None,  # type: ignore[list-item]
]


@pytest.mark.parametrize("phrase", SHOULD_PASS)
def test_gate_accepts_exact_match(phrase: str) -> None:
    assert check_gate(phrase) is True


@pytest.mark.parametrize("phrase", SHOULD_FAIL)
def test_gate_rejects_non_exact(phrase: object) -> None:
    assert check_gate(phrase) is False  # type: ignore[arg-type]


def test_gate_is_pure_function() -> None:
    """Calling 1000 times returns same result — no side effects."""
    results = [check_gate("100% GO") for _ in range(1000)]
    assert all(results)
    results_false = [check_gate("APPROVED") for _ in range(1000)]
    assert not any(results_false)


def test_gate_rejects_bytes() -> None:
    """Non-string types return False — no implicit coercion."""
    assert check_gate(b"100% GO") is False  # type: ignore[arg-type]


def test_gate_rejects_integer() -> None:
    assert check_gate(100) is False  # type: ignore[arg-type]


def test_gate_case_sensitive() -> None:
    """Gate is case-sensitive — lowercase go rejected."""
    assert check_gate("100% go") is False
    assert check_gate("100% Go") is False
    assert check_gate("100% gO") is False


def test_gate_exact_string_only() -> None:
    """Confirm the exact constant string is the only accepted value."""
    from orchestrator.constants import HUMAN_CONFIRMATION_PHRASE

    assert HUMAN_CONFIRMATION_PHRASE == "100% GO"
    assert check_gate(HUMAN_CONFIRMATION_PHRASE) is True
