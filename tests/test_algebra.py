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


def test_groebner_hidden_by_default() -> None:
    from math_mcp.tools.capabilities import get_capabilities

    ops = get_capabilities()["public_tools"]["algebra_compute"]["operations"]
    assert "groebner_basis" not in ops
