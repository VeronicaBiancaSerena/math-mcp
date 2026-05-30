"""Single source of truth for backend capability boundaries (caveats).

Every backend has limits. Rather than letting each tool invent its own wording, the
warnings surfaced to agents, the capabilities document, and the tests all reference the
caveats declared here. A caveat with ``affects_certainty=True`` forces the dispatcher to
downgrade a result's certainty (or demand a structured override reason).
"""

from __future__ import annotations

import fnmatch

from pydantic import BaseModel

from math_mcp.status import Certainty, certainty_rank


class BackendCaveat(BaseModel):
    backend: str
    operation_pattern: str
    caveat: str
    affects_certainty: bool
    recommended_certainty: Certainty | None = None


CAVEATS: list[BackendCaveat] = [
    BackendCaveat(
        backend="sympy",
        operation_pattern="*",
        caveat=(
            "SymPy solve/integrate/limit/simplify may return conditional, partial, or "
            "unsimplified results; side conditions are reported in the structured "
            "'conditions' field."
        ),
        affects_certainty=False,
    ),
    BackendCaveat(
        backend="z3",
        operation_pattern="*",
        caveat=(
            "Z3 may return 'unknown' for nonlinear real arithmetic, quantifiers, or mixed "
            "theories; 'unknown' is never promoted to a proof."
        ),
        affects_certainty=False,
    ),
    BackendCaveat(
        backend="scipy",
        operation_pattern="numeric_optimize",
        caveat=(
            "SciPy optimize performs numeric, initial-value-dependent local search; without "
            "an interval certificate the result is evidence, not a proof."
        ),
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
    BackendCaveat(
        backend="scipy",
        operation_pattern="ode_solve_numeric",
        caveat=(
            "Numeric ODE integration produces an approximate trajectory, not an analytic "
            "proof; treat the result as evidence."
        ),
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
    BackendCaveat(
        backend="networkx",
        operation_pattern="*",
        caveat=(
            "NetworkX graph algorithms are deterministic, but oversized inputs trip resource "
            "limits; a resource error is not a mathematical failure of the property."
        ),
        affects_certainty=False,
    ),
    BackendCaveat(
        backend="mpmath",
        operation_pattern="*",
        caveat=(
            "mpmath sampling and high-precision evaluation are affected by precision, "
            "sample count, and ill-conditioned functions."
        ),
        affects_certainty=False,
    ),
    BackendCaveat(
        backend="mpmath",
        operation_pattern="search_counterexample",
        caveat="Finding no counterexample via sampling is evidence only, never a proof.",
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
    BackendCaveat(
        backend="mpmath",
        operation_pattern="check_inequality_sampled",
        caveat="Sampled inequality checks are evidence only unless a counterexample is found.",
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
    BackendCaveat(
        backend="mpmath",
        operation_pattern="inequality_sample",
        caveat="Sampled inequality checks are evidence only unless a counterexample is found.",
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
    BackendCaveat(
        backend="mpmath",
        operation_pattern="inequality_counterexample_search",
        caveat="Finding no counterexample via sampling is evidence only, never a proof.",
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
    BackendCaveat(
        backend="numpy",
        operation_pattern="probability_simulation",
        caveat=(
            "Monte Carlo simulation yields statistical evidence with a fixed seed, never a "
            "proof of the underlying probability."
        ),
        affects_certainty=True,
        recommended_certainty="evidence",
    ),
]

# Methods that constitute a rigorous derivation; a result reached this way is not
# downgraded by an affects-certainty caveat (the caveat is recorded as context only).
_PROOF_METHODS = {"symbolic", "smt", "finite_exhaustive", "interval", "counterexample"}


def caveats_for(backend: str, operation: str) -> list[BackendCaveat]:
    """Return every caveat whose backend and operation pattern match."""
    out: list[BackendCaveat] = []
    for c in CAVEATS:
        if c.backend != backend:
            continue
        if c.operation_pattern == "*" or fnmatch.fnmatch(operation, c.operation_pattern):
            out.append(c)
    return out


def strongest_downgrade(
    caveats: list[BackendCaveat], current: Certainty
) -> tuple[Certainty | None, list[BackendCaveat]]:
    """Compute the certainty a set of caveats would force ``current`` down to.

    Returns the recommended (weaker) certainty and the caveats that justified it, or
    ``(None, [])`` when no certainty-affecting caveat applies. ``proved`` and
    ``disproved`` of opposite polarity are never swapped: a downgrade only ever moves to
    a strictly weaker rank.
    """
    target: Certainty | None = None
    reasons: list[BackendCaveat] = []
    for c in caveats:
        if not c.affects_certainty or c.recommended_certainty is None:
            continue
        rec = c.recommended_certainty
        if certainty_rank(rec) > certainty_rank(current):
            reasons.append(c)
            if target is None or certainty_rank(rec) > certainty_rank(target):
                target = rec
    return target, reasons


def enforce(
    backend: str,
    operation: str,
    method: str,
    certainty: Certainty,
    *,
    has_override: bool,
) -> tuple[Certainty, list[str], list[dict[str, object]]]:
    """Apply caveats to a result.

    Returns ``(certainty, warnings, records)``. ``records`` (all matching caveats) goes
    into ``metadata["backend_caveats"]``; ``warnings`` holds the active caveat texts.

    A caveat that affects certainty is *active* only when the result was not obtained by
    a rigorous proof method — a sampled counterexample (``method="counterexample"``) is a
    genuine disproof and is never downgraded. When an active certainty-affecting caveat
    recommends a weaker level (and no structured override reason was supplied), the
    certainty is downgraded.
    """
    matched = caveats_for(backend, operation)
    records = [c.model_dump() for c in matched]
    is_proof_method = method in _PROOF_METHODS

    active = [c for c in matched if (not c.affects_certainty) or (not is_proof_method)]
    warnings = [c.caveat for c in active]

    new_certainty = certainty
    if not is_proof_method and not has_override:
        downgrade_candidates = [c for c in active if c.affects_certainty]
        target, _reasons = strongest_downgrade(downgrade_candidates, certainty)
        if target is not None:
            new_certainty = target
    return new_certainty, warnings, records
