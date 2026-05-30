"""Z3 solving over structured ASTs. Imported lazily so Z3 only loads when used."""

from __future__ import annotations

from typing import Any

from math_mcp.parsing.z3_ast import build_constraints, build_term, declare_variables


def solve_constraints(
    variables: dict[str, str], constraints: list[Any], timeout_ms: int
) -> dict[str, Any]:
    """Check satisfiability of a constraint set; return sat/unsat/unknown and any model."""
    import z3  # noqa: PLC0415

    zvars, terms = build_constraints(variables, constraints)
    solver = z3.Solver()
    solver.set("timeout", int(timeout_ms))
    for term in terms:
        solver.add(term)
    verdict = solver.check()
    if verdict == z3.sat:
        model = solver.model()
        return {"result": "sat", "model": _extract_model(zvars, model)}
    if verdict == z3.unsat:
        return {"result": "unsat"}
    return {"result": "unknown"}


def refute_claim(
    variables: dict[str, str],
    assumptions: list[Any],
    claim: Any,
    timeout_ms: int,
) -> dict[str, Any]:
    """Look for a model of ``assumptions ∧ ¬claim``.

    A model disproves ``assumptions ⇒ claim`` (counterexample); UNSAT proves it.
    """
    import z3  # noqa: PLC0415

    zvars = declare_variables(variables)
    counter = {"n": 0}
    solver = z3.Solver()
    solver.set("timeout", int(timeout_ms))
    for node in assumptions:
        solver.add(build_term(node, zvars, 0, counter))
    solver.add(z3.Not(build_term(claim, zvars, 0, counter)))
    verdict = solver.check()
    if verdict == z3.sat:
        model = solver.model()
        return {"result": "sat", "model": _extract_model(zvars, model)}
    if verdict == z3.unsat:
        return {"result": "unsat"}
    return {"result": "unknown"}


def _extract_model(zvars: dict[str, Any], model: Any) -> dict[str, str]:
    return {name: str(model.eval(zv, model_completion=True)) for name, zv in zvars.items()}
