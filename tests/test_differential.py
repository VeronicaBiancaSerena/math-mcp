"""Differential tests (guide §15.5): cross-check independent methods.

Each test confirms two independent routes to the same fact agree:

- algebra: symbolic expansion vs numeric evaluation at sampled points;
- inequality: symbolic interval solve vs pointwise membership sampling;
- Z3: small-integer satisfiability vs brute-force finite enumeration;
- matrix: SymPy exact determinant vs NumPy numeric determinant within tolerance;
- probability: handler finite enumeration (uniform_finite) vs an independent ratio.

When the two methods disagree the test fails loudly; it never silently picks one.
"""

from __future__ import annotations

import numpy as np
import sympy as sp
from conftest import call
from hypothesis import given, settings
from hypothesis import strategies as st

from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.runtime.serialization import to_text

_COEF = st.integers(min_value=-5, max_value=5)
_ENTRY = st.integers(min_value=-9, max_value=9)
_ROW2 = st.tuples(_ENTRY, _ENTRY)
_MAT2 = st.tuples(_ROW2, _ROW2)
_SAMPLE_POINTS = (-3, -1, 0, 2, 5)


@settings(max_examples=30, deadline=None)
@given(_COEF, _COEF, _COEF)
def test_algebra_expand_matches_numeric_sampling(a: int, b: int, c: int) -> None:
    expr_str = f"({a}*x + {b})*(x + {c})"
    result = call(
        "algebra_compute", "expand_expression", {"expression": expr_str, "variables": ["x"]}
    )
    assert result.ok, result.error
    x = sp.Symbol("x")
    original = (a * x + b) * (x + c)
    expanded = parse_expression(str(result.result), allowed_symbols={"x"})
    for v in _SAMPLE_POINTS:
        assert sp.simplify(original.subs(x, v) - expanded.subs(x, v)) == 0


def test_inequality_interval_matches_sampling() -> None:
    result = call(
        "inequality_compute",
        "inequality_domain_solve",
        {"expression": "x**2 - 1", "relation": ">=", "variable": "x"},
    )
    assert result.ok, result.error
    x = sp.Symbol("x", real=True)
    sol = sp.solve_univariate_inequality(x**2 - 1 >= 0, x, relational=False)
    # The handler's symbolic interval result agrees with an independent SymPy solve...
    assert result.result == to_text(sol)
    # ...and membership of that set agrees with pointwise evaluation of the inequality.
    for t in range(-6, 7):
        v = sp.Rational(t, 2)
        assert bool(sol.contains(v)) == bool((v**2 - 1) >= 0)


def test_z3_sat_matches_finite_enumeration() -> None:
    payload = {
        "variables": {"x": "Int", "y": "Int"},
        "constraints": [
            {
                "op": "eq",
                "left": {"op": "add", "args": [{"var": "x"}, {"var": "y"}]},
                "right": {"int": 10},
            },
            {"op": "gt", "left": {"var": "x"}, "right": {"var": "y"}},
            {"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
            {"op": "gt", "left": {"var": "y"}, "right": {"int": 0}},
        ],
    }
    result = call("z3_compute", "z3_satisfiability", payload)
    assert result.ok, result.error
    exists = any(
        x + y == 10 and x > y and x > 0 and y > 0
        for x in range(0, 11)
        for y in range(0, 11)
    )
    assert result.result["satisfiable"] == exists


def test_z3_unsat_matches_finite_enumeration() -> None:
    payload = {
        "variables": {"x": "Int"},
        "constraints": [
            {"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
            {"op": "lt", "left": {"var": "x"}, "right": {"int": 0}},
        ],
    }
    result = call("z3_compute", "z3_satisfiability", payload)
    exists = any(x > 0 and x < 0 for x in range(-50, 51))
    assert exists is False
    assert result.result["satisfiable"] is False


@settings(max_examples=25, deadline=None)
@given(_MAT2)
def test_matrix_det_sympy_matches_numpy(rows: tuple) -> None:
    payload = {"matrix": [[str(v) for v in row] for row in rows]}
    result = call("matrix_compute", "det", payload)
    assert result.ok, result.error
    exact = float(int(result.result))
    numeric = float(np.linalg.det(np.array(rows, dtype=float)))
    assert abs(exact - numeric) < 1e-6


def test_probability_finite_enumeration_matches_ratio() -> None:
    domains = [
        {"variable": "x", "kind": "integer", "lower": "1", "upper": "6"},
        {"variable": "y", "kind": "integer", "lower": "1", "upper": "6"},
    ]
    enumerated = call(
        "probability_compute",
        "event_probability",
        {"mode": "uniform_finite", "variables": ["x", "y"], "condition": "Eq(x + y, 7)"},
        domains=domains,
    )
    assert enumerated.ok, enumerated.error
    favorable = sum(1 for x in range(1, 7) for y in range(1, 7) if x + y == 7)
    ratio = call(
        "probability_compute",
        "event_probability",
        {"mode": "ratio", "favorable": str(favorable), "total": "36"},
    )
    assert enumerated.result == ratio.result
