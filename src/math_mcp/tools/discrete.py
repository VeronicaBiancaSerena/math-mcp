"""Discrete math: combinatorial counting, finite enumeration, recurrence solving."""

from __future__ import annotations

import itertools
from typing import Any

import sympy as sp
from sympy.functions.combinatorial.numbers import (
    catalan,
    partition,
    stirling,
    subfactorial,
)

from math_mcp.errors import DomainUnsupported, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_latex, to_text
from math_mcp.tools.base import Ctx, Outcome, certificate, value_result, verification_result
from math_mcp.tools.dispatch import handler


def _int(ctx: Ctx, key: str) -> int:
    raw = ctx.require(key)
    value = parse_expression(str(raw), limits=ctx.limits)
    if not value.is_Integer or value < 0:
        raise InvalidInput(f"'{key}' must be a non-negative integer")
    return int(value)


@handler("discrete_compute", "combinatorics_count")
def combinatorics_count(ctx: Ctx) -> Outcome:
    kind = str(ctx.require("kind"))
    if kind == "factorial":
        result: Any = sp.factorial(_int(ctx, "n"))
    elif kind in ("combination", "binomial"):
        result = sp.binomial(_int(ctx, "n"), _int(ctx, "k"))
    elif kind == "permutation":
        n, k = _int(ctx, "n"), _int(ctx, "k")
        if k > n:
            raise InvalidInput("permutation requires k <= n")
        result = sp.factorial(n) / sp.factorial(n - k)
    elif kind == "multinomial":
        groups_raw = ctx.require("groups")
        if not isinstance(groups_raw, list):
            raise InvalidInput("'groups' must be a list for multinomial")
        groups = [int(parse_expression(str(g), limits=ctx.limits)) for g in groups_raw]
        result = sp.factorial(sum(groups))
        for g in groups:
            result = result / sp.factorial(g)
    elif kind == "catalan":
        result = catalan(_int(ctx, "n"))
    elif kind == "derangement":
        result = subfactorial(_int(ctx, "n"))
    elif kind == "stirling2":
        result = stirling(_int(ctx, "n"), _int(ctx, "k"))
    elif kind == "partition":
        result = partition(_int(ctx, "n"))
    else:
        raise InvalidInput(f"unsupported combinatorics kind '{kind}'")
    return value_result(sp.simplify(result), certainty="exact", method="backend", backend="python")


@handler("discrete_compute", "finite_enumeration")
def finite_enumeration(ctx: Ctx) -> Outcome:
    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("'variables' must be a non-empty list")
    names = [str(v) for v in variables]
    allowed = set(names)
    predicate = parse_expression(
        ctx.require_str("predicate"), limits=ctx.limits, allowed_symbols=allowed
    )
    domains = _finite_domains(ctx, names)

    total = 1
    for values in domains.values():
        total *= len(values)
    if total > ctx.limits.max_samples * 100:
        raise InvalidInput("enumeration space is too large")

    symbols = {name: parse_symbol(name) for name in names}
    collect = bool(ctx.get("collect_witnesses", True))
    satisfying = 0
    witnesses: list[dict[str, str]] = []
    for combo in itertools.product(*(domains[name] for name in names)):
        subs = {symbols[name]: combo[i] for i, name in enumerate(names)}
        truth = bool(predicate.subs(subs))
        if truth:
            satisfying += 1
            if collect and len(witnesses) < 25:
                witnesses.append({name: to_text(combo[i]) for i, name in enumerate(names)})

    all_true = satisfying == total
    result = {
        "total": total,
        "satisfying_count": satisfying,
        "all_satisfy": all_true,
        "witnesses": witnesses,
    }
    return verification_result(
        status="proved_by_finite_exhaustion",
        certainty="proved",
        method="finite_exhaustive",
        result=result,
        result_kind="verification",
        backend="python",
        certificate_=certificate(
            "finite_exhaustion",
            f"enumerated {total} assignments exhaustively",
            machine_checkable=True,
            details={"total": total},
        ),
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
            lo, hi = int(constraint.lower), int(constraint.upper)
            domains[name] = [sp.Integer(v) for v in range(lo, hi + 1)]
        else:
            raise DomainUnsupported(_missing_domain_message(ctx, name))
    return domains


def _missing_domain_message(ctx: Ctx, name: str) -> str:
    """Explain how to supply the required top-level ``domains`` for finite enumeration.

    A common mistake is putting ``domains`` inside ``payload``; ``domains`` is a top-level
    tool argument (guide §5.2). When that misplacement is detected, point at it directly
    rather than emitting the generic message (V1 §7.3). The field is not auto-moved: doing
    so would mask a malformed call shape.
    """
    if ctx.payload.get("domains") and not ctx.constraints.has_explicit_domains:
        return (
            "finite_enumeration received domains inside payload, but domains must be a "
            "top-level argument. Move payload.domains to the tool argument named domains."
        )
    return (
        f"finite_enumeration requires a finite or bounded-integer domain for '{name}'. "
        "Pass domains as a top-level argument, e.g. "
        'domains=[{"variable":"' + name + '","kind":"integer","lower":"0","upper":"3"}].'
    )


@handler("discrete_compute", "solve_recurrence")
def solve_recurrence(ctx: Ctx) -> Outcome:
    func_name = ctx.require_str("function")
    var_name = ctx.require_str("variable")
    n = sp.Symbol(var_name, integer=True)
    f = sp.Function(func_name)
    recurrence = parse_expression(
        ctx.require_str("recurrence"),
        limits=ctx.limits,
        extra_functions={func_name: f},
        allowed_symbols={var_name},
    )
    # The parser builds the index as a plain ``Symbol``; align it with our integer-assumed
    # ``n`` so ``rsolve`` sees one consistent index symbol. Without this the recurrence's
    # index and the ``f(n)`` handed to ``rsolve`` are distinct symbols and rsolve rejects
    # the shifts ("'f(n + k)' expected, got 'f(n - 1)'").
    recurrence = recurrence.subs(sp.Symbol(var_name), n)

    offsets = _recurrence_offsets(recurrence, f, n, func_name, var_name)
    _require_linear(recurrence, f, func_name)

    initial_raw = ctx.get("initial_conditions") or {}
    if not isinstance(initial_raw, dict):
        raise InvalidInput("'initial_conditions' must be an object mapping index -> value")
    try:
        initial = {
            f(int(k)): parse_expression(str(v), limits=ctx.limits)
            for k, v in initial_raw.items()
        }
    except (TypeError, ValueError) as exc:
        raise InvalidInput("initial_conditions keys must be integers") from exc

    try:
        solution = sp.rsolve(recurrence, f(n), initial or None)
    except (ValueError, NotImplementedError, sp.PolynomialError):
        solution = None
    # rsolve returns the trivial zero sequence when it fails to find the general solution
    # of a homogeneous recurrence (e.g. variable-coefficient higher order). A genuine
    # constant-coefficient homogeneous recurrence without initial conditions always yields
    # a constant-parametrized family, never a bare 0 — so treat that as "unknown".
    if solution is None or (solution == 0 and not initial):
        return Outcome(
            status="unknown",
            certainty="unknown",
            method="none",
            result_kind="none",
            result=None,
            backend="sympy",
            explanation="rsolve could not find a closed form for this recurrence.",
            warnings=["no closed-form solution found"],
        )

    solution = sp.simplify(solution)
    order = max(offsets) - min(offsets)
    return value_result(
        to_text(solution),
        latex=to_latex(solution),
        certainty="exact",
        method="symbolic",
        result_kind="value",
        metadata={"order": order, "homogeneous": bool(initial == {})},
    )


def _recurrence_offsets(
    recurrence: Any, f: Any, n: Any, func_name: str, var_name: str
) -> list[int]:
    """Return the integer index shifts of every ``f(...)`` term, validating their shape."""
    applied = [a for a in recurrence.atoms(sp.Function) if a.func == f]
    if not applied:
        raise InvalidInput(
            f"recurrence must reference the unknown function "
            f"'{func_name}', e.g. {func_name}({var_name})"
        )
    offsets: list[int] = []
    for term in applied:
        if len(term.args) != 1:
            raise InvalidInput(f"'{func_name}(...)' must take exactly one argument")
        shift = sp.simplify(term.args[0] - n)
        if not shift.is_Integer:
            raise InvalidInput(
                f"each '{func_name}(...)' must be an integer shift of '{var_name}', "
                f"e.g. {func_name}({var_name} - 1)"
            )
        offsets.append(int(shift))
    return offsets


def _require_linear(recurrence: Any, f: Any, func_name: str) -> None:
    """Reject nonlinear recurrences; rsolve silently mis-solves them otherwise.

    The recurrence must be affine (degree <= 1) in the ``f(...)`` terms. Coefficients may
    be arbitrary expressions in the index (e.g. ``f(n-1)/n``); only products/powers of the
    unknown-function terms are rejected. This is checked via the Hessian with respect to a
    fresh symbol substituted for each distinct ``f(...)`` term.
    """
    fterms = sorted({a for a in recurrence.atoms(sp.Function) if a.func == f}, key=str)
    dummies = sp.symbols(f"_g0:{len(fterms)}")
    subbed = recurrence.subs(dict(zip(fterms, dummies, strict=False)))
    for i, gi in enumerate(dummies):
        for gj in dummies[i:]:
            if sp.simplify(sp.diff(subbed, gi, gj)) != 0:
                raise InvalidInput(
                    f"only linear recurrences are supported "
                    f"(nonlinear in the '{func_name}(...)' terms)"
                )
