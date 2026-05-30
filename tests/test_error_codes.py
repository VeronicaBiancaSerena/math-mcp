"""Each stable ErrorCode is triggered by at least one scenario."""

from __future__ import annotations

import pytest
from conftest import call

from math_mcp.status import ErrorCode

# error_code -> a call that should produce it.
SCENARIOS: dict[str, tuple] = {
    "PARSE_REJECTED": (
        "algebra_compute",
        "simplify_expression",
        {"expression": "__import__('os')"},
        {},
    ),
    "UNSUPPORTED_OPERATION": ("algebra_compute", "nope", {"expression": "x"}, {}),
    "DOMAIN_UNSUPPORTED": (
        "discrete_compute",
        "finite_enumeration",
        {"predicate": "Eq(x,1)", "variables": ["x"]},
        {},
    ),
    "ASSUMPTION_UNSUPPORTED": (
        "algebra_compute",
        "simplify_expression",
        {"expression": "x", "variables": ["x"]},
        {"assumptions": [{"variable": "x", "predicates": ["banana"]}]},
    ),
    "CONSTRAINT_CONFLICT": (
        "verification_compute",
        "search_counterexample",
        {"left": "x", "relation": ">", "right": "0", "variables": ["x"]},
        {"domains": [{"variable": "x", "kind": "real", "lower": "2", "upper": "1"}]},
    ),
    "INVALID_LIMITS": (
        "algebra_compute",
        "simplify_expression",
        {"expression": "x"},
        {"limits": {"timeout_ms": -1}},
    ),
}


@pytest.mark.parametrize("code", list(SCENARIOS))
def test_error_code_triggered(code: str) -> None:
    tool, op, payload, extra = SCENARIOS[code]
    result = call(
        tool,
        op,
        payload,
        domains=extra.get("domains"),
        assumptions=extra.get("assumptions"),
        limits=extra.get("limits"),
    )
    assert result.ok is False
    assert result.error_code == code, f"expected {code}, got {result.error_code}: {result.error}"


def test_constraint_conflict_does_not_reach_backend() -> None:
    result = call(
        "verification_compute",
        "search_counterexample",
        {"left": "x", "relation": ">", "right": "0", "variables": ["x"]},
        domains=[{"variable": "x", "kind": "real", "lower": "0", "upper": "1"}],
        assumptions=[{"variable": "x", "predicates": ["negative"]}],
    )
    assert result.error_code == "CONSTRAINT_CONFLICT"
    assert result.backend == "none"


def test_invalid_ast_rejected() -> None:
    result = call(
        "algebra_compute",
        "simplify_expression",
        {"expr_ast": {"op": "frobnicate", "args": [{"int": 1}]}},
    )
    assert result.ok is False
    assert result.error_code == "INVALID_AST"


def test_platform_and_sandbox_codes_exist_in_vocabulary() -> None:
    # These are produced by the platform/sandbox gates (see test_sandbox.py); confirm
    # they are part of the stable vocabulary.
    codes = set(ErrorCode.__args__)  # type: ignore[attr-defined]
    assert {"PLATFORM_UNSUPPORTED", "SANDBOX_UNAVAILABLE"} <= codes


def test_numeric_convergence_code_in_vocabulary() -> None:
    codes = set(ErrorCode.__args__)  # type: ignore[attr-defined]
    assert "NUMERIC_CONVERGENCE_FAILED" in codes
    assert "OUTPUT_TOO_LARGE" in codes
    assert "RESOURCE_LIMIT_EXCEEDED" in codes
    assert "BACKEND_TIMEOUT" in codes
    assert "BACKEND_INTERNAL_ERROR" in codes


def test_platform_unsupported_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from math_mcp.errors import PlatformUnsupported
    from math_mcp.runtime.limits import ensure_linux

    monkeypatch.setenv("MATH_MCP_FORCE_PLATFORM_UNSUPPORTED", "1")
    with pytest.raises(PlatformUnsupported):
        ensure_linux()


def test_unexpected_handler_exception_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    # A handler that raises a non-MathMcpError (e.g. a raw backend exception on the
    # in-process path) must still yield a structured ToolResult (guide §5.3), and must not
    # leak the exception message/paths (guide §13.2.1).
    from math_mcp.tools import dispatch

    dispatch._ensure_loaded()
    key = ("algebra_compute", "simplify_expression")
    original = dispatch.HANDLERS[key]

    def _boom(_ctx: object) -> object:
        raise ValueError("secret detail /home/user/file.txt")

    monkeypatch.setitem(dispatch.HANDLERS, key, _boom)
    result = call("algebra_compute", "simplify_expression", {"expression": "x"})
    assert dispatch.HANDLERS[key] is _boom  # sanity: monkeypatch applied
    assert result.ok is False
    assert result.status == "backend_error"
    assert result.error_code == "BACKEND_INTERNAL_ERROR"
    assert "secret detail" not in (result.error or "")
    assert "/home/" not in (result.error or "")
    # restore is handled by monkeypatch; assert the original is a callable we replaced
    assert callable(original)
