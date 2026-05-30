"""Tests for matrix_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
import sympy as sp
from conftest import call, load_golden
from hypothesis import given, settings
from hypothesis import strategies as st


@pytest.mark.parametrize(
    "case", load_golden("matrix_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("matrix_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_det_requires_square() -> None:
    result = call("matrix_compute", "det", {"matrix": [["1", "2", "3"], ["4", "5", "6"]]})
    assert result.ok is False


def test_inverse_singular_rejected() -> None:
    result = call("matrix_compute", "inverse", {"matrix": [["1", "2"], ["2", "4"]]})
    assert result.ok is False


def test_exact_rational_entries() -> None:
    result = call("matrix_compute", "det", {"matrix": [["1/3", "0"], ["0", "3"]]})
    assert result.ok and result.result == "1"


def _det_via_tool(matrix: list[list[int]]) -> sp.Integer:
    payload = {"matrix": [[str(v) for v in row] for row in matrix]}
    result = call("matrix_compute", "det", payload)
    assert result.ok, result.error
    return sp.Integer(int(result.result))


_ENTRY = st.integers(min_value=-9, max_value=9)
_ROW2 = st.tuples(_ENTRY, _ENTRY)
_MAT2 = st.tuples(_ROW2, _ROW2)


@settings(max_examples=30, deadline=None)
@given(_MAT2, _MAT2)
def test_det_is_multiplicative(a_rows, b_rows) -> None:
    # Differential check (guide §15.4): det(A*B) == det(A)*det(B) for 2x2 integer matrices.
    a = sp.Matrix(a_rows)
    b = sp.Matrix(b_rows)
    product = (a * b).tolist()
    det_a = _det_via_tool([list(r) for r in a_rows])
    det_b = _det_via_tool([list(r) for r in b_rows])
    det_ab = _det_via_tool([[int(v) for v in row] for row in product])
    assert det_ab == det_a * det_b


def test_matrix_decomposition_reconstructs() -> None:
    # Differential (guide §15.5): QR and SVD must reconstruct the original matrix.
    import numpy as np

    A = np.array([[1.0, 2.0], [3.0, 4.0]])
    qr = call("matrix_compute", "matrix_decomposition_numeric",
              {"matrix": [["1", "2"], ["3", "4"]], "kind": "qr"})
    assert qr.ok
    Q, R = np.array(qr.result["Q"]), np.array(qr.result["R"])
    assert np.allclose(Q @ R, A, atol=1e-9)
    svd = call("matrix_compute", "matrix_decomposition_numeric",
               {"matrix": [["1", "2"], ["3", "4"]], "kind": "svd"})
    assert svd.ok
    U = np.array(svd.result["U"])
    s = np.array(svd.result["singular_values"])
    Vh = np.array(svd.result["Vh"])
    assert np.allclose(U @ np.diag(s) @ Vh, A, atol=1e-9)
