from __future__ import annotations

import structlog
from pydantic import BaseModel, ConfigDict

logger = structlog.get_logger()

# ZERO LLM CALLS — keyword matching of PRD NFRs against RFC text only.
# Tests mock ModelRouter and assert route() was never called.


class NFRCheck(BaseModel):
    model_config = ConfigDict(strict=True)

    nfr: str
    satisfied: bool
    evidence: str | None        # RFC keyword that satisfies the NFR
    failure_reason: str | None


class NFRSatisfiabilityChecker:
    """Deterministic NFR checker. Zero LLM calls.

    Maps PRD signal keywords to required RFC keywords.
    If a signal appears in the PRD but no required keyword appears in the RFC,
    the check fails. All operations are pure substring matching on lowercased text.
    """

    # Each rule: PRD signals that trigger the check → required RFC keywords
    NFR_RULES: list[dict[str, object]] = [
        {
            "signals": ["99.9%", "99.9 %", "three nines", "high availability"],
            "required_keywords": [
                "multi-az", "replica", "load balancer", "failover", "redundancy",
            ],
            "failure": "99.9% uptime requires replica/multi-AZ/load balancer in RFC",
        },
        {
            "signals": ["< 200ms", "200 ms", "low latency", "p95"],
            "required_keywords": [
                "cache", "cdn", "async", "index", "connection pool",
            ],
            "failure": "Sub-200ms latency requires caching/CDN/async in RFC",
        },
        {
            "signals": ["10,000 concurrent", "10000 concurrent", "high concurrency"],
            "required_keywords": [
                "horizontal scaling", "auto-scaling", "queue", "load balancer",
            ],
            "failure": "High concurrency requires horizontal scaling/queue in RFC",
        },
        {
            "signals": ["gdpr", "data protection", "right to erasure"],
            "required_keywords": [
                "encrypt", "deletion", "anonymi", "data retention", "gdpr",
            ],
            "failure": "GDPR requires encryption + deletion mechanism in RFC",
        },
        {
            "signals": ["hipaa", "phi", "health data"],
            "required_keywords": [
                "audit log", "access control", "encrypt", "hipaa",
            ],
            "failure": "HIPAA requires audit log + access control in RFC",
        },
    ]

    def check(self, prd_text: str, rfc_text: str) -> list[NFRCheck]:
        """Return a list of NFRCheck results for NFRs found in the PRD."""
        results: list[NFRCheck] = []
        prd_lower = prd_text.lower()
        rfc_lower = rfc_text.lower()

        for rule in self.NFR_RULES:
            signals = list(rule["signals"])  # type: ignore[arg-type]
            required_keywords = list(rule["required_keywords"])  # type: ignore[arg-type]
            failure_msg = str(rule["failure"])

            # Check if this NFR is mentioned in the PRD
            nfr_present = any(sig in prd_lower for sig in signals)
            if not nfr_present:
                continue

            # Check if any required keyword appears in the RFC
            satisfied_kw = next(
                (kw for kw in required_keywords if kw in rfc_lower),
                None,
            )
            results.append(
                NFRCheck(
                    nfr=signals[0],
                    satisfied=satisfied_kw is not None,
                    evidence=satisfied_kw,
                    failure_reason=None if satisfied_kw else failure_msg,
                )
            )

        logger.info(
            "nfr_satisfiability.checked",
            total=len(results),
            satisfied=sum(1 for r in results if r.satisfied),
            failed=sum(1 for r in results if not r.satisfied),
        )
        return results

    def all_satisfied(self, checks: list[NFRCheck]) -> bool:
        """Return True only if every check passed."""
        return all(c.satisfied for c in checks)