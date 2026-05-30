"""Sandbox acceptance tests: verify runtime isolation actually holds (real bubblewrap).

These tests do NOT use the in-process fast path; they call the subprocess runner directly
so a real sandbox is exercised. They are skipped only when no sandbox is available at all.
"""

from __future__ import annotations

import pytest

from math_mcp.errors import (
    BackendTimeout,
    PlatformUnsupported,
    ResourceLimitExceeded,
    SandboxUnavailable,
)
from math_mcp.runtime import subprocess_runner
from math_mcp.runtime.subprocess_runner import run_in_subprocess, sandbox_available
from math_mcp.schemas import Limits

requires_sandbox = pytest.mark.skipif(
    not sandbox_available(), reason="bubblewrap sandbox unavailable on this host"
)


def _diag(operation: str, payload: dict, limits: Limits) -> dict:
    return run_in_subprocess("_diag", operation, payload, limits, [], [])


@requires_sandbox
def test_network_is_isolated() -> None:
    out = _diag("_net_probe", {"host": "8.8.8.8", "port": 53}, Limits(timeout_ms=8000))
    assert out["ok"] is True
    assert out["outcome"]["network"] == "blocked"
    assert out["network_isolated"] is True


@requires_sandbox
def test_local_file_read_is_blocked() -> None:
    out = _diag("_path_probe", {"path": "/etc/passwd"}, Limits(timeout_ms=8000))
    assert out["outcome"]["read"] == "blocked"


@requires_sandbox
def test_cpu_limit_enforced() -> None:
    with pytest.raises(ResourceLimitExceeded):
        _diag("_cpu_bomb", {}, Limits(timeout_ms=20000, cpu_time_ms=1000))


@requires_sandbox
def test_memory_limit_enforced() -> None:
    with pytest.raises(ResourceLimitExceeded):
        _diag("_mem_bomb", {}, Limits(timeout_ms=20000, memory_mb=256))


@requires_sandbox
def test_file_size_limit_enforced() -> None:
    with pytest.raises(ResourceLimitExceeded):
        _diag("_fsize_bomb", {}, Limits(timeout_ms=20000, file_size_mb=1))


@requires_sandbox
def test_wall_clock_timeout_kills_worker() -> None:
    with pytest.raises(BackendTimeout):
        _diag("_cpu_bomb", {}, Limits(timeout_ms=600, cpu_time_ms=30000))


@requires_sandbox
def test_worker_returns_json_only() -> None:
    out = _diag("_echo", {"value": 42}, Limits(timeout_ms=8000))
    # The runner parses JSON; a pickle/binary channel would never round-trip like this.
    assert out["ok"] is True
    assert out["outcome"]["echo"] == {"value": 42}


@requires_sandbox
def test_oversized_stdout_is_rejected() -> None:
    # The worker floods stdout past the runner's cap; the runner must refuse it as a
    # structured resource error rather than returning oversized output (guide §15.3.1).
    with pytest.raises(ResourceLimitExceeded):
        _diag("_stdout_flood", {"bytes": 3 * 1024 * 1024}, Limits(timeout_ms=8000))


@requires_sandbox
def test_stderr_does_not_leak_paths() -> None:
    # An unknown diagnostic yields a structured error with no absolute paths leaked.
    out = _diag("_unknown_probe", {}, Limits(timeout_ms=8000))
    assert out["ok"] is False
    assert "/home/" not in str(out)


def test_non_linux_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATH_MCP_FORCE_PLATFORM_UNSUPPORTED", "1")
    with pytest.raises(PlatformUnsupported):
        run_in_subprocess("_diag", "_echo", {}, Limits(), [], [])


def test_refuses_without_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_runner, "sandbox_available", lambda: False)
    monkeypatch.delenv("MATH_MCP_ALLOW_NO_SANDBOX", raising=False)
    with pytest.raises(SandboxUnavailable):
        run_in_subprocess("_diag", "_echo", {}, Limits(), [], [])
