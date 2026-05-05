from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from subscription.byok_manager import BYOKManager


def _make_manager() -> BYOKManager:
    return BYOKManager()


def test_save_key_stores_in_keychain() -> None:
    manager = _make_manager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        manager.save_key("openai", "sk-test-key")
        mock_keyring.set_password.assert_called_once_with("forgesdlc", "openai", "sk-test-key")


def test_save_key_never_logs_key_value(caplog: pytest.LogCaptureFixture) -> None:
    manager = _make_manager()
    secret_key = "sk-super-secret-12345"
    with (
        patch("subscription.byok_manager.keyring"),
        caplog.at_level(logging.DEBUG),
    ):
        manager.save_key("openai", secret_key)
    for record in caplog.records:
        assert secret_key not in record.getMessage(), (
            f"Key value leaked in log: {record.getMessage()}"
        )


def test_get_key_retrieves_from_keychain() -> None:
    manager = _make_manager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = "sk-retrieved"
        result = manager.get_key("openai")
        mock_keyring.get_password.assert_called_once_with("forgesdlc", "openai")
        assert result == "sk-retrieved"


def test_has_key_returns_false_when_not_set() -> None:
    manager = _make_manager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = None
        assert manager.has_key("openai") is False


def test_delete_key_removes_from_keychain() -> None:
    manager = _make_manager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        manager.delete_key("openai")
        mock_keyring.delete_password.assert_called_once_with("forgesdlc", "openai")


def test_anthropic_byok_requires_tos_warning_true_when_key_set() -> None:
    manager = _make_manager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = "sk-ant-test"
        assert manager.anthropic_byok_requires_tos_warning() is True


def test_anthropic_byok_requires_tos_warning_false_when_no_key() -> None:
    manager = _make_manager()
    with patch("subscription.byok_manager.keyring") as mock_keyring:
        mock_keyring.get_password.return_value = None
        assert manager.anthropic_byok_requires_tos_warning() is False
