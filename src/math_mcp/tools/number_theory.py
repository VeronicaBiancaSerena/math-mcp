"""Number theory over integers and finite modular arithmetic."""

from __future__ import annotations

import sympy as sp
from sympy.core.intfunc import igcdex
from sympy.ntheory.modular import crt
from sympy.ntheory.residue_ntheory import is_primitive_root, is_quad_residue, n_order

from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.tools.base import (
    Ctx,
    Outcome,
    object_result,
    solution_set_result,
    value_result,
    verification_result,
)
from math_mcp.tools.dispatch import handler


def _int(ctx: Ctx, key: str) -> int:
    value = parse_expression(str(ctx.require(key)), limits=ctx.limits)
    if not value.is_Integer:
        raise InvalidInput(f"'{key}' must be an integer")
    return int(value)


@handler("number_theory_compute", "gcd_lcm_bezout")
def gcd_lcm_bezout(ctx: Ctx) -> Outcome:
    a, b = _int(ctx, "a"), _int(ctx, "b")
    x, y, g = igcdex(a, b)
    result = {
        "gcd": int(g),
        "lcm": int(abs(a * b) // sp.igcd(a, b)) if (a or b) else 0,
        "bezout": {"x": int(x), "y": int(y)},
        "identity": f"{a}*({x}) + {b}*({y}) = {int(g)}",
    }
    return object_result(result, certainty="exact", method="backend", backend="sympy")


@handler("number_theory_compute", "prime_analyze")
def prime_analyze(ctx: Ctx) -> Outcome:
    n = _int(ctx, "n")
    query = str(ctx.get("query", "factorize"))
    if query == "is_prime":
        return verification_result(
            status="success",
            certainty="exact",
            method="backend",
            result={"is_prime": bool(sp.isprime(n))},
        )
    if query == "next_prime":
        return value_result(int(sp.nextprime(n)), certainty="exact", method="backend")
    if query == "prev_prime":
        if n <= 2:
            raise InvalidInput("no prime below 2")
        return value_result(int(sp.prevprime(n)), certainty="exact", method="backend")
    if query == "factorize":
        factors = {str(p): int(e) for p, e in sp.factorint(n).items()}
        return object_result({"factorization": factors}, certainty="exact", method="backend")
    raise InvalidInput(f"unsupported prime query '{query}'")


@handler("number_theory_compute", "modular_arithmetic")
def modular_arithmetic(ctx: Ctx) -> Outcome:
    kind = str(ctx.require("kind"))
    modulus = _int(ctx, "modulus")
    if modulus <= 0:
        raise InvalidInput("modulus must be positive")
    if kind == "pow":
        base, exponent = _int(ctx, "a"), _int(ctx, "exponent")
        return value_result(pow(base, exponent, modulus), certainty="exact", method="backend")
    if kind == "inverse":
        a = _int(ctx, "a")
        if sp.igcd(a, modulus) != 1:
            raise InvalidInput("inverse does not exist (a and modulus are not coprime)")
        return value_result(int(sp.mod_inverse(a, modulus)), certainty="exact", method="backend")
    if kind == "solve_linear":
        return _solve_linear_congruence(_int(ctx, "a"), _int(ctx, "b"), modulus)
    raise InvalidInput(f"unsupported modular kind '{kind}'")


def _solve_linear_congruence(a: int, b: int, m: int) -> Outcome:
    g = int(sp.igcd(a, m))
    if b % g != 0:
        return solution_set_result(
            [],
            certainty="exact",
            method="backend",
            explanation="no solution: gcd(a, m) does not divide b",
        )
    a2, b2, m2 = a // g, b % m // g, m // g
    base = (b2 * int(sp.mod_inverse(a2 % m2, m2))) % m2
    solutions = [(base + k * m2) % m for k in range(g)]
    return solution_set_result(
        sorted(set(solutions)), certainty="exact", method="backend", metadata={"modulus": m}
    )


@handler("number_theory_compute", "congruence_solve")
def congruence_solve(ctx: Ctx) -> Outcome:
    return _solve_linear_congruence(_int(ctx, "a"), _int(ctx, "b"), _int(ctx, "modulus"))


@handler("number_theory_compute", "chinese_remainder")
def chinese_remainder(ctx: Ctx) -> Outcome:
    remainders = ctx.require("remainders")
    moduli = ctx.require("moduli")
    if not isinstance(remainders, list) or not isinstance(moduli, list):
        raise InvalidInput("'remainders' and 'moduli' must be lists")
    rs = [int(parse_expression(str(r), limits=ctx.limits)) for r in remainders]
    ms = [int(parse_expression(str(m), limits=ctx.limits)) for m in moduli]
    solution = crt(ms, rs)
    if solution is None:
        return value_result(
            None,
            certainty="exact",
            method="backend",
            result_kind="none",
            explanation="no solution: moduli are not pairwise compatible",
        )
    x, modulus = solution
    return value_result(
        int(x), certainty="exact", method="backend", metadata={"modulus": int(modulus)}
    )


@handler("number_theory_compute", "totient_compute")
def totient_compute(ctx: Ctx) -> Outcome:
    n = _int(ctx, "n")
    if n < 1:
        raise InvalidInput("n must be a positive integer")
    kind = str(ctx.get("kind", "euler"))
    if kind == "euler":
        return value_result(int(sp.totient(n)), certainty="exact", method="backend")
    if kind == "carmichael":
        return value_result(int(sp.reduced_totient(n)), certainty="exact", method="backend")
    raise InvalidInput(f"unsupported totient kind '{kind}'")


@handler("number_theory_compute", "multiplicative_order")
def multiplicative_order(ctx: Ctx) -> Outcome:
    a, n = _int(ctx, "a"), _int(ctx, "n")
    if sp.igcd(a, n) != 1:
        raise InvalidInput("multiplicative order requires gcd(a, n) == 1")
    if ctx.get("check_primitive_root"):
        return verification_result(
            status="success",
            certainty="exact",
            method="backend",
            result={"is_primitive_root": bool(is_primitive_root(a, n))},
        )
    return value_result(int(n_order(a, n)), certainty="exact", method="backend")


@handler("number_theory_compute", "quadratic_residue_check")
def quadratic_residue_check(ctx: Ctx) -> Outcome:
    a, p = _int(ctx, "a"), _int(ctx, "p")
    kind = str(ctx.get("kind", "is_qr"))
    if kind == "is_qr":
        if not sp.isprime(p):
            raise InvalidInput("is_qr expects a prime modulus")
        return verification_result(
            status="success",
            certainty="exact",
            method="backend",
            result={"is_quadratic_residue": bool(is_quad_residue(a, p))},
        )
    if kind == "legendre":
        if not sp.isprime(p):
            raise InvalidInput("legendre symbol requires a prime modulus")
        return value_result(int(sp.legendre_symbol(a, p)), certainty="exact", method="backend")
    if kind == "jacobi":
        return value_result(int(sp.jacobi_symbol(a, p)), certainty="exact", method="backend")
    raise InvalidInput(f"unsupported quadratic residue kind '{kind}'")
