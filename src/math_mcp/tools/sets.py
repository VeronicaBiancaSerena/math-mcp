"""Finite-set and one-dimensional interval operations."""

from __future__ import annotations

import itertools
from typing import Any

import sympy as sp

from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import (
    Ctx,
    Outcome,
    certificate,
    object_result,
    verification_result,
)
from math_mcp.tools.dispatch import handler


def _canon(element: Any, ctx: Ctx) -> str:
    try:
        return to_text(parse_expression(str(element), limits=ctx.limits))
    except Exception:  # noqa: BLE001 - opaque tokens stay as-is
        return str(element)


def _canon_set(values: Any, ctx: Ctx) -> list[str]:
    if not isinstance(values, list):
        raise InvalidInput("set must be a list of elements")
    seen: dict[str, None] = {}
    for v in values:
        seen[_canon(v, ctx)] = None
    return list(seen)


@handler("set_compute", "set_operations")
def set_operations(ctx: Ctx) -> Outcome:
    kind = str(ctx.require("kind"))
    a = set(_canon_set(ctx.require("a"), ctx))
    b = set(_canon_set(ctx.get("b", []), ctx))
    if kind == "union":
        result = a | b
    elif kind == "intersection":
        result = a & b
    elif kind == "difference":
        result = a - b
    elif kind == "symmetric_difference":
        result = a ^ b
    elif kind == "complement":
        universe = set(_canon_set(ctx.require("universe"), ctx))
        if not a <= universe:
            raise InvalidInput("set 'a' must be a subset of 'universe' for complement")
        result = universe - a
    else:
        raise InvalidInput(f"unsupported set operation '{kind}'")
    return object_result(sorted(result), certainty="exact", method="backend", backend="python")


@handler("set_compute", "set_membership")
def set_membership(ctx: Ctx) -> Outcome:
    element = _canon(ctx.require("element"), ctx)
    members = set(_canon_set(ctx.require("set"), ctx))
    return verification_result(
        status="success",
        certainty="exact",
        method="backend",
        backend="python",
        result={"member": element in members},
    )


@handler("set_compute", "set_relation_check")
def set_relation_check(ctx: Ctx) -> Outcome:
    a = set(_canon_set(ctx.require("a"), ctx))
    b = set(_canon_set(ctx.require("b"), ctx))
    relation = str(ctx.require("relation"))
    if relation == "subset":
        holds = a <= b
    elif relation == "proper_subset":
        holds = a < b
    elif relation == "equal":
        holds = a == b
    elif relation == "disjoint":
        holds = a.isdisjoint(b)
    else:
        raise InvalidInput(f"unsupported set relation '{relation}'")
    return verification_result(
        status="proved_by_finite_exhaustion",
        certainty="proved",
        method="finite_exhaustive",
        backend="python",
        result={"relation": relation, "holds": bool(holds)},
        certificate_=certificate(
            "finite_exhaustion", "checked over finite sets", machine_checkable=True
        ),
    )


@handler("set_compute", "set_identity_check")
def set_identity_check(ctx: Ctx) -> Outcome:
    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("'variables' must list the set symbols")
    allowed = {str(v) for v in variables}
    left = parse_expression(ctx.require_str("left"), limits=ctx.limits, allowed_symbols=allowed)
    right = parse_expression(ctx.require_str("right"), limits=ctx.limits, allowed_symbols=allowed)
    # Set identity holds iff the membership-indicator boolean identity is a tautology.
    equivalent = not bool(sp.satisfiable(sp.Xor(left, right)))
    if equivalent:
        return verification_result(
            status="proved_by_symbolic_simplification",
            certainty="proved",
            method="symbolic",
            backend="sympy",
            result={"identity_holds": True},
            certificate_=certificate(
                "symbolic_simplification",
                "membership boolean algebra: left and right are logically equivalent",
                machine_checkable=True,
            ),
        )
    return verification_result(
        status="disproved_by_counterexample",
        certainty="disproved",
        method="finite_exhaustive",
        backend="sympy",
        result={"identity_holds": False},
        explanation="The two set expressions are not equivalent.",
    )


@handler("set_compute", "cartesian_product")
def cartesian_product(ctx: Ctx) -> Outcome:
    sets_raw = ctx.require("sets")
    if not isinstance(sets_raw, list) or not sets_raw:
        raise InvalidInput("'sets' must be a non-empty list of lists")
    sets = [_canon_set(s, ctx) for s in sets_raw]
    total = 1
    for s in sets:
        total *= len(s)
    if total > ctx.limits.max_samples * 10:
        raise InvalidInput("cartesian product is too large")
    product = [list(tup) for tup in itertools.product(*sets)]
    return object_result(
        {"tuples": product, "size": len(product)},
        certainty="exact",
        method="backend",
        backend="python",
    )


@handler("set_compute", "power_set")
def power_set(ctx: Ctx) -> Outcome:
    elements = _canon_set(ctx.require("set"), ctx)
    if len(elements) > 16:
        raise InvalidInput("power_set is limited to at most 16 elements")
    subsets: list[list[str]] = []
    for r in range(len(elements) + 1):
        subsets.extend(list(combo) for combo in itertools.combinations(elements, r))
    return object_result(
        {"subsets": subsets, "size": len(subsets)},
        certainty="exact",
        method="backend",
        backend="python",
    )


def _interval(spec: Any, ctx: Ctx) -> Any:
    if not isinstance(spec, dict):
        raise InvalidInput("interval must be an object with lower/upper")
    lower = parse_expression(str(spec.get("lower", "-oo")), limits=ctx.limits)
    upper = parse_expression(str(spec.get("upper", "oo")), limits=ctx.limits)
    left_open = not bool(spec.get("lower_closed", True))
    right_open = not bool(spec.get("upper_closed", True))
    return sp.Interval(lower, upper, left_open, right_open)


@handler("set_compute", "interval_compute")
def interval_compute(ctx: Ctx) -> Outcome:
    kind = str(ctx.require("kind"))
    a = _interval(ctx.require("a"), ctx)
    if kind == "complement":
        result = a.complement(sp.Reals)
    else:
        b = _interval(ctx.require("b"), ctx)
        if kind == "union":
            result = sp.Union(a, b)
        elif kind == "intersection":
            result = sp.Intersection(a, b)
        elif kind == "difference":
            result = sp.Complement(a, b)
        else:
            raise InvalidInput(f"unsupported interval operation '{kind}'")
    return object_result(
        to_text(result),
        latex=None,
        certainty="exact",
        method="backend",
        backend="sympy",
        result_kind="object",
    )
