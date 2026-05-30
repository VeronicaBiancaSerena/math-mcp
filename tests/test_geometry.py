"""Tests for geometry_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("geometry_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("geometry_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_line_intersection() -> None:
    result = call(
        "geometry_compute",
        "geometry_intersection",
        {
            "object1": {"type": "line", "a": "1", "b": "-1", "c": "0"},
            "object2": {"type": "line", "a": "1", "b": "1", "c": "-2"},
        },
    )
    assert result.ok and result.result == [{"x": "1", "y": "1"}]
