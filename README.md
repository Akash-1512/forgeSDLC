# forgeSDLC
The missing SDLC layer for your AI coding tools.
Connect forgeSDLC to Cursor, Claude Code, or GitHub Copilot in one line of config.

[![CI](https://github.com/Akash-1512/forgesdlc/actions/workflows/ci.yml/badge.svg)](https://github.com/Akash-1512/forgesdlc/actions)
[![Release](https://img.shields.io/github/v/release/Akash-1512/forgesdlc)](https://github.com/Akash-1512/forgesdlc/releases)
[![npm](https://img.shields.io/npm/v/@forgesdlc/agent)](https://www.npmjs.com/package/@forgesdlc/agent)
[![PyPI](https://img.shields.io/pypi/v/forgesdlc-mcp)](https://pypi.org/project/forgesdlc-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)

---

## What Is forgeSDLC?

forgeSDLC is an MCP (Model Context Protocol) server that gives your AI coding
tool a **full software engineering brain**: requirements, architecture, living
memory, security scanning, CI/CD generation, deployment, and monitoring — all
orchestrated by 14 agents with human-in-the-loop gates at every architectural
commitment.

Your AI coding tool (Cursor, Claude Code, Copilot, Windsurf) continues to write
the code. forgeSDLC owns the SDLC: *what* to build, *how* it should be
architected, *whether* it's secure enough to deploy.

---

## Quick Start

```bash
# Option A — MCP Server (headless)
npx @forgesdlc/agent
# or: pip install forgesdlc-mcp && python -m mcp_server.server

# Option B — Desktop App (starts server automatically)
# Download from GitHub Releases → forgesdlc-setup-{version}.exe / .dmg / .deb
```

Add one line to your MCP config:

```json
{
  "mcpServers": {
    "forgesdlc": { "url": "http://localhost:8080/mcp" }
  }
}
```

Then in Claude Code / Copilot / Cursor:

```
gather_requirements(prompt="Build a REST API for user management", project_id="my-app")
```

---

## Install

### Option A — MCP Server (headless, works in any MCP client)

```bash
# Node
npx @forgesdlc/agent

# Python
pip install forgesdlc-mcp
python -m mcp_server.server --transport streamable-http --port 8080
```

Add to your MCP config (`.vscode/mcp.json` or `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "forgesdlc": { "url": "http://localhost:8080/mcp" }
  }
}
```

### Option B — Desktop App (starts server automatically)

Download from [GitHub Releases](https://github.com/Akash-1512/forgesdlc/releases):

| Platform | File |
|----------|------|
| Windows | `forgesdlc-setup-{version}.exe` |
| macOS | `forgesdlc-{version}.dmg` |
| Linux | `forgesdlc-{version}.deb` |

First-launch wizard configures Cursor automatically.
The [✅ Approve] companion panel handles all HITL gates.

---

## Pricing

| Tier | Price | Tools Available | Models |
|------|-------|----------------|--------|
| **Free** | $0 | `recall_context` + `save_decision` | Groq only |
| **Pro** | $20/mo | All 11 MCP tools | GPT-5.4-mini + Gemini + Groq |
| **Enterprise** | $80/seat | All tools + Devin | All providers + SLA |

Claude requires BYOK (your Anthropic API key) on all tiers.

> **Free tier note:** Groq free tier (~30 req/min) is suitable for personal use.
> Production teams should use the paid Groq Developer tier.

---

## The 11 MCP Tools

| Tool | What It Does | Free |
|------|-------------|------|
| `recall_context` | Retrieve project memory across sessions | ✅ |
| `save_decision` | Persist architectural decisions to memory | ✅ |
| `gather_requirements` | PRD + NFR generation with HITL | Pro+ |
| `design_architecture` | RFC + ADR + service decomposition | Pro+ |
| `route_code_generation` | Delegate to Cursor/Claude Code/Copilot | Pro+ |
| `run_security_scan` | SAST + DAST + STRIDE threat model | Pro+ |
| `generate_cicd` | GitHub Actions with verified action versions | Pro+ |
| `deploy_project` | Render or Docker deployment | Pro+ |
| `setup_monitoring` | SLOs + runbook + OTel config | Pro+ |
| `generate_docs` | README + CHANGELOG + ProjectContextGraph | Pro+ |
| `track_progress` | Pipeline status across all stages | Pro+ |

---

## Cross-Tool Memory Demo

forgeSDLC's living memory persists decisions across tool sessions:

```bash
# Start the MCP server first
python -m mcp_server.server --transport streamable-http --port 8080

# In another terminal
python demos/cross_tool_memory_demo.py
```

What the demo shows:
1. "Cursor" saves an architecture decision (`save_decision`)
2. "Claude Code" (new session, no shared state) recalls it (`recall_context`)
3. The decision is found via semantic search — cross-tool memory works

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  AI Coding Tool (Cursor / Claude Code / Copilot)         │
│  ← delegates code generation here                        │
└──────────────────┬───────────────────────────────────────┘
                   │ MCP protocol
┌──────────────────▼───────────────────────────────────────┐
│  forgeSDLC MCP Server                                     │
│  14 Agents  ·  5-layer memory  ·  HITL gates             │
│  SAST/DAST  ·  CI/CD  ·  Deploy  ·  Monitor              │
└──────────────────────────────────────────────────────────┘
```

- **14 Agents:** Agents 0-13, each owning one SDLC phase
- **5-Layer Memory:** OrgMemory (ChromaDB) + PostgreSQL + ProjectContextGraph
- **HITL Gates:** every architectural commitment requires human approval
- **Security:** bandit + semgrep (p/python + p/security) + STRIDE threat model

Full architecture: [`docs/architecture/`](docs/architecture/)

---

## Requirements

- Python 3.12+
- PostgreSQL 16 (local Docker: `docker run -p 5432:5432 -e POSTGRES_PASSWORD=forgesdlc postgres:16`)
- Node.js 24+ (for `npx @forgesdlc/agent`)
- API key for at least one LLM provider (Groq recommended — free tier available)

---

## Development

```bash
git clone https://github.com/Akash-1512/forgesdlc
cd forgesdlc
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -m "not slow"

# Start MCP server
python -m mcp_server.server --transport streamable-http --port 8080

# Commercial readiness check
python scripts/commercial_readiness_check.py
```

---

## Known Limitations

- DAST requires `RUN_DAST=true` and a locally runnable application
- Claude BYOK: add your Anthropic API key via Settings → API Keys
- Render deployment: `RENDER_DEPLOY_HOOK_URL` required; free tier = 30-60s cold start
- Cursor integration: disabled by default pending ToS review (`legal/cursor_api_review.md`)
- System tray on Linux requires `libappindicator3-1`

---

## Legal

- [Privacy Policy](legal/privacy_policy.md)
- [EU AI Act Checklist](legal/eu_ai_act_checklist.md)
- [GDPR DPA Template](legal/gdpr_dpa_template.md)
- [License: MIT](LICENSE)

---

## Contributing

PRs welcome. Please read [AGENTS.md](AGENTS.md) before contributing — it
contains the full forgeSDLC architecture context for AI coding tools.

---

Built with forgeSDLC — https://github.com/Akash-1512/forgesdlc
'@ | Set-Content README.md
```