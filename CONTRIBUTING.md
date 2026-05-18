# Contributing to forgeSDLC

## Getting Started

```bash
git clone https://github.com/Akash-1512/forgeSDLC
cd forgeSDLC
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Development Workflow

- Branch from `develop` for all changes
- Branch naming: `fix/short-description`, `feat/short-description`
- Run tests before submitting a PR: `python -m pytest tests/ -m "not slow"`
- Lint: `ruff check . && ruff format --check .`

## Pull Requests

- Keep PRs focused — one change per PR
- Include a test for any new behaviour or bug fix
- Update `CHANGELOG.md` under `[Unreleased]`
- Read `AGENTS.md` before modifying the agent pipeline or memory layers

## Reporting Bugs

Open an issue using the bug report template. Include the forgeSDLC version,
your MCP client, and the full error message including traceback.

## Security Issues

Do not open a public issue for security vulnerabilities.
See [SECURITY.md](SECURITY.md) for the disclosure process.
