"""Calculus operations: differentiation, integration, limits, series, numeric evaluation."""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.backends.sympy_backend import to_latex
from math_mcp.errors import BackendInternalError, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, condition, value_result
from math_mcp.tools.dispatch import handler


@handler("calculus_compute", "differentiate")
def differentiate(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    order = int(ctx.get("order", 1))
    if order < 1 or order > 20:
        raise InvalidInput("order must be between 1 and 20")
    out = sp.diff(expr, var, order)
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("calculus_compute", "integrate")
def integrate(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    lower = ctx.get("lower")
    upper = ctx.get("upper")
    conditions: list[dict[str, Any]] = []
    if lower is not None and upper is not None:
        lo = parse_expression(str(lower), limits=ctx.limits)
        hi = parse_expression(str(upper), limits=ctx.limits)
        out = sp.integrate(expr, (var, lo, hi))
    else:
        out = sp.integrate(expr, var)
        conditions.append(
            condition(
                "+ C",
                source="backend",
                description="indefinite integral is defined up to a constant of integration",
            )
        )
    if out.has(sp.Integral):
        raise BackendInternalError("integral could not be evaluated in closed form")
    if out.has(sp.Piecewise):
        conditions.append(
            condition(
                to_text(out),
                source="piecewise",
                description="result is piecewise; branch conditions apply",
            )
        )
    return value_result(
        out,
        latex=to_latex(out),
        certainty="exact",
        method="symbolic",
        result_kind="value",
        conditions=conditions,
    )


@handler("calculus_compute", "limit_expression")
def limit_expression(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    point = parse_expression(str(ctx.require("point")), limits=ctx.limits)
    direction = str(ctx.get("direction", "+-"))
    if direction not in ("+", "-", "+-"):
        raise InvalidInput("direction must be one of '+', '-', '+-'")
    out = sp.limit(expr, var, point, dir=direction)
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("calculus_compute", "series_expand")
def series_expand(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    point = parse_expression(str(ctx.get("point", "0")), limits=ctx.limits)
    order = int(ctx.require("order"))
    if order < 0 or order > 30:
        raise InvalidInput("order must be between 0 and 30")
    out = sp.series(expr, var, point, order + 1)
    return value_result(
        out,
        latex=to_latex(out),
        certainty="exact",
        method="symbolic",
        result_kind="value",
    )


@handler("calculus_compute", "numeric_evaluate")
def numeric_evaluate(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    if getattr(expr, "free_symbols", set()):
        raise InvalidInput("numeric_evaluate requires an expression with no free variables")
    digits = int(ctx.get("precision_digits", ctx.limits.precision_digits))
    if digits < 15 or digits > 200:
        raise InvalidInput("precision_digits must be between 15 and 200")
    value = sp.N(expr, digits)
    return value_result(
        to_text(value),
        certainty="exact",
        method="backend",
        backend="mpmath",
        metadata={"precision_digits": digits},
    )


@handler("calculus_compute", "numeric_optimize")
def numeric_optimize(ctx: Ctx) -> Outcome:
    from math_mcp.backends.scipy_backend import optimize_expression

    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("'variables' must be a non-empty list")
    names = [str(v) for v in variables]
    expr = ctx.expression(allowed_symbols=set(names))
    goal = str(ctx.get("goal", "min"))
    start_raw = ctx.get("start")
    start = (
        [float(parse_expression(str(s), limits=ctx.limits)) for s in start_raw]
        if isinstance(start_raw, list)
        else None
    )
    result = optimize_expression(expr, names, goal, start)
    if not result["converged"]:
        from math_mcp.errors import NumericConvergenceFailed

        raise NumericConvergenceFailed("numeric optimization did not converge")
    return value_result(
        result,
        certainty="evidence",
        method="numeric_optimization",
        backend="scipy",
        result_kind="witness",
        warnings=["numeric local optimization is evidence, not a proof"],
    )
