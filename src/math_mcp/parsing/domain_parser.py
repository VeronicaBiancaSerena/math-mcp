"""Normalize structured domains/assumptions and reject conflicting constraints.

This runs *before* any backend sees the request. Conflicts (kind clashes, empty
intervals, predicate/domain contradictions) are surfaced as
``error_code="CONSTRAINT_CONFLICT"`` rather than being silently downgraded or passed on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sympy as sp

from math_mcp.errors import AssumptionUnsupported, ConstraintConflict
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.schemas import AssumptionSpec, DomainSpec, Limits

# Predicates the assumption layer understands, mapped to SymPy Symbol assumption kwargs.
_PREDICATE_ASSUMPTIONS: dict[str, dict[str, bool]] = {
    "positive": {"positive": True},
    "negative": {"negative": True},
    "nonnegative": {"nonnegative": True},
    "nonzero": {"nonzero": True},
    "integer": {"integer": True},
    "real": {"real": True},
    "rational": {"rational": True},
    "complex": {"complex": True},
    "prime": {"prime": True, "integer": True, "positive": True},
    "finite": {"finite": True},
}

_KIND_ASSUMPTIONS: dict[str, dict[str, bool]] = {
    "real": {"real": True},
    "integer": {"integer": True},
    "rational": {"rational": True},
    "complex": {"complex": True},
    "boolean": {},
    "finite": {},
}

_BOOLEAN_VALUES = {"0", "1", "true", "false", "True", "False"}

# Predicate pairs that directly contradict each other.
_CONTRADICTIONS = [
    ("positive", "negative"),
    ("positive", "nonpositive"),
    ("negative", "nonnegative"),
    ("nonzero", "zero"),
    ("real", "complex_only"),
]


@dataclass
class VarConstraint:
    variable: str
    kind: str | None = None
    lower: Any | None = None
    upper: Any | None = None
    lower_closed: bool = True
    upper_closed: bool = True
    values: list[Any] | None = None
    predicates: set[str] = field(default_factory=set)

    def sympy_assumptions(self) -> dict[str, bool]:
        out: dict[str, bool] = {}
        if self.kind is not None:
            out.update(_KIND_ASSUMPTIONS.get(self.kind, {}))
        for pred in self.predicates:
            out.update(_PREDICATE_ASSUMPTIONS.get(pred, {}))
        return out

    def symbol(self) -> Any:
        return sp.Symbol(self.variable, **self.sympy_assumptions())

    def float_bounds(self, default: tuple[float, float] = (-10.0, 10.0)) -> tuple[float, float]:
        lo = float(self.lower) if self.lower is not None else default[0]
        hi = float(self.upper) if self.upper is not None else default[1]
        return lo, hi


@dataclass
class NormalizedConstraints:
    variables: dict[str, VarConstraint]
    has_explicit_domains: bool

    def get(self, variable: str) -> VarConstraint:
        return self.variables.get(variable, VarConstraint(variable=variable))

    def symbol(self, variable: str) -> Any:
        return self.get(variable).symbol()


def _to_number(text: str, limits: Limits) -> Any:
    expr = parse_expression(text, limits=limits)
    if not getattr(expr, "is_number", False):
        raise ConstraintConflict(f"domain bound '{text}' is not a constant number")
    return expr


def normalize(
    domains: list[DomainSpec],
    assumptions: list[AssumptionSpec],
    *,
    limits: Limits | None = None,
) -> NormalizedConstraints:
    """Validate and merge domains/assumptions, raising on any conflict."""
    limits = limits or Limits()
    variables: dict[str, VarConstraint] = {}

    for dom in domains:
        existing = variables.get(dom.variable)
        if existing is not None and existing.kind is not None and existing.kind != dom.kind:
            raise ConstraintConflict(
                f"variable '{dom.variable}' has conflicting domain kinds "
                f"'{existing.kind}' and '{dom.kind}'"
            )
        constraint = existing or VarConstraint(variable=dom.variable)
        constraint.kind = dom.kind

        if dom.kind == "finite":
            if not dom.values:
                raise ConstraintConflict(
                    f"finite domain for '{dom.variable}' requires non-empty 'values'"
                )
            constraint.values = [_to_number(v, limits) for v in dom.values]
        elif dom.kind == "boolean":
            if dom.values is not None:
                for v in dom.values:
                    if v not in _BOOLEAN_VALUES:
                        raise ConstraintConflict(
                            f"boolean domain value '{v}' for '{dom.variable}' is invalid"
                        )
        else:
            if dom.lower is not None:
                constraint.lower = _to_number(dom.lower, limits)
            if dom.upper is not None:
                constraint.upper = _to_number(dom.upper, limits)
            constraint.lower_closed = dom.lower_closed
            constraint.upper_closed = dom.upper_closed
            _check_interval(constraint)

        variables[dom.variable] = constraint

    for assum in assumptions:
        constraint = variables.get(assum.variable) or VarConstraint(variable=assum.variable)
        for pred in assum.predicates:
            if pred not in _PREDICATE_ASSUMPTIONS:
                raise AssumptionUnsupported(f"unsupported assumption predicate '{pred}'")
            constraint.predicates.add(pred)
        _check_predicate_contradictions(constraint)
        _check_predicate_vs_domain(constraint)
        variables[assum.variable] = constraint

    return NormalizedConstraints(variables=variables, has_explicit_domains=bool(domains))


def _check_interval(c: VarConstraint) -> None:
    if c.lower is None or c.upper is None:
        return
    diff = sp.nsimplify(c.upper - c.lower)
    try:
        is_neg = bool(diff < 0)
        is_zero = bool(sp.Eq(diff, 0))
    except TypeError:
        return
    if is_neg:
        raise ConstraintConflict(
            f"domain for '{c.variable}' is empty: lower {c.lower} > upper {c.upper}"
        )
    if is_zero and not (c.lower_closed and c.upper_closed):
        raise ConstraintConflict(
            f"domain for '{c.variable}' is empty: open interval at a single point"
        )


def _check_predicate_contradictions(c: VarConstraint) -> None:
    for a, b in _CONTRADICTIONS:
        if a in c.predicates and b in c.predicates:
            raise ConstraintConflict(
                f"variable '{c.variable}' has contradictory assumptions '{a}' and '{b}'"
            )


def _check_predicate_vs_domain(c: VarConstraint) -> None:
    """Reject assumptions that contradict the variable's numeric domain."""

    def positive_required() -> bool:
        return "positive" in c.predicates

    def negative_required() -> bool:
        return "negative" in c.predicates

    def nonnegative_required() -> bool:
        return "nonnegative" in c.predicates

    try:
        if positive_required() and c.upper is not None and bool(c.upper <= 0):
            raise ConstraintConflict(
                f"'{c.variable}' assumed positive but domain upper bound {c.upper} <= 0"
            )
        if negative_required() and c.lower is not None and bool(c.lower >= 0):
            raise ConstraintConflict(
                f"'{c.variable}' assumed negative but domain lower bound {c.lower} >= 0"
            )
        if nonnegative_required() and c.upper is not None and bool(c.upper < 0):
            raise ConstraintConflict(
                f"'{c.variable}' assumed nonnegative but domain upper bound {c.upper} < 0"
            )
    except TypeError:
        return
