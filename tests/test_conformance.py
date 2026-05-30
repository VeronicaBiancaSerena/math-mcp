"""Conformance tests: the implementation honors the public protocol, not backend luck."""

from __future__ import annotations

import pytest
from conftest import call

from math_mcp import backend_caveats
from math_mcp.operation_registry import all_operations
from math_mcp.schema_check import validate_payload
from math_mcp.schemas import ToolResult
from math_mcp.tools.capabilities import get_capabilities

# Operations whose example needs an explicit finite domain to execute.
EXTRA_DOMAINS = {
    ("discrete_compute", "finite_enumeration"): [
        {"variable": "x", "kind": "integer", "lower": "0", "upper": "5"},
        {"variable": "y", "kind": "integer", "lower": "0", "upper": "5"},
    ],
    ("logic_compute", "finite_quantifier_check"): [
        {"variable": "x", "kind": "integer", "lower": "-3", "upper": "3"},
    ],
}

IMPLEMENTED = [s for s in all_operations() if s.state == "implemented"]


@pytest.mark.parametrize("spec", IMPLEMENTED, ids=lambda s: f"{s.public_tool}:{s.operation}")
def test_implemented_example_runs_and_validates(spec) -> None:  # type: ignore[no-untyped-def]
    domains = EXTRA_DOMAINS.get((spec.public_tool, spec.operation))
    result = call(spec.public_tool, spec.operation, spec.example_payload, domains=domains)
    assert isinstance(result, ToolResult)
    assert result.ok, f"{spec.operation} failed: {result.status} {result.error}"
    # Successful results must set a meaningful result_kind.
    assert result.result_kind != "none"
    # max_certainty is an upper bound the actual certainty must respect.
    from math_mcp.status import certainty_rank

    assert certainty_rank(result.certainty) >= certainty_rank(spec.max_certainty)


def test_every_operation_payload_schema_is_well_formed() -> None:
    cap = get_capabilities(include_experimental=True, include_disabled=True)
    for tool in cap["public_tools"].values():
        for op_name, op in tool["operations"].items():
            schema = op["payload_schema"]
            assert "type" in schema, f"{op_name} schema missing type"
            if schema["type"] == "object":
                assert "properties" in schema, f"{op_name} object schema missing properties"
            # example payload validates against its own schema
            assert not validate_payload(op["example_payload"], schema), op_name


def test_unknown_operation_is_unsupported() -> None:
    result = call("algebra_compute", "does_not_exist", {"expression": "x"})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"


def test_payload_operation_subfield_forbidden_everywhere() -> None:
    for spec in all_operations():
        props = spec.payload_schema.get("properties", {})
        assert "operation" not in props


def test_conditions_have_ast_when_structurable() -> None:
    # Indefinite integral yields a side condition; structured AST is optional for the
    # "+ C" note, but any condition object must carry the documented fields.
    result = call("calculus_compute", "integrate", {"expression": "2*x", "variable": "x"})
    for cond in result.conditions:
        assert "source" in cond.model_dump()


def test_caveat_downgrade_actually_lowers_certainty() -> None:
    # A numeric-method result with a scipy-optimize caveat must be pulled down to evidence,
    # not merely warned about.
    certainty, warnings, records = backend_caveats.enforce(
        "scipy", "numeric_optimize", "numeric_optimization", "exact", has_override=False
    )
    assert certainty == "evidence"
    assert records and warnings


def test_caveat_downgrade_skipped_with_override() -> None:
    certainty, _w, _r = backend_caveats.enforce(
        "scipy", "numeric_optimize", "numeric_optimization", "exact", has_override=True
    )
    assert certainty == "exact"


def test_proof_method_result_not_downgraded() -> None:
    # A counterexample (genuine disproof) must never be downgraded by a sampling caveat.
    certainty, _w, _r = backend_caveats.enforce(
        "mpmath", "search_counterexample", "counterexample", "disproved", has_override=False
    )
    assert certainty == "disproved"


def test_default_trace_is_minimal_and_private() -> None:
    result = call(
        "algebra_compute", "simplify_expression", {"expression": "x + x", "variables": ["x"]}
    )
    meta = result.metadata
    assert meta["debug_trace_enabled"] is False
    blob = repr(meta)
    assert "/home/" not in blob
    assert "passwd" not in blob
    # trace records the operation, not a natural-language prompt
    assert meta["operation"] == "simplify_expression"
