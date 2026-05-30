"""Algebra operations: simplify/expand/factor/cancel/together, solving, roots, Groebner."""

from __future__ import annotations

import sympy as sp

from math_mcp.backends.sympy_backend import to_latex
from math_mcp.errors import BackendInternalError, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, solution_set_result, value_result
from math_mcp.tools.dispatch import handler

_UNARY = {
    "simplify_expression": sp.simplify,
    "expand_expression": sp.expand,
    "factor_expression": sp.factor,
    "cancel_expression": sp.cancel,
    "together_expression": sp.together,
}


def _unary_handler(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    fn = _UNARY[ctx.operation]
    try:
        out = fn(expr)
    except Exception as exc:  # noqa: BLE001
        raise BackendInternalError(f"sympy {ctx.operation} failed: {type(exc).__name__}") from exc
    return value_result(out, latex=to_latex(out), certainty="exact", method="backend")


for _name in _UNARY:
    handler("algebra_compute", _name)(_unary_handler)


@handler("algebra_compute", "solve_equation")
def solve_equation(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    right_raw = ctx.get("right")
    rhs = (
        parse_expression(str(right_raw), limits=ctx.limits)
        if right_raw is not None
        else sp.Integer(0)
    )
    solutions = sp.solve(sp.Eq(expr, rhs), var, dict=False)
    result = [to_text(s) for s in solutions]
    return solution_set_result(result, certainty="exact", method="symbolic")


@handler("algebra_compute", "solve_system")
def solve_system(ctx: Ctx) -> Outcome:
    equations = ctx.require("equations")
    variables = ctx.require("variables")
    if not isinstance(equations, list) or not isinstance(variables, list):
        raise InvalidInput("'equations' and 'variables' must be lists")
    allowed = {str(v) for v in variables}
    exprs = [
        parse_expression(str(e), limits=ctx.limits, allowed_symbols=allowed) for e in equations
    ]
    syms = [parse_symbol(str(v)) for v in variables]
    solution = sp.solve(exprs, syms, dict=True)
    result = [{str(k): to_text(v) for k, v in sol.items()} for sol in solution]
    return solution_set_result(result, certainty="exact", method="symbolic")


@handler("algebra_compute", "polynomial_roots")
def polynomial_roots(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    var = parse_symbol(ctx.require_str("variable"))
    roots = sp.roots(sp.Poly(expr, var))
    result = {to_text(root): int(mult) for root, mult in roots.items()}
    return solution_set_result(
        {"roots_with_multiplicity": result},
        certainty="exact",
        method="symbolic",
        metadata={"note": "keys are roots, values are multiplicities"},
    )


@handler("algebra_compute", "groebner_basis")
def groebner_basis(ctx: Ctx) -> Outcome:
    polynomials = ctx.require("polynomials")
    variables = ctx.require("variables")
    if not isinstance(polynomials, list) or not isinstance(variables, list):
        raise InvalidInput("'polynomials' and 'variables' must be lists")
    allowed = {str(v) for v in variables}
    polys = [
        parse_expression(str(p), limits=ctx.limits, allowed_symbols=allowed) for p in polynomials
    ]
    syms = [parse_symbol(str(v)) for v in variables]
    order = str(ctx.get("order", "lex"))
    basis = sp.groebner(polys, *syms, order=order)
    result: list[str] = [to_text(g) for g in basis.exprs]
    return Outcome(
        status="success",
        certainty="exact",
        method="symbolic",
        result_kind="object",
        result=result,
        backend="sympy",
        metadata_extra={"monomial_order": order},
    )
