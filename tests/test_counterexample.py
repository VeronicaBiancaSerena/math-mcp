"""Tests for counterexample search semantics (evidence vs. strict disproof)."""

from __future__ import annotations

from conftest import call

DOMAIN_01 = [{"variable": "x", "kind": "real", "lower": "0", "upper": "1"}]


def test_counterexample_found_on_bounded_domain() -> None:
    # x**2 >= x is false on (0, 1).
    result = call(
        "verification_compute",
        "search_counterexample",
        {"left": "x**2", "relation": ">=", "right": "x", "variables": ["x"]},
        domains=DOMAIN_01,
        limits={"seed": 1},
    )
    assert result.ok
    assert result.status == "counterexample_found"
    assert result.certainty == "disproved"
    assert result.method == "counterexample"
    assert result.result_kind == "witness"
    assert "x" in result.result["assignment"]


def test_no_counterexample_is_evidence() -> None:
    result = call(
        "verification_compute",
        "search_counterexample",
        {"left": "x**2 + 1", "relation": ">", "right": "0", "variables": ["x"]},
        domains=DOMAIN_01,
        limits={"seed": 1},
    )
    assert result.ok
    assert result.status == "no_counterexample_found"
    assert result.certainty == "evidence"
    assert result.method == "numeric_sampling"


def test_counterexample_search_is_reproducible() -> None:
    args = (("left", "x"), ("relation", ">="), ("right", "x**2"), ("variables", ["x"]))
    payload = dict(args)
    r1 = call(
        "verification_compute",
        "search_counterexample",
        payload,
        domains=DOMAIN_01,
        limits={"seed": 99},
    )
    r2 = call(
        "verification_compute",
        "search_counterexample",
        payload,
        domains=DOMAIN_01,
        limits={"seed": 99},
    )
    assert r1.result == r2.result
