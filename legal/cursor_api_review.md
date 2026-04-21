# Cursor API Review — forgeSDLC

**Status:** DOCUMENTED STANCE — not yet approved for commercial use.
**Last updated:** April 2026
**Owner:** Akash Chaudhari (ag.chaudhari.1512@gmail.com)

---

## Summary

forgeSDLC's Cursor adapter delegates code generation TO Cursor (as an AI coding
tool). forgeSDLC does not compete with Cursor — it orchestrates Cursor.

The `CURSOR_API_VERIFIED` guard is the current mitigation. `_check_cursor()`
returns `False` unless explicitly enabled, making Cursor integration opt-in
and disabled in production by default.

---

## Current Position

Each forgeSDLC user uses their own Cursor subscription. forgeSDLC does not
resell, sublicense, or white-label Cursor. The integration is:

- **User** installs Cursor (their own subscription)
- **User** installs forgeSDLC MCP server
- **forgeSDLC** sends code generation tasks to Cursor via MCP protocol
- **Cursor** generates code, returns result to forgeSDLC orchestration layer

This is analogous to a developer using Cursor's own MCP integration — forgeSDLC
is another MCP client, not a Cursor reseller.

---

## Risk Assessment

| Risk | Assessment |
|------|-----------|
| Reselling Cursor | None — each user's own subscription |
| Competing with Cursor | None — forgeSDLC delegates TO Cursor |
| ToS violation | Unknown — cursor.sh/terms not explicit on orchestration-layer MCP use |
| Revenue impact | None — forgeSDLC does not charge for Cursor access |

---

## Action Required Before Enabling Production

1. Review [cursor.sh/terms](https://cursor.sh/terms) for explicit language on
   orchestration-layer API/MCP usage
2. Confirm user-subscription model is compliant (each user pays Cursor directly)
3. Update this document with legal approval and date
4. Remove `CURSOR_API_VERIFIED` requirement from `_check_cursor()`
5. Add Cursor to the verified provider list in `providers/manifest.py`

---

## Fallback (No Cursor Required)

The ToolRouter fallback chain works without Cursor: