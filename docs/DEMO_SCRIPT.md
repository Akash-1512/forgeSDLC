# forgeSDLC v1.0.0 — 90-Second Demo Script

**Target:** 90 seconds. No cuts. Real install, real tools, real memory.

---

## Pre-Recording Setup

```bash
# 1. Publish must be live first
npm install -g @forgesdlc/agent   # verify @forgesdlc/agent@1.0.0 on npm

# 2. Start MCP server
python -m mcp_server.server --transport streamable-http --port 8080

# 3. Configure both tools
# Cursor:     ~/.cursor/mcp.json   → {"mcpServers": {"forgesdlc": {"url": "http://localhost:8080/mcp"}}}
# Claude Code: .vscode/mcp.json   → same entry

# 4. Start forgeSDLC Desktop
# Show system tray icon visible in taskbar

# 5. Set project ID
PROJECT_ID = "demo-$(date +%s)"   # unique per recording
```

---

## Script

### 00–05s — TITLE CARD
forgeSDLC 1.0.0
The missing SDLC layer for your AI coding tools

### 05–15s — INSTALL (text overlay, terminal visible)
```bash
npx @forgesdlc/agent
```
Show: server starts, "Running on http://localhost:8080"
Text overlay:
One line. Works in Cursor, Claude Code, Copilot, Windsurf.

### 15–30s — REQUIREMENTS (Cursor)
In Cursor chat:
gather_requirements(
prompt="Build a REST API for a todo app with user auth",
project_id="demo-01"
)
Show: `awaiting_confirmation` response with interpretation text visible.
Switch to forgeSDLC Desktop → click [✅ Approve].
Show: PRD generated in workspace.
Voiceover: *"Full PRD generated. Requirements locked in memory."*

### 30–45s — ARCHITECTURE (Cursor, same session)
design_architecture(project_id="demo-01")
Show: RFC generated, Mermaid diagram visible in workspace file.
Show: Architecture scores — Scalability 7/10, Security 9/10.
Voiceover: *"Architecture validated. Zero HIGH anti-patterns detected."*

### 45–60s — CROSS-TOOL RECALL (Claude Code, NEW SESSION)
Switch to Claude Code window.
recall_context(
query="What database did we choose and why?",
project_id="demo-01"
)
Show: Claude Code response contains the PostgreSQL decision from the RFC.
Voiceover: *"Zero copy-paste. Zero context loss."*

### 60–75s — MONEY LINE (text overlay)
The architecture decided in Cursor
is visible in Claude Code.
The decision made in Claude Code
is visible in Copilot.
One memory. Every tool.

### 75–90s — DESKTOP APP
Switch to forgeSDLC Desktop (already running in taskbar).
Show:
- System tray icon
- 4-zone companion panel: pipeline progress, current interpretation, memory viewer
- Token history showing session cost
Final frame:
github.com/Akash-1512/forgesdlc
npm install -g @forgesdlc/agent

---

## Recording Notes

- Resolution: 1920×1080, 60fps
- No mouse cursor on text overlays
- Terminal font: 18pt minimum (legible at 720p)
- Record AFTER v1.0.0 is live on npm — show real `npx @forgesdlc/agent` install
- Upload to: YouTube (primary), GitHub Releases description, README

---

## Voiceover Script (optional)

> "forgeSDLC is the missing SDLC layer for your AI coding tools. One command
> to install. One line of config to connect. Then — requirements, architecture,
> security, CI/CD, deploy, and monitoring — all orchestrated with human approval
> at every architectural commitment. And every decision persists in living
> memory, accessible from any AI tool you use. One memory. Every tool."