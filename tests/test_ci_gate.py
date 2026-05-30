"""Consolidated CI hard gate.

This module is the single guard that fails the build if the spec-conformance surface
regresses. It enforces, in one place, the four invariants called out as release-blocking:

1. §10.3 — every domain/assumption/payload conflict case is detected as CONSTRAINT_CONFLICT
   and never reaches a backend.
2. §15 — every required test category is present in the suite.
3. §15.9/§15.10 — every stable ``ErrorCode`` is triggered as a real ``ToolResult.error_code``.
4. §10.6/§15.9 — every backend caveat in the registry is referenced by at least one operation.

Adding a new ErrorCode, caveat, or removing a test category without updating coverage makes
this module fail, surfacing the gap early instead of letting it ship.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest
from conftest import call

from math_mcp import backend_caveats
from math_mcp.operation_registry import all_operations
from math_mcp.status import ErrorCode

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# 1. §10.3 — every conflict case yields CONSTRAINT_CONFLICT, before any backend.
# ---------------------------------------------------------------------------

# (label, tool, operation, payload, domains, assumptions)
_CONFLICT_CASES = [
    (
        "domain_kind_clash",
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        [
            {"variable": "x", "kind": "real"},
            {"variable": "x", "kind": "complex"},
        ],
        None,
    ),
    (
        "empty_interval_lower_gt_upper",
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        [{"variable": "x", "kind": "real", "lower": "2", "upper": "1"}],
        None,
    ),
    (
        "empty_open_single_point",
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        [
            {
                "variable": "x",
                "kind": "real",
                "lower": "1",
                "upper": "1",
                "lower_closed": False,
                "upper_closed": False,
            }
        ],
        None,
    ),
    (
        "boolean_bad_value",
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        [{"variable": "x", "kind": "boolean", "values": ["0", "2"]}],
        None,
    ),
    (
        "predicate_contradiction",
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        None,
        [{"variable": "x", "predicates": ["positive", "negative"]}],
    ),
    (
        "assumption_vs_domain",
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        [{"variable": "x", "kind": "real", "lower": "0", "upper": "1"}],
        [{"variable": "x", "predicates": ["negative"]}],
    ),
    (
        "z3_sort_vs_domain",
        "z3_compute",
        "z3_satisfiability",
        {
            "variables": {"x": "Int"},
            "constraints": [{"op": "gt", "left": {"var": "x"}, "right": {"int": 0}}],
        },
        [{"variable": "x", "kind": "real"}],
        None,
    ),
]


@pytest.mark.parametrize("case", _CONFLICT_CASES, ids=lambda c: c[0])
def test_section10_conflicts_yield_constraint_conflict(case) -> None:  # type: ignore[no-untyped-def]
    _label, tool, op, payload, domains, assumptions = case
    result = call(tool, op, payload, domains=domains, assumptions=assumptions)
    assert result.ok is False
    assert result.error_code == "CONSTRAINT_CONFLICT", (
        f"{_label}: expected CONSTRAINT_CONFLICT, got {result.error_code}"
    )
    # A conflict must never reach a backend (guide §10.3).
    assert result.backend == "none"


# ---------------------------------------------------------------------------
# 2. §15 — every required test category is present in the suite.
# ---------------------------------------------------------------------------

_COMPUTE_TOOLS = [
    "algebra", "calculus", "verification", "z3_tools", "matrix", "discrete", "graph",
    "probability", "sets", "geometry", "trigonometry", "number_theory", "logic", "ode",
    "complex_tools", "inequalities",
]

# guide section -> required test artifact (file under tests/).
_REQUIRED_TEST_FILES = [
    *(f"test_{name}.py" for name in _COMPUTE_TOOLS),  # §15.2 per-tool
    "test_capabilities.py",       # §15.8
    "test_security.py",           # §15.3
    "test_sandbox.py",            # §15.3.1
    "test_parsing_sympy.py",      # §15.4 fuzz/property
    "test_differential.py",       # §15.5
    "test_counterexample.py",     # §15.6 numeric evidence (test_verification.py covered above)
    "test_operation_registry.py", # §15.9
    "test_error_codes.py",        # §15.9
    "test_seed_determinism.py",   # §15.9
    "test_conformance.py",        # §15.10
    "test_server_smoke.py",       # §15.11
    "test_benchmarks.py",         # §15.15
    "test_evals.py",              # §15.16
    "test_timeouts.py",           # §13.4 timeout
]


@pytest.mark.parametrize("filename", _REQUIRED_TEST_FILES)
def test_required_test_category_present(filename: str) -> None:
    path = TESTS_DIR / filename
    assert path.exists(), f"required §15 test category missing: {filename}"
    assert "def test_" in path.read_text(), f"{filename} contains no test functions"


def test_golden_and_eval_artifacts_present() -> None:
    golden = TESTS_DIR / "golden"
    assert golden.is_dir() and list(golden.glob("*.json")), "golden fixtures missing (§15.12)"
    evals = REPO_ROOT / "evals" / "math_agent_cases.jsonl"
    assert evals.exists() and evals.read_text().strip(), "eval set missing (§15.16)"
    matrix = REPO_ROOT / "benchmarks" / "operation_matrix.json"
    assert matrix.exists(), "benchmark operation matrix missing (§15.15)"


# ---------------------------------------------------------------------------
# 3. §15.9/§15.10 — every ErrorCode is triggered as a real ToolResult.error_code.
# ---------------------------------------------------------------------------

# Codes producible in-process by a normal operation call.
_INPROCESS_ERROR_SCENARIOS = {
    "PARSE_REJECTED": (
        "algebra_compute", "simplify_expression", {"expression": "__import__('os')"}, {},
    ),
    "UNSUPPORTED_OPERATION": ("algebra_compute", "nope", {"expression": "x"}, {}),
    "DOMAIN_UNSUPPORTED": (
        "discrete_compute", "finite_enumeration",
        {"predicate": "Eq(x,1)", "variables": ["x"]}, {},
    ),
    "ASSUMPTION_UNSUPPORTED": (
        "algebra_compute", "simplify_expression", {"expression": "x", "variables": ["x"]},
        {"assumptions": [{"variable": "x", "predicates": ["banana"]}]},
    ),
    "CONSTRAINT_CONFLICT": (
        "algebra_compute", "simplify_expression", {"expression": "x", "variables": ["x"]},
        {"domains": [{"variable": "x", "kind": "real", "lower": "2", "upper": "1"}]},
    ),
    "INVALID_LIMITS": (
        "algebra_compute", "simplify_expression", {"expression": "x"},
        {"limits": {"timeout_ms": -1}},
    ),
    "INVALID_AST": (
        "algebra_compute", "simplify_expression",
        {"expr_ast": {"op": "frobnicate", "args": [{"int": 1}]}}, {},
    ),
    "NUMERIC_CONVERGENCE_FAILED": (
        "calculus_compute", "numeric_optimize",
        {"expression": "x", "variables": ["x"], "goal": "min"}, {},
    ),
    "OUTPUT_TOO_LARGE": (
        "algebra_compute", "expand_expression",
        {"expression": "(x + 1)**40", "variables": ["x"]},
        {"limits": {"max_output_chars": 256}},
    ),
}

# Codes that originate from the runtime/sandbox layer: triggered by forcing the dispatcher's
# subprocess path to raise the corresponding exception, then asserting the mapped error_code.
_RUNTIME_ERROR_EXCEPTIONS = {
    "BACKEND_TIMEOUT": "BackendTimeout",
    "RESOURCE_LIMIT_EXCEEDED": "ResourceLimitExceeded",
    "SANDBOX_UNAVAILABLE": "SandboxUnavailable",
    "PLATFORM_UNSUPPORTED": "PlatformUnsupported",
}

# BACKEND_INTERNAL_ERROR is exercised by test_error_codes (in-process handler raising a raw
# exception); reproduce the trigger here so the gate's coverage set is self-contained.


def test_every_error_code_is_triggered(monkeypatch: pytest.MonkeyPatch) -> None:
    import math_mcp.errors as errors
    from math_mcp.tools import dispatch

    seen: set[str] = set()

    for code, (tool, op, payload, extra) in _INPROCESS_ERROR_SCENARIOS.items():
        result = call(
            tool, op, payload,
            domains=extra.get("domains"),
            assumptions=extra.get("assumptions"),
            limits=extra.get("limits"),
        )
        assert result.error_code == code, f"{code}: got {result.error_code}"
        seen.add(code)

    # BACKEND_INTERNAL_ERROR: an in-process handler raising a raw exception.
    dispatch._ensure_loaded()
    key = ("algebra_compute", "simplify_expression")

    def _boom(_ctx: object) -> object:
        raise ValueError("unexpected backend failure")

    monkeypatch.setitem(dispatch.HANDLERS, key, _boom)
    r = call("algebra_compute", "simplify_expression", {"expression": "x"})
    assert r.error_code == "BACKEND_INTERNAL_ERROR"
    seen.add("BACKEND_INTERNAL_ERROR")
    monkeypatch.undo()

    # Runtime/sandbox-origin codes: force the subprocess path and raise the exception there,
    # then assert the dispatcher maps it to the right error_code on the returned ToolResult.
    for code, exc_name in _RUNTIME_ERROR_EXCEPTIONS.items():
        exc_cls = getattr(errors, exc_name)

        def _raise(*_a: object, _exc: type[Exception] = exc_cls, **_k: object) -> object:
            raise _exc("forced for CI gate")

        monkeypatch.setattr(dispatch, "force_inprocess", lambda: False)
        monkeypatch.setattr(dispatch, "run_in_subprocess", _raise)
        # 'integrate' is a subprocess-bound operation.
        r = call("calculus_compute", "integrate", {"expression": "2*x", "variable": "x"})
        assert r.error_code == code, f"{code}: got {r.error_code}"
        seen.add(code)
        monkeypatch.undo()

    required = set(ErrorCode.__args__)  # type: ignore[attr-defined]
    missing = required - seen
    assert not missing, f"ErrorCodes with no triggering sample (guide §15.10): {sorted(missing)}"


# ---------------------------------------------------------------------------
# 4. §10.6/§15.9 — every backend caveat is referenced by at least one operation.
# ---------------------------------------------------------------------------


def test_every_backend_caveat_is_referenced() -> None:
    specs = all_operations()
    for caveat in backend_caveats.CAVEATS:
        referenced = any(
            spec.backend == caveat.backend
            and (
                caveat.operation_pattern == "*"
                or fnmatch.fnmatch(spec.operation, caveat.operation_pattern)
            )
            for spec in specs
        )
        assert referenced, (
            f"caveat {caveat.backend}:{caveat.operation_pattern} is referenced by no operation"
        )
