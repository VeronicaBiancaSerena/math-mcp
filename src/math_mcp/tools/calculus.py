"""Calculus operations: differentiation, integration, limits, series, numeric evaluation."""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.backends.sympy_backend import to_latex
from math_mcp.errors import BackendInternalError, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, condition, object_result, value_result
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


def _optimize_constraints(ctx: Ctx, allowed: set[str]) -> list[dict[str, Any]]:
    raw = ctx.require("constraints")
    if not isinstance(raw, list) or not raw:
        raise InvalidInput("'constraints' must be a non-empty list of relation objects")
    out: list[dict[str, Any]] = []
    for c in raw:
        if not isinstance(c, dict):
            raise InvalidInput("each constraint must be an object with relation/left/right")
        out.append(
            {
                "relation": str(c.get("relation", "==")),
                "left": parse_expression(
                    str(c["left"]), limits=ctx.limits, allowed_symbols=allowed
                ),
                "right": parse_expression(
                    str(c.get("right", "0")), limits=ctx.limits, allowed_symbols=allowed
                ),
            }
        )
    return out


@handler("calculus_compute", "constrained_optimize")
def constrained_optimize(ctx: Ctx) -> Outcome:
    """Optimize an objective subject to constraints (V1 §9/§24).

    Two honest paths, both capped at ``certainty="evidence"`` (we do not prove global
    optimality): ``symbolic_lagrange`` returns the Lagrange critical points for equality
    constraints; ``numeric`` runs a SciPy constrained local search with reported residuals.
    """
    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("'variables' must be a non-empty list")
    names = [str(v) for v in variables]
    allowed = set(names)
    objective = parse_expression(
        ctx.require_str("objective"), limits=ctx.limits, allowed_symbols=allowed
    )
    goal = str(ctx.get("goal", "min"))
    if goal not in ("min", "max"):
        raise InvalidInput("goal must be 'min' or 'max'")
    constraints = _optimize_constraints(ctx, allowed)

    all_equality = all(c["relation"] == "==" for c in constraints)
    method = str(ctx.get("method") or ("symbolic_lagrange" if all_equality else "numeric"))
    if method == "symbolic_lagrange":
        return _lagrange_optimize(ctx, objective, names, goal, constraints)
    if method == "numeric":
        return _numeric_constrained(ctx, objective, names, goal, constraints)
    raise InvalidInput("method must be 'symbolic_lagrange' or 'numeric'")


def _lagrange_optimize(
    ctx: Ctx, objective: Any, names: list[str], goal: str, constraints: list[dict[str, Any]]
) -> Outcome:
    if any(c["relation"] != "==" for c in constraints):
        raise InvalidInput(
            "symbolic_lagrange supports equality constraints only; use method='numeric' "
            "for inequality constraints"
        )
    syms = [parse_symbol(n) for n in names]
    gs = [c["left"] - c["right"] for c in constraints]
    lambdas = list(sp.symbols(f"_lam0:{len(gs)}"))
    lagrangian = objective - sum(lam * g for lam, g in zip(lambdas, gs, strict=True))
    equations = [sp.diff(lagrangian, s) for s in syms] + gs
    solutions = sp.solve(equations, [*syms, *lambdas], dict=True)

    candidates: list[dict[str, Any]] = []
    for sol in solutions:
        if any(not sol.get(s, sp.Symbol("u")).is_real for s in syms):
            continue
        point = {str(s): to_text(sol[s]) for s in syms if s in sol}
        if len(point) != len(syms):
            continue
        value = sp.simplify(objective.subs({s: sol[s] for s in syms}))
        if not value.is_real:
            continue
        candidates.append({"point": point, "value": to_text(value), "_value": value})

    if not candidates:
        return Outcome(
            status="unknown",
            certainty="unknown",
            method="none",
            result_kind="none",
            result=None,
            backend="sympy",
            explanation="No real Lagrange critical point was found for these constraints.",
            warnings=["no closed-form constrained optimum found"],
            metadata_extra={"method_detail": "symbolic_lagrange"},
        )

    best = (max if goal == "max" else min)(candidates, key=lambda c: c["_value"])
    for c in candidates:
        c.pop("_value", None)
    best.pop("_value", None)
    result = {
        "goal": goal,
        "optimum": best["point"],
        "value": best["value"],
        "candidates": candidates,
        "constraints": [f"{to_text(c['left'])} == {to_text(c['right'])}" for c in constraints],
    }
    return object_result(
        result,
        certainty="evidence",
        method="symbolic",
        backend="sympy",
        warnings=[
            "Lagrange critical points are candidate extrema; global optimality is not proved"
        ],
        metadata={"method_detail": "symbolic_lagrange"},
    )


def _numeric_constrained(
    ctx: Ctx, objective: Any, names: list[str], goal: str, constraints: list[dict[str, Any]]
) -> Outcome:
    from math_mcp.backends.scipy_backend import optimize_constrained

    start_raw = ctx.get("start")
    start = (
        [float(parse_expression(str(s), limits=ctx.limits)) for s in start_raw]
        if isinstance(start_raw, list)
        else None
    )
    result = optimize_constrained(objective, names, goal, constraints, start)
    if not result["converged"]:
        from math_mcp.errors import NumericConvergenceFailed

        raise NumericConvergenceFailed("constrained numeric optimization did not converge")
    return object_result(
        result,
        certainty="evidence",
        method="numeric_optimization",
        backend="scipy",
        warnings=["numeric constrained optimization is evidence, not a proof"],
        metadata={"method_detail": "numeric"},
    )
