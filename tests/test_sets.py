"""Tests for set_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("set_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("set_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_power_set_size() -> None:
    result = call("set_compute", "power_set", {"set": ["1", "2", "3"]})
    assert result.ok and result.result["size"] == 8


def test_set_identity_disproved() -> None:
    result = call(
        "set_compute",
        "set_identity_check",
        {"left": "A & B", "right": "A | B", "variables": ["A", "B"]},
    )
    assert result.ok and result.certainty == "disproved"
