.PHONY: run-local run-prod mode db-start db-stop db-logs install test lint

# ── Local dev (Groq + ChromaDB local + SQLite checkpoint + PostgreSQL Docker) ──
run-local:
	DATABASE_URL=postgresql+asyncpg://postgres:forgesdlc@localhost:5432/forgesdlc \
	python -m mcp_server.server

# ── Production (set DATABASE_URL env var to managed PostgreSQL URL) ──────────
run-prod:
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "ERROR: DATABASE_URL must be set for production run."; \
		echo "Example: export DATABASE_URL=postgresql+asyncpg://user:pass@host/db"; \
		exit 1; \
	fi
	python -m mcp_server.server

# ── Show active mode ──────────────────────────────────────────────────────────
mode:
	@echo "LOCAL mode: PostgreSQL=localhost:5432 | ChromaDB=./chroma_db"
	@echo "PROD  mode: PostgreSQL=\$$DATABASE_URL  | ChromaDB=./chroma_db"

# ── Database (local Docker postgres:16) ──────────────────────────────────────
db-start:
	docker run -d \
		-p 5432:5432 \
		-e POSTGRES_PASSWORD=forgesdlc \
		--name forgesdlc-db \
		postgres:16
	@echo "PostgreSQL started on localhost:5432 (password: forgesdlc)"

db-stop:
	docker stop forgesdlc-db && docker rm forgesdlc-db

db-logs:
	docker logs -f forgesdlc-db

# ── Dev setup ─────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	python -m pytest

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	ruff check . && ruff format --check .