"""Tests for probability_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("probability_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("probability_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_simulation_is_evidence_only() -> None:
    result = call(
        "probability_compute",
        "probability_simulation",
        {"experiment": "coin", "trials": 2000, "target": "1"},
        limits={"seed": 7},
    )
    assert result.ok
    assert result.certainty == "evidence"
    assert result.method == "simulation"
