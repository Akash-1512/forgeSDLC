from __future__ import annotations

from unittest.mock import patch

from architecture_intelligence.anti_pattern_detector import AntiPatternDetector


def _make_svc(
    name: str,
    responsibility: str = "",
    depends_on: list[str] | None = None,
    database: str | None = None,
    owns_data: bool = False,
    exposes: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "responsibility": responsibility,
        "depends_on": depends_on or [],
        "database": database,
        "owns_data": owns_data,
        "exposes": exposes or [],
    }


def test_god_service_detected_when_responsibility_mentions_6_domains() -> None:
    detector = AntiPatternDetector()
    svc = _make_svc(
        "monolith",
        responsibility="handles auth payment notification user order inventory analytics",
    )
    result = detector.detect("", {"services": [svc]})
    high_findings = [f for f in result.findings if f.rule == 1 and f.severity == "HIGH"]
    assert len(high_findings) >= 1
    assert result.all_clear is False


def test_god_service_not_detected_for_5_or_fewer_domains() -> None:
    detector = AntiPatternDetector()
    svc = _make_svc(
        "api",
        responsibility="handles auth payment notification user order",  # exactly 5
    )
    result = detector.detect("", {"services": [svc]})
    rule1_findings = [f for f in result.findings if f.rule == 1]
    assert len(rule1_findings) == 0


def test_synchronous_chain_depth_4_fails_with_high() -> None:
    detector = AntiPatternDetector()
    # A → B → C → D → E (depth 4)
    services = [
        _make_svc("A", depends_on=["B"]),
        _make_svc("B", depends_on=["C"]),
        _make_svc("C", depends_on=["D"]),
        _make_svc("D", depends_on=["E"]),
        _make_svc("E"),
    ]
    result = detector.detect("", {"services": services})
    rule2_findings = [f for f in result.findings if f.rule == 2 and f.severity == "HIGH"]
    assert len(rule2_findings) >= 1
    assert result.all_clear is False


def test_synchronous_chain_depth_3_passes() -> None:
    detector = AntiPatternDetector()
    # A → B → C → D (depth 3 — exactly at limit)
    services = [
        _make_svc("A", depends_on=["B"]),
        _make_svc("B", depends_on=["C"]),
        _make_svc("C", depends_on=["D"]),
        _make_svc("D"),
    ]
    result = detector.detect("", {"services": services})
    rule2_findings = [f for f in result.findings if f.rule == 2]
    assert len(rule2_findings) == 0


def test_shared_database_3_services_fails_with_high() -> None:
    detector = AntiPatternDetector()
    services = [
        _make_svc("svc_a", database="postgres_main"),
        _make_svc("svc_b", database="postgres_main"),
        _make_svc("svc_c", database="postgres_main"),
    ]
    result = detector.detect("", {"services": services})
    rule3_findings = [f for f in result.findings if f.rule == 3 and f.severity == "HIGH"]
    assert len(rule3_findings) >= 1
    assert result.all_clear is False


def test_shared_database_2_services_passes() -> None:
    detector = AntiPatternDetector()
    services = [
        _make_svc("svc_a", database="postgres_main"),
        _make_svc("svc_b", database="postgres_main"),
    ]
    result = detector.detect("", {"services": services})
    rule3_findings = [f for f in result.findings if f.rule == 3]
    assert len(rule3_findings) == 0


def test_all_clear_true_when_no_high_findings() -> None:
    detector = AntiPatternDetector()
    result = detector.detect("", {"services": []})
    assert result.all_clear is True
    assert result.high_count == 0


def test_all_clear_false_when_any_high_finding() -> None:
    detector = AntiPatternDetector()
    svc = _make_svc(
        "monolith",
        responsibility="auth payment notification user order inventory analytics reporting",
    )
    result = detector.detect("", {"services": [svc]})
    assert result.all_clear is False


def test_medium_finding_does_not_set_all_clear_false() -> None:
    detector = AntiPatternDetector()
    # Only trigger rule 5 (MEDIUM) — read-heavy without cache
    rfc = "This is a read-heavy system with high throughput requirements."
    result = detector.detect(rfc, {"services": []})
    medium_findings = [f for f in result.findings if f.severity == "MEDIUM"]
    assert len(medium_findings) >= 1
    # all_clear only cares about HIGH
    assert result.all_clear is True


def test_no_llm_calls_in_any_rule() -> None:
    """AntiPatternDetector must never call ModelRouter — zero LLM."""
    from model_router.router import ModelRouter

    with patch.object(ModelRouter, "route") as mock_route:
        detector = AntiPatternDetector()
        svc = _make_svc("api", responsibility="auth payment user order", database="db1")
        detector.detect("some rfc text with circuit breaker", {"services": [svc]})
        mock_route.assert_not_called()
