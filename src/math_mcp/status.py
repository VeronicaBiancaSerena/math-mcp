"""Status, certainty, method, and error-code enumerations.

These ``Literal`` aliases are the controlled vocabulary shared by every tool result.
Keeping them in one module lets ``schemas.py``, the registry, the backends, and the
tests agree on a single set of stable strings.
"""

from __future__ import annotations

from typing import Literal

Status = Literal[
    "success",
    "failure",
    "timeout",
    "invalid_input",
    "unsupported",
    "unknown",
    "backend_error",
    "output_too_large",
    "counterexample_found",
    "no_counterexample_found",
    "proved_by_symbolic_simplification",
    "proved_by_smt",
    "proved_by_finite_exhaustion",
    "proved_by_interval_analysis",
    "disproved_by_counterexample",
    "numeric_evidence_only",
]

Certainty = Literal[
    "proved",
    "disproved",
    "exact",
    "evidence",
    "unknown",
    "error",
]

Method = Literal[
    "symbolic",
    "smt",
    "finite_exhaustive",
    "interval",
    "counterexample",
    "numeric_sampling",
    "numeric_optimization",
    "simulation",
    "backend",
    "none",
]

ErrorCode = Literal[
    "PARSE_REJECTED",
    "UNSUPPORTED_OPERATION",
    "DOMAIN_UNSUPPORTED",
    "ASSUMPTION_UNSUPPORTED",
    "CONSTRAINT_CONFLICT",
    "BACKEND_TIMEOUT",
    "OUTPUT_TOO_LARGE",
    "RESOURCE_LIMIT_EXCEEDED",
    "BACKEND_INTERNAL_ERROR",
    "INVALID_AST",
    "INVALID_LIMITS",
    "NUMERIC_CONVERGENCE_FAILED",
    "PLATFORM_UNSUPPORTED",
    "SANDBOX_UNAVAILABLE",
]

ResultKind = Literal[
    "value",
    "solution_set",
    "witness",
    "verification",
    "object",
    "none",
]

# Conservative ordering used when a backend caveat forces a certainty downgrade.
# ``proved`` and ``disproved`` are both strict propositional verdicts (rank 0) but are
# semantically opposite and must never be swapped for one another; a downgrade may only
# move *down* this ladder (toward ``error``), never up.
_CERTAINTY_RANK: dict[Certainty, int] = {
    "proved": 0,
    "disproved": 0,
    "exact": 1,
    "evidence": 2,
    "unknown": 3,
    "error": 4,
}


def certainty_rank(certainty: Certainty) -> int:
    """Return the conservative rank of a certainty level (lower == stronger)."""
    return _CERTAINTY_RANK[certainty]


def is_weaker_or_equal(candidate: Certainty, reference: Certainty) -> bool:
    """Return True if ``candidate`` is no stronger than ``reference``.

    Used by the caveat layer to decide whether a recommended certainty would actually
    be a downgrade. Strict verdicts of opposite polarity (``proved``/``disproved``)
    share a rank, so this never treats them as interchangeable.
    """
    return certainty_rank(candidate) >= certainty_rank(reference)
