"""Tests for discrete_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
import sympy as sp
from conftest import call, load_golden

from math_mcp.parsing.sympy_parser import parse_expression


@pytest.mark.parametrize(
    "case", load_golden("discrete_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("discrete_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_finite_enumeration_requires_domain() -> None:
    result = call(
        "discrete_compute", "finite_enumeration", {"predicate": "Eq(x, 1)", "variables": ["x"]}
    )
    assert result.ok is False
    assert result.error_code == "DOMAIN_UNSUPPORTED"


def _recurrence(recurrence: str, **extra: object):  # type: ignore[no-untyped-def]
    payload = {"recurrence": recurrence, "function": "f", "variable": "n", **extra}
    return call("discrete_compute", "solve_recurrence", payload)


def test_solve_recurrence_geometric_with_initial_condition() -> None:
    result = _recurrence("f(n) - 2*f(n-1)", initial_conditions={"0": "1"})
    assert result.ok and result.status == "success"
    assert result.certainty == "exact"
    assert result.method == "symbolic"
    assert result.result_kind == "value"
    assert result.result == "2**n"
    assert result.result_latex is not None


def test_solve_recurrence_fibonacci_backward_form_values() -> None:
    # The classic backward-shift form f(n)=f(n-1)+f(n-2) must solve (this was the bug).
    result = _recurrence("f(n) - f(n-1) - f(n-2)", initial_conditions={"0": "0", "1": "1"})
    assert result.ok and result.certainty == "exact"
    sol = parse_expression(result.result, allowed_symbols={"n"})
    n = next(s for s in sol.free_symbols if s.name == "n")
    values = [int(sp.nsimplify(sol.subs(n, k))) for k in range(11)]
    assert values == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]


def test_solve_recurrence_general_solution_has_constant() -> None:
    # Without initial conditions a homogeneous recurrence yields a parametrized family.
    result = _recurrence("f(n) - 2*f(n-1)")
    assert result.ok and result.certainty == "exact"
    assert "2**n" in result.result
    assert any(s.name.startswith("C") for s in parse_expression(
        result.result, allowed_symbols=None
    ).free_symbols)


def test_solve_recurrence_requires_the_function() -> None:
    result = _recurrence("n - 1")
    assert result.ok is False
    assert result.status == "invalid_input"


def test_solve_recurrence_rejects_nonlinear() -> None:
    result = _recurrence("f(n) - f(n-1)*f(n-2)")
    assert result.ok is False
    assert result.status == "invalid_input"


def test_solve_recurrence_rejects_non_integer_shift() -> None:
    result = _recurrence("f(n) - f(2*n)")
    assert result.ok is False
    assert result.status == "invalid_input"


def test_solve_recurrence_unsolvable_is_unknown() -> None:
    # Harmonic-number recurrence has no elementary closed form -> honest "unknown".
    result = _recurrence("f(n) - f(n-1) - 1/n")
    assert result.ok is True
    assert result.status == "unknown"
    assert result.certainty == "unknown"
    assert result.result is None
