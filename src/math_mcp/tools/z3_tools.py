"""Z3 constraint operations: satisfiability and refutation (counterexample/proof)."""

from __future__ import annotations

from math_mcp.backends.z3_backend import refute_claim, solve_constraints
from math_mcp.errors import InvalidInput
from math_mcp.tools.base import Ctx, Outcome, certificate, verification_result
from math_mcp.tools.dispatch import handler


def _variables(ctx: Ctx) -> dict[str, str]:
    variables = ctx.require("variables")
    if not isinstance(variables, dict):
        raise InvalidInput("'variables' must be an object mapping name -> sort")
    return {str(k): str(v) for k, v in variables.items()}


@handler("z3_compute", "z3_satisfiability")
def z3_satisfiability(ctx: Ctx) -> Outcome:
    variables = _variables(ctx)
    constraints = ctx.require("constraints")
    if not isinstance(constraints, list):
        raise InvalidInput("'constraints' must be a list of AST nodes")
    outcome = solve_constraints(variables, constraints, ctx.limits.timeout_ms)
    if outcome["result"] == "sat":
        return verification_result(
            status="success",
            certainty="exact",
            method="backend",
            backend="z3",
            result={"satisfiable": True, "model": outcome["model"]},
            result_kind="witness",
        )
    if outcome["result"] == "unsat":
        return verification_result(
            status="proved_by_smt",
            certainty="proved",
            method="smt",
            backend="z3",
            result={"satisfiable": False},
            result_kind="verification",
            certificate_=certificate(
                "smt_unsat",
                "the constraint set is UNSAT",
                details={"solver": "z3"},
            ),
        )
    return verification_result(
        status="unknown",
        certainty="unknown",
        method="none",
        backend="z3",
        result={"satisfiable": "unknown"},
        result_kind="none",
        explanation="Z3 returned unknown; this is not a proof.",
        warnings=["z3 returned unknown (nonlinear/quantified theory may be undecidable here)"],
    )


@handler("z3_compute", "z3_find_counterexample")
def z3_find_counterexample(ctx: Ctx) -> Outcome:
    variables = _variables(ctx)
    assumptions = ctx.get("assumptions", []) or []
    if not isinstance(assumptions, list):
        raise InvalidInput("'assumptions' must be a list of AST nodes")
    claim = ctx.require("claim")
    outcome = refute_claim(variables, assumptions, claim, ctx.limits.timeout_ms)
    if outcome["result"] == "sat":
        witness = {"counterexample": outcome["model"]}
        return verification_result(
            status="disproved_by_counterexample",
            certainty="disproved",
            method="counterexample",
            backend="z3",
            result=witness,
            result_kind="witness",
            certificate_=certificate(
                "counterexample",
                "Z3 found a model violating the claim",
                machine_checkable=True,
                details=witness,
            ),
        )
    if outcome["result"] == "unsat":
        return verification_result(
            status="proved_by_smt",
            certainty="proved",
            method="smt",
            backend="z3",
            result={"claim_holds": True},
            result_kind="verification",
            certificate_=certificate(
                "smt_unsat",
                "negation of the claim is UNSAT under the assumptions",
                details={"solver": "z3", "query_kind": "unsat_check"},
            ),
        )
    return verification_result(
        status="unknown",
        certainty="unknown",
        method="none",
        backend="z3",
        result={"claim_holds": "unknown"},
        result_kind="none",
        explanation="Z3 returned unknown; this is not a proof.",
        warnings=["z3 returned unknown"],
    )
