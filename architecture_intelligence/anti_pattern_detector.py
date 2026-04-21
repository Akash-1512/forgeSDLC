from __future__ import annotations

from collections import Counter
from typing import Literal

import structlog
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger()

# ZERO LLM CALLS — deterministic string matching + graph traversal only.
# Tests mock ModelRouter and assert route() was never called.

_DOMAIN_KEYWORDS = [
    "auth", "payment", "notification", "user", "order", "inventory",
    "report", "analytics", "search", "email", "storage", "cache",
    "queue", "scheduler", "webhook",
]


class AntiPatternFinding(BaseModel):
    model_config = ConfigDict(strict=True)

    rule: int                               # 1-7
    severity: Literal["HIGH", "MEDIUM"]
    description: str
    service_affected: str | None
    blocking: bool                          # HIGH → True, MEDIUM → False


class AntiPatternResult(BaseModel):
    model_config = ConfigDict(strict=True)

    findings: list[AntiPatternFinding]
    high_count: int
    medium_count: int
    all_clear: bool                         # True ONLY when high_count == 0


class AntiPatternDetector:
    """7 deterministic anti-pattern rules. Zero LLM calls.

    HIGH findings block the gate (blocking=True).
    MEDIUM findings are advisory (blocking=False).
    Input: RFC text + ServiceGraph dict.
    """

    def detect(
        self, rfc_text: str, service_graph: dict[str, object]
    ) -> AntiPatternResult:
        findings: list[AntiPatternFinding] = []
        services = list(service_graph.get("services", []) or [])
        rfc_lower = rfc_text.lower()

        # ── Rule 1: God Service (HIGH) ──────────────────────────────────────
        # ServiceNode.responsibility mentions > 5 distinct domain keywords
        for svc in services:
            resp = str(svc.get("responsibility", "")).lower()
            domains_found = sum(1 for kw in _DOMAIN_KEYWORDS if kw in resp)
            if domains_found > 5:
                findings.append(AntiPatternFinding(
                    rule=1, severity="HIGH", blocking=True,
                    description=(
                        f"Service '{svc.get('name')}' handles {domains_found} "
                        f"distinct domains. Split into focused services."
                    ),
                    service_affected=str(svc.get("name", "")),
                ))

        # ── Rule 2: Synchronous Chain (HIGH) ────────────────────────────────
        # Depth-first traversal of depends_on chains, depth > 3
        def chain_depth(name: str, visited: set[str], depth: int) -> int:
            if name in visited or depth > 10:
                return depth
            visited.add(name)
            svc = next((s for s in services if s.get("name") == name), None)
            if not svc:
                return depth
            max_d = depth
            for dep in (svc.get("depends_on") or []):
                max_d = max(max_d, chain_depth(str(dep), visited.copy(), depth + 1))
            return max_d

        for svc in services:
            depth = chain_depth(str(svc.get("name", "")), set(), 0)
            if depth > 3:
                findings.append(AntiPatternFinding(
                    rule=2, severity="HIGH", blocking=True,
                    description=(
                        f"Synchronous chain depth {depth} starting at "
                        f"'{svc.get('name')}'. Add async messaging or caching."
                    ),
                    service_affected=str(svc.get("name", "")),
                ))

        # ── Rule 3: Shared Database (HIGH) ──────────────────────────────────
        # > 2 services sharing the same database name
        db_usage: Counter[str] = Counter(
            str(svc.get("database"))
            for svc in services
            if svc.get("database")
        )
        for db_name, count in db_usage.items():
            if count > 2:
                findings.append(AntiPatternFinding(
                    rule=3, severity="HIGH", blocking=True,
                    description=(
                        f"Database '{db_name}' shared by {count} services. "
                        f"Each service should own its data."
                    ),
                    service_affected=db_name,
                ))

        # ── Rule 4: Missing Circuit Breaker (MEDIUM) ────────────────────────
        _external_indicators = [
            "http://", "https://", "external", "third-party",
            "api.github", "stripe", "twilio", "sendgrid",
        ]
        _circuit_breaker_signals = [
            "circuit breaker", "circuit-breaker", "hystrix", "resilience4j",
        ]
        has_circuit_breaker = any(kw in rfc_lower for kw in _circuit_breaker_signals)
        for svc in services:
            deps = " ".join(str(d) for d in (svc.get("depends_on") or [])).lower()
            if any(ind in deps for ind in _external_indicators) and not has_circuit_breaker:
                findings.append(AntiPatternFinding(
                    rule=4, severity="MEDIUM", blocking=False,
                    description=(
                        f"External dependency in '{svc.get('name')}' "
                        f"without circuit breaker pattern."
                    ),
                    service_affected=str(svc.get("name", "")),
                ))
                break  # one finding per rule

        # ── Rule 5: Missing Cache for Read-Heavy NFR (MEDIUM) ───────────────
        _read_heavy_signals = [
            "read-heavy", "read heavy", "read-intensive",
            "1000 req/s", "10000 req/s", "high throughput",
        ]
        _cache_signals = ["redis", "memcached", "cdn", "cache", "caching"]
        if any(s in rfc_lower for s in _read_heavy_signals):
            if not any(s in rfc_lower for s in _cache_signals):
                findings.append(AntiPatternFinding(
                    rule=5, severity="MEDIUM", blocking=False,
                    description="Read-heavy workload without caching layer in RFC.",
                    service_affected=None,
                ))

        # ── Rule 6: Single Point of Failure (HIGH) ──────────────────────────
        _replica_signals = [
            "replica", "replication", "failover", "cluster",
            "primary", "standby", "multi-az", "high availability",
        ]
        data_owners = [s for s in services if s.get("owns_data", False)]
        if len(data_owners) == 1:
            if not any(sig in rfc_lower for sig in _replica_signals):
                findings.append(AntiPatternFinding(
                    rule=6, severity="HIGH", blocking=True,
                    description=(
                        f"'{data_owners[0].get('name')}' is a single point "
                        f"of failure. Add replicas or failover."
                    ),
                    service_affected=str(data_owners[0].get("name", "")),
                ))

        # ── Rule 7: Chatty Interface (MEDIUM) ───────────────────────────────
        # Service exposes > 5 synchronous endpoints
        for svc in services:
            exposed = list(svc.get("exposes") or [])
            sync_endpoints = [
                e for e in exposed
                if any(m in str(e).upper() for m in ["GET", "POST", "PUT", "DELETE", "PATCH"])
            ]
            if len(sync_endpoints) > 5:
                findings.append(AntiPatternFinding(
                    rule=7, severity="MEDIUM", blocking=False,
                    description=(
                        f"Service '{svc.get('name')}' exposes "
                        f"{len(sync_endpoints)} synchronous endpoints. "
                        f"Consider aggregation or GraphQL."
                    ),
                    service_affected=str(svc.get("name", "")),
                ))

        high_count = sum(1 for f in findings if f.severity == "HIGH")
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")

        logger.info(
            "anti_pattern_detector.complete",
            high_count=high_count,
            medium_count=medium_count,
        )
        return AntiPatternResult(
            findings=findings,
            high_count=high_count,
            medium_count=medium_count,
            all_clear=(high_count == 0),
        )