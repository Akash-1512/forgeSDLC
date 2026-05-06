# Changelog

All notable changes to forgeSDLC are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Fixed
- Server startup no longer downloads the HuggingFace embedding model eagerly.
  `OrgMemory` now initialises lazily and runs in degraded mode when the model
  is not cached, allowing the server to start without network access.
- All 8 MCP tool handlers were unpacking `Infrastructure` (a `NamedTuple`) into
  a plain `tuple` and passing it to `build_agent_kwargs`, which expected the
  named tuple. Fixed by returning `infra` directly from `_build_infrastructure`.
- `ToolRouter()` in `cicd_tool` and `code_generation_tool` was called without
  the required `context_file_manager` argument.
- `/health` and `/auth/token` endpoints returned HTTP 500 because FastMCP 3.x
  `custom_route` handlers must return a Starlette `Response`, not a plain `dict`.
- `BYOKManager.get_key()` raised `NoKeyringError` on headless Linux where no
  keyring backend is available. Now returns `None` and continues.
- All PostgreSQL store read/write methods now catch `OSError` and return empty
  results gracefully, so the server operates without a database connection.
- `PostMortemStore.get_recent_failures` was calling `self._emit_record` which
  does not exist on that class (correct name is `self._emit`).
- `get_recent_failures` was constructing `PostMortem` objects with wrong field
  names (`what_went_wrong`, `fix_applied`) instead of the schema-defined fields.

### Changed
- `memory/organisational_memory.py` renamed to `memory/organizational_memory.py`
  (American English, consistent with the rest of the codebase). The old path is
  kept as a one-release compatibility shim.
- `ProviderResolver.print_table()` renamed to `log_table()` — output now goes
  through the `structlog` logger instead of `print()`.

---

## [1.1.0] — 2026-05-05

### Added
- `GET /health` endpoint for smithery.yaml and Electron health polling
- `POST /auth/token` endpoint — issues signed JWT with subscription tier claim
- Alembic migration system with baseline schema (`001`) and `project_id` column (`002`)
- `mcp_server/shared_infrastructure.py` — single infrastructure factory used by all tools
- `mcp_server/state_factory.py` — canonical SDLCState builder (48 keys, all typed)
- `mcp_server/tier_resolver.py` — resolves subscription tier from JWT or `FORGESDLC_TIER` env var
- MCP prompts (requirements, architecture, review) registered with FastMCP server
- MCP resources (`project://{id}/prd`, `/adr`, `/memory`) registered with FastMCP server
- `_TrackingAdapter.inner` property on ModelRouter return value for adapter inspection
- `hard_gate` attribute on `BaseAgent` — surfaced to companion panel for red-border HITL
- `interpret_node()` and `interrupt_node()` from `interpret/loop.py` wired into `BaseAgent.run()`
- OPENAI_API_KEY and GOOGLE_API_KEY validation in ModelRouter before routing to paid models
- `track_progress` tool wires `TokenAggregator` — surfaces real token and cost data
- PostgreSQL and ChromaDB health checks run at server startup
- `build_graph()` now accepts real agent instances and wires conditional edges
- Per-file ruff ignores for files with unavoidable long lines (YAML template strings)
- `[tool.mypy]` and ruff `exclude` config in `pyproject.toml`
- `FORGESDLC_TIER` and `FORGESDLC_CI` documented in `.env.example`

### Changed
- Package name: `forgesdlc` → `forgesdlc-mcp` (aligns with `pip install forgesdlc-mcp`)
- Server binds `127.0.0.1` by default (was `0.0.0.0`) — set `MCP_SERVER_HOST=0.0.0.0` for LAN
- `OrgMemory` uses a module-level singleton embeddings instance (was per-call, loaded 90 MB each time)
- `MemoryContextBuilder` uses module-level singleton DB stores (was creating 5 engine pools per call)
- All tool state builders call `resolve_tier()` instead of hardcoding `"free"`
- `_build_infrastructure()` in all 8 tool files delegates to `build_infrastructure()` shared factory
- `MemoryArchiver.Layer1` extracts short stack identifier from ADR header (was storing full document)
- Layer 5 `run_id` linked to `trace_id` for cross-reference with Layer 1 pipeline runs
- Layer 4 `user_id` derived from `mcp_session_id` (was hardcoded `"default"`)
- Agent 0 LLM call moved from `_interpret` to `_execute` — no tokens burned before gate approval
- `DiffEngine.apply_diff()` accepts `workspace_root` parameter and rejects paths outside it
- `WorkspaceBridge` logs informative message for non-git workspaces (was silent pass)
- `WorkspaceBridge.iter_commits` limited to `max_count=5` (was materialising full history)
- `WorkspaceContext` gains `project_graph` field (was missing, blocking Layer 3 archival)
- `_PostMortemRow` gains `project_id` column — `get_recent_failures` filters by project
- `PipelineHistoryStore.save_run` uses `INSERT ... ON CONFLICT DO UPDATE` (was delete+insert)
- `GroqAdapter.astream()` uses real SSE streaming (was blocking `ainvoke` with single yield)
- `GroqAdapter.ainvoke()` has tenacity retry with exponential backoff on 429 responses
- CI workflows upgraded: `actions/checkout@v4`, `actions/setup-python@v5`, Node 20 LTS
- CI adds pip caching, mypy (advisory), semgrep scoped to source dirs, 60% coverage threshold
- Release workflow adds `environment: production` protection on all publish jobs
- `ruff line-length` raised from 88 to 100

### Fixed
- `pyproject.toml` wheel now ships all 14 Python packages and 22 runtime dependencies
- HITL gate in `gather_requirements` checks correct output keys per agent
- `recall_context` uses Pydantic attribute access on `MemoryContext` (was dict subscript, crashed)
- `groq/llama-3.3-70b-specdec` replaced with `groq/llama-3.3-70b-versatile` (model decommissioned)
- All placeholder model names replaced with real API strings
- Database password removed from source — reads from `DATABASE_URL` environment variable
- SQLite connection in `requirements_tool` closed with context manager (was leaking file descriptors)
- `asyncio.get_event_loop()` replaced with `get_running_loop()` throughout (deprecated in 3.12)
- `embed_documents` and `embed_query` wrapped in `run_in_executor` (was blocking the event loop)
- Security gate loaded from LangGraph checkpoint in `deploy_tool` (was always `None`, gate bypassed)
- `api_key_source` field uses valid `Literal["byok","subscription","free_tier"]` values
- `chromadb.PersistentClient()` guarded against `None` when chromadb is not installed
- Agent 5 Pass 4 returns `ADVISORY` for non-Python files (was silently returning empty list)
- Agent 7 `_ACTION_DEFAULTS` uses real action versions — `checkout@v4`, `setup-python@v5`
- Agent 13 topological sort handles plain string services from Agent 0 output
- `MemoryArchiver._archive_layer3` reconstructs `ProjectContextGraph` from dict before saving
- `DASTRunner` SQLi detection branch implemented (was empty, never fired)
- All lazy imports (`fastmcp`, `gitpython`, `chromadb`, `keyring`, `langchain_huggingface`) guarded with `try/except ImportError` so tests collect in environments without heavy deps
- 794 ruff lint errors resolved

---

## [1.0.0] — 2026-04-20

### Added
- MCP server with 11 tools: `gather_requirements`, `design_architecture`, `recall_context`,
  `save_decision`, `route_code_generation`, `run_security_scan`, `generate_cicd`,
  `deploy_project`, `setup_monitoring`, `generate_docs`, `track_progress`
- 14 agents (0–13), each owning one SDLC phase with HITL gate
- 5-layer cross-tool memory: pipeline history (PostgreSQL), organisational memory (ChromaDB),
  project context graph (PostgreSQL), user preferences (PostgreSQL), post-mortems (PostgreSQL)
- InterpretRecord audit trail across 13 named layers — no silent executions
- ToolRouter priority chain: Cursor → Claude Code → Devin → direct LLM fallback
- ModelRouter with 9 adapters, budget-aware routing, long-context routing (Gemini >100K tokens)
- AntiPatternDetector with 7 deterministic AST rules
- STRIDE threat model via o3-mini (OpenAI Responses API)
- ContextWindowManager with 14 `AgentContextSpec` definitions and compression
- Electron desktop app with system tray and companion panel
- VS Code extension with MCP config injection
- GitHub Actions CI/CD with Electron matrix build, PyPI and npm publish
- 353 Python tests (unit + integration), 19 VS Code extension tests
