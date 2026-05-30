"""Tests for graph_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("graph_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("graph_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_topological_sort_requires_directed() -> None:
    result = call(
        "graph_compute",
        "topological_sort",
        {"directed": False, "nodes": ["A", "B"], "edges": [["A", "B"]]},
    )
    assert result.ok is False
    assert result.status == "unsupported"


def test_unreachable_target() -> None:
    result = call(
        "graph_compute",
        "shortest_path",
        {
            "directed": False,
            "nodes": ["A", "B", "C"],
            "edges": [["A", "B"]],
            "source": "A",
            "target": "C",
        },
    )
    assert result.ok and result.result["reachable"] is False
