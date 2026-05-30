"""Tests for z3_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden

import math_mcp.tools.z3_tools as z3_tools
from math_mcp.errors import BackendTimeout


@pytest.mark.parametrize(
    "case", load_golden("z3_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("z3_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_sat_returns_model() -> None:
    result = call(
        "z3_compute",
        "z3_satisfiability",
        {
            "variables": {"x": "Int"},
            "constraints": [{"op": "gt", "left": {"var": "x"}, "right": {"int": 5}}],
        },
    )
    assert result.ok and result.result["satisfiable"] is True
    assert "x" in result.result["model"]


def test_invalid_ast_rejected() -> None:
    result = call(
        "z3_compute",
        "z3_satisfiability",
        {
            "variables": {"x": "Int"},
            "constraints": [{"op": "bogus", "left": {"var": "x"}, "right": {"int": 0}}],
        },
    )
    assert result.ok is False
    assert result.error_code == "INVALID_AST"


def test_proof_via_unsat_has_certificate() -> None:
    result = call(
        "z3_compute",
        "z3_find_counterexample",
        {
            "variables": {"x": "Int"},
            "assumptions": [{"op": "ge", "left": {"var": "x"}, "right": {"int": 0}}],
            "claim": {
                "op": "ge",
                "left": {"op": "mul", "args": [{"var": "x"}, {"var": "x"}]},
                "right": {"int": 0},
            },
        },
    )
    assert result.certainty == "proved"
    assert result.certificate is not None and result.certificate.type == "smt_unsat"


def test_z3_unknown_is_not_promoted(monkeypatch: pytest.MonkeyPatch) -> None:
    # When Z3 returns "unknown" (e.g. undecidable nonlinear/quantified fragment) the tool
    # must report unknown, never a proof (guide §15.7).
    monkeypatch.setattr(
        z3_tools, "solve_constraints", lambda *a, **k: {"result": "unknown", "model": {}}
    )
    result = call(
        "z3_compute",
        "z3_satisfiability",
        {
            "variables": {"x": "Real"},
            "constraints": [{"op": "gt", "left": {"var": "x"}, "right": {"int": 0}}],
        },
    )
    assert result.status == "unknown"
    assert result.certainty == "unknown"
    assert result.method == "none"


def test_z3_timeout_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    # A solver timeout surfaces as a structured timeout result (guide §15.7).
    def _timeout(*_a: object, **_k: object) -> dict[str, object]:
        raise BackendTimeout("Computation exceeded timeout_ms=1")

    monkeypatch.setattr(z3_tools, "solve_constraints", _timeout)
    result = call(
        "z3_compute",
        "z3_satisfiability",
        {
            "variables": {"x": "Int"},
            "constraints": [{"op": "gt", "left": {"var": "x"}, "right": {"int": 0}}],
        },
    )
    assert result.ok is False
    assert result.status == "timeout"
    assert result.error_code == "BACKEND_TIMEOUT"
