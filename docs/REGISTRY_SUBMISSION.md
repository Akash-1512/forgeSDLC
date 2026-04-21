# MCP Registry Submission — forgeSDLC v1.0.0

Complete these steps AFTER v1.0.0 is live on npm and pip.
Each registry is manual — no automated submission API exists.

---

## 1. mcp.so

**URL:** https://mcp.so/submit

**Fields:**

| Field | Value |
|-------|-------|
| Name | forgeSDLC |
| Description | The missing SDLC layer for Cursor, Claude Code, and Copilot — requirements, architecture, memory, security, CI/CD, deploy, monitor |
| Install command | `npx @forgesdlc/agent` |
| Alternative install | `pip install forgesdlc-mcp` |
| Category | Developer Tools |
| GitHub URL | https://github.com/Akash-1512/forgesdlc |
| MCP endpoint | http://localhost:8080/mcp |
| Transport | streamable-http |
| License | MIT |

**Tools to list:**
- gather_requirements
- design_architecture
- recall_context
- save_decision
- route_code_generation
- run_security_scan
- generate_cicd
- deploy_project
- setup_monitoring
- generate_docs
- track_progress

---

## 2. Smithery

**URL:** https://smithery.ai/new

**Steps:**
1. Ensure `smithery.yaml` exists in repo root (committed in Session 20)
2. Submit via https://smithery.ai/new
3. Smithery reads `smithery.yaml` to auto-populate the listing
4. Review and publish

**smithery.yaml is at:** `smithery.yaml` (repo root)

---

## 3. mcpservers.org

**URL:** https://github.com/mcpservers-org/registry

**Steps:**
1. Fork the `mcpservers-org/registry` repository
2. Add forgeSDLC entry to `servers.json`:

```json
{
  "id": "forgesdlc",
  "name": "forgeSDLC",
  "description": "The missing SDLC layer for AI coding tools",
  "url": "https://github.com/Akash-1512/forgesdlc",
  "install": {
    "npm": "@forgesdlc/agent",
    "pip": "forgesdlc-mcp"
  },
  "tools": [
    "gather_requirements", "design_architecture", "recall_context",
    "save_decision", "route_code_generation", "run_security_scan",
    "generate_cicd", "deploy_project", "setup_monitoring",
    "generate_docs", "track_progress"
  ],
  "transport": "streamable-http",
  "category": "developer-tools",
  "license": "MIT",
  "author": "Akash Chaudhari"
}
```

3. Open a pull request titled: `Add forgeSDLC — SDLC intelligence layer for AI coding tools`

---

## 4. Claude.ai MCP Directory (future)

Anthropic is building an official MCP directory. Monitor:
https://docs.anthropic.com/en/docs/agents-and-tools/mcp

---

## Post-Submission Checklist

- [ ] mcp.so listing live and searchable
- [ ] Smithery listing live and searchable
- [ ] mcpservers.org PR merged
- [ ] Links added to README.md badges section
- [ ] Demo video link added to all registry listings
