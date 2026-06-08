"""V1 discoverability and self-correction optimizations (guide §24).

Covers: operation aliases, capabilities summary mode, unknown-operation suggestions,
and the finite_enumeration top-level-domains help. The two new constrained operations
(check_identity_constrained, constrained_optimize) are exercised in test_verification.py
and test_calculus.py respectively.
"""

from __future__ import annotations

from conftest import call

from math_mcp.operation_registry import all_operations, suggest_operations
from math_mcp.tools.capabilities import get_capabilities

# --- operation aliases (§5/§24) --------------------------------------------


def test_algebra_simplify_alias_resolves() -> None:
    result = call("algebra_compute", "simplify", {"expression": "x + x", "variables": ["x"]})
    assert result.ok and result.status == "success"
    assert result.metadata["operation"] == "simplify_expression"
    assert result.metadata["requested_operation"] == "simplify"
    assert result.metadata["operation_alias_resolved"] is True


def test_trig_simplify_alias_resolves() -> None:
    result = call(
        "trigonometry_compute",
        "simplify",
        {"expression": "sin(x)**2 + cos(x)**2", "variables": ["x"]},
    )
    assert result.ok
    assert result.metadata["operation"] == "trig_simplify"
    assert result.metadata["requested_operation"] == "simplify"


def test_more_aliases_resolve() -> None:
    cases = {
        ("algebra_compute", "factor"): "factor_expression",
        ("algebra_compute", "solve"): "solve_equation",
        ("trigonometry_compute", "expand"): "trig_expand",
        ("trigonometry_compute", "check_identity"): "trig_identity_check",
    }
    for (tool, alias), canonical in cases.items():
        # solve_equation needs a 'variable'; identity_check needs left/right — use minimal
        # payloads that at least route to the canonical operation.
        payload = {
            "factor": {"expression": "x**2 - 1", "variables": ["x"]},
            "solve": {"expression": "x - 1", "variable": "x"},
            "expand": {"expression": "sin(2*x)", "variables": ["x"]},
            "check_identity": {"left": "sin(x)", "right": "sin(x)", "variables": ["x"]},
        }[alias]
        result = call(tool, alias, payload)
        assert result.metadata["operation"] == canonical, (tool, alias)


def test_canonical_name_wins_over_alias() -> None:
    # A direct canonical call is not flagged as alias-resolved.
    result = call(
        "algebra_compute", "simplify_expression", {"expression": "x + x", "variables": ["x"]}
    )
    assert result.ok
    assert result.metadata["requested_operation"] == "simplify_expression"
    assert "operation_alias_resolved" not in result.metadata


def test_aliases_never_collide_with_real_operation_names() -> None:
    # The registry primary keys stay canonical: no alias shadows a real operation.
    from math_mcp.operation_registry import _ALIASES

    for tool, mapping in _ALIASES.items():
        real = {s.operation for s in all_operations() if s.public_tool == tool}
        for alias, target in mapping.items():
            assert alias not in real
            assert target in real


# --- unknown-operation suggestions (§6/§24) --------------------------------


def test_typo_returns_suggestion_and_does_not_reach_backend() -> None:
    result = call("algebra_compute", "simlify", {"expression": "x"})
    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error_code == "UNSUPPORTED_OPERATION"
    assert result.metadata["suggested_operations"] == ["simplify_expression"]
    assert result.metadata["operation_state"] == "unknown"
    assert "Did you mean 'simplify_expression'?" in (result.error or "")
    # An unknown operation must never reach a backend or subprocess.
    assert result.backend == "none"


def test_unknown_operation_lists_available_operations() -> None:
    result = call("algebra_compute", "zzz_not_real", {"expression": "x"})
    assert result.ok is False
    available = result.metadata["available_operations"]
    assert "simplify_expression" in available
    assert len(available) <= 20


def test_suggest_operations_helper_priorities() -> None:
    # exact alias match wins
    sugg, source = suggest_operations("algebra_compute", "simplify")
    assert sugg == ["simplify_expression"] and source == "alias"
    # fuzzy typo against alias keys
    sugg, source = suggest_operations("trigonometry_compute", "simplifu")
    assert "trig_simplify" in sugg


# --- capabilities summary mode (§4/§24) ------------------------------------


def test_summary_mode_is_lightweight() -> None:
    cap = get_capabilities(mode="summary")
    assert cap["mode"] == "summary"
    alg = cap["public_tools"]["algebra_compute"]
    assert alg["kind"] == "compute"
    assert isinstance(alg["operations"], list)
    assert "simplify_expression" in alg["operations"]
    assert alg["aliases"]["simplify"] == "simplify_expression"
    # summary must NOT carry the heavy per-operation schema/limits.
    blob = repr(cap)
    assert "payload_schema" not in blob
    assert "default_limits" not in blob


def test_summary_includes_utility_tools() -> None:
    cap = get_capabilities(mode="summary")
    for name in ("ping", "math_capabilities"):
        assert cap["public_tools"][name]["kind"] == "utility"


def test_full_mode_unchanged_plus_aliases() -> None:
    cap = get_capabilities()
    assert cap["mode"] == "full"
    alg = cap["public_tools"]["algebra_compute"]
    assert isinstance(alg["operations"], dict)
    assert "payload_schema" in alg["operations"]["simplify_expression"]
    assert alg["aliases"]["solve"] == "solve_equation"


# --- finite_enumeration domain help (§7/§24) -------------------------------


def test_finite_enumeration_capabilities_show_top_level_domains() -> None:
    cap = get_capabilities()
    fe = cap["public_tools"]["discrete_compute"]["operations"]["finite_enumeration"]
    assert fe["requires_domains"] is True
    assert "domain_schema" in fe
    # the example_request shows domains as a TOP-LEVEL argument, not inside payload
    example = fe["example_request"]
    assert "domains" in example
    assert "domains" not in example["payload"]


def test_finite_enumeration_missing_domain_message_is_actionable() -> None:
    result = call(
        "discrete_compute", "finite_enumeration", {"predicate": "Eq(x, 1)", "variables": ["x"]}
    )
    assert result.ok is False
    assert result.error_code == "DOMAIN_UNSUPPORTED"
    assert "top-level argument" in (result.error or "")


def test_finite_enumeration_domains_in_payload_gets_migration_hint() -> None:
    result = call(
        "discrete_compute",
        "finite_enumeration",
        {
            "predicate": "Eq(x, 1)",
            "variables": ["x"],
            "domains": [{"variable": "x", "kind": "integer", "lower": "0", "upper": "3"}],
        },
    )
    assert result.ok is False
    assert result.error_code == "DOMAIN_UNSUPPORTED"
    assert "domains inside payload" in (result.error or "")
    assert "top-level argument" in (result.error or "")


# --- runtime payload_schema gate (guide §24.10) ----------------------------


def test_schema_gate_rejects_bad_enum_before_backend() -> None:
    result = call(
        "calculus_compute",
        "constrained_optimize",
        {
            "objective": "x",
            "variables": ["x"],
            "goal": "maximize",  # not in enum {min, max}
            "constraints": [{"relation": "==", "left": "x", "right": "1"}],
        },
    )
    assert result.ok is False
    assert result.status == "invalid_input"
    assert result.backend == "none"
    assert "schema" in (result.error or "")


def test_schema_gate_rejects_wrong_type() -> None:
    result = call("matrix_compute", "det", {"matrix": "not-a-matrix"})
    assert result.ok is False
    assert result.status == "invalid_input"
    assert result.backend == "none"


def test_schema_gate_rejects_out_of_bounds() -> None:
    result = call(
        "verification_compute",
        "search_counterexample",
        {"left": "x", "relation": ">", "right": "0", "variables": ["x"], "samples": 10**9},
    )
    assert result.ok is False
    assert result.status == "invalid_input"


def test_schema_gate_preserves_expr_ast_alternative() -> None:
    # 'expression' is schema-required, but expr_ast is an accepted alternative; the gate
    # must not reject a valid expr_ast-only payload (required-checking stays in handlers).
    result = call(
        "algebra_compute",
        "simplify_expression",
        {"expr_ast": {"op": "add", "args": [{"var": "x"}, {"var": "x"}]}, "variables": ["x"]},
    )
    assert result.ok and result.result == "2*x"


def test_schema_gate_still_routes_bad_ast_to_invalid_ast() -> None:
    # A structurally-typed-but-invalid expr_ast passes the schema gate (it is an object)
    # and is rejected by the handler with INVALID_AST, not a generic schema error.
    result = call(
        "algebra_compute",
        "simplify_expression",
        {"expr_ast": {"op": "frobnicate", "args": [{"int": 1}]}},
    )
    assert result.ok is False
    assert result.error_code == "INVALID_AST"
