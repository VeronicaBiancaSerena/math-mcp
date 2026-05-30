"""Propositional logic and boolean algebra operations."""

from __future__ import annotations

import itertools
from typing import Any

import sympy as sp

from math_mcp.errors import DomainUnsupported, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import (
    Ctx,
    Outcome,
    certificate,
    object_result,
    value_result,
    verification_result,
)
from math_mcp.tools.dispatch import handler


def _vars(ctx: Ctx) -> set[str]:
    raw = ctx.require("variables")
    if not isinstance(raw, list) or not raw:
        raise InvalidInput("'variables' must be a non-empty list")
    return {str(v) for v in raw}


@handler("logic_compute", "boolean_simplify")
def boolean_simplify(ctx: Ctx) -> Outcome:
    raw = ctx.get("variables")
    allowed = {str(v) for v in raw} if isinstance(raw, list) and raw else None
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols=allowed
    )
    out = sp.simplify_logic(expr)
    return value_result(out, certainty="exact", method="symbolic")


@handler("logic_compute", "truth_table")
def truth_table(ctx: Ctx) -> Outcome:
    names = sorted(_vars(ctx))
    if len(names) > 12:
        raise InvalidInput("truth_table supports at most 12 variables")
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols=set(names)
    )
    symbols = [parse_symbol(n) for n in names]
    rows = []
    for combo in itertools.product([False, True], repeat=len(names)):
        subs = dict(zip(symbols, combo, strict=False))
        rows.append(
            {"assignment": dict(zip(names, combo, strict=False)), "value": bool(expr.subs(subs))}
        )
    return object_result(
        {"variables": names, "rows": rows}, certainty="exact", method="finite_exhaustive"
    )


@handler("logic_compute", "logic_equivalence_check")
def logic_equivalence_check(ctx: Ctx) -> Outcome:
    allowed = _vars(ctx)
    left = parse_expression(ctx.require_str("left"), limits=ctx.limits, allowed_symbols=allowed)
    right = parse_expression(ctx.require_str("right"), limits=ctx.limits, allowed_symbols=allowed)
    equivalent = not bool(sp.satisfiable(sp.Xor(left, right)))
    if equivalent:
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            result={"equivalent": True},
            certificate_=certificate(
                "symbolic_simplification", "left XOR right is unsatisfiable", machine_checkable=True
            ),
        )
    return verification_result(
        status="disproved_by_counterexample",
        certainty="disproved",
        method="finite_exhaustive",
        result={"equivalent": False},
        explanation="the formulas differ on some assignment",
    )


@handler("logic_compute", "logic_satisfiability")
def logic_satisfiability(ctx: Ctx) -> Outcome:
    allowed = _vars(ctx)
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols=allowed
    )
    model = sp.satisfiable(expr)
    if model is False:
        return verification_result(
            status="proved_by_finite_exhaustion",
            certainty="proved",
            method="finite_exhaustive",
            result={"satisfiable": False},
            certificate_=certificate(
                "finite_exhaustion", "no assignment satisfies the formula", machine_checkable=True
            ),
        )
    assignment = {str(k): bool(v) for k, v in model.items()}
    return verification_result(
        status="success",
        certainty="exact",
        method="finite_exhaustive",
        result_kind="witness",
        result={"satisfiable": True, "model": assignment},
    )


@handler("logic_compute", "normal_form_convert")
def normal_form_convert(ctx: Ctx) -> Outcome:
    allowed = _vars(ctx)
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols=allowed
    )
    form = str(ctx.require("form"))
    if form == "cnf":
        out = sp.to_cnf(expr, simplify=True)
    elif form == "dnf":
        out = sp.to_dnf(expr, simplify=True)
    elif form == "nnf":
        out = sp.to_nnf(expr, simplify=True)
    else:
        raise InvalidInput(f"unsupported normal form '{form}'")
    return value_result(out, certainty="exact", method="symbolic", metadata={"form": form})


@handler("logic_compute", "finite_quantifier_check")
def finite_quantifier_check(ctx: Ctx) -> Outcome:
    quantifier = str(ctx.require("quantifier"))
    names = [str(v) for v in _vars(ctx)]
    predicate = parse_expression(
        ctx.require_str("predicate"), limits=ctx.limits, allowed_symbols=set(names)
    )
    domains = _finite_domains(ctx, names)
    symbols = {n: parse_symbol(n) for n in names}

    witness: dict[str, str] | None = None
    counterexample: dict[str, str] | None = None
    holds = quantifier == "forall"
    for combo in itertools.product(*(domains[n] for n in names)):
        subs = {symbols[n]: combo[i] for i, n in enumerate(names)}
        truth = bool(predicate.subs(subs))
        assignment = {n: to_text(combo[i]) for i, n in enumerate(names)}
        if quantifier == "forall" and not truth:
            counterexample = assignment
            holds = False
            break
        if quantifier == "exists" and truth:
            witness = assignment
            holds = True
            break

    if holds:
        result: dict[str, Any] = {"holds": True}
        if witness is not None:
            result["witness"] = witness
        return verification_result(
            status="proved_by_finite_exhaustion",
            certainty="proved",
            method="finite_exhaustive",
            result=result,
            result_kind="witness" if witness else "verification",
            certificate_=certificate(
                "finite_exhaustion",
                "checked exhaustively over finite domain",
                machine_checkable=True,
            ),
        )
    result = {"holds": False}
    if counterexample is not None:
        result["counterexample"] = counterexample
    return verification_result(
        status="disproved_by_counterexample",
        certainty="disproved",
        method="finite_exhaustive",
        result=result,
        result_kind="witness" if counterexample else "verification",
    )


def _finite_domains(ctx: Ctx, names: list[str]) -> dict[str, list[Any]]:
    domains: dict[str, list[Any]] = {}
    for name in names:
        constraint = ctx.constraints.get(name)
        if constraint.values is not None:
            domains[name] = list(constraint.values)
        elif (
            constraint.kind == "integer"
            and constraint.lower is not None
            and constraint.upper is not None
        ):
            domains[name] = [
                sp.Integer(v) for v in range(int(constraint.lower), int(constraint.upper) + 1)
            ]
        elif constraint.kind == "boolean":
            domains[name] = [sp.false, sp.true]
        else:
            raise DomainUnsupported(
                f"finite_quantifier_check requires a finite/bounded domain for '{name}'"
            )
    return domains
