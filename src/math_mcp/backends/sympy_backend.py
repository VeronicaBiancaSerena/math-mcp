"""Shared SymPy helpers: bounded matrix/vector construction and serialization."""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.runtime.serialization import to_latex, to_text
from math_mcp.schemas import Limits

__all__ = ["build_matrix", "parse_vector", "to_text", "to_latex"]


def build_matrix(data: Any, limits: Limits) -> Any:
    """Parse a list-of-lists of strings into a SymPy Matrix with bounded dimensions."""
    if not isinstance(data, list) or not data:
        raise InvalidInput("matrix must be a non-empty list of rows")
    rows = len(data)
    if rows > limits.max_matrix_rows:
        raise InvalidInput(f"matrix has {rows} rows, exceeds limit {limits.max_matrix_rows}")
    parsed: list[list[Any]] = []
    width: int | None = None
    for row in data:
        if not isinstance(row, list):
            raise InvalidInput("each matrix row must be a list")
        if width is None:
            width = len(row)
            if width > limits.max_matrix_cols:
                raise InvalidInput(
                    f"matrix has {width} columns, exceeds limit {limits.max_matrix_cols}"
                )
        elif len(row) != width:
            raise InvalidInput("matrix rows must all have the same length")
        parsed.append([parse_expression(str(cell), limits=limits) for cell in row])
    return sp.Matrix(parsed)


def parse_vector(data: Any, limits: Limits) -> list[Any]:
    """Parse a list of strings into a list of SymPy expressions, bounded by matrix rows."""
    if not isinstance(data, list):
        raise InvalidInput("vector must be a list")
    if len(data) > limits.max_matrix_rows:
        raise InvalidInput("vector length exceeds limit")
    return [parse_expression(str(v), limits=limits) for v in data]
