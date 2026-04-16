from __future__ import annotations

from unittest.mock import patch

import pytest

from subscription.anthropic_tos_warning import AnthropicTosWarning
from subscription.byok_manager import BYOKManager


def _make_warning() -> AnthropicTosWarning:
    return AnthropicTosWarning()


def test_warning_text_contains_anthropic_mention() -> None:
    warning = _make_warning()
    text = warning.get_warning_text()
    assert "Anthropic" in text or "ANTHROPIC" in text
    assert "BYOK" in text


def test_confirm_returns_true_only_when_user_confirmed_true() -> None:
    warning = _make_warning()
    assert warning.confirm(True) is True


def test_confirm_returns_false_for_false_input() -> None:
    warning = _make_warning()
    assert warning.confirm(False) is False


def test_confirm_returns_false_for_none_input() -> None:
    """Guard against accidental truthy evaluation."""
    warning = _make_warning()
    assert warning.confirm(None) is False


def test_claude_available_requires_both_key_and_tos_confirmation() -> None:
    warning = _make_warning()
    manager = BYOKManager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = "sk-ant-test"
        assert warning.claude_is_available(manager, user_confirmed_tos=True) is True


def test_claude_not_available_with_key_but_no_tos_confirmation() -> None:
    warning = _make_warning()
    manager = BYOKManager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = "sk-ant-test"
        assert warning.claude_is_available(manager, user_confirmed_tos=False) is False


def test_claude_not_available_with_tos_but_no_key() -> None:
    warning = _make_warning()
    manager = BYOKManager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = None
        assert warning.claude_is_available(manager, user_confirmed_tos=True) is False