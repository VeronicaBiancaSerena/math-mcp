"""Tests for number_theory_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("number_theory_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("number_theory_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_inverse_requires_coprime() -> None:
    result = call(
        "number_theory_compute", "modular_arithmetic", {"kind": "inverse", "a": "4", "modulus": "8"}
    )
    assert result.ok is False
