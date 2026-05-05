from __future__ import annotations


class ForgeSDLCError(Exception):
    """Base exception for all forgeSDLC errors."""


class GateNotPassedError(ForgeSDLCError):
    """Raised when execute_node is called without gate confirmation."""


class ToolRouterError(ForgeSDLCError):
    """Raised when no ToolRouter adapter is available or delegation fails."""


class ModelRouterError(ForgeSDLCError):
    """Raised when ModelRouter cannot resolve a provider for the request."""


class MemoryLayerError(ForgeSDLCError):
    """Raised when a memory layer read or write operation fails."""


class SecurityScanError(ForgeSDLCError):
    """Raised when a security scan step fails unexpectedly."""


class ContextFileManagerError(ForgeSDLCError):
    """Raised when AGENTS.md / CLAUDE.md / .cursorrules write fails."""


class BudgetExceededError(ForgeSDLCError):
    """Raised when a request would exceed the session or subscription budget."""


class SubscriptionError(ForgeSDLCError):
    """Raised for invalid or expired subscription tokens."""
