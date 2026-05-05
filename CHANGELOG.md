## [1.1.0] — 2026-05-05

### Fixed — Critical (P0)
- Fix #1/#33: pyproject.toml wheel now ships all 14 Python packages and 22 runtime dependencies (chromadb, langchain-core, openai, sqlalchemy, gitpython, watchdog, etc.) — pip install no longer crashes on import
- Fix #2: HITL gate in gather_requirements now checks correct state keys per agent (service_graph for Agent 0, prd for Agent 1, adr for Agent 2) — Agents 1 and 2 no longer bypass user review
- Fix #3/#100: memory_tool.py recall_context uses correct Pydantic attribute access (context.relevant_patterns) instead of dict subscript — recall_context no longer crashes on every call
- Fix #4: groq/llama-3.3-70b-specdec replaced with groq/llama-3.3-70b-versatile across all 21 occurrences — free-tier inference no longer returns 404
- Fix #5: gpt-5.4/gpt-5.4-mini/gemini-3.1-pro-preview replaced with gpt-4o/gpt-4o-mini/gemini-1.5-pro — all 62 fake model references now point to real APIs
- Fix #6: /health endpoint registered on server — smithery.yaml health check no longer returns 404
- Fix #48: actions/checkout@v4 and actions/setup-python@v5 — CI now actually runs (v6 did not exist)
- Fix #49: electron/package.json name changed to @forgesdlc/agent — npx @forgesdlc/agent now works
- Fix #66/#67: deploy_tool loads security_gate from checkpoint — security gate no longer bypassed; removed duplicate dict key
- Fix #98: BUDGET_DOWNGRADE_CHAIN now contains only valid live model strings

### Fixed — High (P1)
- Fix #7: DB password no longer hardcoded in source — reads from DATABASE_URL env var
- Fix #9: SQLite connection closed with context manager — no more file descriptor leak
- Fix #14: server.py uses single PORT reference — log and bind can no longer diverge
- Fix #17: OrgMemory uses shared embeddings singleton — 90MB model loaded once not per-call
- Fix #18/#123: embed_documents/embed_query wrapped in run_in_executor — event loop no longer blocked
- Fix #20: GroqAdapter.astream() now uses real SSE streaming — token-by-token delivery works
- Fix #21: GroqAdapter.ainvoke() has tenacity retry with exponential backoff on 429 rate limits
- Fix #22/#101: asyncio.get_event_loop() replaced with get_running_loop() — no Python 3.12 deprecation
- Fix #23: WorkspaceBridge.get_context() raises RuntimeError instead of silently returning None
- Fix #25: ANTHROPIC_API_KEY added to .env.example
- Fix #34: Dead code block removed from MemoryArchiver._archive_layer2
- Fix #35/#36: Agent 0 LLM call moved from _interpret to _execute — no API tokens burned before gate approval
- Fix #39: DiffEngine path traversal guard added — writes outside workspace root rejected
- Fix #40: WorkspaceBridge uses iter_commits(max_count=5) — no more full history materialisation
- Fix #44: GroqAdapter logs token usage from API response
- Fix #51: MCP server default host changed to 127.0.0.1 — no unauthenticated LAN exposure
- Fix #75/#102: python3/sys.executable replaces hardcoded 'python' in Electron and DASTRunner
- Fix #80: CHANGELOG now accurately reflects model fix status
- Fix #111: WorkspaceContext gains project_graph field — Layer 3 archival no longer always skipped
- Fix #112/#124: init_db() called at server startup — PostgreSQL tables created automatically
- Fix #113: PostMortemStore.get_recent_failures filters by project_id — no cross-project contamination
- Fix #114: user_id derived from mcp_session_id — Layer 4 preferences no longer shared globally
- Fix #116: OrgMemory n_results guard corrected
- Fix #118: project_id column added to _PostMortemRow schema

### Fixed — Medium (P2)
- Fix #8: budget_remaining_usd initialised correctly (0.0 for free tier) instead of hardcoded 99
- Fix #11: assert in interpret/loop.py replaced with proper TypeError raise
- Fix #15: gather_requirements validates prompt length and project_id at tool boundary
- Fix #53: ProviderResolver.print_table() called at startup — provider status logged on boot

---


# Changelog

## [1.0.0] — Session 20 — 392 tests — PUBLIC RELEASE

### Products Shipped
- **forgeSDLC MCP Server v1.0.0** — `@forgesdlc/agent` on npm, `forgesdlc-mcp` on pip
- **forgeSDLC Desktop v1.0.0** — `.exe` (Windows NSIS) / `.dmg` (macOS) / `.deb` (Linux)
- **forgeSDLC VS Code Extension v0.1.0** — VS Code Marketplace (`Akash-1512.forgesdlc`)

### Full Single-Service Pipeline (8 HITL-gated stages)
`gather_requirements` → `design_architecture` → `route_code_generation` →
`run_security_scan` → `generate_cicd` → `deploy_project` → `setup_monitoring` →
`generate_docs`

### Multi-Service Pipeline (Agents 11-13, fires on multi_service architecture)
Cross-service integration tests (gemini 1M ctx) → Pact consumer contracts →
OTel trace propagation + Docker Compose (topological deploy order)

### Infrastructure Highlights
- 5-layer cross-tool memory: OrgMemory (ChromaDB) + PostgreSQL + ProjectContextGraph
  + UserPreferences + PostMortemRecords
- 13 InterpretRecord layers — zero silent executions
- 14 agents (0-13) — each owns one SDLC phase
- ToolRouter: Cursor → Claude Code → Devin → Direct LLM fallback chain
- ModelRouter: 9 adapters, budget-aware routing, long-context (gemini >100K tokens)
- AntiPatternDetector: 7 deterministic AST rules, zero LLM
- STRIDE threat model via o3-mini (Responses API)
- ContextWindowManager: 14 AgentContextSpecs, compression, token estimation

### Security
- SAST: bandit + semgrep (p/python + p/security — never --config=auto)
- DAST: uvicorn subprocess (RUN_DAST=true)
- Secrets: detect-secrets scan
- Gate: HIGH/CRITICAL findings block deployment via graph conditional edge

### Electron Desktop
- contextIsolation: true, nodeIntegration: false (non-negotiable)
- System tray with HITL gate notifications
- [✅ Approve] → "100% GO" (internal — never shown in UI)
- ServerManager: PYTHON_PATH → "python" fallback, auto-restart on crash
- first_launch: writes ~/.cursor/mcp.json (global Cursor config)

### MCP Registry Listings
- mcp.so
- Smithery (smithery.yaml in repo root)
- mcpservers.org

### Legal
- EU AI Act: GPAI classification, Articles 52-55 documented
- GDPR DPA template for enterprise customers
- Privacy policy: API keys in OS keychain, no central servers
- Cursor API: documented stance, CURSOR_API_VERIFIED guard

---


All notable changes to forgeSDLC are documented here.
Format: `## [version] — Session NN — N tests — capability`

---

## [Unreleased] — Session 19 — 392 tests

### Added
- Commercial readiness check script (`scripts/commercial_readiness_check.py`)
- Legal documents: Cursor API review, EU AI Act checklist, GDPR DPA template, privacy policy
- Cross-tool memory demo (`demos/cross_tool_memory_demo.py`)
- README: pricing table, two install paths, 11-tool reference table
- CI: commercial readiness check step

---

## [0.9.0] — Session 16 — 346 tests

### Added
- Agent 11 (IntegrationAgent): cross-service integration tests, gemini-3.1-pro-preview via long-context router (150K tokens)
- Agent 12 (ContractAgent): Pact consumer-driven contract tests, skips without openapi.yaml
- Agent 13 (PlatformAgent): OTel trace propagation + Docker Compose, Kahn's topological sort for deploy order
- VS Code extension: adds forgeSDLC to `.vscode/mcp.json`, idempotent merge, works in VS Code + Cursor + Windsurf
- Silent skip pattern: Agents 11-13 leave zero interpret_log entries on monolith architecture

---

## [0.8.0] — Session 15 — 335 tests

### Added
- Agent 10 (DocsAgent): README + CHANGELOG generation, Known Limitations from state (never hardcoded)
- BYOK model selection: `claude-sonnet-4-6` when Anthropic key set, `gpt-5.4-mini` fallback
- Attribution "Built with forgeSDLC" always appended unconditionally after model output
- ProjectContextGraph saved to Layer 3 memory — `recall_context()` now returns rich structured context
- Comprehensive 5-layer MemoryArchiver write at pipeline completion
- `generate_docs()` MCP tool live — returns `pipeline_complete: True`
- Single-service pipeline fully complete (Agents 0-10)

---

## [0.7.0] — Session 14 — 323 tests

### Added
- Agent 8 (DeployAgent): HardGate (`hard_gate=True`), security gate pre-check before interpret_node
- Cold start warning always shown in Agent 8 interpret (content varies by tier, presence is invariant)
- Agent 9 (MonitoringAgent): groq/llama-3.3-70b-specdec (regression guard test), SLOs from PRD NFRs
- RenderTool: L8 InterpretRecord before every webhook call and health poll
- PostMortem written to Layer 5 on deployment failure
- Dockerfile: multi-stage, non-root UID 1000, HEALTHCHECK on /health
- `deploy_project()` + `setup_monitoring()` MCP tools live
- Full pipeline end-to-end: requirements → architecture → code → security → CI/CD → deploy → monitor

---

## [0.6.0] — Session 12 — 278 tests

### Added
- Agent 5b (SecurityAgent): SAST (bandit + semgrep p/python + p/security) + DAST + STRIDE via o3-mini
- Security gate: HIGH/CRITICAL findings block Agent 8 (deployment) via `orchestrator/graph.py` conditional edge
- `BanditRunner`, `SemgrepRunner` (never `--config=auto`), `PipAuditRunner`, `DASTRunner`
- DASTRunner emits L10 InterpretRecord before env check — always in audit trail
- `run_security_scan()` MCP tool live

---

## [0.5.0] — Session 10 — 239 tests

### Added
- Agent 3 (ArchitectureAgent): HardGate, MAANG standards gate (2-retry), anti-pattern detector
- Deterministic AST validation: `_check_maang_standards()` uses stdlib ast — zero LLM
- `AntPatternDetector`, `NFRSatisfiabilityChecker`, `ArchitectureScorer`
- Architecture scoring: weighted rubric, blocking on CRITICAL anti-patterns
- `design_architecture()` MCP tool live

---

## [0.4.0] — Session 09 — 210 tests

### Added
- Agents 0-2: `ServiceDecompositionAgent`, `RequirementsAgent`, `ArchitectureProposalAgent`
- 13-layer InterpretRecord system fully wired
- `gather_requirements()` MCP tool live — first end-to-end HITL flow
- ContextFileManager: writes AGENTS.md, CLAUDE.md, .cursorrules, copilot-instructions.md
- SqliteSaver HITL persistence: state survives process restart

---

## [0.3.0] — Session 06 — 144 tests

### Added
- ModelRouter: 13-provider fallback chain, LongContextRouter (gemini for >100K tokens)
- ProviderResolver: detects available providers from env vars at startup
- GeminiAdapter, OpenAIAdapter, GroqAdapter, ClaudeAdapter (BYOK)
- BYOKManager: API keys stored in OS keychain — never in plaintext
- Token tracking + budget monitoring per session
- FIM routing: fill-in-the-middle for code completion tasks
- Context compression: ContextWindowManager with token estimator

---

## [0.2.0] — Session 04 — 67 tests

### Added
- ToolRouter: detects Cursor / Claude Code / Copilot / Windsurf / Direct LLM
- FIM adapter for code completion
- WorkspaceBridge: git context, uncommitted files, branch detection
- DiffEngine: `.forgesdlc.bak` backups, reversible diffs, L3 InterpretRecord
- ContextWindowManager: token estimation, compression, per-agent specs
- Mode router: IDE, CLI, MCP transport detection

---

## [0.1.0] — Session 02 — 27 tests

### Added
- `recall_context()` MCP tool — the wedge product
- `save_decision()` MCP tool
- OrgMemory (ChromaDB PersistentClient): semantic search across sessions
- PipelineHistoryStore (PostgreSQL): run records survive server restart
- 5-layer memory architecture: OrgMemory + PipelineHistory + ProjectContextGraph + UserPrefs + PostMortem
- MemoryArchiver: comprehensive write across all 5 layers
- FastMCP server with streamable-HTTP transport
- Cross-tool memory proven: decision saved in Cursor retrievable in Claude Code

---

## Version Tag Summary

| Tag | Session | Tests | Milestone |
|-----|---------|-------|-----------|
| v0.1.0 | 02 | 27 | recall_context() + save_decision() live |
| v0.2.0 | 04 | 67 | ToolRouter + WorkspaceBridge + DiffEngine |
| v0.3.0 | 06 | 144 | ModelRouter + 13-provider fallback + BYOK |
| v0.4.0 | 09 | 210 | Agents 0-2 + gather_requirements() live |
| v0.5.0 | 10 | 239 | Agent 3 architecture + deterministic validation |
| v0.6.0 | 12 | 278 | Agent 5b security + SAST/DAST/STRIDE gate |
| v0.7.0 | 14 | 323 | Agents 8-9 + full pipeline end-to-end |
| v0.8.0 | 15 | 335 | Agent 10 docs + living memory + pipeline complete |
| v0.9.0 | 16 | 346 | Agents 11-13 multi-service + VS Code extension |
| v1.0.0 | 20 | TBD | npm/pip publish + Electron distributables + demo |
