"""Tests for ode_compute (golden cases + error paths)."""

from __future__ import annotations

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
