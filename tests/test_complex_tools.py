"""Tests for complex_compute (golden cases + error paths)."""

from __future__ import annotations

import pytest
from conftest import call, load_golden


@pytest.mark.parametrize(
    "case", load_golden("complex_cases.json"), ids=lambda c: c["input"]["operation"]
)
def test_golden(case, golden) -> None:
    golden(case)


def test_unsupported_operation() -> None:
    result = call("complex_compute", "definitely_not_an_op", {})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_roots_of_unity_count() -> None:
    result = call("complex_compute", "complex_roots_of_unity", {"n": 4})
    assert result.ok and result.result["n"] == 4
    assert len(result.result["roots"]) == 4


def test_mod_arg_declares_principal_branch() -> None:
    # arg uses SymPy's principal branch (-pi, pi]; this convention must be surfaced as a
    # structured branch condition + metadata (guide §10.2/§21).
    result = call("complex_compute", "complex_mod_arg", {"expression": "1 + I"})
    assert result.ok
    assert result.metadata.get("branch_conventions") == {"arg": "principal value in (-pi, pi]"}
    branch = [c for c in result.conditions if c.source == "branch"]
    assert branch and branch[0].condition_ast is not None
