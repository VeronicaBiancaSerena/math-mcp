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
