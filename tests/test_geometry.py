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


@pytest.mark.parametrize(
    "expr,kind",
    [
        ("x**2 + y**2 - 1", "circle"),
        ("x**2/4 + y**2/9 - 1", "ellipse"),
        ("y - x**2", "parabola"),
        ("x**2 - y**2 - 1", "hyperbola"),
    ],
)
def test_conic_classification(expr: str, kind: str) -> None:
    r = call("geometry_compute", "conic_analyze", {"expression": expr, "variables": ["x", "y"]})
    assert r.ok and r.result["type"] == kind
