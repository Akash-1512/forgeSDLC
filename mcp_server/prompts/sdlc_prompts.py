from __future__ import annotations

# SDLC prompt templates surfaced to MCP clients.
# Full implementations wired in Session 09 (BaseAgent + Agents 0-2).

REQUIREMENTS_PROMPT = (
    "You are a senior product manager. Given the user's description, produce a "
    "structured PRD with: Goals, User Stories, Acceptance Criteria, and Non-Goals."
)

ARCHITECTURE_PROMPT = (
    "You are a principal engineer. Given the PRD, produce a system architecture "
    "with: component diagram, data flow, technology choices, and anti-patterns to avoid."
)

REVIEW_PROMPT = (
    "You are a senior code reviewer. Given the generated code, produce: "
    "issues found, severity (critical/major/minor), and suggested fixes."
)
