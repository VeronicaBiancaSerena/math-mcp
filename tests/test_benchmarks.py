"""Smoke tests for the benchmark harness and operation matrix."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX = REPO_ROOT / "benchmarks" / "operation_matrix.json"


def _load_basic_latency():  # type: ignore[no-untyped-def]
    path = REPO_ROOT / "benchmarks" / "basic_latency.py"
    spec = importlib.util.spec_from_file_location("basic_latency", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_operation_matrix_is_valid() -> None:
    data = json.loads(MATRIX.read_text())
    assert "operations" in data and data["operations"]
    for entry in data["operations"]:
        assert {"tool", "operation", "payload"} <= set(entry)


def test_benchmark_records_required_fields() -> None:
    module = _load_basic_latency()
    entry = json.loads(MATRIX.read_text())["operations"][0]
    record = module.benchmark_operation(entry, repeats=2)
    for field in (
        "operation",
        "operation_version",
        "operation_state",
        "complexity_class",
        "p50_ms",
        "p95_ms",
        "timeout_rate",
        "output_size_bytes",
        "subprocess_overhead_ms",
        "backend_versions",
    ):
        assert field in record


def test_benchmark_runs_all_entries() -> None:
    module = _load_basic_latency()
    records = module.run_benchmarks(repeats=1)
    assert len(records) == len(json.loads(MATRIX.read_text())["operations"])
