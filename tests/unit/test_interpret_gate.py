from __future__ import annotations

from interpret.gate import check_gate


def test_gate_accepts_100_percent_go() -> None:
    assert check_gate("100% GO") is True


def test_gate_rejects_approved() -> None:
    assert check_gate("APPROVED") is False


def test_gate_rejects_yes() -> None:
    assert check_gate("yes") is False


def test_gate_rejects_empty_string() -> None:
    assert check_gate("") is False


def test_gate_is_case_sensitive() -> None:
    assert check_gate("100% go") is False


def test_gate_rejects_whitespace() -> None:
    assert check_gate(" 100% GO ") is False


def test_gate_is_pure_no_side_effects() -> None:
    results = [check_gate("100% GO") for _ in range(100)]
    assert all(results)
