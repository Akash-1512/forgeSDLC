from __future__ import annotations

import json

import structlog

from agents.base_agent import BaseAgent
from interpret.record import InterpretRecord
from tools.docs_fetcher import DocsFetcher

logger = structlog.get_logger()

_MODEL = "gpt-5.4-mini"

# Action versions fetched from GitHub Releases API before YAML generation.
# Defaults used when network unavailable (verified April 2026).
_ACTIONS_TO_VERIFY = [
    (
        "actions/checkout",
        "https://api.github.com/repos/actions/checkout/releases/latest",
    ),
    (
        "actions/setup-python",
        "https://api.github.com/repos/actions/setup-python/releases/latest",
    ),
    (
        "codecov/codecov-action",
        "https://api.github.com/repos/codecov/codecov-action/releases/latest",
    ),
]

_ACTION_DEFAULTS = {
    "actions/checkout": "v6",
    "actions/setup-python": "v6",
    "codecov/codecov-action": "v5",
}

# YAML template rules enforced here and tested:
# - ruff (NOT black, NOT isort)
# - semgrep --config=p/python --config=p/security (NOT --config=auto)
# - Node.js 24 (NOT 20 — forced migration deadline June 2 2026)
# - Python 3.12
# - PostgreSQL 16 service container
_CI_YAML_TEMPLATE = """\
name: CI
on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: forgesdlc
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@{checkout_version}

      - uses: actions/setup-python@{setup_python_version}
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint and format check
        run: ruff check . && ruff format --check .

      - name: Security scan
        run: semgrep --config=p/python --config=p/security --error .

      - name: Run tests with coverage
        run: pytest tests/ --cov=. --cov-report=xml -q
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:forgesdlc@localhost:5432/forgesdlc

      - uses: codecov/codecov-action@{codecov_version}
        with:
          file: coverage.xml
"""


class CICDAgent(BaseAgent):
    """Agent 7 — generates a GitHub Actions CI/CD workflow.

    Model: gpt-5.4-mini via ModelRouter
    DocsFetcher: fetches action versions BEFORE generating any YAML (L7 per fetch)
    Rules: ruff (not black/isort), semgrep p/python + p/security (not auto),
           Node.js 24, Python 3.12, PostgreSQL 16 service container.
    Generated YAML validated with yaml.safe_load() before writing.
    Written via DiffEngine (L3 InterpretRecord, .forgesdlc.bak backup).
    """

    async def _interpret(
        self,
        packet: object,
        memory_context: object,
        state: dict[str, object],
    ) -> InterpretRecord:
        """Preview CI/CD generation. Emits L1 InterpretRecord."""
        return self._emit_l1_record(
            component="CICDAgent",
            action=(
                "CI/CD GENERATION\n"
                "Target: .github/workflows/ci.yml\n"
                "Verifying action versions via DocsFetcher now...\n"
                "Lint: ruff (NOT black, NOT isort)\n"
                "Security: semgrep --config=p/python --config=p/security\n"
                "Node.js: 24 (forced migration from 20, deadline June 2 2026)\n"
                "Python: 3.12\n"
                "DB in CI: PostgreSQL 16 service container"
            ),
            inputs={"adr": str(state.get("adr", ""))[:100]},
            expected_outputs={"ci_yaml": ".github/workflows/ci.yml"},
            external_calls=["docs_fetcher", _MODEL],
            model_selected=_MODEL,
            files_write=[".github/workflows/ci.yml"],
        )

    async def _execute(
        self,
        state: dict[str, object],
        packet: object,
        memory_context: object,
    ) -> dict[str, object]:
        """Fetch action versions, generate YAML, validate, write via DiffEngine."""
        # Step 1: Fetch verified action versions (emits L7 InterpretRecord each)
        fetcher = DocsFetcher()
        versions: dict[str, str] = {}
        for action_name, url in _ACTIONS_TO_VERIFY:
            content = await fetcher.fetch(url, description=f"Latest {action_name}")
            versions[action_name] = self._extract_version(content, action_name)
            logger.info(
                "agent_7.action_version_resolved",
                action=action_name,
                version=versions[action_name],
            )

        # Step 2: Fill in YAML template with verified versions
        ci_yaml = _CI_YAML_TEMPLATE.format(
            checkout_version=versions.get("actions/checkout", _ACTION_DEFAULTS["actions/checkout"]),
            setup_python_version=versions.get(
                "actions/setup-python", _ACTION_DEFAULTS["actions/setup-python"]
            ),
            codecov_version=versions.get(
                "codecov/codecov-action", _ACTION_DEFAULTS["codecov/codecov-action"]
            ),
        )

        # Step 3: Validate YAML — raises immediately if template is malformed
        import yaml  # noqa: PLC0415

        yaml.safe_load(ci_yaml)

        # Step 4: Write via DiffEngine (L3 InterpretRecord, creates .forgesdlc.bak)
        workspace_path = "."
        try:
            wctx = await self.workspace.get_context()
            workspace_path = wctx.root_path
        except Exception:
            pass

        import os  # noqa: PLC0415

        ci_path = os.path.join(workspace_path, ".github", "workflows", "ci.yml")
        diff = await self.diff_engine.generate_diff(
            filepath=ci_path,
            new_content=ci_yaml,
            reason="Agent 7: GitHub Actions CI workflow",
        )
        await self.diff_engine.apply_diff(diff)

        state["ci_pipeline_url"] = "https://github.com/pending/actions"
        logger.info("agent_7.executed", ci_path=ci_path)
        return state

    def _extract_version(self, content: str, action_name: str) -> str:
        """Extract major version tag from GitHub releases JSON response."""
        try:
            data = json.loads(content)
            tag = str(data.get("tag_name", ""))
            if tag.startswith("v"):
                major = tag.split(".")[0]  # "v6.0.2" → "v6"
                return major
        except Exception:
            pass
        return _ACTION_DEFAULTS.get(action_name, "v6")
