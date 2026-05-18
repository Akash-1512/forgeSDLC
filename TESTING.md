# forgeSDLC — Testing & Evaluation Guide

This guide is for tech managers and senior engineers evaluating the codebase.
It covers every layer: unit tests, integration, E2E, and a live demo walkthrough.

---

## Quick Start (2 minutes)

```bash
git clone https://github.com/Akash-1512/forgeSDLC
cd forgeSDLC
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run all fast tests (364 tests, ~8 seconds)
pytest tests/ -m "not slow" -v --tb=short

# Run the automated demo (no LLM keys needed)
python scripts/demo_runner.py
```

---

## Test Suite

### Unit Tests (353 tests, < 8s)

```bash
pytest tests/unit/ -v
```

**What they cover:**

| Module | Tests | What's verified |
|--------|-------|----------------|
| `test_model_router.py` | 18 | Budget routing, tier gates, BYOK, FIM, long-context |
| `test_mcp_server_tools.py` | 28 | All 11 MCP tools — state, approval flow, HITL gate |
| `test_memory_*.py` | 45 | All 5 memory layers — write, read, degraded-mode |
| `test_agent_*.py` | 90+ | Every agent's interpret → gate → execute contract |
| `test_tier_resolver.py` | 8 | JWT, env var, fallback chain |
| `test_interpret_*.py` | 22 | InterpretRecord validation, gate enforcement |
| `test_workspace_*.py` | 12 | Git integration, diff engine, path traversal guard |
| `test_architecture_intelligence.py` | 10 | Anti-pattern detection, NFR checks |

### Integration Tests (68 tests, slow marker)

```bash
pytest tests/integration/ -v  # needs PostgreSQL
# OR
pytest tests/integration/ -v -k "not memory_persistence and not cross_tool"
```

These test multi-agent flows, HITL gate enforcement, and memory compound queries.

### Coverage

```bash
pytest tests/ -m "not slow" --cov=. --cov-report=term-missing --cov-report=html
open htmlcov/index.html
```

Expected: > 65% overall. Model router, agents, memory stores individually > 80%.

---

## E2E Server Test (no LLM keys needed)

The MCP server degrades gracefully when no API keys are set.
All 11 tools respond correctly without PostgreSQL or HuggingFace network.

```bash
# Terminal 1: start the server
export SECRET_KEY="demo-secret-key-minimum-32-chars"
python -m mcp_server.server --transport streamable-http --port 8080

# Terminal 2: run the E2E check
python scripts/demo_runner.py --mode e2e
```

### Manual endpoint tests

```bash
# Health check
curl http://127.0.0.1:8080/health

# Expected:
# {"status": "ok", "version": "1.1.0", "transport": "streamable-http"}

# Get a session token (free tier)
curl -X POST http://127.0.0.1:8080/auth/token \
     -H "Content-Type: application/json" \
     -d '{"user_id": "demo", "tier": "free"}'
```

---

## Full Live Demo (GROQ_API_KEY required — free at console.groq.com)

```bash
export GROQ_API_KEY="your-groq-key"
export SECRET_KEY="demo-secret-minimum-32-chars-long"

# Optional: PostgreSQL for full memory persistence
# make db-start  (requires Docker)

python scripts/demo_runner.py --mode full --project "task-api-demo"
```

The demo runs a complete SDLC cycle:

1. **Decompose** — splits "REST API for task management" into services
2. **Requirements** — generates PRD with NFRs (calls GROQ)
3. **Architecture** — scores anti-patterns, proposes RFC (waits for approval)
4. **Stack** — writes ADR with tech stack decision
5. **Security** — runs bandit + semgrep SAST on `/tmp`
6. **CI/CD** — generates GitHub Actions workflow for FastAPI
7. **Track** — shows pipeline progress across all stages

Each agent that writes files shows you exactly:
- What it will read/write
- Which model it will call
- Whether the action is reversible
- The gate: soft (advisory) or hard (red border — requires `100% GO`)

---

## Architecture Evaluation Points

### What to look for

**14-agent LangGraph pipeline** (`orchestrator/graph.py`, `agents/`)
- Each agent implements `_interpret()` → approval gate → `_execute()`
- Hard gates block irreversible actions (deployment, RFC write)
- All agents share infrastructure via `mcp_server/shared_infrastructure.py`

**5-layer memory** (`memory/`)
- L1: PostgreSQL pipeline history
- L2: ChromaDB semantic memory (degrades gracefully without network)
- L3: Filesystem project graph (JSON)
- L4: PostgreSQL user preferences
- L5: PostgreSQL post-mortems

**Model routing** (`model_router/router.py`)
- 8-step routing: FIM → long-context → budget → tier → BYOK → normal
- Every LLM call tracked via `_TrackingAdapter` → `TokenTracker`
- All 9 adapters: Groq, OpenAI, Claude, Gemini, Codestral, Ollama, Azure

**Subscription tiers** (`subscription/`)
- JWT session tokens, OS keychain BYOK, Anthropic ToS enforcement
- Tier gates in ModelRouter — free/pro/enterprise model lists

**InterpretRecord** (`interpret/`)
- Every agent action emits a record before executing
- 13 named layers (agent, memory, model_router, security, diff, ...)
- Companion panel renders these for the developer

### Code quality metrics

```bash
# Zero lint errors
ruff check .

# Type coverage
mypy mcp_server/ agents/ memory/ model_router/ --ignore-missing-imports

# Security scan (self-hosted)
bandit -r mcp_server/ agents/ memory/ -ll

# Pre-commit hooks
pre-commit run --all-files
```

---

## Repo Structure

```
mcp_server/          FastMCP server — 11 tools, /health, /auth/token
  tools/             One file per MCP tool (requirements, architecture, ...)
agents/              14 agents, base_agent.py with interpret→gate→execute
memory/              5-layer memory: PostgreSQL + ChromaDB + filesystem
model_router/        9 LLM adapters, budget-aware routing, token tracking
tool_router/         Cursor → Claude Code → Devin → direct LLM fallback
orchestrator/        SDLCState (48 keys), LangGraph graph, exceptions
interpret/           InterpretRecord, gate enforcement, 13 named layers
architecture_intelligence/  AntiPatternDetector, NFR checker, scorer
context_management/  ContextWindowManager, TokenEstimator, Compressor
subscription/        JWT tokens, BYOK, tier resolution, Anthropic ToS
workspace/           Git bridge, DiffEngine with .forgesdlc.bak backups
providers/           Health checks, provider resolution, factory pattern
token_tracker/       Per-call cost tracking, CSV export, budget monitor
context_files/       AGENTS.md, CLAUDE.md, .cursorrules writers
tests/               364 unit + integration tests (pytest)
```

---

## What This Demonstrates

This repo shows production-grade agentic AI engineering:

- **Multi-agent orchestration** with LangGraph state machines and HITL gates
- **Resilient architecture** — every component degrades gracefully without dependencies
- **Observability** — structured logging (structlog) throughout, InterpretRecord audit trail
- **Security** — no hardcoded secrets, keychain BYOK, path traversal guard, ToS enforcement
- **Test discipline** — 364 passing tests, specific exception types, no assert True stubs
- **CI/CD** — GitHub Actions with postgres service, semgrep, mypy, coverage gate
- **Enterprise standards** — MIT license, SECURITY.md, CONTRIBUTING.md, issue templates
