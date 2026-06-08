"""Tests for calculus_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("calculus_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("calculus_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_numeric_evaluate_rejects_free_symbol() -> None:
    result = call("calculus_compute", "numeric_evaluate", {"expression": "x + 1"})
    assert result.ok is False


def test_indefinite_integral_has_condition() -> None:
    result = call("calculus_compute", "integrate", {"expression": "2*x", "variable": "x"})
    assert result.ok and result.conditions


def test_numeric_optimize_finds_minimum_as_evidence() -> None:
    # Numeric local optimization is evidence, never a proof (guide §4.2/§10.6).
    result = call(
        "calculus_compute",
        "numeric_optimize",
        {"expression": "(x-3)**2 + 2", "variables": ["x"], "goal": "min"},
    )
    assert result.ok and result.status == "success"
    assert result.certainty == "evidence"
    assert result.method == "numeric_optimization"
    assert result.result_kind == "witness"
    # Cross-check the numeric optimum against the analytic minimum (x=3, value=2).
    assert abs(result.result["point"]["x"] - 3.0) < 1e-4
    assert abs(result.result["value"] - 2.0) < 1e-6
    assert "numeric local optimization is evidence, not a proof" in result.warnings


def test_numeric_optimize_unbounded_reports_convergence_failure() -> None:
    result = call(
        "calculus_compute",
        "numeric_optimize",
        {"expression": "x", "variables": ["x"], "goal": "min"},
    )
    assert result.ok is False
    assert result.error_code == "NUMERIC_CONVERGENCE_FAILED"


def test_numeric_optimize_requires_variables() -> None:
    result = call("calculus_compute", "numeric_optimize", {"expression": "x**2"})
    assert result.ok is False
    assert result.status == "invalid_input"


# --- constrained_optimize (guide §9/§24) -----------------------------------


def test_constrained_optimize_symbolic_lagrange() -> None:
    # min x^2 + y^2 s.t. x + y = 1  ->  x = y = 1/2, value = 1/2 (Lagrange critical point).
    result = call(
        "calculus_compute",
        "constrained_optimize",
        {
            "objective": "x**2 + y**2",
            "variables": ["x", "y"],
            "goal": "min",
            "constraints": [{"relation": "==", "left": "x + y", "right": "1"}],
            "method": "symbolic_lagrange",
        },
    )
    assert result.ok and result.status == "success"
    assert result.certainty == "evidence"  # candidate extremum, not a global-optimality proof
    assert result.method == "symbolic"
    assert result.result["optimum"] == {"x": "1/2", "y": "1/2"}
    assert result.result["value"] == "1/2"
    assert result.result["optimum_point_type"] == "local_min"  # reduced-Hessian classification
    assert result.metadata["method_detail"] == "symbolic_lagrange"


def test_constrained_optimize_lagrange_classifies_local_max() -> None:
    # max x*y s.t. x + y = 10  ->  (5,5); the reduced Hessian must classify it local_max.
    result = call(
        "calculus_compute",
        "constrained_optimize",
        {
            "objective": "x*y",
            "variables": ["x", "y"],
            "goal": "max",
            "constraints": [{"relation": "==", "left": "x + y", "right": "10"}],
            "method": "symbolic_lagrange",
        },
    )
    assert result.ok and result.result["optimum"] == {"x": "5", "y": "5"}
    assert result.result["optimum_point_type"] == "local_max"


def test_constrained_optimize_numeric_with_residuals() -> None:
    # max x*y s.t. x + y = 10  ->  x = y = 5, value = 25 (numeric local search, evidence).
    result = call(
        "calculus_compute",
        "constrained_optimize",
        {
            "objective": "x*y",
            "variables": ["x", "y"],
            "goal": "max",
            "constraints": [{"relation": "==", "left": "x + y", "right": "10"}],
            "method": "numeric",
            "start": ["1", "1"],
        },
    )
    assert result.ok and result.certainty == "evidence"
    assert result.method == "numeric_optimization"
    assert abs(result.result["value"] - 25.0) < 1e-4
    assert result.result["constraint_residuals"][0]["relation"] == "=="
    assert abs(result.result["constraint_residuals"][0]["residual"]) < 1e-6


def test_constrained_optimize_inequality_routes_to_numeric() -> None:
    # An inequality constraint cannot use symbolic_lagrange; it auto-routes to numeric.
    result = call(
        "calculus_compute",
        "constrained_optimize",
        {
            "objective": "x**2",
            "variables": ["x"],
            "goal": "min",
            "constraints": [{"relation": ">=", "left": "x", "right": "2"}],
        },
    )
    assert result.ok and result.certainty == "evidence"
    assert abs(result.result["point"]["x"] - 2.0) < 1e-3


def test_constrained_optimize_lagrange_rejects_inequality() -> None:
    result = call(
        "calculus_compute",
        "constrained_optimize",
        {
            "objective": "x**2",
            "variables": ["x"],
            "goal": "min",
            "constraints": [{"relation": ">=", "left": "x", "right": "2"}],
            "method": "symbolic_lagrange",
        },
    )
    assert result.ok is False
    assert result.status == "invalid_input"
