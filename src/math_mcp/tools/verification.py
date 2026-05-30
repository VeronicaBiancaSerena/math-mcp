"""Verification operations: identity checking, sampled inequality checks, counterexamples.

Only symbolic simplification to zero counts as a proof of an identity. Numeric sampling
is reported as evidence (no counterexample) or a strict disproof (a concrete witness) —
never as a proof.
"""

from __future__ import annotations

import itertools
from typing import Any

import sympy as sp

from math_mcp.backends.mpmath_backend import sample_relation
from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, certificate, verification_result
from math_mcp.tools.dispatch import handler

_DET_POINTS = [
    sp.Integer(-2),
    sp.Integer(-1),
    sp.Rational(-1, 2),
    sp.Rational(1, 2),
    sp.Integer(1),
    sp.Integer(2),
    sp.Integer(3),
]


def _variables(ctx: Ctx) -> set[str] | None:
    raw = ctx.get("variables")
    if isinstance(raw, list) and raw:
        return {str(v) for v in raw}
    return None


def _parse_side(ctx: Ctx, key: str, allowed: set[str] | None) -> Any:
    return parse_expression(ctx.require_str(key), limits=ctx.limits, allowed_symbols=allowed)


@handler("verification_compute", "check_identity")
def check_identity(ctx: Ctx) -> Outcome:
    allowed = _variables(ctx)
    left = _parse_side(ctx, "left", allowed)
    right = _parse_side(ctx, "right", allowed)
    difference = sp.simplify(left - right)
    if difference == 0:
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            result="0",
            certificate_=certificate(
                "symbolic_simplification",
                "simplify(left - right) reduced to 0",
                machine_checkable=True,
                details={"difference": "0"},
            ),
        )

    witness = _deterministic_counterexample(difference)
    if witness is not None:
        return verification_result(
            status="disproved_by_counterexample",
            certainty="disproved",
            method="counterexample",
            result=witness,
            result_kind="witness",
            certificate_=certificate(
                "counterexample",
                "left and right differ at a sampled point",
                machine_checkable=True,
                details=witness,
            ),
        )
    return verification_result(
        status="numeric_evidence_only",
        certainty="evidence",
        method="numeric_sampling",
        result=None,
        backend="sympy",
        explanation="No counterexample found at sampled points. This is not a proof.",
        warnings=["numeric sampling is not proof"],
    )


def _deterministic_counterexample(difference: Any) -> dict[str, Any] | None:
    free = sorted(difference.free_symbols, key=str)
    if not free:
        return None
    if len(free) > 4:
        free = free[:4]
    for combo in itertools.product(_DET_POINTS, repeat=len(free)):
        subs = dict(zip(free, combo, strict=False))
        try:
            value = complex(difference.subs(subs).evalf())
        except (TypeError, ValueError):
            continue
        if abs(value) > 1e-9:
            return {str(sym): to_text(val) for sym, val in subs.items()}
    return None


def _sampled(ctx: Ctx) -> dict[str, Any]:
    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("'variables' must be a non-empty list")
    allowed = {str(v) for v in variables}
    left = _parse_side(ctx, "left", allowed)
    right = _parse_side(ctx, "right", allowed)
    relation = str(ctx.require("relation"))
    requested = int(ctx.get("samples", 1000))
    samples = min(requested, ctx.limits.max_samples)
    return sample_relation(
        left,
        right,
        relation,
        [str(v) for v in variables],
        ctx.constraints,
        samples=samples,
        seed=ctx.limits.seed,
    )


def _sampling_outcome(result: dict[str, Any], *, witness_kind: str) -> Outcome:
    metadata = {
        "samples_used": result["samples_used"],
        "seed": result["seed"],
    }
    warnings = []
    if result.get("used_default_domain"):
        warnings.append("no domain provided for some variables; sampled default [-10, 10]")
    if result["found"]:
        witness = {
            k: v
            for k, v in result.items()
            if k in ("assignment", "left_value", "right_value", "relation")
        }
        return verification_result(
            status="counterexample_found",
            certainty="disproved",
            method="counterexample",
            result=witness,
            result_kind="witness",
            backend="mpmath",
            certificate_=certificate(
                "counterexample",
                "a sampled point violates the claim",
                machine_checkable=True,
                details=witness,
            ),
            warnings=warnings,
            metadata=metadata,
        )
    warnings.append("numeric sampling is not proof")
    return verification_result(
        status="no_counterexample_found",
        certainty="evidence",
        method="numeric_sampling",
        result=None,
        backend="mpmath",
        explanation="No counterexample found in the sampled bounded domain. Not a proof.",
        warnings=warnings,
        metadata=metadata,
    )


@handler("verification_compute", "check_inequality_sampled")
def check_inequality_sampled(ctx: Ctx) -> Outcome:
    return _sampling_outcome(_sampled(ctx), witness_kind="verification")


@handler("verification_compute", "search_counterexample")
def search_counterexample(ctx: Ctx) -> Outcome:
    return _sampling_outcome(_sampled(ctx), witness_kind="witness")
