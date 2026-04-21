# forgeSDLC — SDLC Intelligence Layer

Requirements, architecture, 5-layer memory, security scanning, and monitoring
for AI coding tools. Works in VS Code, Cursor, and Windsurf.

## Installation

```bash
# Option 1: VS Code Marketplace (Session 20)
ext install Akash-1512.forgesdlc

# Option 2: Local .vsix install
code --install-extension forgesdlc-0.1.0.vsix
```

## Quick Start

1. Open your project in VS Code/Cursor/Windsurf
2. Open the Command Palette (`Ctrl+Shift+P`)
3. Run: **forgeSDLC: Add to MCP Config**
4. Start the server: `npx @forgesdlc/agent`
5. In Claude Code / Copilot: `gather_requirements(prompt="...", project_id="...")`

## What It Does

- Writes `.vscode/mcp.json` (workspace-level, not global)
- Opens companion panel for HITL review (`forgeSDLC: Open Companion Panel`)
- Provides activity bar view for project status

## Commands

| Command | Description |
|---------|-------------|
| `forgeSDLC: Add to MCP Config` | Adds forgeSDLC to `.vscode/mcp.json` (idempotent) |
| `forgeSDLC: Open Companion Panel` | Opens HITL panel alongside editor |

## Architecture

forgeSDLC owns orchestration. Code generation is delegated to your AI coding tool
(Cursor, Claude Code, Copilot, Windsurf). The MCP server runs locally on port 8080.

## Known Limitations

- DAST requires `RUN_DAST=true` and a locally runnable application
- Claude BYOK requires adding your Anthropic API key in Settings → API Keys
- Render deployment requires `RENDER_DEPLOY_HOOK_URL` environment variable

---
Built with forgeSDLC — https://github.com/Akash-1512/forgesdlc