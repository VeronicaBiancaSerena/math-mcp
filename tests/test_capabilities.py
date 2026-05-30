"""Tests for the math_capabilities document (generated from the registry)."""

from __future__ import annotations

from math_mcp.operation_registry import all_operations, public_tools
from math_mcp.schema_check import validate_payload
from math_mcp.tools.capabilities import get_capabilities

EXPECTED_PUBLIC_TOOLS = {
    "ping",
    "math_capabilities",
    "algebra_compute",
    "calculus_compute",
    "verification_compute",
    "z3_compute",
    "matrix_compute",
    "discrete_compute",
    "graph_compute",
    "probability_compute",
    "set_compute",
    "geometry_compute",
    "trigonometry_compute",
    "number_theory_compute",
    "logic_compute",
    "ode_compute",
    "complex_compute",
    "inequality_compute",
}

OPERATION_REQUIRED_FIELDS = (
    "operation_version",
    "state",
    "default_limits",
    "risk",
    "complexity_class",
    "runs_in_subprocess",
    "proof_modes",
    "max_certainty",
    "numeric_only",
    "result_kinds",
    "accepted_input_forms",
    "determinism",
    "payload_schema",
    "example_payload",
    "deprecated",
    "replacement",
    "proof_capable",
)


def test_capabilities_top_level() -> None:
    cap = get_capabilities()
    assert cap["server"] == "math-mcp"
    assert cap["schema_version"] == "1.0"
    assert cap["capabilities_version"] == "1.0"
    assert set(cap["public_tools"]) == EXPECTED_PUBLIC_TOOLS


def test_utility_tools_are_marked() -> None:
    cap = get_capabilities()
    for name in ("ping", "math_capabilities"):
        tool = cap["public_tools"][name]
        assert tool["kind"] == "utility"
        assert tool["operations"] == {}


def test_compute_tools_have_operations() -> None:
    cap = get_capabilities()
    for name, tool in cap["public_tools"].items():
        if name in ("ping", "math_capabilities"):
            continue
        assert tool["kind"] == "compute"
        assert tool["operations"], f"{name} has no operations"


def test_every_operation_declares_required_fields() -> None:
    cap = get_capabilities(include_experimental=True, include_disabled=True)
    for tool in cap["public_tools"].values():
        for op_name, op in tool["operations"].items():
            for field in OPERATION_REQUIRED_FIELDS:
                assert field in op, f"{op_name} missing {field}"
            # proof_capable is derived, never hand-written.
            assert op["proof_capable"] == bool(op["proof_modes"])


def test_example_payloads_validate_against_schema() -> None:
    for spec in all_operations():
        errors = validate_payload(spec.example_payload, spec.payload_schema)
        assert not errors, f"{spec.operation}: {errors}"


def test_payload_schema_has_no_operation_subfield() -> None:
    cap = get_capabilities(include_experimental=True, include_disabled=True)
    for tool in cap["public_tools"].values():
        for op in tool["operations"].values():
            props = op["payload_schema"].get("properties", {})
            assert "operation" not in props


def test_experimental_hidden_by_default() -> None:
    # All registry operations are currently implemented, so the guarantee is verified at
    # the mechanism level: the visibility filter must hide experimental/disabled by default
    # and reveal them only with the explicit flags (guide §15.8). This stays correct even
    # when no experimental operation exists in the registry.
    from math_mcp.tools.capabilities import _state_visible

    assert _state_visible("implemented", False, False)
    assert _state_visible("deprecated", False, False)
    assert not _state_visible("experimental", False, False)
    assert _state_visible("experimental", True, False)
    assert not _state_visible("disabled", False, False)
    assert _state_visible("disabled", False, True)
    # And no experimental/disabled operation may leak into the default document.
    default = get_capabilities()
    for spec in all_operations():
        if spec.state in ("experimental", "disabled"):
            assert spec.operation not in default["public_tools"][spec.public_tool]["operations"]


def test_documented_public_tools_match_registry() -> None:
    registry_tools = set(public_tools())
    cap_tools = set(get_capabilities()["public_tools"]) - {"ping", "math_capabilities"}
    assert registry_tools == cap_tools
