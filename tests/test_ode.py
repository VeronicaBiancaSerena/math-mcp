"""Tests for ode_compute (golden cases + error paths)."""

from __future__ import annotations

import math

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("ode_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("ode_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_verify_uses_second_derivative() -> None:
    result = call(
        "ode_compute",
        "ode_verify_solution",
        {"solution": "sin(x)", "variable": "x", "residual": "d2y + y"},
    )
    assert result.ok and result.certainty == "proved"


def test_ode_solve_numeric_matches_analytic_solution_as_evidence() -> None:
    # y' = y, y(0)=1 has the exact solution e^t. The numeric trajectory must match it
    # within tolerance and be reported as evidence, never a proof (guide §4.12/§10.6).
    result = call(
        "ode_compute",
        "ode_solve_numeric",
        {
            "expression": "y",
            "variable": "t",
            "function": "y",
            "t_span": ["0", "1"],
            "y0": ["1"],
            "points": 50,
        },
    )
    assert result.ok and result.status == "success"
    assert result.certainty == "evidence"
    assert result.method == "numeric_sampling"
    assert result.result_kind == "object"
    ts, ys = result.result["t"], result.result["y"]
    # Differential check: numeric trajectory vs the analytic solution e^t.
    assert max(abs(y - math.exp(t)) for t, y in zip(ts, ys, strict=False)) < 1e-3
    assert "numeric ODE integration is an approximate trajectory, not a proof" in result.warnings


def test_ode_solve_symbolic_verified() -> None:
    # Differential (guide §15.5): solve dy = y, then verify the solution satisfies the ODE.
    sol = call("ode_compute", "ode_solve_symbolic",
               {"equation": "dy - y", "function": "y", "variable": "x"})
    assert sol.ok and sol.result == "Eq(y(x), C1*exp(x))"
    verify = call("ode_compute", "ode_verify_solution",
                  {"solution": "C1*exp(x)", "variable": "x", "residual": "dy - y",
                   "parameters": ["C1"]})
    assert verify.ok and verify.certainty == "proved"


def test_ode_ivp_satisfies_condition_and_ode() -> None:
    ivp = call("ode_compute", "ode_initial_value_solve",
               {"equation": "dy - y", "function": "y", "variable": "x",
                "initial_conditions": {"0": "1"}})
    assert ivp.ok and ivp.result == "Eq(y(x), exp(x))"
    verify = call("ode_compute", "ode_verify_solution",
                  {"solution": "exp(x)", "variable": "x", "residual": "dy - y"})
    assert verify.ok and verify.certainty == "proved"


def test_ode_classify_identifies_linear() -> None:
    r = call("ode_compute", "ode_classify",
             {"equation": "dy - y", "function": "y", "variable": "x"})
    assert r.ok and "1st_linear" in r.result["classification"]
