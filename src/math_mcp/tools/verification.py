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
from math_mcp.errors import DomainUnsupported, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
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


# ---------------------------------------------------------------------------
# Constrained identity verification (V1 §8/§24).
#
# Unlike check_identity, this never falls back to free-variable grid sampling that ignores
# the constraints. It proves an identity *on a constraint surface* by an explicit
# parameterization or substitution (symbolic), and only otherwise samples points that
# actually satisfy the constraints. A counterexample is therefore always a genuine point
# of the feasible set, never an unrelated free-variable assignment.
# ---------------------------------------------------------------------------

# Deterministic grid (rationals + 0) used for constraint-feasible sampling and for the
# parameter/free-variable counterexample search; keeps the operation reproducible.
_GRID_POINTS = [
    sp.Integer(-2),
    sp.Integer(-1),
    sp.Rational(-1, 2),
    sp.Integer(0),
    sp.Rational(1, 2),
    sp.Integer(1),
    sp.Integer(2),
    sp.Integer(3),
]
_TOL = 1e-9


@handler("verification_compute", "check_identity_constrained")
def check_identity_constrained(ctx: Ctx) -> Outcome:
    var_names = [str(v) for v in (ctx.get("variables") or [])]
    allowed = set(var_names) or None
    left = parse_expression(ctx.require_str("left"), limits=ctx.limits, allowed_symbols=allowed)
    right = parse_expression(ctx.require_str("right"), limits=ctx.limits, allowed_symbols=allowed)
    constraints = _parse_constraints(ctx, allowed)

    param = ctx.get("parameterization")
    if isinstance(param, dict) and isinstance(param.get("substitutions"), dict):
        param_vars = {str(v) for v in (param.get("variables") or [])}
        return _constrained_symbolic(
            ctx,
            left,
            right,
            constraints,
            sub_dict=param["substitutions"],
            value_symbols=param_vars or None,
            mode="parameterized_symbolic",
        )

    subs_payload = ctx.get("substitutions")
    if isinstance(subs_payload, dict) and subs_payload:
        return _constrained_symbolic(
            ctx,
            left,
            right,
            constraints,
            sub_dict=subs_payload,
            value_symbols=allowed,
            mode="substitution_symbolic",
        )

    return _constrained_sampling(ctx, left, right, constraints, var_names)


def _parse_constraints(ctx: Ctx, allowed: set[str] | None) -> list[dict[str, Any]]:
    raw = ctx.get("constraints") or []
    if not isinstance(raw, list):
        raise InvalidInput("'constraints' must be a list")
    out: list[dict[str, Any]] = []
    for c in raw:
        if not isinstance(c, dict):
            raise InvalidInput("each constraint must be an object with relation/left/right")
        relation = str(c.get("relation", "=="))
        left = parse_expression(str(c["left"]), limits=ctx.limits, allowed_symbols=allowed)
        right = parse_expression(
            str(c.get("right", "0")), limits=ctx.limits, allowed_symbols=allowed
        )
        out.append({"relation": relation, "left": left, "right": right, "raw": c})
    return out


def _constrained_symbolic(
    ctx: Ctx,
    left: Any,
    right: Any,
    constraints: list[dict[str, Any]],
    *,
    sub_dict: dict[str, Any],
    value_symbols: set[str] | None,
    mode: str,
) -> Outcome:
    """Prove an identity on the constraint surface via an explicit substitution.

    The substitution (a parameterization or a constraint-elimination) must first satisfy
    every equality constraint; otherwise the request is reported as unsupported rather
    than silently trusted.
    """
    subs = {
        parse_symbol(str(var)): parse_expression(
            str(expr), limits=ctx.limits, allowed_symbols=value_symbols
        )
        for var, expr in sub_dict.items()
    }

    unsatisfied = _unsatisfied_equality_constraints(constraints, subs)
    if unsatisfied:
        exc = DomainUnsupported(
            f"the supplied {mode.split('_')[0]} does not satisfy the equality constraint(s) "
            f"{unsatisfied}; provide a substitution that lies on the constraint surface."
        )
        exc.extra_metadata = {"constraint_mode": "unsupported"}
        raise exc

    difference = sp.simplify((left - right).subs(subs))
    cert_details = {
        "constraints": [_constraint_text(c) for c in constraints],
        "substitutions": {str(k): to_text(v) for k, v in subs.items()},
        "constraint_satisfaction": "all equality constraints reduce to 0 under the substitution",
        "post_substitution_difference": to_text(difference),
    }
    metadata = {"constraint_mode": mode}

    if difference == 0:
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            result="0",
            certificate_=certificate(
                "symbolic_simplification",
                "left - right reduces to 0 on the constraint surface after substitution",
                machine_checkable=True,
                details=cert_details,
            ),
            metadata=metadata,
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
                "a constraint-satisfying point makes left and right differ",
                machine_checkable=True,
                details={**cert_details, "witness": witness},
            ),
            metadata=metadata,
        )
    return verification_result(
        status="numeric_evidence_only",
        certainty="evidence",
        method="numeric_sampling",
        backend="sympy",
        explanation=(
            "Substitution did not simplify to 0 and no counterexample was found on the "
            "constraint surface. This is not a proof."
        ),
        warnings=["numeric sampling is not proof"],
        metadata=metadata,
    )


def _unsatisfied_equality_constraints(
    constraints: list[dict[str, Any]], subs: dict[Any, Any]
) -> list[str]:
    bad: list[str] = []
    for c in constraints:
        if c["relation"] != "==":
            continue
        residual = sp.simplify((c["left"] - c["right"]).subs(subs))
        if residual != 0:
            bad.append(_constraint_text(c))
    return bad


def _constrained_sampling(
    ctx: Ctx,
    left: Any,
    right: Any,
    constraints: list[dict[str, Any]],
    var_names: list[str],
) -> Outcome:
    """Search a deterministic grid restricted to constraint-feasible points only."""
    if not var_names:
        raise InvalidInput("'variables' must be a non-empty list for constrained sampling")
    symbols = {name: parse_symbol(name) for name in var_names}
    grids = [_candidate_values(ctx, name) for name in var_names]

    total = 1
    for g in grids:
        total *= len(g)
    if total > ctx.limits.max_samples:
        raise InvalidInput("constrained sampling space is too large; reduce variables or domains")

    metadata = {"constraint_mode": "constrained_sampling"}
    difference = left - right
    feasible = 0
    for combo in itertools.product(*grids):
        assignment = {symbols[name]: combo[i] for i, name in enumerate(var_names)}
        if not _feasible(constraints, assignment):
            continue
        feasible += 1
        try:
            value = complex(difference.subs(assignment).evalf())
        except (TypeError, ValueError):
            continue
        if abs(value) > _TOL:
            witness = {name: to_text(combo[i]) for i, name in enumerate(var_names)}
            return verification_result(
                status="disproved_by_counterexample",
                certainty="disproved",
                method="counterexample",
                result=witness,
                result_kind="witness",
                certificate_=certificate(
                    "counterexample",
                    "a constraint-satisfying sampled point makes left and right differ",
                    machine_checkable=True,
                    details={
                        "constraints": [_constraint_text(c) for c in constraints],
                        "witness": witness,
                    },
                ),
                metadata={**metadata, "feasible_samples": feasible},
            )

    if feasible == 0:
        exc = DomainUnsupported(
            "could not find constraint-feasible sample points on the deterministic grid "
            "(equality constraints rarely admit grid points); provide a 'parameterization' "
            "or 'substitutions' for an exact symbolic check."
        )
        exc.extra_metadata = {"constraint_mode": "unsupported"}
        raise exc

    return verification_result(
        status="numeric_evidence_only",
        certainty="evidence",
        method="numeric_sampling",
        backend="sympy",
        explanation=(
            "No counterexample found among constraint-feasible sampled points. Not a proof."
        ),
        warnings=["numeric sampling is not proof"],
        metadata={**metadata, "feasible_samples": feasible},
    )


def _candidate_values(ctx: Ctx, name: str) -> list[Any]:
    """Per-variable grid: a finite/integer domain when given, else a default rational grid."""
    c = ctx.constraints.get(name)
    if c.values is not None:
        return list(c.values)
    if c.kind == "integer" and c.lower is not None and c.upper is not None:
        lo, hi = int(c.lower), int(c.upper)
        return [sp.Integer(v) for v in range(lo, hi + 1)]
    return list(_GRID_POINTS)


def _feasible(constraints: list[dict[str, Any]], assignment: dict[Any, Any]) -> bool:
    for c in constraints:
        try:
            value = complex((c["left"] - c["right"]).subs(assignment).evalf())
        except (TypeError, ValueError):
            return False
        if not _relation_holds(value.real, c["relation"]):
            return False
    return True


def _relation_holds(value: float, relation: str) -> bool:
    if relation == "==":
        return abs(value) <= _TOL
    if relation == "!=":
        return abs(value) > _TOL
    if relation == "<":
        return value < -_TOL
    if relation == "<=":
        return value <= _TOL
    if relation == ">":
        return value > _TOL
    if relation == ">=":
        return value >= -_TOL
    raise InvalidInput(f"unsupported constraint relation '{relation}'")


def _constraint_text(c: dict[str, Any]) -> str:
    return f"{to_text(c['left'])} {c['relation']} {to_text(c['right'])}"
