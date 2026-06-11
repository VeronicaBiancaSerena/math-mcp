"""Run backend computations in an isolated subprocess.

High-risk operations execute in a bubblewrap sandbox with a fresh network namespace,
a minimal read-only filesystem view, a clean environment, and resource limits. The
worker speaks JSON over stdin/stdout only — never pickle.

If a sandbox cannot be enforced the runner refuses to run, returning
``error_code="SANDBOX_UNAVAILABLE"`` (or ``PLATFORM_UNSUPPORTED`` off Linux). The single
development escape hatch is ``MATH_MCP_ALLOW_NO_SANDBOX=1``, which falls back to a plain
resource-limited subprocess (no network namespace) and is never used in production.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import math_mcp
from math_mcp.config import allow_no_sandbox
from math_mcp.errors import (
    BackendTimeout,
    ResourceLimitExceeded,
    SandboxUnavailable,
)
from math_mcp.runtime.limits import ensure_linux, is_linux, rlimit_preexec
from math_mcp.schemas import Limits

_WORKER_MODULE = "math_mcp.runtime.worker"
_MAX_STDOUT_BYTES = 2 * 1024 * 1024
_MAX_STDERR_CHARS = 2000

# stderr markers that indicate a resource limit was hit (memory, file size, open files).
_RESOURCE_MARKERS = ("MemoryError", "File too large", "Errno 27", "Errno 12", "Errno 24")


def _src_root() -> str:
    # .../src/math_mcp/__init__.py -> .../src
    return str(Path(math_mcp.__file__).resolve().parents[1])


def _env_prefix() -> str:
    return sys.prefix


@functools.lru_cache(maxsize=1)
def sandbox_available() -> bool:
    """Return True if bubblewrap can create a network-isolated sandbox here."""
    if not is_linux():
        return False
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    try:
        probe = subprocess.run(
            [bwrap, "--unshare-net", "--ro-bind", "/", "/", "--dev", "/dev", "/bin/true"],
            capture_output=True,
            timeout=15,
        )
        return probe.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _clean_env(src_root: str) -> dict[str, str]:
    return {
        "PATH": f"{_env_prefix()}/bin:/usr/bin:/bin",
        "PYTHONPATH": src_root,
        "HOME": "/tmp",
        # Keep the sandbox deterministic while still allowing Python's site module to
        # read editable-install .pth files whose source path contains non-ASCII text.
        # Plain "C" makes Python decode those .pth files as ASCII before our worker
        # starts, which breaks checkouts under paths such as "文档/math-mcp".
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        # Pin BLAS/OpenMP thread pools to 1. Their per-thread virtual-memory
        # reservations otherwise blow past the RLIMIT_AS memory cap.
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OPENBLAS_MAIN_FREE": "1",
    }


def _bwrap_command(src_root: str) -> list[str]:
    bwrap = shutil.which("bwrap")
    assert bwrap is not None  # guarded by sandbox_available()
    env_prefix = _env_prefix()
    cmd = [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        env_prefix,
        env_prefix,
        "--ro-bind-try",
        src_root,
        src_root,
        "--ro-bind-try",
        "/lib",
        "/lib",
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--ro-bind-try",
        "/usr/lib",
        "/usr/lib",
        "--ro-bind-try",
        "/usr/lib64",
        "/usr/lib64",
        "--ro-bind-try",
        "/bin",
        "/bin",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--clearenv",
    ]
    for key, value in _clean_env(src_root).items():
        cmd += ["--setenv", key, value]
    cmd += [f"{env_prefix}/bin/python", "-I", "-m", _WORKER_MODULE]
    return cmd


def _plain_command() -> list[str]:
    return [sys.executable, "-I", "-m", _WORKER_MODULE]


def _sanitize_stderr(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")[:_MAX_STDERR_CHARS]
    # Strip absolute paths so worker errors never leak filesystem layout.
    cleaned: list[str] = []
    for token in text.split():
        if token.startswith("/") and "/" in token[1:]:
            cleaned.append("<path>")
        else:
            cleaned.append(token)
    return " ".join(cleaned)[:_MAX_STDERR_CHARS]


def run_in_subprocess(
    public_tool: str,
    operation: str,
    payload: dict[str, Any],
    limits: Limits,
    domains: list[dict[str, Any]],
    assumptions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute an operation in an isolated worker and return its JSON outcome dict.

    The returned dict is either ``{"ok": True, "outcome": {...}}`` or
    ``{"ok": False, "error": {...}}`` plus a ``network_isolated`` flag.
    """
    ensure_linux()
    src_root = _src_root()

    if sandbox_available():
        cmd = _bwrap_command(src_root)
        network_isolated = True
    elif allow_no_sandbox():
        cmd = _plain_command()
        network_isolated = False
    else:
        raise SandboxUnavailable(
            "bubblewrap network-isolated sandbox is unavailable; refusing to run a "
            "subprocess-bound operation without isolation"
        )

    request = json.dumps(
        {
            "public_tool": public_tool,
            "operation": operation,
            "payload": payload,
            "limits": limits.model_dump(),
            "domains": domains,
            "assumptions": assumptions,
        }
    ).encode("utf-8")

    env = None if sandbox_available() else _clean_env(src_root)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=rlimit_preexec(limits),
        start_new_session=True,
        env=env,
    )
    timeout_s = limits.timeout_ms / 1000.0
    try:
        out, err = proc.communicate(request, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        proc.communicate()
        raise BackendTimeout(f"Computation exceeded timeout_ms={limits.timeout_ms}") from None

    return _interpret(proc.returncode, out, err, network_isolated)


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


def _interpret(
    returncode: int | None, out: bytes, err: bytes, network_isolated: bool
) -> dict[str, Any]:
    # Signal-based termination from resource limits.
    if returncode is not None and returncode < 0:
        sig = -returncode
        if sig in (signal.SIGXCPU, signal.SIGXFSZ, signal.SIGKILL):
            raise ResourceLimitExceeded(f"worker terminated by signal {sig}")
    if returncode is not None and returncode in (137, 152, 153):  # 128+9/24/25
        raise ResourceLimitExceeded(f"worker terminated by resource signal (exit {returncode})")

    if len(out) > _MAX_STDOUT_BYTES:
        raise ResourceLimitExceeded("worker stdout exceeded the maximum size")

    text = out.decode("utf-8", errors="replace").strip()
    if not text:
        stderr_summary = _sanitize_stderr(err)
        if any(marker in stderr_summary for marker in _RESOURCE_MARKERS):
            raise ResourceLimitExceeded(f"worker exceeded a resource limit: {stderr_summary}")
        raise _worker_failed(stderr_summary, returncode)

    try:
        result: dict[str, Any] = json.loads(text.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        raise _worker_failed(_sanitize_stderr(err) or "invalid worker output", returncode) from None

    result["network_isolated"] = network_isolated
    return result


def _worker_failed(summary: str, returncode: int | None) -> Exception:
    from math_mcp.errors import BackendInternalError

    return BackendInternalError(f"backend worker failed (exit {returncode}): {summary}")
