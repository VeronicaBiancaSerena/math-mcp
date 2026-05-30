"""Inequality operations: symbolic solving/reducing, symbolic proof, and sampling."""

from __future__ import annotations

import sympy as sp

from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, certificate, solution_set_result, verification_result
from math_mcp.tools.dispatch import handler
from math_mcp.tools.verification import _sampled, _sampling_outcome

_RELATIONS = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge, "==": sp.Eq, "!=": sp.Ne}


def _relation(ctx: Ctx) -> str:
    relation = str(ctx.require("relation"))
    if relation not in _RELATIONS:
        raise InvalidInput(f"unsupported relation '{relation}'")
    return relation


@handler("inequality_compute", "inequality_domain_solve")
def inequality_domain_solve(ctx: Ctx) -> Outcome:
    var_name = ctx.require_str("variable")
    var = sp.Symbol(var_name, real=True)
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols={var_name}
    ).subs(sp.Symbol(var_name), var)
    relation = _relation(ctx)
    right_raw = ctx.get("right")
    rhs = (
        parse_expression(str(right_raw), limits=ctx.limits)
        if right_raw is not None
        else sp.Integer(0)
    )
    rel = _RELATIONS[relation](expr, rhs)
    solution = sp.solve_univariate_inequality(rel, var, relational=False)
    return solution_set_result(
        to_text(solution),
        certainty="exact",
        method="symbolic",
        certificate_=certificate("symbolic_simplification", "solution set derived symbolically"),
    )


@handler("inequality_compute", "inequality_reduce")
def inequality_reduce(ctx: Ctx) -> Outcome:
    var_name = ctx.require_str("variable")
    var = sp.Symbol(var_name, real=True)
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols={var_name}
    ).subs(sp.Symbol(var_name), var)
    relation = _relation(ctx)
    right_raw = ctx.get("right")
    rhs = (
        parse_expression(str(right_raw), limits=ctx.limits)
        if right_raw is not None
        else sp.Integer(0)
    )
    rel = _RELATIONS[relation](expr, rhs)
    reduced = sp.reduce_inequalities([rel], [var])
    return solution_set_result(to_text(reduced), certainty="exact", method="symbolic")


@handler("inequality_compute", "inequality_check_symbolic")
def inequality_check_symbolic(ctx: Ctx) -> Outcome:
    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("'variables' must be a non-empty list")
    allowed = {str(v) for v in variables}
    left = parse_expression(ctx.require_str("left"), limits=ctx.limits, allowed_symbols=allowed)
    right = parse_expression(ctx.require_str("right"), limits=ctx.limits, allowed_symbols=allowed)
    relation = _relation(ctx)
    # Treat variables as real by default (inequalities are over the reals), merging any
    # explicit domain/assumption-derived assumptions so sign inference can use them.
    subs = {}
    for name in allowed:
        constraint = ctx.constraints.get(name)
        assumptions = {"real": True, **constraint.sympy_assumptions()}
        subs[sp.Symbol(name)] = sp.Symbol(name, **assumptions)
    diff = sp.simplify((left - right).subs(subs))

    checks = {
        ">": diff.is_positive,
        ">=": diff.is_nonnegative,
        "<": diff.is_negative,
        "<=": diff.is_nonpositive,
        "==": diff.is_zero,
        "!=": diff.is_nonzero,
    }
    verdict = checks[relation]
    if verdict is True:
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            result={"holds": True},
            certificate_=certificate(
                "symbolic_simplification",
                f"sign of (left - right) establishes '{relation}'",
                machine_checkable=True,
            ),
        )
    if verdict is False:
        return verification_result(
            status="disproved_by_counterexample",
            certainty="disproved",
            method="symbolic",
            result={"holds": False},
            explanation="the relation does not hold under the given assumptions",
        )
    return verification_result(
        status="unknown",
        certainty="unknown",
        method="none",
        result={"holds": "unknown"},
        result_kind="none",
        explanation="could not determine the sign symbolically; try sampling instead",
    )


@handler("inequality_compute", "inequality_counterexample_search")
def inequality_counterexample_search(ctx: Ctx) -> Outcome:
    return _sampling_outcome(_sampled(ctx), witness_kind="witness")


@handler("inequality_compute", "inequality_sample")
def inequality_sample(ctx: Ctx) -> Outcome:
    return _sampling_outcome(_sampled(ctx), witness_kind="verification")
