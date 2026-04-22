from __future__ import annotations

from unittest.mock import patch

from architecture_intelligence.nfr_satisfiability import NFRSatisfiabilityChecker


def test_99_9_uptime_satisfied_when_replica_in_rfc() -> None:
    checker = NFRSatisfiabilityChecker()
    prd = "System must achieve 99.9% uptime SLA."
    rfc = "We deploy with multi-az replica and load balancer for redundancy."
    results = checker.check(prd, rfc)
    uptime_checks = [r for r in results if "99.9" in r.nfr]
    assert len(uptime_checks) >= 1
    assert uptime_checks[0].satisfied is True
    assert uptime_checks[0].evidence is not None


def test_99_9_uptime_fails_when_no_replica_in_rfc() -> None:
    checker = NFRSatisfiabilityChecker()
    prd = "System must achieve 99.9% uptime."
    rfc = "Single server deployment with basic monitoring."
    results = checker.check(prd, rfc)
    uptime_checks = [r for r in results if "99.9" in r.nfr]
    assert len(uptime_checks) >= 1
    assert uptime_checks[0].satisfied is False
    assert uptime_checks[0].failure_reason is not None


def test_no_nfrs_in_prd_returns_empty_list() -> None:
    checker = NFRSatisfiabilityChecker()
    prd = "Build a simple todo app with basic CRUD."
    rfc = "FastAPI backend with PostgreSQL."
    results = checker.check(prd, rfc)
    assert results == []


def test_all_satisfied_true_when_all_checks_pass() -> None:
    checker = NFRSatisfiabilityChecker()
    from architecture_intelligence.nfr_satisfiability import NFRCheck

    checks = [
        NFRCheck(nfr="99.9%", satisfied=True, evidence="replica", failure_reason=None),
        NFRCheck(nfr="< 200ms", satisfied=True, evidence="cache", failure_reason=None),
    ]
    assert checker.all_satisfied(checks) is True


def test_all_satisfied_false_when_any_check_fails() -> None:
    checker = NFRSatisfiabilityChecker()
    from architecture_intelligence.nfr_satisfiability import NFRCheck

    checks = [
        NFRCheck(nfr="99.9%", satisfied=True, evidence="replica", failure_reason=None),
        NFRCheck(nfr="< 200ms", satisfied=False, evidence=None, failure_reason="needs cache"),
    ]
    assert checker.all_satisfied(checks) is False


def test_no_llm_calls_in_checker() -> None:
    """NFRSatisfiabilityChecker must never call ModelRouter — zero LLM."""
    from model_router.router import ModelRouter

    with patch.object(ModelRouter, "route") as mock_route:
        checker = NFRSatisfiabilityChecker()
        checker.check("99.9% uptime required.", "multi-az replica deployed.")
        mock_route.assert_not_called()
