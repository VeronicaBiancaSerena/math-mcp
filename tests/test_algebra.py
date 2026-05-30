"""Tests for algebra_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("algebra_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("algebra_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_missing_required_field() -> None:
    result = call("algebra_compute", "solve_equation", {"expression": "x**2 - 1"})
    assert result.ok is False
    assert result.status == "invalid_input"


def test_groebner_visible_after_promotion() -> None:
    # groebner_basis was promoted experimental -> implemented; it is now visible by default.
    from math_mcp.tools.capabilities import get_capabilities

    ops = get_capabilities()["public_tools"]["algebra_compute"]["operations"]
    assert "groebner_basis" in ops
    assert ops["groebner_basis"]["state"] == "implemented"


def test_groebner_basis_is_ideal_equivalent() -> None:
    # Differential check (guide §15.5): every input polynomial must reduce to 0 modulo the
    # returned basis, i.e. the basis generates the same ideal.
    import sympy as sp

    x, y = sp.symbols("x y")
    polys = [x**2 + y**2 - 1, x - y]
    result = call(
        "algebra_compute",
        "groebner_basis",
        {"polynomials": ["x**2 + y**2 - 1", "x - y"], "variables": ["x", "y"]},
    )
    assert result.ok and result.certainty == "exact"
    basis = [sp.sympify(g) for g in result.result]
    for p in polys:
        _q, r = sp.reduced(p, basis, x, y, order="lex")
        assert sp.simplify(r) == 0
