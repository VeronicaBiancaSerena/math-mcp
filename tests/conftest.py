"""Shared pytest fixtures and helpers.

The unit suite runs subprocess-bound operations in-process for speed (via
MATH_MCP_FORCE_INPROCESS). The sandbox acceptance tests deliberately do NOT rely on this;
they call the subprocess runner directly to exercise the real bubblewrap sandbox.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

# Run subprocess-bound ops in-process so the unit suite is fast. Set before any
# run_operation call reads it.
os.environ.setdefault("MATH_MCP_FORCE_INPROCESS", "1")

from math_mcp.schemas import ToolResult  # noqa: E402
from math_mcp.tools.dispatch import run_operation  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden"
STABLE_FIELDS = ("ok", "status", "certainty", "method", "result_kind", "result")


def call(
    public_tool: str,
    operation: str,
    payload: dict[str, Any] | None = None,
    *,
    domains: list[dict[str, Any]] | None = None,
    assumptions: list[dict[str, Any]] | None = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Invoke an operation through the full dispatch pipeline."""
    return run_operation(public_tool, operation, payload or {}, domains, assumptions, limits)


def load_golden(name: str) -> list[dict[str, Any]]:
    path = GOLDEN_DIR / name
    return json.loads(path.read_text())


def assert_golden(case: dict[str, Any]) -> ToolResult:
    """Run one golden case and assert its stable fields match expectations."""
    inp = case["input"]
    result = call(
        case["tool"],
        inp["operation"],
        inp.get("payload", {}),
        domains=inp.get("domains"),
        assumptions=inp.get("assumptions"),
        limits=inp.get("limits"),
    )
    dumped = result.model_dump()
    for field, expected in case["expected"].items():
        assert dumped[field] == expected, (
            f"{case['tool']}/{inp['operation']} field {field}: "
            f"got {dumped[field]!r}, expected {expected!r}"
        )
    return result


@pytest.fixture
def golden() -> Any:
    return assert_golden
