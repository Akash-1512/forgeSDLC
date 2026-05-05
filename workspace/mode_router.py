from __future__ import annotations

from enum import StrEnum

import structlog

from workspace.context import WorkspaceContext

logger = structlog.get_logger()


class Mode(StrEnum):
    INLINE = "inline"  # small targeted edit — companion panel diff view
    PIPELINE = "pipeline"  # full SDLC agent graph via MCP


# Keywords that always trigger PipelineMode regardless of request length.
# These indicate explicit SDLC intent — never route to InlineMode.
PIPELINE_KEYWORDS: frozenset[str] = frozenset(
    {
        "requirements",
        "architecture",
        "deploy",
        "monitor",
        "security scan",
        "generate ci",
        "full pipeline",
        "new project",
        "generate docs",
        "design",
        "scaffold",
    }
)


class ModeRouter:
    """Routes requests to InlineMode or PipelineMode.

    PIPELINE is the default for anything ambiguous — the safe choice.
    A false positive on InlineMode silently produces wrong output.
    A false positive on PipelineMode is slower but always correct.

    InlineMode fires ONLY when ALL of these are true:
      1. No pipeline keyword in the request
      2. Request length ≤ 200 characters
      3. workspace_context.active_file is not None
    """

    def route(
        self,
        request: str,
        workspace_context: WorkspaceContext,
    ) -> Mode:
        """Return Mode.INLINE or Mode.PIPELINE for this request."""
        request_lower = request.lower()

        # Pipeline keywords always win — explicit SDLC intent
        if any(kw in request_lower for kw in PIPELINE_KEYWORDS):
            logger.info(
                "mode_router.pipeline",
                reason="pipeline_keyword_match",
                request_preview=request[:50],
            )
            return Mode.PIPELINE

        # InlineMode: short + focused file — narrow path, intentional
        if len(request) <= 200 and workspace_context.active_file is not None:
            logger.info(
                "mode_router.inline",
                active_file=workspace_context.active_file,
                request_len=len(request),
            )
            return Mode.INLINE

        # Default: PIPELINE — never assume InlineMode for ambiguous requests
        logger.info(
            "mode_router.pipeline",
            reason="default_ambiguous",
            request_len=len(request),
            has_active_file=workspace_context.active_file is not None,
        )
        return Mode.PIPELINE
