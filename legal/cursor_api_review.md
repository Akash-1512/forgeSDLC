# Cursor Background Agent API — Legal Review

**Status:** PENDING —  not enabled in production.

## What Needs Review
The Cursor Background Agent API (`api.cursor.sh/v1/background-agent/*`) is used
by `tool_router/adapters/cursor_adapter.py` to delegate code generation tasks.

Before enabling this adapter in a commercial product (forgeSDLC v1.0.0), the
following must be reviewed:

1. Does Cursor's ToS permit third-party tools to call the Background Agent API?
2. Are there rate limits or usage restrictions for commercial use?
3. Is the API endpoint stable and officially documented?
4. What data retention policies apply to prompts sent via the API?

## Current Guard
`cursor_adapter.py` returns `False` from `_check_cursor()` unless:
- `CURSOR_API_KEY` is set AND
- `CURSOR_API_VERIFIED=true` is explicitly set

Neither env var is set by default. The adapter is fully built and testable
via mocks but disabled in all environments until this review is complete.

## Action Required
- [ ] Review Cursor ToS at https://cursor.sh/terms
- [ ] Confirm Background Agent API is approved for commercial use
- [ ] Set `CURSOR_API_VERIFIED=true` in production config after approval
- [ ] Update this document with review date and findings
