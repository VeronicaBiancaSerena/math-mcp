"""Complex number operations: simplification, polar/rectangular forms, roots of unity."""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.backends.sympy_backend import to_latex
from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import (
    Ctx,
    Outcome,
    condition,
    object_result,
    solution_set_result,
    value_result,
)
from math_mcp.tools.dispatch import handler

# SymPy's ``arg`` returns the principal value in (-pi, pi]. This is a branch-cut
# convention, so results that expose an argument must declare it as a structured branch
# condition (guide §10.2/§11.1) and record the convention in metadata (guide §21).
_ARG_BRANCH_AST: dict[str, Any] = {
    "op": "and",
    "args": [
        {"op": "lt", "left": {"op": "neg", "arg": {"const": "pi"}}, "right": {"var": "arg"}},
        {"op": "le", "left": {"var": "arg"}, "right": {"const": "pi"}},
    ],
}


def _arg_branch_condition() -> dict[str, Any]:
    return condition(
        "-pi < arg <= pi",
        condition_ast=_ARG_BRANCH_AST,
        source="branch",
        variables=["arg"],
        description="argument uses SymPy's principal branch (-pi, pi]",
    )


_ARG_BRANCH_CONVENTIONS = {"arg": "principal value in (-pi, pi]"}


@handler("complex_compute", "complex_simplify")
def complex_simplify(ctx: Ctx) -> Outcome:
    expr = ctx.expression(allowed_symbols=ctx.declared_symbols())
    out = sp.simplify(expr)
    return value_result(out, latex=to_latex(out), certainty="exact", method="symbolic")


@handler("complex_compute", "complex_mod_arg")
def complex_mod_arg(ctx: Ctx) -> Outcome:
    expr = parse_expression(ctx.require_str("expression"), limits=ctx.limits)
    info = {
        "modulus": to_text(sp.simplify(sp.Abs(expr))),
        "argument": to_text(sp.simplify(sp.arg(expr))),
        "conjugate": to_text(sp.simplify(sp.conjugate(expr))),
        "real_part": to_text(sp.simplify(sp.re(expr))),
        "imag_part": to_text(sp.simplify(sp.im(expr))),
    }
    return object_result(
        info,
        certainty="exact",
        method="symbolic",
        conditions=[_arg_branch_condition()],
        metadata={"branch_conventions": _ARG_BRANCH_CONVENTIONS},
    )


@handler("complex_compute", "complex_to_polar")
def complex_to_polar(ctx: Ctx) -> Outcome:
    expr = parse_expression(ctx.require_str("expression"), limits=ctx.limits)
    info = {
        "modulus": to_text(sp.simplify(sp.Abs(expr))),
        "argument": to_text(sp.simplify(sp.arg(expr))),
    }
    return object_result(
        info,
        certainty="exact",
        method="symbolic",
        conditions=[_arg_branch_condition()],
        metadata={"branch_conventions": _ARG_BRANCH_CONVENTIONS},
    )


@handler("complex_compute", "complex_from_polar")
def complex_from_polar(ctx: Ctx) -> Outcome:
    modulus = parse_expression(ctx.require_str("modulus"), limits=ctx.limits)
    argument = parse_expression(ctx.require_str("argument"), limits=ctx.limits)
    rectangular = sp.simplify(modulus * (sp.cos(argument) + sp.I * sp.sin(argument)))
    return value_result(
        rectangular, latex=to_latex(rectangular), certainty="exact", method="symbolic"
    )


@handler("complex_compute", "complex_roots_of_unity")
def complex_roots_of_unity(ctx: Ctx) -> Outcome:
    n = int(ctx.require("n"))
    if n < 1 or n > 1000:
        raise InvalidInput("n must be between 1 and 1000")
    roots = [to_text(sp.simplify(sp.exp(2 * sp.pi * sp.I * k / n))) for k in range(n)]
    return object_result({"roots": roots, "n": n}, certainty="exact", method="symbolic")


@handler("complex_compute", "complex_equation_solve")
def complex_equation_solve(ctx: Ctx) -> Outcome:
    var_name = ctx.require_str("variable")
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols={var_name}
    )
    z = parse_symbol(var_name)
    solutions = sp.solve(sp.Eq(expr, 0), z, dict=False)
    return solution_set_result(
        [to_text(s) for s in solutions], certainty="exact", method="symbolic"
    )
