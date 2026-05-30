"""Probability operations: exact event probabilities, Bayes, distributions, simulation.

Exact computations report ``certainty="exact"``; Monte Carlo simulation reports
``certainty="evidence"`` with ``method="simulation"`` and never claims a proof.
"""

from __future__ import annotations

import itertools
from typing import Any

import sympy as sp

from math_mcp.backends.numpy_backend import markov_analyze, simulate
from math_mcp.errors import DomainUnsupported, InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression, parse_symbol
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, object_result, value_result, verification_result
from math_mcp.tools.dispatch import handler


def _prob(ctx: Ctx, key: str) -> Any:
    return parse_expression(str(ctx.require(key)), limits=ctx.limits)


@handler("probability_compute", "event_probability")
def event_probability(ctx: Ctx) -> Outcome:
    mode = str(ctx.require("mode"))
    if mode == "ratio":
        value = sp.Rational(_prob(ctx, "favorable"), _prob(ctx, "total"))
    elif mode == "conditional":
        value = _prob(ctx, "p_a_and_b") / _prob(ctx, "p_b")
    elif mode == "union":
        value = _prob(ctx, "p_a") + _prob(ctx, "p_b") - _prob(ctx, "p_a_and_b")
    elif mode == "complement":
        value = 1 - _prob(ctx, "p_a")
    elif mode == "independence":
        independent = (
            sp.simplify(_prob(ctx, "p_a_and_b") - _prob(ctx, "p_a") * _prob(ctx, "p_b")) == 0
        )
        return verification_result(
            status="success",
            certainty="exact",
            method="backend",
            result={"independent": bool(independent)},
        )
    elif mode == "uniform_finite":
        return _uniform_finite(ctx)
    else:
        raise InvalidInput(f"unsupported event_probability mode '{mode}'")
    return value_result(sp.nsimplify(value), certainty="exact", method="backend")


def _uniform_finite(ctx: Ctx) -> Outcome:
    variables = ctx.require("variables")
    if not isinstance(variables, list) or not variables:
        raise InvalidInput("uniform_finite mode requires 'variables'")
    names = [str(v) for v in variables]
    allowed = set(names)
    condition = parse_expression(
        ctx.require_str("condition"), limits=ctx.limits, allowed_symbols=allowed
    )
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
        else:
            raise DomainUnsupported(f"uniform_finite requires a finite domain for '{name}'")
    symbols = {name: parse_symbol(name) for name in names}
    total = 0
    favorable = 0
    for combo in itertools.product(*(domains[name] for name in names)):
        total += 1
        subs = {symbols[name]: combo[i] for i, name in enumerate(names)}
        if bool(condition.subs(subs)):
            favorable += 1
    if total == 0:
        raise InvalidInput("uniform_finite sample space is empty")
    return value_result(
        sp.Rational(favorable, total),
        certainty="exact",
        method="backend",
        metadata={"favorable": favorable, "total": total},
    )


@handler("probability_compute", "bayes_update")
def bayes_update(ctx: Ctx) -> Outcome:
    prior = _prob(ctx, "prior")
    likelihood = _prob(ctx, "likelihood")
    if ctx.get("evidence") is not None:
        evidence = _prob(ctx, "evidence")
    else:
        false_likelihood = _prob(ctx, "false_likelihood")
        evidence = prior * likelihood + (1 - prior) * false_likelihood
    if evidence == 0:
        raise InvalidInput("evidence probability is zero")
    posterior = sp.nsimplify(prior * likelihood / evidence)
    return value_result(
        posterior, certainty="exact", method="backend", metadata={"evidence": to_text(evidence)}
    )


def _rv(distribution: str, params: dict[str, Any], ctx: Ctx) -> Any:
    import sympy.stats as st  # noqa: PLC0415

    def p(name: str) -> Any:
        return parse_expression(str(params[name]), limits=ctx.limits)

    name = "X"
    if distribution == "bernoulli":
        return st.Bernoulli(name, p("p"))
    if distribution == "binomial":
        return st.Binomial(name, int(p("n")), p("p"))
    if distribution == "poisson":
        return st.Poisson(name, p("lambda"))
    if distribution == "geometric":
        return st.Geometric(name, p("p"))
    if distribution == "uniform":
        return st.Uniform(name, p("a"), p("b"))
    if distribution == "normal":
        return st.Normal(name, p("mu"), p("sigma"))
    if distribution == "exponential":
        return st.Exponential(name, p("rate"))
    raise InvalidInput(f"unsupported distribution '{distribution}'")


@handler("probability_compute", "distribution_moments")
def distribution_moments(ctx: Ctx) -> Outcome:
    import sympy.stats as st  # noqa: PLC0415

    rv = _rv(str(ctx.require("distribution")), ctx.get("params", {}) or {}, ctx)
    moment = str(ctx.require("moment"))
    if moment == "mean":
        value = st.E(rv)
    elif moment == "variance":
        value = st.variance(rv)
    elif moment == "std":
        value = st.std(rv)
    elif moment == "skewness":
        value = st.skewness(rv)
    else:
        raise InvalidInput(f"unsupported moment '{moment}'")
    return value_result(sp.simplify(value), certainty="exact", method="symbolic")


@handler("probability_compute", "probability_distribution")
def probability_distribution(ctx: Ctx) -> Outcome:
    import sympy.stats as st  # noqa: PLC0415

    rv = _rv(str(ctx.require("distribution")), ctx.get("params", {}) or {}, ctx)
    query = str(ctx.require("query"))
    at = parse_expression(str(ctx.require("at")), limits=ctx.limits)
    if query in ("pmf", "pdf"):
        value = st.density(rv)(at)
    elif query == "cdf":
        value = st.cdf(rv)(at)
    else:
        raise InvalidInput(f"unsupported query '{query}'")
    return value_result(sp.simplify(value), certainty="exact", method="symbolic")


@handler("probability_compute", "random_variable_transform")
def random_variable_transform(ctx: Ctx) -> Outcome:
    import sympy.stats as st  # noqa: PLC0415

    var = ctx.require_str("variable")
    rv = st.Normal(var, 0, 1)  # placeholder base; transform expressed in 'var'
    expr = parse_expression(ctx.require_str("expression"), limits=ctx.limits, allowed_symbols={var})
    transform = str(ctx.get("transform", "mean"))
    substituted = expr.subs(parse_symbol(var), rv)
    value = st.E(substituted) if transform == "mean" else st.variance(substituted)
    return value_result(sp.simplify(value), certainty="exact", method="symbolic")


@handler("probability_compute", "markov_chain_analyze")
def markov_chain_analyze(ctx: Ctx) -> Outcome:
    matrix_raw = ctx.require("transition_matrix")
    matrix = [
        [float(parse_expression(str(c), limits=ctx.limits)) for c in row] for row in matrix_raw
    ]
    query = str(ctx.get("query", "stationary"))
    steps = int(ctx.get("steps", 1))
    try:
        result = markov_analyze(matrix, query, steps)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    return object_result(result, certainty="exact", method="backend", backend="numpy")


@handler("probability_compute", "probability_simulation")
def probability_simulation(ctx: Ctx) -> Outcome:
    experiment = str(ctx.require("experiment"))
    trials = int(ctx.require("trials"))
    seed = ctx.limits.seed if ctx.limits.seed is not None else 12345
    p = float(parse_expression(str(ctx.get("p", "0.5")), limits=ctx.limits))
    sides = int(ctx.get("sides", 6))
    target = float(parse_expression(str(ctx.get("target", "1")), limits=ctx.limits))
    try:
        result = simulate(experiment, trials, p=p, sides=sides, target=target, seed=seed)
    except ValueError as exc:
        raise InvalidInput(str(exc)) from exc
    return value_result(
        result["estimate"],
        certainty="evidence",
        method="simulation",
        backend="numpy",
        warnings=["Monte Carlo estimate is statistical evidence, not a proof"],
        metadata={"seed": seed, "trials": trials, "hits": result["hits"]},
    )
