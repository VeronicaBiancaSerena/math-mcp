"""Trigonometric operations: simplification, expansion, rewriting, equations, identities."""

from __future__ import annotations

import sympy as sp

from math_mcp.backends.sympy_backend import to_latex
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.tools.base import (
    Ctx,
    Outcome,
    certificate,
    solution_set_result,
    value_result,
    verification_result,
)
from math_mcp.tools.dispatch import handler
from math_mcp.tools.verification import _deterministic_counterexample

_REWRITE = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp}


@handler("trigonometry_compute", "trig_simplify")
def trig_simplify(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    out = sp.trigsimp(expr)
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("trigonometry_compute", "trig_expand")
def trig_expand(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    out = sp.expand_trig(expr)
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("trigonometry_compute", "trig_reduce")
def trig_reduce(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    out = sp.trigsimp(sp.expand_trig(expr))
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("trigonometry_compute", "trig_rewrite")
def trig_rewrite(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    target = str(ctx.require("target"))
    if target not in _REWRITE:
        raise ValueError(f"unsupported rewrite target '{target}'")
    out = sp.simplify(expr.rewrite(_REWRITE[target]))
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("trigonometry_compute", "solve_trig_equation")
def solve_trig_equation(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    right_raw = ctx.get("right")
    rhs = (
        parse_expression(str(right_raw), limits=ctx.limits)
        if right_raw is not None
        else sp.Integer(0)
    )
    solution = sp.solveset(sp.Eq(expr, rhs), var, domain=sp.S.Reals)
    from math_mcp.runtime.serialization import to_text

    return solution_set_result(to_text(solution), certainty="exact", method="symbolic")


@handler("trigonometry_compute", "trig_identity_check")
def trig_identity_check(ctx: Ctx) -> Outcome:
    raw = ctx.get("variables")
    allowed = {str(v) for v in raw} if isinstance(raw, list) and raw else None
    left = parse_expression(ctx.require_str("left"), limits=ctx.limits, allowed_symbols=allowed)
    right = parse_expression(ctx.require_str("right"), limits=ctx.limits, allowed_symbols=allowed)
    difference = sp.simplify(sp.expand_trig(left - right))
    if difference == 0:
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            result="0",
            certificate_=certificate(
                "symbolic_simplification",
                "expand_trig then simplify reduced left - right to 0",
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
                "counterexample", "left and right differ at a sampled point", details=witness
            ),
        )
    return verification_result(
        status="numeric_evidence_only",
        certainty="evidence",
        method="numeric_sampling",
        backend="sympy",
        explanation="Could not prove symbolically and found no counterexample at sampled points.",
        warnings=["numeric sampling is not proof"],
    )
