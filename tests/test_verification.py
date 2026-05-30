"""Tests for verification_compute: identities and the proof/evidence distinction."""

from __future__ import annotations

from conftest import call


def test_identity_proved_symbolically() -> None:
    result = call(
        "verification_compute",
        "check_identity",
        {"left": "sin(x)**2 + cos(x)**2", "right": "1", "variables": ["x"]},
    )
    assert result.ok
    assert result.status == "proved_by_symbolic_simplification"
    assert result.certainty == "proved"
    assert result.method == "symbolic"
    assert result.certificate is not None
    assert result.certificate.type == "symbolic_simplification"


def test_identity_disproved_by_counterexample() -> None:
    result = call(
        "verification_compute", "check_identity", {"left": "x**2", "right": "x", "variables": ["x"]}
    )
    assert result.ok
    assert result.certainty == "disproved"
    assert result.result_kind == "witness"


def test_sampling_only_is_evidence_not_proof() -> None:
    # An identity SymPy cannot simplify but which holds at sampled points -> evidence.
    result = call(
        "verification_compute",
        "check_inequality_sampled",
        {"left": "x**2 + 1", "relation": ">", "right": "0", "variables": ["x"], "samples": 50},
    )
    assert result.ok
    assert result.status == "no_counterexample_found"
    assert result.certainty == "evidence"
    assert result.method == "numeric_sampling"
    assert "numeric sampling is not proof" in result.warnings


def test_check_identity_sampling_pass_is_numeric_evidence_only() -> None:
    # Abs(x)**2 == x**2 holds for all real x but SymPy does not simplify the difference to
    # 0 without a real assumption, so the deterministic grid finds no counterexample.
    # Per guide §15.6 this must be reported as evidence, never as a proof.
    result = call(
        "verification_compute",
        "check_identity",
        {"left": "Abs(x)**2", "right": "x**2", "variables": ["x"]},
    )
    assert result.ok
    assert result.status == "numeric_evidence_only"
    assert result.certainty == "evidence"
    assert result.certificate is None
    # The grid evaluation is SymPy evalf, not mpmath (guide §4.3: "SymPy + sampling").
    assert result.backend == "sympy"



def test_unsupported_operation() -> None:
    result = call("verification_compute", "nope", {})
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_missing_variables_rejected() -> None:
    result = call(
        "verification_compute",
        "search_counterexample",
        {"left": "x", "relation": ">", "right": "0"},
    )
    assert result.ok is False
