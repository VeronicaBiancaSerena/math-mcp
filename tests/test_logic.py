"""Tests for logic_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("logic_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("logic_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_satisfiable_returns_model() -> None:
    result = call(
        "logic_compute", "logic_satisfiability", {"expression": "p | q", "variables": ["p", "q"]}
    )
    assert result.ok and result.result["satisfiable"] is True


def test_finite_quantifier_forall() -> None:
    result = call(
        "logic_compute",
        "finite_quantifier_check",
        {"quantifier": "forall", "predicate": "x**2 >= 0", "variables": ["x"]},
        domains=[{"variable": "x", "kind": "integer", "lower": "-3", "upper": "3"}],
    )
    assert result.ok and result.certainty == "proved"
