from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from typing import Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field

from interpret.record import InterpretRecord
from orchestrator.constants import HEALTH_CHECK_TIMEOUT_SECONDS

logger = structlog.get_logger()

# DAST runs against the app on this port — override via FORGESDLC_DAST_PORT
_DAST_PORT: str = os.getenv("FORGESDLC_DAST_PORT", "18080")


class SecurityFinding(BaseModel):
    model_config = ConfigDict(strict=True)

    tool: Literal["bandit", "semgrep", "pip_audit", "dast", "detect_secrets"]
    rule: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    file: str | None
    line: int | None = Field(default=None, ge=1)
    description: str
    fix_suggestion: str | None
    blocking: bool  # True for CRITICAL and HIGH


class SecurityFindings(BaseModel):
    model_config = ConfigDict(strict=True)

    bandit_findings: list[SecurityFinding]
    semgrep_findings: list[SecurityFinding]
    pip_audit_findings: list[SecurityFinding]
    dast_findings: list[SecurityFinding]
    detect_secrets_findings: list[SecurityFinding]
    threat_model_path: str | None
    gate_blocked: bool  # True if any HIGH or CRITICAL finding


def _emit_l10(component: str, action: str, code_path: str) -> None:
    """Emit InterpretRecord Layer 10 (security) before running any tool."""
    InterpretRecord(
        layer="security",
        component=component,
        action=action,
        inputs={"code_path": code_path},
        expected_outputs={"findings": "list[SecurityFinding]"},
        files_it_will_read=[code_path],
        files_it_will_write=[],
        external_calls=[f"{component} subprocess"],
        model_selected=None,
        tool_delegated_to=None,
        reversible=True,
        workspace_files_affected=[],
        timestamp=datetime.now(tz=UTC),
    )
    logger.info("interpret_record.security", layer="security", component=component)


class BanditRunner:
    """SAST for Python. Emits InterpretRecord L10 before subprocess."""

    async def run(self, code_path: str) -> list[SecurityFinding]:
        # L10 emitted BEFORE subprocess
        _emit_l10("BanditRunner", f"Running bandit SAST on {code_path}", code_path)
        try:
            proc = await asyncio.create_subprocess_exec(
                "bandit",
                "-r",
                code_path,
                "-f",
                "json",
                "-q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            return self._parse_bandit_json(stdout.decode(errors="replace"))
        except Exception as exc:
            logger.warning("bandit_runner.failed", error=str(exc))
            return []

    def _parse_bandit_json(self, output: str) -> list[SecurityFinding]:
        try:
            data = json.loads(output)
            findings: list[SecurityFinding] = []
            for result in data.get("results", []):
                severity = str(result.get("issue_severity", "LOW")).upper()
                if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
                    severity = "LOW"
                line_num = result.get("line_number")
                findings.append(
                    SecurityFinding(
                        tool="bandit",
                        rule=str(result.get("test_id", "B000")),
                        severity=severity,  # type: ignore[arg-type]
                        file=result.get("filename"),
                        line=int(line_num) if line_num and int(line_num) >= 1 else None,
                        description=str(result.get("issue_text", "")),
                        fix_suggestion=result.get("more_info"),
                        blocking=severity in ("CRITICAL", "HIGH"),
                    )
                )
            return findings
        except (json.JSONDecodeError, KeyError, ValueError):
            return []


class SemgrepRunner:
    """SAST with semgrep. ALWAYS uses p/python + p/security.

    CRITICAL: NEVER --config=auto.
    Tests verify this at subprocess argument level.
    """

    async def run(self, code_path: str) -> list[SecurityFinding]:
        # L10 emitted BEFORE subprocess
        _emit_l10("SemgrepRunner", f"Running semgrep SAST on {code_path}", code_path)
        try:
            proc = await asyncio.create_subprocess_exec(
                "semgrep",
                "--config=p/python",  # always — never --config=auto
                "--config=p/security",  # always — never --config=auto
                "--json",
                code_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            return self._parse_semgrep_json(stdout.decode(errors="replace"))
        except Exception as exc:
            logger.warning("semgrep_runner.failed", error=str(exc))
            return []

    def _parse_semgrep_json(self, output: str) -> list[SecurityFinding]:
        try:
            data = json.loads(output)
            findings: list[SecurityFinding] = []
            for result in data.get("results", []):
                severity = str(result.get("extra", {}).get("severity", "INFO")).upper()
                if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
                    severity = "INFO"
                line_num = result.get("start", {}).get("line")
                findings.append(
                    SecurityFinding(
                        tool="semgrep",
                        rule=str(result.get("check_id", "unknown")),
                        severity=severity,  # type: ignore[arg-type]
                        file=result.get("path"),
                        line=int(line_num) if line_num and int(line_num) >= 1 else None,
                        description=str(result.get("extra", {}).get("message", "")),
                        fix_suggestion=result.get("extra", {}).get("fix"),
                        blocking=severity in ("CRITICAL", "HIGH"),
                    )
                )
            return findings
        except (json.JSONDecodeError, KeyError, ValueError):
            return []


class PipAuditRunner:
    """Dependency CVE scanning. Skips gracefully if no requirements file."""

    async def run(self, workspace_path: str) -> list[SecurityFinding]:
        from pathlib import Path  # noqa: PLC0415

        # Find requirements file
        req_file: str | None = None
        for candidate in ["requirements.txt", "pyproject.toml"]:
            p = Path(workspace_path) / candidate
            if p.exists():
                req_file = str(p)
                break

        if req_file is None:
            logger.info("pip_audit_skipped", reason="no requirements file found")
            return []  # Graceful skip — not a failure

        _emit_l10("PipAuditRunner", f"Running pip-audit on {req_file}", req_file)
        try:
            proc = await asyncio.create_subprocess_exec(
                "pip-audit",
                "-r",
                req_file,
                "--format=json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            return self._parse_pip_audit_json(stdout.decode(errors="replace"))
        except Exception as exc:
            logger.warning("pip_audit_runner.failed", error=str(exc))
            return []

    def _parse_pip_audit_json(self, output: str) -> list[SecurityFinding]:
        try:
            data = json.loads(output)
            findings: list[SecurityFinding] = []
            for dep in data if isinstance(data, list) else []:
                for vuln in dep.get("vulns", []):
                    findings.append(
                        SecurityFinding(
                            tool="pip_audit",
                            rule=str(vuln.get("id", "CVE-UNKNOWN")),
                            severity="HIGH",
                            file=None,
                            line=None,
                            description=(
                                f"{dep.get('name', '')} {dep.get('version', '')}: "
                                f"{vuln.get('description', '')}"
                            ),
                            fix_suggestion=f"Upgrade to {vuln.get('fix_versions', ['latest'])}",
                            blocking=True,
                        )
                    )
            return findings
        except (json.JSONDecodeError, KeyError, ValueError):
            return []


class DASTRunner:
    """Dynamic Application Security Testing.

    KNOWN LIMITATION: Requires locally runnable application on port 18080.
    NOT CI-safe — skipped automatically when RUN_DAST != "true".
    InterpretRecord L10 is always emitted — even when skipped.
    """

    ATTACK_PAYLOADS = [
        # GET query-string SQLi
        {
            "path": "/api/users?id=1' OR '1'='1",
            "check": "multiple_results",
            "method": "GET",
        },
        # Path traversal
        {
            "path": "/files?path=../../etc/passwd",
            "check": "root_in_body",
            "method": "GET",
        },
        # Unauthenticated admin access
        {"path": "/admin", "check": "status_200", "method": "GET"},
        # POST body SQLi — tests login endpoint with tautology payload
        {
            "path": "/api/login",
            "check": "sqli_in_post",
            "method": "POST",
            "body": {"username": "admin' OR '1'='1", "password": "x"},
        },
    ]

    async def run(self, workspace_path: str) -> list[SecurityFinding]:
        # L10 emitted BEFORE the env var check (always fires for audit trail)
        _emit_l10(
            "DASTRunner",
            f"DAST scan on {workspace_path} (port 18080)",
            workspace_path,
        )

        if os.getenv("RUN_DAST", "false").lower() != "true":
            logger.info("dast_skipped", reason="RUN_DAST not set to true")
            return []  # Always empty when env var not set

        app_proc = None
        try:
            app_proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                _DAST_PORT,
                "--log-level",
                "error",
                cwd=workspace_path,
            )
            await self._wait_for_health(
                f"http://127.0.0.1:{_DAST_PORT}/health",
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            return await self._run_payloads()
        except Exception as exc:
            logger.warning("dast_failed", error=str(exc))
            return []
        finally:
            if app_proc:
                app_proc.terminate()
                import contextlib  # noqa: PLC0415

                with contextlib.suppress(Exception):
                    await asyncio.wait_for(app_proc.wait(), timeout=5)

    async def _wait_for_health(self, url: str, timeout: int) -> None:
        import time as _time

        import httpx  # noqa: PLC0415

        deadline = _time.monotonic() + timeout
        async with httpx.AsyncClient() as client:
            while _time.monotonic() < deadline:
                try:
                    r = await client.get(url, timeout=2)
                    if r.status_code == 200:
                        return
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        raise TimeoutError(f"DAST health check timed out after {timeout}s")

    async def _run_payloads(self) -> list[SecurityFinding]:
        import httpx  # noqa: PLC0415

        findings: list[SecurityFinding] = []
        async with httpx.AsyncClient(timeout=5) as client:
            for payload in self.ATTACK_PAYLOADS:
                try:
                    method = str(payload.get("method", "GET")).upper()
                    url = f"http://127.0.0.1:{_DAST_PORT}{payload['path']}"
                    if method == "POST":
                        body = payload.get("body", {})
                        r = await client.post(url, json=body)
                    else:
                        r = await client.get(url)
                    finding = self._check_response(r, payload)
                    if finding:
                        findings.append(finding)
                except Exception:
                    pass
        return findings

    def _check_response(
        self, response: object, payload: dict[str, object]
    ) -> SecurityFinding | None:
        try:
            status = getattr(response, "status_code", 999)
            text = str(getattr(response, "text", ""))
            check = str(payload["check"])

            if check == "status_200" and status == 200:
                return SecurityFinding(
                    tool="dast",
                    rule="auth_bypass",
                    severity="HIGH",
                    file=None,
                    line=None,
                    description=f"Admin endpoint accessible without authentication: {payload['path']}",  # noqa: E501
                    fix_suggestion="Add authentication middleware to /admin routes",
                    blocking=True,
                )

            if check == "root_in_body" and "root:" in text:
                return SecurityFinding(
                    tool="dast",
                    rule="path_traversal",
                    severity="CRITICAL",
                    file=None,
                    line=None,
                    description="Path traversal vulnerability: /etc/passwd content returned",
                    fix_suggestion="Validate and sanitise file path inputs. Use Path.resolve() and check is_relative_to(safe_root).",  # noqa: E501
                    blocking=True,
                )

            # Detect SQLi via tautology — more rows than expected or SQL error in response
            if check == "multiple_results" and status == 200:
                # Heuristic: SQLi tautology returns more rows than a normal single-user query
                # Signs: JSON array with more than 1 item, or error message containing SQL keywords
                sqli_indicators = [
                    '"id"' in text and text.count('"id"') > 1,  # multiple rows returned
                    "syntax error" in text.lower(),
                    "mysql" in text.lower() and "error" in text.lower(),
                    "postgresql" in text.lower() and "error" in text.lower(),
                    "ora-" in text.lower(),  # Oracle error
                    "sqlite" in text.lower() and "error" in text.lower(),
                ]
                if any(sqli_indicators):
                    return SecurityFinding(
                        tool="dast",
                        rule="sql_injection",
                        severity="CRITICAL",
                        file=None,
                        line=None,
                        description=f"Potential SQL injection via GET parameter: {payload['path']}",
                        fix_suggestion="Use parameterised queries / prepared statements. Never interpolate user input into SQL strings.",  # noqa: E501
                        blocking=True,
                    )

            # Successful login with SQLi tautology indicates auth bypass
            if check == "sqli_in_post" and status == 200:
                # Successful login with SQLi tautology payload indicates bypass
                auth_bypass_indicators = [
                    "token" in text.lower(),
                    "access_token" in text.lower(),
                    '"authenticated": true' in text,
                    '"success": true' in text,
                ]
                if any(auth_bypass_indicators):
                    return SecurityFinding(
                        tool="dast",
                        rule="sql_injection_auth_bypass",
                        severity="CRITICAL",
                        file=None,
                        line=None,
                        description="SQL injection authentication bypass: login succeeded with tautology payload",  # noqa: E501
                        fix_suggestion="Use parameterised queries for authentication. Hash and compare passwords, never query by plain password.",  # noqa: E501
                        blocking=True,
                    )

        except Exception:
            pass
        return None
