"""Ordinary differential equation operations.

Symbolic verification of a candidate solution can yield a proof; numeric integration is
evidence only. The residual interface uses ``y``, ``dy``, ``d2y``, ``d3y`` to denote the
solution and its derivatives, avoiding undefined-function parsing in the safe parser.
"""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.backends.scipy_backend import solve_ode_numeric
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import (
    Ctx,
    Outcome,
    certificate,
    object_result,
    solution_set_result,
    value_result,
    verification_result,
)
from math_mcp.tools.dispatch import handler

_DERIV_NAMES = ["y", "dy", "d2y", "d3y"]


def _params(ctx: Ctx) -> list[str]:
    raw = ctx.get("parameters") or []
    return [str(p) for p in raw]


@handler("ode_compute", "ode_verify_solution")
def ode_verify_solution(ctx: Ctx) -> Outcome:
    var = ctx.require_str("variable")
    x = parse_symbol(var)
    params = _params(ctx)
    solution = parse_expression(
        ctx.require_str("solution"), limits=ctx.limits, allowed_symbols={var, *params}
    )
    derivatives = {
        "y": solution,
        "dy": sp.diff(solution, x, 1),
        "d2y": sp.diff(solution, x, 2),
        "d3y": sp.diff(solution, x, 3),
    }
    residual = parse_expression(
        ctx.require_str("residual"),
        limits=ctx.limits,
        allowed_symbols={var, *params, *_DERIV_NAMES},
    )
    subs = {parse_symbol(name): expr for name, expr in derivatives.items()}
    value = sp.simplify(residual.subs(subs))
    if value == 0 or value.equals(0):
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            result={"satisfies": True},
            certificate_=certificate(
                "symbolic_simplification",
                "residual simplified to 0 after substitution",
                machine_checkable=True,
                details={"residual": "0"},
            ),
        )
    return verification_result(
        status="disproved_by_counterexample",
        certainty="disproved",
        method="symbolic",
        result={"satisfies": False, "residual": to_text(value)},
        explanation="the candidate does not satisfy the ODE",
    )


def _build_ode(ctx: Ctx) -> tuple[Any, Any, Any]:
    var = ctx.require_str("variable")
    func = ctx.require_str("function")
    x = sp.Symbol(var)
    f = sp.Function(func)
    residual = parse_expression(
        ctx.require_str("equation"), limits=ctx.limits, allowed_symbols={var, *_DERIV_NAMES}
    )
    subs = {
        parse_symbol("y"): f(x),
        parse_symbol("dy"): f(x).diff(x),
        parse_symbol("d2y"): f(x).diff(x, 2),
        parse_symbol("d3y"): f(x).diff(x, 3),
    }
    return sp.Eq(residual.subs(subs), 0), f(x), x


@handler("ode_compute", "ode_solve_symbolic")
def ode_solve_symbolic(ctx: Ctx) -> Outcome:
    eq, fx, _x = _build_ode(ctx)
    solution = sp.dsolve(eq, fx)
    return solution_set_result(to_text(solution), certainty="exact", method="symbolic")


@handler("ode_compute", "ode_classify")
def ode_classify(ctx: Ctx) -> Outcome:
    eq, fx, _x = _build_ode(ctx)
    classes = sp.classify_ode(eq, fx)
    return object_result({"classification": list(classes)}, certainty="exact", method="symbolic")


@handler("ode_compute", "ode_initial_value_solve")
def ode_initial_value_solve(ctx: Ctx) -> Outcome:
    eq, fx, x = _build_ode(ctx)
    ics_raw = ctx.get("initial_conditions") or {}
    ics = {
        fx.subs(x, int(k)): parse_expression(str(v), limits=ctx.limits) for k, v in ics_raw.items()
    }
    solution = sp.dsolve(eq, fx, ics=ics or None)
    return value_result(to_text(solution), certainty="exact", method="symbolic")


@handler("ode_compute", "ode_solve_numeric")
def ode_solve_numeric_handler(ctx: Ctx) -> Outcome:
    t_var = ctx.require_str("variable")
    y_var = ctx.require_str("function")
    rhs = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols={t_var, y_var}
    )
    t_span_raw = ctx.require("t_span")
    y0_raw = ctx.require("y0")
    t_span = (
        float(parse_expression(str(t_span_raw[0]), limits=ctx.limits)),
        float(parse_expression(str(t_span_raw[1]), limits=ctx.limits)),
    )
    y0 = [float(parse_expression(str(v), limits=ctx.limits)) for v in y0_raw]
    points = int(ctx.get("points", 50))
    result = solve_ode_numeric(rhs, t_var, y_var, t_span, y0, points)
    return object_result(
        result,
        certainty="evidence",
        method="numeric_sampling",
        backend="scipy",
        warnings=["numeric ODE integration is an approximate trajectory, not a proof"],
    )
