"""Tests that the operation registry is the single source of truth and is well-formed."""

from __future__ import annotations

from math_mcp.operation_registry import all_operations, get_spec
from math_mcp.tools.dispatch import HANDLERS, _ensure_loaded


def test_every_operation_routes_to_a_handler() -> None:
    _ensure_loaded()
    for spec in all_operations():
        assert (spec.public_tool, spec.operation) in HANDLERS, (
            f"no handler for {spec.public_tool}/{spec.operation}"
        )


def test_handlers_all_have_registry_entries() -> None:
    _ensure_loaded()
    for public_tool, operation in HANDLERS:
        assert get_spec(public_tool, operation) is not None


def test_operation_state_default_is_experimental() -> None:
    from math_mcp.operation_registry import OperationSpec

    spec = OperationSpec.model_validate(
        {
            "public_tool": "x",
            "operation": "y",
            "backend": "sympy",
            "risk": "low",
            "complexity_class": "constant",
            "runs_in_subprocess": False,
            "max_certainty": "exact",
            "numeric_only": False,
            "result_kinds": ["value"],
            "determinism": "deterministic",
            "accepted_input_forms": ["expression_string"],
            "payload_schema": {"type": "object"},
            "example_payload": {},
        }
    )
    assert spec.state == "experimental"


def test_deprecated_consistency() -> None:
    for spec in all_operations():
        if spec.state == "deprecated":
            assert spec.deprecated is True
            assert spec.replacement is not None
        if spec.replacement is not None:
            target = get_spec(spec.replacement.public_tool, spec.replacement.operation)
            assert target is not None
            assert target.state == "implemented"


def test_default_limits_within_hard_caps() -> None:
    for spec in all_operations():
        dl = spec.default_limits
        assert dl.timeout_ms <= 60000
        assert dl.cpu_time_ms <= 60000
        assert dl.memory_mb <= 8192
        assert dl.max_samples <= 100000


def test_proof_capable_is_computed() -> None:
    for spec in all_operations():
        assert spec.proof_capable == bool(spec.proof_modes)


def test_first_batch_is_implemented() -> None:
    first_batch = [
        ("algebra_compute", "simplify_expression"),
        ("verification_compute", "check_identity"),
        ("verification_compute", "search_counterexample"),
        ("z3_compute", "z3_satisfiability"),
        ("matrix_compute", "det"),
        ("matrix_compute", "rank"),
        ("calculus_compute", "numeric_evaluate"),
    ]
    for tool, op in first_batch:
        spec = get_spec(tool, op)
        assert spec is not None and spec.state == "implemented"
