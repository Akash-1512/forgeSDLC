"""
H14 Fix: MCP prompt handlers registered with the FastMCP server.

These were previously defined as plain string constants but never registered.
MCP prompts surface template instructions to MCP clients (Cursor, Claude Code, VS Code+Copilot).
"""

from __future__ import annotations


def get_requirements_prompt(project_description: str = "") -> str:
    """MCP Prompt: generate structured PRD from a natural language description."""
    return (
        "You are a senior product manager. Given the user's description, produce a "
        "structured PRD with these sections: Goals, User Stories (As a [persona] I want "
        "[action] so that [benefit]), Acceptance Criteria (Given/When/Then), "
        "Non-Functional Requirements, Out of Scope, and Assumptions.\n\n"
        f"Project description: {project_description}"
        if project_description
        else (
            "You are a senior product manager. Given the user's description, produce a "
            "structured PRD with these sections: Goals, User Stories (As a [persona] I want "
            "[action] so that [benefit]), Acceptance Criteria (Given/When/Then), "
            "Non-Functional Requirements, Out of Scope, and Assumptions."
        )
    )


def get_architecture_prompt(prd_summary: str = "") -> str:
    """MCP Prompt: generate RFC + ADR from a PRD."""
    return (
        "You are a principal engineer. Given the PRD, produce:\n"
        "1. Architecture Decision Record (ADR-001): chosen stack with rationale\n"
        "2. RFC (Request for Comments): component diagram, data flow, "
        "technology choices, scaling strategy, anti-patterns to avoid.\n\n"
        f"PRD Summary: {prd_summary}"
        if prd_summary
        else (
            "You are a principal engineer. Given the PRD, produce:\n"
            "1. Architecture Decision Record (ADR-001): chosen stack with rationale\n"
            "2. RFC (Request for Comments): component diagram, data flow, "
            "technology choices, scaling strategy, anti-patterns to avoid."
        )
    )


def get_review_prompt(files_summary: str = "") -> str:
    """MCP Prompt: 5-pass code review template."""
    return (
        "You are a senior code reviewer conducting a 5-pass review:\n"
        "Pass 1: Correctness — logic errors, edge cases, null handling\n"
        "Pass 2: Security — OWASP Top 10, injection, auth bypass\n"
        "Pass 3: Performance — N+1 queries, blocking calls, memory leaks\n"
        "Pass 4: Standards — function length (<50 lines), type hints, bare except\n"
        "Pass 5: Error Handling — exception coverage, logging, recovery paths\n\n"
        "For each finding: severity (BLOCKING/ADVISORY), file, line, description, fix.\n\n"
        f"Files to review: {files_summary}"
        if files_summary
        else (
            "You are a senior code reviewer conducting a 5-pass review:\n"
            "Pass 1: Correctness — logic errors, edge cases, null handling\n"
            "Pass 2: Security — OWASP Top 10, injection, auth bypass\n"
            "Pass 3: Performance — N+1 queries, blocking calls, memory leaks\n"
            "Pass 4: Standards — function length (<50 lines), type hints, bare except\n"
            "Pass 5: Error Handling — exception coverage, logging, recovery paths\n\n"
            "For each finding: severity (BLOCKING/ADVISORY), file, line, description, fix."
        )
    )
