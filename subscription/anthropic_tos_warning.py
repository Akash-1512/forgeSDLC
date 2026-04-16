from __future__ import annotations

import structlog

logger = structlog.get_logger()


class AnthropicTosWarning:
    """Enforces explicit ToS acknowledgement before Claude BYOK unlocks.

    Called by the model picker in the Desktop companion panel (Session 17).
    In CLI/MCP contexts: returns warning text that the client must display.

    DESIGN RULES:
    - confirm() NEVER auto-confirms — only explicit True passes
    - confirm(None) → False (guards against accidental truthy evaluation)
    - claude_is_available() requires BOTH key AND confirmed ToS
    - This transfers ToS responsibility to the developer, not forgeSDLC
    """

    WARNING_TEXT = (
        "⚠️  ANTHROPIC TERMS OF SERVICE NOTICE\n"
        "Claude is available as a BYOK (Bring Your Own Key) option.\n"
        "forgeSDLC is an MCP orchestration server — it adds requirements,\n"
        "architecture, and memory to your coding tools. It does not compete\n"
        "with Claude Code or any Anthropic product.\n\n"
        "By enabling Claude BYOK, you confirm:\n"
        "1. You have read Anthropic's usage policies\n"
        "2. Your use case is permitted under your Anthropic agreement\n"
        "3. You accept ToS responsibility for your Claude API usage\n\n"
        "forgeSDLC stores your key in the OS keychain only — never in plaintext."
    )

    def get_warning_text(self) -> str:
        """Return the full ToS warning text for display to the developer."""
        return self.WARNING_TEXT

    def confirm(self, user_confirmed: object) -> bool:
        """Return True ONLY when user_confirmed is exactly True.

        Never auto-confirms. confirm(None) → False. confirm(False) → False.
        confirm("yes") → False. Only confirm(True) → True.
        """
        return user_confirmed is True

    def claude_is_available(
        self,
        byok_manager: object,
        user_confirmed_tos: bool,
    ) -> bool:
        """Claude is available only when BYOK key exists AND ToS is confirmed.

        Both conditions must be true — either alone is insufficient.
        """
        from subscription.byok_manager import BYOKManager  # noqa: PLC0415
        if not isinstance(byok_manager, BYOKManager):
            return False
        has_key = byok_manager.has_key("anthropic")
        confirmed = self.confirm(user_confirmed_tos)
        logger.info(
            "anthropic_tos_warning.claude_available_check",
            has_key=has_key,
            tos_confirmed=confirmed,
        )
        return has_key and confirmed