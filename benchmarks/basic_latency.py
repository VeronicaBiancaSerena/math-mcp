"""Latency benchmarks for math-mcp operations.

Reads ``benchmarks/operation_matrix.json`` and times each operation through the full
dispatch pipeline, recording p50/p95 latency, output size, timeout rate, and backend
version. Benchmarks are diagnostics, not correctness tests.

Run with::

    python benchmarks/basic_latency.py            # uses the real sandbox
    MATH_MCP_FORCE_INPROCESS=1 python benchmarks/basic_latency.py   # fast, in-process
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import median
from typing import Any

from math_mcp.operation_registry import get_spec
from math_mcp.runtime.limits import is_linux
from math_mcp.runtime.subprocess_runner import run_in_subprocess, sandbox_available
from math_mcp.schemas import Limits
from math_mcp.tools.dispatch import run_operation
from math_mcp.tools.versions import backend_versions

MATRIX_PATH = Path(__file__).with_name("operation_matrix.json")


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1))))
    return ordered[index]


def _subprocess_overhead_ms(spec: Any) -> float | None:
    """Measure the per-call isolation cost for subprocess-bound operations.

    Returns the wall-clock time of one sandbox worker round-trip (spawn + echo), or
    ``None`` for in-process operations or when no sandbox can be exercised here.
    """
    if spec is None or not spec.runs_in_subprocess:
        return None
    if not (is_linux() and sandbox_available()):
        return None
    try:
        start = time.monotonic()
        run_in_subprocess("_diag", "_echo", {"probe": 1}, Limits(timeout_ms=8000), [], [])
        return round((time.monotonic() - start) * 1000.0, 2)
    except Exception:  # noqa: BLE001 - a benchmark probe must never abort the run
        return None



def benchmark_operation(entry: dict[str, Any], repeats: int = 5) -> dict[str, Any]:
    tool, operation, payload = entry["tool"], entry["operation"], entry["payload"]
    spec = get_spec(tool, operation)
    domains = entry.get("domains")
    latencies: list[float] = []
    timeouts = 0
    output_size = 0
    for _ in range(repeats):
        start = time.monotonic()
        result = run_operation(tool, operation, payload, domains=domains)
        latencies.append((time.monotonic() - start) * 1000.0)
        if result.status == "timeout":
            timeouts += 1
        output_size = len(json.dumps(result.model_dump(), default=str))
    return {
        "tool": tool,
        "operation": operation,
        "operation_version": spec.operation_version if spec else "unknown",
        "operation_state": spec.state if spec else "unknown",
        "complexity_class": spec.complexity_class if spec else "unknown",
        "runs_in_subprocess": spec.runs_in_subprocess if spec else None,
        "payload_size_bytes": len(json.dumps(payload)),
        "p50_ms": round(median(latencies), 2),
        "p95_ms": round(_percentile(latencies, 95), 2),
        "timeout_rate": timeouts / repeats,
        "output_size_bytes": output_size,
        "subprocess_overhead_ms": _subprocess_overhead_ms(spec),
        "backend_versions": backend_versions(spec.backend) if spec else {},
    }


def run_benchmarks(repeats: int = 5) -> list[dict[str, Any]]:
    matrix = json.loads(MATRIX_PATH.read_text())
    return [benchmark_operation(entry, repeats) for entry in matrix["operations"]]


def main() -> None:
    records = run_benchmarks()
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
