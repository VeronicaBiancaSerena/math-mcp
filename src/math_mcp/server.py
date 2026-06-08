"""MCP server: registers the public domain-level tools.

This module contains no math logic. Every compute tool forwards to
:func:`math_mcp.tools.dispatch.run_operation`, which owns validation, routing, sandbox
execution, caveat enforcement, and ToolResult assembly. Concrete capabilities are
addressed through the ``operation`` argument and described by ``math_capabilities``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from math_mcp.schemas import ToolResult
from math_mcp.tools.capabilities import get_capabilities
from math_mcp.tools.dispatch import run_operation

mcp = FastMCP("math-mcp")

Domains = list[dict[str, Any]] | None


@mcp.tool()
def ping() -> dict[str, str]:
    """Return a health check response for the local math MCP server."""
    return {"status": "ok", "server": "math-mcp"}


@mcp.tool()
def math_capabilities(
    include_experimental: bool = False,
    include_disabled: bool = False,
    mode: str = "full",
) -> dict[str, Any]:
    """Return supported math domains, operations, input limits, and examples.

    Default output (mode="full") lists only implemented (and still-callable deprecated)
    operations with their full payload schema and examples. Use mode="summary" for a
    lightweight index of tool names, operation names, and aliases — ideal for cheap
    discovery before requesting the full schema of the operation you pick.

    Set include_experimental=true to discover experimental operations (not recommended
    for default agent use) and include_disabled=true to discover disabled ones.
    """
    return get_capabilities(
        include_experimental=include_experimental,
        include_disabled=include_disabled,
        mode=mode,
    )


@mcp.tool()
def algebra_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run an algebra operation: simplify, expand, factor, cancel, together, solve,
    polynomial roots, or Groebner basis.

    The operation must be one returned by math_capabilities. Expressions use SymPy-style
    syntax (not LaTeX or natural language). Exact symbolic results report certainty
    "exact"; this tool does not by itself prove propositions.
    """
    return run_operation("algebra_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def calculus_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a calculus operation: differentiate, integrate, limit, series expansion, or
    high-precision numeric evaluation.

    Symbolic results are exact; conditions (e.g. piecewise integrals) are returned in the
    structured "conditions" field. Numeric evaluation reports an exact computed value.
    """
    return run_operation("calculus_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def verification_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a verification operation: identity checking, sampled inequality checks, or
    counterexample search.

    Proof is reported only for symbolic simplification to zero. Numeric sampling is
    reported as evidence, or as a strict disproof when a concrete counterexample is found;
    it must never be treated as a proof. Z3 constraint checks live under z3_compute.
    """
    return run_operation("verification_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def z3_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a Z3 SMT operation over a structured AST: satisfiability or counterexample/proof.

    Variables and constraints are supplied as structured AST (never strings). UNSAT yields
    a proof (certainty "proved"); a found model is a witness; Z3 "unknown" is reported as
    unknown and is never promoted to a proof.
    """
    return run_operation("z3_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def matrix_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a linear algebra operation: det, rank, inverse, rref, eigenvals, trace,
    transpose, charpoly, exact linear solve, or numeric decomposition.

    Matrix entries are strings parsed exactly (e.g. "1/3"). Exact SymPy results report
    certainty "exact"; numeric decomposition is a numeric object.
    """
    return run_operation("matrix_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def discrete_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a discrete-math operation: combinatorial counting, finite enumeration, or
    recurrence solving.

    finite_enumeration requires a finite or bounded-integer domain per variable and
    returns a finite-exhaustion proof. Counting returns exact integers.
    """
    return run_operation("discrete_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def graph_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a graph algorithm: connectivity, components, shortest path, cycle detection,
    topological sort, maximum matching, or minimum spanning tree.

    Graphs are given as nodes plus edges (optionally directed/weighted). Operations that
    do not apply (e.g. topological sort on an undirected graph) return "unsupported".
    """
    return run_operation("graph_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def probability_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a probability operation: event probabilities, Bayes update, distribution
    moments/queries, Markov analysis, or Monte Carlo simulation.

    Exact computations report certainty "exact". Monte Carlo simulation reports
    certainty "evidence" with method "simulation" and a fixed seed; it is never a proof.
    """
    return run_operation("probability_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def set_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a set/interval operation: finite-set algebra, membership, relations, identity
    checking, cartesian product, power set, or interval algebra.

    Handles finite sets and one-dimensional interval sets only — not arbitrary axiomatic
    set theory. Set identities are proved via membership boolean algebra.
    """
    return run_operation("set_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def geometry_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run an analytic geometry operation: distances, intersections, line/circle/polygon
    analysis, or coordinate transforms.

    Coordinates and coefficients are strings parsed exactly. Results are exact computed
    geometric quantities, not natural-language Euclidean proofs.
    """
    return run_operation("geometry_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def trigonometry_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a trigonometry operation: simplify, expand, rewrite, reduce, solve, or identity
    check.

    Identity checks prove via symbolic trig reduction to zero; otherwise they report a
    disproof (counterexample) or numeric evidence — never a proof from sampling alone.
    """
    return run_operation("trigonometry_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def number_theory_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a number theory operation: gcd/lcm/Bezout, primality and factorization, modular
    arithmetic, congruences, CRT, totients, multiplicative order, or quadratic residues.

    Operates over integers and finite modular arithmetic only. Results are exact.
    """
    return run_operation("number_theory_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def logic_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a propositional logic operation: boolean simplification, truth tables,
    equivalence, satisfiability, normal-form conversion, or finite quantifier checking.

    Equivalence, satisfiability, and finite quantifier checks return finite-exhaustion or
    symbolic proofs; truth tables return the exact table.
    """
    return run_operation("logic_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def ode_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run an ODE operation: symbolic solving, candidate-solution verification,
    classification, initial-value solving, or numeric integration.

    Solution verification yields a symbolic proof; numeric integration is an approximate
    trajectory reported as evidence, never an analytic proof.
    """
    return run_operation("ode_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def complex_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a complex-number operation: simplify, polar/rectangular conversion, roots of
    unity, modulus/argument/conjugate, or equation solving.

    Returns exact expressions (and LaTeX where available); use I for the imaginary unit.
    """
    return run_operation("complex_compute", operation, payload, domains, assumptions, limits)


@mcp.tool()
def inequality_compute(
    operation: str,
    payload: dict[str, Any],
    domains: Domains = None,
    assumptions: Domains = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run an inequality operation: solve/reduce to a solution set, symbolic proof under
    assumptions, counterexample search, or sampling.

    A "proved" verdict is returned only when symbolic sign analysis is conclusive.
    Sampling yields evidence or a strict counterexample disproof, never a proof.
    """
    return run_operation("inequality_compute", operation, payload, domains, assumptions, limits)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
