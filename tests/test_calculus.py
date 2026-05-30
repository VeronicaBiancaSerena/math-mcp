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
