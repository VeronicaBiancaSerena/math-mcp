"""Tests for the core Pydantic schemas and status vocabulary."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from math_mcp.schemas import (
    AssumptionSpec,
    Certificate,
    DomainSpec,
    Limits,
    OperationRequest,
    ResultCondition,
    ToolResult,
)
from math_mcp.status import certainty_rank, is_weaker_or_equal


def test_toolresult_minimal() -> None:
    result = ToolResult(
        ok=True, status="success", certainty="exact", method="backend", duration_ms=1
    )
    assert result.result_kind == "none"
    assert result.warnings == []
    assert result.metadata == {}


def test_limits_defaults_and_bounds() -> None:
    limits = Limits()
    assert limits.timeout_ms == 5000
    assert limits.max_samples == 1000
    with pytest.raises(ValidationError):
        Limits(timeout_ms=0)
    with pytest.raises(ValidationError):
        Limits(memory_mb=10)  # below the 64 MB floor


def test_limits_forbids_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Limits(unknown_field=5)  # type: ignore[call-arg]


def test_operation_request_defaults() -> None:
    req = OperationRequest(operation="simplify_expression", payload={"expression": "x"})
    assert req.domains == []
    assert req.assumptions == []
    assert req.limits.timeout_ms == 5000


def test_domain_spec_kind_validation() -> None:
    DomainSpec(variable="x", kind="real", lower="0", upper="1")
    with pytest.raises(ValidationError):
        DomainSpec(variable="x", kind="not_a_kind")  # type: ignore[arg-type]


def test_assumption_spec() -> None:
    spec = AssumptionSpec(variable="x", predicates=["positive"])
    assert spec.predicates == ["positive"]


def test_certificate_and_condition_models() -> None:
    cert = Certificate(type="smt_unsat", summary="unsat")
    assert cert.machine_checkable is False
    cond = ResultCondition(expression="x != 0", source="backend")
    assert cond.condition_ast is None


def test_certainty_ordering() -> None:
    assert certainty_rank("proved") == certainty_rank("disproved") == 0
    assert certainty_rank("exact") < certainty_rank("evidence")
    assert is_weaker_or_equal("evidence", "exact")
    assert not is_weaker_or_equal("exact", "evidence")
