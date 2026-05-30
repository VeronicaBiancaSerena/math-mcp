"""Timeout handling: wall-clock kills and the structured timeout ToolResult."""

from __future__ import annotations

import pytest
from conftest import call

from math_mcp.errors import BackendTimeout
from math_mcp.runtime.subprocess_runner import run_in_subprocess, sandbox_available
from math_mcp.schemas import Limits
from math_mcp.tools import dispatch


@pytest.mark.skipif(not sandbox_available(), reason="sandbox unavailable")
def test_wall_clock_timeout_raises() -> None:
    with pytest.raises(BackendTimeout):
        run_in_subprocess(
            "_diag", "_cpu_bomb", {}, Limits(timeout_ms=600, cpu_time_ms=30000), [], []
        )


def test_timeout_maps_to_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the subprocess path and make it time out; the dispatcher must produce a
    # structured timeout ToolResult rather than raising.
    monkeypatch.setattr(dispatch, "force_inprocess", lambda: False)

    def fake_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise BackendTimeout("Computation exceeded timeout_ms=5000")

    monkeypatch.setattr(dispatch, "run_in_subprocess", fake_run)
    result = call("z3_compute", "z3_satisfiability", {"variables": {"x": "Int"}, "constraints": []})
    assert result.ok is False
    assert result.status == "timeout"
    assert result.certainty == "error"
    assert result.method == "none"
    assert result.error_code == "BACKEND_TIMEOUT"
