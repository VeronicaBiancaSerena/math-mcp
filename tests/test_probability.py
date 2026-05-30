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


def test_simulation_estimate_in_tolerance_and_records_seed() -> None:
    # A seeded Monte Carlo coin estimate should land near the true probability 0.5, and
    # the seed/trials/hits must be surfaced for auditability (guide §13.2/§13.3).
    result = call(
        "probability_compute",
        "probability_simulation",
        {"experiment": "coin", "trials": 20000, "target": "1"},
        limits={"seed": 123},
    )
    assert result.ok and result.result_kind == "value"
    assert abs(float(result.result) - 0.5) < 0.05
    assert result.metadata.get("seed") == 123
    assert result.metadata.get("trials") == 20000
    assert 0 <= result.metadata.get("hits") <= 20000
    assert "Monte Carlo estimate is statistical evidence, not a proof" in result.warnings


def test_simulation_default_seed_is_surfaced() -> None:
    result = call(
        "probability_compute",
        "probability_simulation",
        {"experiment": "dice", "trials": 1000, "sides": 6, "target": "6"},
    )
    assert result.ok
    assert result.metadata.get("seed") is not None
