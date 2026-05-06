# AGENTS.md — forgeSDLC Architecture Context

This file is the canonical context document for AI coding tools working inside this repository.
Add it to your MCP client or paste it into the system prompt before contributing.

---

## What This Repo Is

forgeSDLC is an MCP server that gives AI coding tools (Cursor, Claude Code, Copilot) a
complete software engineering layer: requirements, architecture decisions, security scanning,
CI/CD generation, deployment, and monitoring — all with human-in-the-loop approval gates.

The AI coding tool writes code. forgeSDLC owns the SDLC.

---

## Repository Layout

```
mcp_server/         FastMCP server, 11 registered tools, /health, /auth/token
  tools/            One file per MCP tool — each calls shared infrastructure + agents
  prompts/          MCP prompt templates (slash-commands)
  resources/        MCP resources (project artefacts via URI)
agents/             14 agents (0–13), each owns one SDLC phase
  base_agent.py     Abstract base: interpret → HITL gate → execute → archive
memory/             5-layer cross-tool memory (PostgreSQL + ChromaDB + filesystem)
model_router/       9 LLM adapters, budget-aware routing, long-context (Gemini >100K)
tool_router/        Cursor → Claude Code → Devin → direct LLM fallback chain
interpret/          InterpretRecord (13 named layers), gate check, loop
orchestrator/       SDLCState TypedDict (48 keys), constants, exceptions
context_management/ ContextWindowManager, TokenEstimator, ContextCompressor
architecture_intelligence/ AntiPatternDetector (7 AST rules), NFR checker, scorer
subscription/       JWT session tokens, BYOK key management, tier resolution
token_tracker/      Per-call cost tracking, budget monitor, CSV export
workspace/          WorkspaceBridge (git), DiffEngine (path traversal guard)
providers/          ProviderResolver, health checks (PostgreSQL, ChromaDB, Ollama)
tools/              SecurityTools (bandit, semgrep, DAST), DocseFetcher, RenderTool
tests/              353 unit tests + integration tests (marked @pytest.mark.slow)
```

---

## Key Invariants — Never Break These

- `HUMAN_CONFIRMATION_PHRASE = "100% GO"` — exact string, never shown to users
- MCP server port: `8080`; host: `127.0.0.1` (never `0.0.0.0` in production)
- PostgreSQL everywhere — SQLite only for LangGraph HITL checkpointing
- `ruff` for lint+format, `semgrep --config=p/python --config=p/security`
- Agent 4 (ToolRouter) has `AGENT_MODELS["agent_4_tool_router"] = None` — it must never call ModelRouter directly
- All agents extend `BaseAgent` and implement `_interpret()`, `_execute()`
- Every architectural commitment requires human approval before `_execute()` runs

---

## Development Commands

```bash
pip install -e ".[dev]"         # install with dev deps
python -m pytest tests/ -m "not slow"   # run unit tests (fast)
ruff check . && ruff format --check .   # lint + format
python -m mcp_server.server             # start server at localhost:8080
make db-start                           # start local PostgreSQL via Docker
python scripts/commercial_readiness_check.py  # pre-release checklist
```

---

## Adding a New MCP Tool

1. Create `mcp_server/tools/my_tool.py`
2. Import `build_infrastructure` and `build_agent_kwargs` from `mcp_server.shared_infrastructure`
3. Instantiate only the agents this tool needs
4. Register in `mcp_server/server.py`: `mcp.tool()(my_tool_fn)`
5. Add at least one unit test in `tests/unit/test_mcp_server_tools.py`

---

## Memory Layers

| Layer | Store | Backend | What It Holds |
|-------|-------|---------|---------------|
| L1 | PipelineHistoryStore | PostgreSQL | Run records, cost, HITL rounds |
| L2 | OrgMemory | ChromaDB | Semantic decisions (requires model download on first use) |
| L3 | ProjectContextGraphStore | Filesystem | Service dependency graph |
| L4 | UserPreferenceStore | PostgreSQL | Tool and stack preferences |
| L5 | PostMortemStore | PostgreSQL | Failure analysis |

All stores degrade gracefully — if the database is unavailable, they log a warning and return empty results rather than crashing.

---

## CI/CD

- `ci.yml`: lint → mypy (advisory) → semgrep (advisory) → pytest (60% coverage min)
- `release.yml`: test → publish-python → publish-npm → build-electron (matrix: win/mac/linux) → github-release → publish-vscode
- Set `FORGESDLC_CI=true` in CI to make API-key checks advisory
