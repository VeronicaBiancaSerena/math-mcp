"""Tests for inequality_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("inequality_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("inequality_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_counterexample_search_finds_witness() -> None:
    result = call(
        "inequality_compute",
        "inequality_counterexample_search",
        {"left": "x**2", "relation": ">=", "right": "x", "variables": ["x"]},
        domains=[{"variable": "x", "kind": "real", "lower": "0", "upper": "1"}],
        limits={"seed": 1},
    )
    assert result.ok and result.certainty == "disproved"


def test_sample_no_counterexample_is_evidence() -> None:
    result = call(
        "inequality_compute",
        "inequality_sample",
        {"left": "x**2 + 1", "relation": ">", "right": "0", "variables": ["x"]},
        limits={"seed": 1},
    )
    assert result.ok and result.certainty == "evidence"
