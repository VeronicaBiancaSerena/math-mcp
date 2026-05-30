"""Tests for trigonometry_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("trigonometry_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("trigonometry_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_trig_identity_disproved() -> None:
    result = call(
        "trigonometry_compute",
        "trig_identity_check",
        {"left": "sin(x)", "right": "cos(x)", "variables": ["x"]},
    )
    assert result.ok and result.certainty == "disproved"
