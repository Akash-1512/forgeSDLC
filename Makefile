.PHONY: run dev db-start db-stop db-logs install test lint check

DB_PASS ?= localdev

# ── Development server (local PostgreSQL + ChromaDB) ─────────────────────────
dev:
	DATABASE_URL=postgresql+asyncpg://postgres:$(DB_PASS)@localhost:5432/forgesdlc \
	python -m mcp_server.server

# ── Production (DATABASE_URL must be set externally) ─────────────────────────
run:
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "ERROR: set DATABASE_URL before running in production."; \
		exit 1; \
	fi
	python -m mcp_server.server

# ── Local PostgreSQL via Docker ───────────────────────────────────────────────
db-start:
	docker run -d \
		-p 5432:5432 \
		-e POSTGRES_PASSWORD=$(DB_PASS) \
		-e POSTGRES_DB=forgesdlc \
		--name forgesdlc-db \
		postgres:16
	@echo "PostgreSQL listening on localhost:5432 (DB_PASS=$(DB_PASS))"
	@echo "Override: make db-start DB_PASS=yourpass"

db-stop:
	docker stop forgesdlc-db && docker rm forgesdlc-db

db-logs:
	docker logs -f forgesdlc-db

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"
	pre-commit install

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/ -m "not slow"

test-all:
	python -m pytest tests/

# ── Lint / format ─────────────────────────────────────────────────────────────
lint:
	ruff check . && ruff format --check .

fix:
	ruff check . --fix && ruff format .

# ── Pre-release ───────────────────────────────────────────────────────────────
check:
	python scripts/commercial_readiness_check.py

context-stats:
	python -c "from context_management.agent_context_specs import print_spec_table; print_spec_table()"
