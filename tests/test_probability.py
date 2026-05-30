"""Tests for probability_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("probability_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("probability_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_simulation_is_evidence_only() -> None:
    result = call(
        "probability_compute",
        "probability_simulation",
        {"experiment": "coin", "trials": 2000, "target": "1"},
        limits={"seed": 7},
    )
    assert result.ok
    assert result.certainty == "evidence"
    assert result.method == "simulation"


def test_simulation_estimate_in_tolerance_and_records_seed() -> None:
    # A seeded Monte Carlo coin estimate should land near the true probability 0.5, and
    # the seed/trials/hits must be surfaced for auditability (guide §13.2/§13.3).
    result = call(
        "probability_compute",
        "probability_simulation",
        {"experiment": "coin", "trials": 20000, "target": "1"},
        limits={"seed": 123},
    )
    assert result.ok and result.result_kind == "value"
    assert abs(float(result.result) - 0.5) < 0.05
    assert result.metadata.get("seed") == 123
    assert result.metadata.get("trials") == 20000
    assert 0 <= result.metadata.get("hits") <= 20000
    assert "Monte Carlo estimate is statistical evidence, not a proof" in result.warnings


def test_simulation_default_seed_is_surfaced() -> None:
    result = call(
        "probability_compute",
        "probability_simulation",
        {"experiment": "dice", "trials": 1000, "sides": 6, "target": "6"},
    )
    assert result.ok
    assert result.metadata.get("seed") is not None


def test_distribution_moments_match_closed_form() -> None:
    # Differential (guide §15.5): binomial(n,p) mean = n*p, variance = n*p*(1-p).
    import sympy as sp

    mean = call("probability_compute", "distribution_moments",
                {"distribution": "binomial", "params": {"n": "10", "p": "1/2"},
                 "moment": "mean"})
    var = call("probability_compute", "distribution_moments",
               {"distribution": "binomial", "params": {"n": "10", "p": "1/2"},
                "moment": "variance"})
    assert mean.ok and sp.sympify(mean.result) == sp.Integer(10) * sp.Rational(1, 2)
    expected_var = sp.Integer(10) * sp.Rational(1, 2) * sp.Rational(1, 2)
    assert var.ok and sp.sympify(var.result) == expected_var


def test_probability_distribution_matches_combinatorics() -> None:
    # Differential (guide §15.5): binomial pmf(5; 10, 1/2) == C(10,5) / 2**10.
    import sympy as sp

    pmf = call("probability_compute", "probability_distribution",
               {"distribution": "binomial", "params": {"n": "10", "p": "1/2"},
                "query": "pmf", "at": "5"})
    comb = call("discrete_compute", "combinatorics_count",
                {"kind": "combination", "n": "10", "k": "5"})
    assert pmf.ok and comb.ok
    expected = sp.Rational(int(comb.result), 2 ** 10)
    assert sp.sympify(pmf.result) == expected


def test_random_variable_transform_linear() -> None:
    # E[2X+1] = 1 and Var[2X+1] = 4 for X ~ N(0,1).
    import sympy as sp

    m = call("probability_compute", "random_variable_transform",
             {"expression": "2*X + 1", "variable": "X", "transform": "mean"})
    v = call("probability_compute", "random_variable_transform",
             {"expression": "2*X + 1", "variable": "X", "transform": "variance"})
    assert m.ok and sp.sympify(m.result) == 1
    assert v.ok and sp.sympify(v.result) == 4


def test_markov_stationary_is_fixed_point() -> None:
    # Differential (guide §15.5): stationary pi must satisfy pi @ P == pi and sum to 1.
    import numpy as np

    P = np.array([[0.5, 0.5], [1 / 3, 2 / 3]])
    r = call("probability_compute", "markov_chain_analyze",
             {"transition_matrix": [["1/2", "1/2"], ["1/3", "2/3"]], "query": "stationary"})
    assert r.ok and r.certainty == "exact"
    pi = np.array(r.result["stationary_distribution"])
    assert np.allclose(pi @ P, pi, atol=1e-9)
    assert np.isclose(pi.sum(), 1.0)
