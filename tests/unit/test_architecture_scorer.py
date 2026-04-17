from __future__ import annotations

from unittest.mock import patch

import pytest

from architecture_intelligence.architecture_scorer import ArchitectureScorer


def test_zero_keywords_returns_score_of_1() -> None:
    scorer = ArchitectureScorer()
    result = scorer.score("")
    assert result.scalability == 1
    assert result.reliability == 1
    assert result.security == 1
    assert result.maintainability == 1
    assert result.cost == 1
    assert result.overall == 1.0


def test_high_keyword_density_returns_score_of_9() -> None:
    scorer = ArchitectureScorer()
    rfc = (
        "horizontal scaling auto-scaling stateless queue load balancer sharding "
        "partitioning caching replica failover circuit breaker retry health check "
        "graceful degradation backup redundancy authentication authorization rbac "
        "encrypt tls jwt oauth api key rate limiting waf opentelemetry logging "
        "tracing monitoring alert documentation api versioning ci/cd testing "
        "serverless managed service spot instance right-sizing reserved cost estimate budget"
    )
    result = scorer.score(rfc)
    assert result.scalability == 9
    assert result.reliability == 9
    assert result.security == 9
    assert result.maintainability == 9


def test_all_scores_between_1_and_10() -> None:
    scorer = ArchitectureScorer()
    result = scorer.score("some rfc with load balancer and logging and encryption")
    assert 1 <= result.scalability <= 10
    assert 1 <= result.reliability <= 10
    assert 1 <= result.security <= 10
    assert 1 <= result.maintainability <= 10
    assert 1 <= result.cost <= 10


def test_overall_is_mean_of_5_dimensions() -> None:
    scorer = ArchitectureScorer()
    result = scorer.score("")
    expected = round((1 + 1 + 1 + 1 + 1) / 5, 1)
    assert result.overall == expected


def test_no_llm_calls_in_scorer() -> None:
    """ArchitectureScorer must never call ModelRouter — zero LLM."""
    from model_router.router import ModelRouter
    with patch.object(ModelRouter, "route") as mock_route:
        scorer = ArchitectureScorer()
        scorer.score("some rfc with load balancer and replica and logging")
        mock_route.assert_not_called()