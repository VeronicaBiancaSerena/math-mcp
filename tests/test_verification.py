"""Tests for verification_compute: identities and the proof/evidence distinction."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("verification_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


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


# --- check_identity_constrained (guide §8/§24) -----------------------------


def test_constrained_identity_proved_by_parameterization() -> None:
    # On the ellipse x^2/4 + y^2/3 = 1, the parameterization x=2cos t, y=√3 sin t makes
    # the identity reduce to 0 — a genuine symbolic proof on the constraint surface.
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x**2/4 + y**2/3",
            "right": "1",
            "variables": ["x", "y"],
            "constraints": [{"relation": "==", "left": "x**2/4 + y**2/3", "right": "1"}],
            "parameterization": {
                "variables": ["t"],
                "substitutions": {"x": "2*cos(t)", "y": "sqrt(3)*sin(t)"},
            },
        },
    )
    assert result.ok and result.status == "proved_by_symbolic_simplification"
    assert result.certainty == "proved"
    assert result.metadata["constraint_mode"] == "parameterized_symbolic"
    assert result.certificate is not None


def test_constrained_identity_proved_by_substitution() -> None:
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x + y",
            "right": "1",
            "variables": ["x", "y"],
            "constraints": [{"relation": "==", "left": "x + y", "right": "1"}],
            "substitutions": {"y": "1 - x"},
        },
    )
    assert result.ok and result.certainty == "proved"
    assert result.metadata["constraint_mode"] == "substitution_symbolic"


def test_constrained_identity_bad_parameterization_is_unsupported() -> None:
    # A parameterization that does NOT satisfy the constraint must be rejected, not trusted.
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x",
            "right": "1",
            "variables": ["x", "y"],
            "constraints": [{"relation": "==", "left": "x + y", "right": "1"}],
            "substitutions": {"y": "2 - x"},
        },
    )
    assert result.ok is False
    assert result.error_code == "DOMAIN_UNSUPPORTED"
    assert result.metadata.get("constraint_mode") == "unsupported"


def test_constrained_sampling_finds_feasible_counterexample() -> None:
    # left=x, right=2 on 0<=x<=1: feasible grid points exist and none equals 2 -> disproved
    # by a constraint-satisfying point (never a free-variable point outside the region).
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x",
            "right": "2",
            "variables": ["x"],
            "constraints": [
                {"relation": ">=", "left": "x", "right": "0"},
                {"relation": "<=", "left": "x", "right": "1"},
            ],
        },
    )
    assert result.ok and result.certainty == "disproved"
    assert result.metadata["constraint_mode"] == "constrained_sampling"
    assert result.metadata["feasible_samples"] >= 1


def test_constrained_sampling_no_counterexample_is_evidence() -> None:
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x",
            "right": "x",
            "variables": ["x"],
            "constraints": [{"relation": ">=", "left": "x", "right": "0"}],
        },
    )
    assert result.ok and result.status == "numeric_evidence_only"
    assert result.certainty == "evidence"
    assert "numeric sampling is not proof" in result.warnings


def test_parameterized_disproof_requires_a_feasible_witness() -> None:
    # x == |x| holds on the feasible region x>=0, but the parameterization x=t,y=t also
    # covers t<0. A parameter value t=-1 maps to x=-1, which VIOLATES x>=0, so it must NOT
    # be reported as a counterexample. With no feasible counterexample -> evidence.
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x",
            "right": "Abs(x)",
            "variables": ["x", "y"],
            "constraints": [
                {"relation": "==", "left": "x", "right": "y"},
                {"relation": ">=", "left": "x", "right": "0"},
            ],
            "parameterization": {"variables": ["t"], "substitutions": {"x": "t", "y": "t"}},
        },
    )
    assert result.ok and result.certainty == "evidence"
    assert result.status == "numeric_evidence_only"


def test_parameterized_disproof_at_a_feasible_point() -> None:
    # x == 2 is false at the feasible point x=0 (satisfies x>=0): a genuine disproof whose
    # witness is a real feasible point.
    result = call(
        "verification_compute",
        "check_identity_constrained",
        {
            "left": "x",
            "right": "2",
            "variables": ["x"],
            "constraints": [{"relation": ">=", "left": "x", "right": "0"}],
            "parameterization": {"variables": ["t"], "substitutions": {"x": "t"}},
        },
    )
    assert result.ok and result.certainty == "disproved"
    assert "point" in result.result
