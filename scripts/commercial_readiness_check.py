#!/usr/bin/env python3
"""
forgeSDLC Commercial Readiness Check
=====================================
Exit 0: all hard checks passed — ready to tag v1.0.0.
Exit 1: one or more hard failures — prints actionable fix instructions.

Usage:
    python scripts/commercial_readiness_check.py

CI usage:
    - Hard failures block merge (exit 1)
    - Advisories print but do not block (exit 0 if only advisories)

Hard checks: DATABASE_URL not sqlite, GROQ_API_KEY, OPENAI_API_KEY,
             SECRET_KEY >= 32 chars, all 4 legal files exist, Python >= 3.12

Advisory checks: EU AI Act deadline, RENDER_DEPLOY_HOOK_URL
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

FAILURES: list[tuple[bool, str]] = []


def check(
    name: str,
    condition: bool,
    fix: str,
    hard: bool = True,
) -> None:
    """Record a check result. hard=True blocks exit 0."""
    if not condition:
        prefix = "❌" if hard else "⚠️ "
        FAILURES.append((hard, f"  {prefix} {name}\n     Fix: {fix}"))


def main() -> int:
    # ── Hard checks ─────────────────────────────────────────────────────────

    # DATABASE_URL: empty is acceptable (defaults to local Docker PostgreSQL).
    # Any non-empty value containing "sqlite" is a hard failure.
    db_url = os.getenv("DATABASE_URL", "")
    check(
        "DATABASE_URL is not SQLite",
        "sqlite" not in db_url.lower(),
        (
            "Replace sqlite:// with postgresql://\n"
            "     Local default: postgresql+asyncpg://postgres:forgesdlc@localhost:5432/forgesdlc\n"
            "     Start DB: docker run -p 5432:5432 -e POSTGRES_PASSWORD=forgesdlc postgres:16"
        ),
    )

    check(
        "GROQ_API_KEY is set",
        bool(os.getenv("GROQ_API_KEY")),
        (
            "Set GROQ_API_KEY (paid Groq Developer tier required — "
            "free tier fails at ~100 concurrent users)\n"
            "     Get key: https://console.groq.com/keys"
        ),
    )

    check(
        "OPENAI_API_KEY is set",
        bool(os.getenv("OPENAI_API_KEY")),
        (
            "Set OPENAI_API_KEY for gpt-5.4/gpt-5.4-mini (Pro + Enterprise tiers)\n"
            "     Get key: https://platform.openai.com/api-keys"
        ),
    )

    secret = os.getenv("SECRET_KEY", "")
    check(
        "SECRET_KEY >= 32 chars",
        len(secret) >= 32,
        ('Generate a secure key:\n     python -c "import secrets; print(secrets.token_hex(32))"'),
    )

    legal_files = [
        "legal/cursor_api_review.md",
        "legal/eu_ai_act_checklist.md",
        "legal/gdpr_dpa_template.md",
        "legal/privacy_policy.md",
    ]
    for lf in legal_files:
        check(
            f"{lf} exists",
            Path(lf).exists(),
            f"Run Session 19 script to create {lf}",
        )

    check(
        f"Python >= 3.12 (current: {sys.version_info.major}.{sys.version_info.minor})",
        sys.version_info >= (3, 12),
        (
            f"Upgrade Python. Current: {sys.version.split()[0]}\n"
            "     Required: 3.12+ for asyncio.TaskGroup and Pydantic v2"
        ),
    )

    # ── Advisory checks (hard=False — print warning, don't block) ────────────

    days_remaining = (date(2026, 8, 2) - date.today()).days
    eu_label = (
        f"EU AI Act deadline ({days_remaining}d remaining)"
        if days_remaining >= 0
        else f"EU AI Act deadline PASSED ({abs(days_remaining)}d ago — advisory only)"
    )
    check(
        eu_label,
        days_remaining >= 0,
        "Review legal/eu_ai_act_checklist.md — model card must be published",
        hard=False,
    )

    check(
        "RENDER_DEPLOY_HOOK_URL set (Render deployment advisory)",
        bool(os.getenv("RENDER_DEPLOY_HOOK_URL")),
        (
            "Set RENDER_DEPLOY_HOOK_URL for Render deployment.\n"
            "     ⚠️  Free tier = 30-60s cold start — use Render Starter ($7/mo) for production"
        ),
        hard=False,
    )

    check(
        "GEMINI_API_KEY set (Enterprise tier advisory)",
        bool(os.getenv("GEMINI_API_KEY")),
        (
            "Set GEMINI_API_KEY for gemini-3.1-pro-preview (Agent 11 long-context routing)\n"
            "     Required for Enterprise tier and multi-service projects"
        ),
        hard=False,
    )

    # ── Report ────────────────────────────────────────────────────────────────

    hard_failures = [(hard, msg) for hard, msg in FAILURES if hard]
    all_messages = [msg for _, msg in FAILURES]

    if all_messages:
        print("\nforgeSDLC Commercial Readiness Check")
        print("=" * 40)
        for msg in all_messages:
            print(msg)
        print()

    if hard_failures:
        print(f"❌ {len(hard_failures)} hard failure(s). Resolve before tagging v1.0.0.\n")
        return 1

    if FAILURES:
        # Only advisories
        print("✅ All hard checks passed (advisory warnings above).")
        print("   Ready for v1.0.0 — address advisories before GA launch.\n")
    else:
        print("\n✅ All checks passed. Ready to tag v1.0.0.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
