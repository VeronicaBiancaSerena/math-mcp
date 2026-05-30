"""Linear algebra operations over exact SymPy matrices (plus numeric decomposition)."""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.backends.sympy_backend import build_matrix, parse_vector, to_latex
from math_mcp.errors import InvalidInput
from math_mcp.runtime.serialization import to_text
from math_mcp.tools.base import Ctx, Outcome, object_result, solution_set_result, value_result
from math_mcp.tools.dispatch import handler


def _matrix_to_lists(matrix: Any) -> list[list[str]]:
    return [[to_text(matrix[r, c]) for c in range(matrix.cols)] for r in range(matrix.rows)]


def _load(ctx: Ctx) -> Any:
    return build_matrix(ctx.require("matrix"), ctx.limits)


@handler("matrix_compute", "det")
def det(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    if matrix.rows != matrix.cols:
        raise InvalidInput("determinant requires a square matrix")
    value = matrix.det()
    return value_result(value, latex=to_latex(value), certainty="exact", method="backend")


@handler("matrix_compute", "rank")
def rank(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    return value_result(matrix.rank(), certainty="exact", method="backend")


@handler("matrix_compute", "trace")
def trace(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    if matrix.rows != matrix.cols:
        raise InvalidInput("trace requires a square matrix")
    value = matrix.trace()
    return value_result(value, latex=to_latex(value), certainty="exact", method="backend")


@handler("matrix_compute", "transpose")
def transpose(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    return object_result(_matrix_to_lists(matrix.T), certainty="exact", method="backend")


@handler("matrix_compute", "inverse")
def inverse(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    if matrix.rows != matrix.cols:
        raise InvalidInput("inverse requires a square matrix")
    if matrix.det() == 0:
        raise InvalidInput("matrix is singular and has no inverse")
    return object_result(_matrix_to_lists(matrix.inv()), certainty="exact", method="backend")


@handler("matrix_compute", "rref")
def rref(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    reduced, pivots = matrix.rref()
    return object_result(
        {"rref": _matrix_to_lists(reduced), "pivot_columns": list(pivots)},
        certainty="exact",
        method="backend",
    )


@handler("matrix_compute", "eigenvals")
def eigenvals(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    if matrix.rows != matrix.cols:
        raise InvalidInput("eigenvalues require a square matrix")
    values = matrix.eigenvals()
    result = {to_text(val): int(mult) for val, mult in values.items()}
    return object_result(
        {"eigenvalues_with_multiplicity": result},
        certainty="exact",
        method="backend",
    )


@handler("matrix_compute", "charpoly")
def charpoly(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    if matrix.rows != matrix.cols:
        raise InvalidInput("characteristic polynomial requires a square matrix")
    lam = sp.Symbol("lambda")
    poly = matrix.charpoly(lam).as_expr()
    return value_result(
        poly,
        latex=to_latex(poly),
        certainty="exact",
        method="backend",
        metadata={"variable": "lambda"},
    )


@handler("matrix_compute", "solve_linear_system")
def solve_linear_system(ctx: Ctx) -> Outcome:
    matrix = _load(ctx)
    rhs = parse_vector(ctx.require("rhs"), ctx.limits)
    if len(rhs) != matrix.rows:
        raise InvalidInput("rhs length must match the number of matrix rows")
    b = sp.Matrix(rhs)
    solution = sp.linsolve((matrix, b))
    result = [[to_text(v) for v in sol] for sol in solution]
    return solution_set_result(result, certainty="exact", method="symbolic")


@handler("matrix_compute", "matrix_decomposition_numeric")
def matrix_decomposition_numeric(ctx: Ctx) -> Outcome:
    import numpy as np  # noqa: PLC0415

    matrix = _load(ctx)
    kind = str(ctx.require("kind"))
    try:
        arr = np.array(matrix.evalf().tolist(), dtype=float)
    except (TypeError, ValueError) as exc:
        raise InvalidInput("matrix must be numeric for decomposition") from exc

    if kind == "lu":
        import scipy.linalg as sla  # noqa: PLC0415

        p, lo, up = sla.lu(arr)
        result: Any = {"P": p.tolist(), "L": lo.tolist(), "U": up.tolist()}
    elif kind == "qr":
        q, r = np.linalg.qr(arr)
        result = {"Q": q.tolist(), "R": r.tolist()}
    elif kind == "svd":
        u, s, vh = np.linalg.svd(arr)
        result = {"U": u.tolist(), "singular_values": s.tolist(), "Vh": vh.tolist()}
    elif kind == "eig":
        vals, vecs = np.linalg.eig(arr)
        result = {
            "eigenvalues": [complex(v).__repr__() for v in vals],
            "eigenvectors": vecs.tolist(),
        }
    else:
        raise InvalidInput(f"unsupported decomposition kind '{kind}'")
    return object_result(result, certainty="exact", method="backend", backend="numpy")
