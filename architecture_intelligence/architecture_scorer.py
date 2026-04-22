from __future__ import annotations

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger()

# ZERO LLM CALLS — keyword count maps to 1-10 score via fixed lookup.
# Informational only — scores NEVER block the gate.
# Tests mock ModelRouter and assert route() was never called.


class ArchitectureScore(BaseModel):
    model_config = ConfigDict(strict=True)

    scalability: int = Field(ge=1, le=10)
    reliability: int = Field(ge=1, le=10)
    security: int = Field(ge=1, le=10)
    maintainability: int = Field(ge=1, le=10)
    cost: int = Field(ge=1, le=10)
    overall: float  # mean of 5 dimensions, rounded to 1 decimal


class ArchitectureScorer:
    """Deterministic 5-dimension architecture scorer. Zero LLM calls.

    Keyword hit count → fixed 1-10 score mapping:
      0 hits → 1  |  1-2 → 3  |  3-4 → 5  |  5-6 → 7  |  7+ → 9

    Scores are informational — they help the developer understand trade-offs
    but NEVER block the gate regardless of how low the scores are.
    Only AntiPatternDetector HIGH findings and NFR failures block.
    """

    DIMENSIONS: dict[str, list[str]] = {
        "scalability": [
            "horizontal scaling",
            "auto-scaling",
            "stateless",
            "queue",
            "load balancer",
            "sharding",
            "partitioning",
            "caching",
        ],
        "reliability": [
            "replica",
            "failover",
            "circuit breaker",
            "retry",
            "health check",
            "graceful degradation",
            "backup",
            "redundancy",
        ],
        "security": [
            "authentication",
            "authorization",
            "rbac",
            "encrypt",
            "tls",
            "jwt",
            "oauth",
            "api key",
            "rate limiting",
            "waf",
        ],
        "maintainability": [
            "opentelemetry",
            "logging",
            "tracing",
            "monitoring",
            "alert",
            "documentation",
            "api versioning",
            "ci/cd",
            "testing",
        ],
        "cost": [
            "serverless",
            "managed service",
            "auto-scaling",
            "spot instance",
            "right-sizing",
            "reserved",
            "cost estimate",
            "budget",
        ],
    }

    def score(self, rfc_text: str) -> ArchitectureScore:
        """Score the RFC across 5 dimensions using keyword matching."""
        rfc_lower = rfc_text.lower()
        scores: dict[str, int] = {}

        for dimension, keywords in self.DIMENSIONS.items():
            hits = sum(1 for kw in keywords if kw in rfc_lower)
            scores[dimension] = self._hits_to_score(hits)

        overall = round(sum(scores.values()) / len(scores), 1)
        logger.info("architecture_scorer.scored", scores=scores, overall=overall)

        return ArchitectureScore(
            scalability=scores["scalability"],
            reliability=scores["reliability"],
            security=scores["security"],
            maintainability=scores["maintainability"],
            cost=scores["cost"],
            overall=overall,
        )

    @staticmethod
    def _hits_to_score(hits: int) -> int:
        """Map keyword hit count to 1-10 score via fixed lookup."""
        if hits == 0:
            return 1
        if hits <= 2:
            return 3
        if hits <= 4:
            return 5
        if hits <= 6:
            return 7
        return 9
