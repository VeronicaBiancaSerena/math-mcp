"""Sandbox worker entry point: ``python -m math_mcp.runtime.worker``.

Reads a single JSON request from stdin, runs the requested operation (or a diagnostic
probe used by the sandbox acceptance tests), and writes exactly one JSON line to stdout.
It never emits pickled or binary objects. Heavy handler machinery is imported lazily so
diagnostic probes stay lightweight under tight memory limits.
"""

from __future__ import annotations

import json
import socket
import sys
from typing import Any


def _emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _run_diagnostic(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic probes for the sandbox acceptance tests."""
    if operation == "_echo":
        return {"ok": True, "outcome": {"status": "success", "echo": payload}}
    if operation == "_net_probe":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((payload.get("host", "8.8.8.8"), int(payload.get("port", 53))))
            s.close()
            return {"ok": True, "outcome": {"status": "success", "network": "reachable"}}
        except OSError as exc:
            return {
                "ok": True,
                "outcome": {"status": "success", "network": "blocked", "errno": exc.errno},
            }
    if operation == "_path_probe":
        path = payload.get("path", "/etc/passwd")
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                fh.read(16)
            return {"ok": True, "outcome": {"status": "success", "read": "allowed"}}
        except OSError as exc:
            return {
                "ok": True,
                "outcome": {
                    "status": "success",
                    "read": "blocked",
                    "error": exc.__class__.__name__,
                },
            }
    if operation == "_cpu_bomb":
        while True:  # consumes CPU until RLIMIT_CPU fires (SIGXCPU)
            pass
    if operation == "_mem_bomb":
        chunks = []
        while True:  # grows until RLIMIT_AS triggers MemoryError
            chunks.append(bytearray(16 * 1024 * 1024))
    if operation == "_fsize_bomb":
        with open("/tmp/fsize_bomb.bin", "wb") as fh:
            while True:  # writes until RLIMIT_FSIZE fires (SIGXFSZ)
                fh.write(b"\0" * (1024 * 1024))
                fh.flush()
    if operation == "_stdout_flood":
        # Emit more than the runner's stdout cap so it is rejected, not truncated silently.
        size = int(payload.get("bytes", 3 * 1024 * 1024))
        sys.stdout.write("x" * size)
        sys.stdout.flush()
        return {"ok": True, "outcome": {"status": "success"}}
    return {
        "ok": False,
        "error": {
            "status": "unsupported",
            "error_code": "UNSUPPORTED_OPERATION",
            "certainty": "error",
            "method": "none",
            "message": f"unknown diagnostic '{operation}'",
        },
    }


def _run_real(request: dict[str, Any]) -> dict[str, Any]:
    from math_mcp.errors import BackendInternalError, MathMcpError
    from math_mcp.parsing.domain_parser import normalize
    from math_mcp.runtime.limits import normalize_limits
    from math_mcp.schemas import AssumptionSpec, DomainSpec
    from math_mcp.tools.dispatch import execute_handler

    try:
        limits = normalize_limits(request.get("limits"))
        domains = [DomainSpec.model_validate(d) for d in request.get("domains", [])]
        assumptions = [AssumptionSpec.model_validate(a) for a in request.get("assumptions", [])]
        constraints = normalize(domains, assumptions, limits=limits)
        outcome = execute_handler(
            request["public_tool"],
            request["operation"],
            request.get("payload", {}),
            limits,
            constraints,
        )
        return {"ok": True, "outcome": outcome.to_json()}
    except MathMcpError as exc:
        return {
            "ok": False,
            "error": {
                "status": exc.status,
                "error_code": exc.error_code,
                "certainty": exc.certainty,
                "method": exc.method,
                "message": str(exc),
            },
        }
    except Exception as exc:  # noqa: BLE001
        err = BackendInternalError(f"{type(exc).__name__}")
        return {
            "ok": False,
            "error": {
                "status": err.status,
                "error_code": err.error_code,
                "certainty": err.certainty,
                "method": err.method,
                "message": str(err),
            },
        }


def main() -> None:
    raw = sys.stdin.buffer.read()
    try:
        request = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        # Non-JSON / binary / pickled input is rejected structurally and never unpickled
        # or executed (guide §15.3.1).
        _emit(
            {
                "ok": False,
                "error": {
                    "status": "invalid_input",
                    "error_code": "PARSE_REJECTED",
                    "certainty": "error",
                    "method": "none",
                    "message": "worker received non-JSON input",
                },
            }
        )
        return

    public_tool = request.get("public_tool", "")
    operation = request.get("operation", "")
    if public_tool == "_diag":
        _emit(_run_diagnostic(operation, request.get("payload", {})))
        return
    _emit(_run_real(request))


if __name__ == "__main__":
    main()
