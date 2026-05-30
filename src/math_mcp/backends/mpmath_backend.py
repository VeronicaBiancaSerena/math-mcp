"""Bounded-domain numeric sampling for counterexample search and identity evidence.

Sampling can *disprove* a claim by exhibiting a concrete counterexample, but never
*prove* it. Handlers built on this report ``certainty="disproved"`` only when a witness is
found and ``certainty="evidence"`` otherwise. A deterministic grid is tried before seeded
random points so common counterexamples are found reproducibly.
"""

from __future__ import annotations

import math
import random
from typing import Any

import sympy as sp

from math_mcp.parsing.domain_parser import NormalizedConstraints
from math_mcp.runtime.serialization import to_text

_TOL = 1e-9

_Relation = str


def _holds(lv: float, rv: float, relation: _Relation) -> bool:
    if relation == "==":
        return abs(lv - rv) <= _TOL
    if relation == "!=":
        return abs(lv - rv) > _TOL
    if relation == "<":
        return lv < rv
    if relation == "<=":
        return lv <= rv + _TOL
    if relation == ">":
        return lv > rv
    if relation == ">=":
        return lv >= rv - _TOL
    raise ValueError(f"unknown relation '{relation}'")


def _evaluate(expr: Any, subs: dict[Any, Any]) -> float | None:
    try:
        value = complex(expr.subs(subs).evalf())
    except (TypeError, ValueError, AttributeError):
        return None
    if abs(value.imag) > _TOL:
        return None
    real = value.real
    if math.isnan(real) or math.isinf(real):
        return None
    return real


def _grid_points(lo: float, hi: float, count: int, is_integer: bool) -> list[float]:
    if is_integer:
        lo_i, hi_i = math.ceil(lo), math.floor(hi)
        if hi_i < lo_i:
            return []
        span = hi_i - lo_i
        step = max(1, span // max(1, count - 1))
        return [float(v) for v in range(lo_i, hi_i + 1, step)]
    if count <= 1:
        return [(lo + hi) / 2]
    return [lo + (hi - lo) * i / (count - 1) for i in range(count)]


def sample_relation(
    left: Any,
    right: Any,
    relation: _Relation,
    variables: list[str],
    constraints: NormalizedConstraints,
    *,
    samples: int,
    seed: int | None,
) -> dict[str, Any]:
    """Search a bounded domain for a point where ``left RELATION right`` fails."""
    rng_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
    rng = random.Random(rng_seed)

    used_default = False
    bounds: dict[str, tuple[float, float, bool]] = {}
    for name in variables:
        constraint = constraints.get(name)
        is_integer = constraint.kind in ("integer",)
        if (
            constraint.lower is None
            and constraint.upper is None
            and name not in constraints.variables
        ):
            used_default = True
        lo, hi = constraint.float_bounds()
        bounds[name] = (lo, hi, is_integer)

    symbols = {name: sp.Symbol(name) for name in variables}

    def make_subs(point: dict[str, float]) -> dict[Any, Any]:
        return {symbols[name]: sp.Float(value) for name, value in point.items()}

    def check(point: dict[str, float]) -> dict[str, Any] | None:
        subs = make_subs(point)
        lv = _evaluate(left, subs)
        rv = _evaluate(right, subs)
        if lv is None or rv is None:
            return None
        if not _holds(lv, rv, relation):
            return {
                "assignment": {
                    k: to_text(sp.nsimplify(v, rational=True)) for k, v in point.items()
                },
                "left_value": repr(lv),
                "right_value": repr(rv),
                "relation": relation,
            }
        return None

    grid_count = min(21, max(2, samples // max(1, len(variables))))
    grids = {
        name: _grid_points(lo, hi, grid_count, is_int) for name, (lo, hi, is_int) in bounds.items()
    }

    tested = 0
    # Single-variable deterministic grid sweep first.
    if len(variables) == 1:
        name = variables[0]
        for value in grids[name]:
            tested += 1
            witness = check({name: value})
            if witness is not None:
                return {
                    "found": True,
                    "samples_used": tested,
                    "seed": rng_seed,
                    "used_default_domain": used_default,
                    **witness,
                }

    for _ in range(samples):
        tested += 1
        point: dict[str, float] = {}
        for name, (lo, hi, is_int) in bounds.items():
            point[name] = (
                float(rng.randint(math.ceil(lo), math.floor(hi))) if is_int else rng.uniform(lo, hi)
            )
        witness = check(point)
        if witness is not None:
            return {
                "found": True,
                "samples_used": tested,
                "seed": rng_seed,
                "used_default_domain": used_default,
                **witness,
            }

    return {
        "found": False,
        "samples_used": tested,
        "seed": rng_seed,
        "used_default_domain": used_default,
    }
