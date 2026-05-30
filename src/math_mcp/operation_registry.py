"""Single source of truth for every operation the server exposes.

Nothing else (server routing, capabilities, tests, docs) is allowed to keep a second
copy of this list. ``math_capabilities`` is generated from here; tests assert that the
server's handler tables and the documentation agree with it.

Adding an operation means adding an :class:`OperationSpec` here *first*; the handler is
wired up afterwards. New operations default to ``state="experimental"`` so a forgotten
state field can never accidentally advertise an unverified capability.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

from math_mcp.schemas import Limits
from math_mcp.status import Certainty

# ---------------------------------------------------------------------------
# JSON-Schema-style payload fragment helpers (a small, deliberate subset).
# ---------------------------------------------------------------------------


def _str(max_len: int = 5000) -> dict[str, Any]:
    return {"type": "string", "maxLength": max_len}


def _str_array(max_items: int = 20, max_len: int = 5000) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "maxLength": max_len},
        "maxItems": max_items,
    }


def _int(minimum: int | None = None, maximum: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "integer"}
    if minimum is not None:
        out["minimum"] = minimum
    if maximum is not None:
        out["maximum"] = maximum
    return out


def _enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


def _matrix(max_rows: int = 50, max_cols: int = 50) -> dict[str, Any]:
    return {
        "type": "array",
        "maxItems": max_rows,
        "items": {"type": "array", "maxItems": max_cols, "items": {"type": "string"}},
    }


def _obj(
    required: Sequence[str],
    properties: dict[str, Any],
    *,
    additional: bool = False,
) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": additional,
    }


# ---------------------------------------------------------------------------
# Registry models
# ---------------------------------------------------------------------------

State = Literal["implemented", "experimental", "disabled", "deprecated"]


class ReplacementSpec(BaseModel):
    public_tool: str
    operation: str


class OperationSpec(BaseModel):
    public_tool: str
    operation: str
    operation_version: str = "1.0"
    state: State = "experimental"
    backend: str
    risk: Literal["low", "medium", "high"]
    complexity_class: Literal[
        "constant",
        "linear",
        "polynomial",
        "exponential",
        "solver_dependent",
    ]
    runs_in_subprocess: bool
    proof_modes: list[
        Literal["symbolic", "smt", "finite_exhaustive", "interval", "counterexample"]
    ] = Field(default_factory=list)
    max_certainty: Certainty
    numeric_only: bool
    result_kinds: list[
        Literal["value", "solution_set", "witness", "verification", "object", "none"]
    ]
    determinism: Literal["deterministic", "seeded_random", "nondeterministic"]
    accepted_input_forms: list[str]
    payload_schema: dict[str, Any]
    default_limits: Limits = Field(default_factory=Limits)
    example_payload: dict[str, Any]
    deprecated: bool = False
    replacement: ReplacementSpec | None = None
    disabled_reason: str | None = None

    @property
    def proof_capable(self) -> bool:
        """Compatibility summary derived from ``proof_modes`` — never hand-written."""
        return bool(self.proof_modes)


# Default reporting method per operation, keyed by (public_tool, operation). This is
# a handler hint (which Method to report on success), not part of the wire schema, so
# it is kept beside the registry rather than on OperationSpec.
_METHOD_HINTS: dict[tuple[str, str], str] = {}


def _op(**fields: Any) -> OperationSpec:
    """Build an :class:`OperationSpec` from a plain dict with broad defaults.

    Using ``model_validate`` keeps the call sites free of ``Literal`` typing noise
    while still validating every field at import time. A ``method_hint`` keyword is
    accepted and stored in :data:`_METHOD_HINTS` rather than on the spec.
    """
    data: dict[str, Any] = {
        "backend": "sympy",
        "risk": "medium",
        "complexity_class": "solver_dependent",
        "runs_in_subprocess": False,
        "proof_modes": [],
        "max_certainty": "exact",
        "numeric_only": False,
        "result_kinds": ["value"],
        "determinism": "deterministic",
        "accepted_input_forms": ["expression_string", "expr_ast"],
        "state": "implemented",
    }
    data.update(fields)
    method_hint = data.pop("method_hint", None)
    spec = OperationSpec.model_validate(data)
    if method_hint is not None:
        _METHOD_HINTS[(spec.public_tool, spec.operation)] = str(method_hint)
    return spec


# Common payload schemas reused across symbolic operations.
_EXPR = _obj(
    ["expression"],
    {
        "expression": _str(5000),
        "variables": _str_array(20),
        "expr_ast": {"type": "object"},
    },
)
_IDENTITY = _obj(
    ["left", "right"],
    {
        "left": _str(5000),
        "right": _str(5000),
        "variables": _str_array(20),
        "sample_points": _int(0, 10000),
        "expr_ast_left": {"type": "object"},
        "expr_ast_right": {"type": "object"},
    },
)
_INEQ = _obj(
    ["left", "relation", "right", "variables"],
    {
        "left": _str(5000),
        "right": _str(5000),
        "relation": _enum("==", "!=", "<", "<=", ">", ">="),
        "variables": _str_array(20),
        "samples": _int(1, 100000),
        "expr_ast_left": {"type": "object"},
        "expr_ast_right": {"type": "object"},
    },
)


def _build_specs() -> list[OperationSpec]:  # noqa: C901 - a flat declarative table
    specs: list[OperationSpec] = []

    # ----- algebra_compute -------------------------------------------------
    for name in (
        "simplify_expression",
        "expand_expression",
        "factor_expression",
        "cancel_expression",
        "together_expression",
    ):
        specs.append(
            _op(
                public_tool="algebra_compute",
                operation=name,
                payload_schema=_EXPR,
                example_payload={"expression": "sin(x)**2 + cos(x)**2 - 1", "variables": ["x"]},
            )
        )
    specs.append(
        _op(
            public_tool="algebra_compute",
            operation="solve_equation",
            risk="high",
            runs_in_subprocess=True,
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["expression", "variable"],
                {
                    "expression": _str(5000),
                    "variable": _str(64),
                    "right": _str(5000),
                    "expr_ast": {"type": "object"},
                },
            ),
            example_payload={"expression": "x**2 - 5*x + 6", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="algebra_compute",
            operation="solve_system",
            risk="high",
            runs_in_subprocess=True,
            result_kinds=["solution_set"],
            complexity_class="solver_dependent",
            payload_schema=_obj(
                ["equations", "variables"],
                {"equations": _str_array(40), "variables": _str_array(20)},
            ),
            example_payload={"equations": ["x + y - 3", "x - y - 1"], "variables": ["x", "y"]},
        )
    )
    specs.append(
        _op(
            public_tool="algebra_compute",
            operation="polynomial_roots",
            runs_in_subprocess=True,
            risk="high",
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["expression", "variable"],
                {"expression": _str(5000), "variable": _str(64), "expr_ast": {"type": "object"}},
            ),
            example_payload={"expression": "x**2 - 5*x + 6", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="algebra_compute",
            operation="groebner_basis",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            complexity_class="exponential",
            result_kinds=["object"],
            payload_schema=_obj(
                ["polynomials", "variables"],
                {
                    "polynomials": _str_array(40),
                    "variables": _str_array(20),
                    "order": _enum("lex", "grlex", "grevlex"),
                },
            ),
            example_payload={"polynomials": ["x**2 + y**2 - 1", "x - y"], "variables": ["x", "y"]},
        )
    )

    # ----- calculus_compute ------------------------------------------------
    specs.append(
        _op(
            public_tool="calculus_compute",
            operation="differentiate",
            payload_schema=_obj(
                ["expression", "variable"],
                {
                    "expression": _str(5000),
                    "variable": _str(64),
                    "order": _int(1, 20),
                    "expr_ast": {"type": "object"},
                },
            ),
            example_payload={"expression": "sin(x)*x**2", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="calculus_compute",
            operation="integrate",
            risk="high",
            runs_in_subprocess=True,
            result_kinds=["value", "solution_set"],
            default_limits=Limits(timeout_ms=10000, cpu_time_ms=10000),
            payload_schema=_obj(
                ["expression", "variable"],
                {
                    "expression": _str(5000),
                    "variable": _str(64),
                    "lower": _str(2000),
                    "upper": _str(2000),
                    "expr_ast": {"type": "object"},
                },
            ),
            example_payload={"expression": "2*x", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="calculus_compute",
            operation="limit_expression",
            risk="high",
            runs_in_subprocess=True,
            payload_schema=_obj(
                ["expression", "variable", "point"],
                {
                    "expression": _str(5000),
                    "variable": _str(64),
                    "point": _str(2000),
                    "direction": _enum("+", "-", "+-"),
                    "expr_ast": {"type": "object"},
                },
            ),
            example_payload={"expression": "sin(x)/x", "variable": "x", "point": "0"},
        )
    )
    specs.append(
        _op(
            public_tool="calculus_compute",
            operation="series_expand",
            result_kinds=["value", "object"],
            payload_schema=_obj(
                ["expression", "variable", "order"],
                {
                    "expression": _str(5000),
                    "variable": _str(64),
                    "point": _str(2000),
                    "order": _int(0, 30),
                    "expr_ast": {"type": "object"},
                },
            ),
            example_payload={"expression": "exp(x)", "variable": "x", "point": "0", "order": 5},
        )
    )
    specs.append(
        _op(
            public_tool="calculus_compute",
            operation="numeric_evaluate",
            backend="mpmath",
            numeric_only=True,
            complexity_class="polynomial",
            max_certainty="exact",
            accepted_input_forms=["expression_string", "expr_ast"],
            payload_schema=_obj(
                ["expression"],
                {
                    "expression": _str(5000),
                    "precision_digits": _int(15, 200),
                    "expr_ast": {"type": "object"},
                },
            ),
            example_payload={"expression": "pi*E", "precision_digits": 30},
        )
    )
    specs.append(
        _op(
            public_tool="calculus_compute",
            operation="numeric_optimize",
            backend="scipy",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            numeric_only=True,
            max_certainty="evidence",
            method_hint="numeric_optimization",
            result_kinds=["value", "witness"],
            determinism="seeded_random",
            complexity_class="solver_dependent",
            payload_schema=_obj(
                ["expression", "variables"],
                {
                    "expression": _str(5000),
                    "variables": _str_array(20),
                    "goal": _enum("min", "max"),
                    "start": _str_array(20),
                },
            ),
            example_payload={"expression": "(x-3)**2 + 2", "variables": ["x"], "goal": "min"},
        )
    )

    # ----- verification_compute -------------------------------------------
    specs.append(
        _op(
            public_tool="verification_compute",
            operation="check_identity",
            proof_modes=["symbolic", "counterexample"],
            max_certainty="proved",
            result_kinds=["verification"],
            complexity_class="solver_dependent",
            payload_schema=_IDENTITY,
            example_payload={"left": "sin(x)**2 + cos(x)**2", "right": "1", "variables": ["x"]},
        )
    )
    specs.append(
        _op(
            public_tool="verification_compute",
            operation="check_inequality_sampled",
            backend="mpmath",
            proof_modes=["counterexample"],
            max_certainty="disproved",
            determinism="seeded_random",
            method_hint="numeric_sampling",
            result_kinds=["verification", "witness"],
            runs_in_subprocess=True,
            payload_schema=_INEQ,
            example_payload={
                "left": "x**2 + 1",
                "relation": ">",
                "right": "0",
                "variables": ["x"],
                "samples": 200,
            },
        )
    )
    specs.append(
        _op(
            public_tool="verification_compute",
            operation="search_counterexample",
            backend="mpmath",
            proof_modes=["counterexample"],
            max_certainty="disproved",
            determinism="seeded_random",
            method_hint="counterexample",
            runs_in_subprocess=True,
            result_kinds=["witness", "verification"],
            payload_schema=_INEQ,
            example_payload={
                "left": "x",
                "relation": ">=",
                "right": "x**2",
                "variables": ["x"],
                "samples": 500,
            },
        )
    )

    # ----- z3_compute ------------------------------------------------------
    _Z3_VARS = {"type": "object", "additionalProperties": {"type": "string"}}
    specs.append(
        _op(
            public_tool="z3_compute",
            operation="z3_satisfiability",
            backend="z3",
            proof_modes=["smt"],
            max_certainty="proved",
            runs_in_subprocess=True,
            accepted_input_forms=["z3_ast"],
            result_kinds=["witness", "verification"],
            complexity_class="solver_dependent",
            payload_schema=_obj(
                ["variables", "constraints"],
                {
                    "variables": _Z3_VARS,
                    "constraints": {"type": "array", "items": {"type": "object"}},
                },
            ),
            example_payload={
                "variables": {"x": "Int", "y": "Int"},
                "constraints": [
                    {"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
                    {"op": "gt", "left": {"var": "y"}, "right": {"int": 0}},
                    {
                        "op": "eq",
                        "left": {"op": "add", "args": [{"var": "x"}, {"var": "y"}]},
                        "right": {"int": 10},
                    },
                    {"op": "gt", "left": {"var": "x"}, "right": {"var": "y"}},
                ],
            },
        )
    )
    specs.append(
        _op(
            public_tool="z3_compute",
            operation="z3_find_counterexample",
            backend="z3",
            proof_modes=["smt", "counterexample"],
            max_certainty="proved",
            runs_in_subprocess=True,
            accepted_input_forms=["z3_ast"],
            result_kinds=["witness", "verification"],
            complexity_class="solver_dependent",
            payload_schema=_obj(
                ["variables", "claim"],
                {
                    "variables": _Z3_VARS,
                    "assumptions": {"type": "array", "items": {"type": "object"}},
                    "claim": {"type": "object"},
                },
            ),
            example_payload={
                "variables": {"x": "Int"},
                "assumptions": [{"op": "ge", "left": {"var": "x"}, "right": {"int": 0}}],
                "claim": {
                    "op": "ge",
                    "left": {"op": "mul", "args": [{"var": "x"}, {"var": "x"}]},
                    "right": {"var": "x"},
                },
            },
        )
    )

    # ----- matrix_compute --------------------------------------------------
    for name, rk in (
        ("det", "value"),
        ("rank", "value"),
        ("trace", "value"),
        ("transpose", "object"),
        ("inverse", "object"),
        ("rref", "object"),
        ("eigenvals", "object"),
        ("charpoly", "value"),
    ):
        specs.append(
            _op(
                public_tool="matrix_compute",
                operation=name,
                complexity_class="polynomial",
                accepted_input_forms=["matrix"],
                result_kinds=[rk],
                payload_schema=_obj(["matrix"], {"matrix": _matrix()}),
                example_payload={"matrix": [["1", "2"], ["3", "4"]]},
            )
        )
    specs.append(
        _op(
            public_tool="matrix_compute",
            operation="solve_linear_system",
            runs_in_subprocess=True,
            risk="high",
            complexity_class="polynomial",
            accepted_input_forms=["matrix"],
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["matrix", "rhs"],
                {"matrix": _matrix(), "rhs": _str_array(50)},
            ),
            example_payload={"matrix": [["1", "1"], ["1", "-1"]], "rhs": ["3", "1"]},
        )
    )
    specs.append(
        _op(
            public_tool="matrix_compute",
            operation="matrix_decomposition_numeric",
            backend="numpy",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            numeric_only=True,
            complexity_class="polynomial",
            accepted_input_forms=["matrix"],
            result_kinds=["object"],
            max_certainty="exact",
            payload_schema=_obj(
                ["matrix", "kind"],
                {"matrix": _matrix(), "kind": _enum("lu", "qr", "svd", "eig")},
            ),
            example_payload={"matrix": [["1", "2"], ["3", "4"]], "kind": "svd"},
        )
    )

    # ----- discrete_compute ------------------------------------------------
    specs.append(
        _op(
            public_tool="discrete_compute",
            operation="combinatorics_count",
            backend="python",
            complexity_class="polynomial",
            accepted_input_forms=["finite_set"],
            payload_schema=_obj(
                ["kind"],
                {
                    "kind": _enum(
                        "permutation",
                        "combination",
                        "binomial",
                        "multinomial",
                        "factorial",
                        "catalan",
                        "derangement",
                        "stirling2",
                        "partition",
                    ),
                    "n": _str(64),
                    "k": _str(64),
                    "groups": _str_array(40),
                },
            ),
            example_payload={"kind": "combination", "n": "10", "k": "3"},
        )
    )
    specs.append(
        _op(
            public_tool="discrete_compute",
            operation="finite_enumeration",
            backend="python",
            runs_in_subprocess=True,
            proof_modes=["finite_exhaustive"],
            max_certainty="proved",
            complexity_class="exponential",
            accepted_input_forms=["expression_string", "expr_ast"],
            result_kinds=["verification", "witness"],
            payload_schema=_obj(
                ["predicate", "variables"],
                {
                    "predicate": _str(5000),
                    "variables": _str_array(10),
                    "collect_witnesses": {"type": "boolean"},
                },
            ),
            example_payload={"predicate": "Eq(x + y, 3)", "variables": ["x", "y"]},
        )
    )
    specs.append(
        _op(
            public_tool="discrete_compute",
            operation="solve_recurrence",
            state="implemented",
            risk="high",
            runs_in_subprocess=True,
            accepted_input_forms=["expression_string"],
            result_kinds=["value"],
            payload_schema=_obj(
                ["recurrence", "function", "variable"],
                {
                    "recurrence": _str(5000),
                    "function": _str(64),
                    "variable": _str(64),
                    "initial_conditions": {"type": "object"},
                },
            ),
            example_payload={
                "recurrence": "f(n) - f(n-1) - f(n-2)",
                "function": "f",
                "variable": "n",
                "initial_conditions": {"0": "0", "1": "1"},
            },
        )
    )

    # ----- graph_compute ---------------------------------------------------
    _GRAPH_PROPS = {
        "directed": {"type": "boolean"},
        "nodes": _str_array(10000),
        "edges": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
    }
    for name, rk in (
        ("is_connected", "verification"),
        ("connected_components", "object"),
        ("has_cycle", "verification"),
        ("maximum_matching", "object"),
        ("minimum_spanning_tree", "object"),
    ):
        specs.append(
            _op(
                public_tool="graph_compute",
                operation=name,
                backend="networkx",
                complexity_class="polynomial",
                accepted_input_forms=["graph"],
                result_kinds=[rk],
                payload_schema=_obj(["nodes", "edges"], dict(_GRAPH_PROPS)),
                example_payload={
                    "directed": False,
                    "nodes": ["A", "B", "C"],
                    "edges": [["A", "B"], ["B", "C"]],
                },
            )
        )
    specs.append(
        _op(
            public_tool="graph_compute",
            operation="topological_sort",
            backend="networkx",
            complexity_class="polynomial",
            accepted_input_forms=["graph"],
            result_kinds=["object"],
            payload_schema=_obj(["nodes", "edges"], dict(_GRAPH_PROPS)),
            example_payload={
                "directed": True,
                "nodes": ["A", "B", "C"],
                "edges": [["A", "B"], ["B", "C"]],
            },
        )
    )
    specs.append(
        _op(
            public_tool="graph_compute",
            operation="shortest_path",
            backend="networkx",
            complexity_class="polynomial",
            accepted_input_forms=["graph"],
            result_kinds=["object", "solution_set"],
            payload_schema=_obj(
                ["nodes", "edges", "source", "target"],
                {**_GRAPH_PROPS, "source": _str(256), "target": _str(256)},
            ),
            example_payload={
                "directed": False,
                "nodes": ["A", "B", "C"],
                "edges": [["A", "B"], ["B", "C"]],
                "source": "A",
                "target": "C",
            },
        )
    )

    # ----- probability_compute --------------------------------------------
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="event_probability",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["value", "verification"],
            accepted_input_forms=["expression_string", "finite_set"],
            payload_schema=_obj(
                ["mode"],
                {
                    "mode": _enum(
                        "ratio",
                        "conditional",
                        "union",
                        "complement",
                        "independence",
                        "uniform_finite",
                    ),
                    "favorable": _str(64),
                    "total": _str(64),
                    "p_a": _str(64),
                    "p_b": _str(64),
                    "p_a_and_b": _str(64),
                    "condition": _str(5000),
                    "variables": _str_array(10),
                },
            ),
            example_payload={"mode": "ratio", "favorable": "3", "total": "4"},
        )
    )
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="bayes_update",
            backend="sympy",
            complexity_class="constant",
            payload_schema=_obj(
                ["prior", "likelihood"],
                {
                    "prior": _str(64),
                    "likelihood": _str(64),
                    "false_likelihood": _str(64),
                    "evidence": _str(64),
                },
            ),
            example_payload={"prior": "1/100", "likelihood": "9/10", "false_likelihood": "1/10"},
        )
    )
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="distribution_moments",
            backend="sympy",
            state="experimental",
            complexity_class="polynomial",
            payload_schema=_obj(
                ["distribution", "moment"],
                {
                    "distribution": _enum(
                        "bernoulli",
                        "binomial",
                        "poisson",
                        "geometric",
                        "uniform",
                        "normal",
                        "exponential",
                    ),
                    "params": {"type": "object"},
                    "moment": _enum("mean", "variance", "std", "skewness"),
                },
            ),
            example_payload={
                "distribution": "binomial",
                "params": {"n": "10", "p": "1/2"},
                "moment": "mean",
            },
        )
    )
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="probability_distribution",
            backend="sympy",
            state="experimental",
            complexity_class="polynomial",
            payload_schema=_obj(
                ["distribution", "query"],
                {
                    "distribution": _enum(
                        "bernoulli",
                        "binomial",
                        "poisson",
                        "geometric",
                        "uniform",
                        "normal",
                        "exponential",
                    ),
                    "params": {"type": "object"},
                    "query": _enum("pmf", "pdf", "cdf"),
                    "at": _str(64),
                },
            ),
            example_payload={
                "distribution": "binomial",
                "params": {"n": "10", "p": "1/2"},
                "query": "pmf",
                "at": "5",
            },
        )
    )
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="random_variable_transform",
            backend="sympy",
            state="experimental",
            complexity_class="solver_dependent",
            payload_schema=_obj(
                ["expression", "variable"],
                {"expression": _str(5000), "variable": _str(64), "transform": _str(5000)},
            ),
            example_payload={"expression": "2*X + 1", "variable": "X", "transform": "mean"},
        )
    )
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="markov_chain_analyze",
            backend="numpy",
            state="experimental",
            numeric_only=True,
            complexity_class="polynomial",
            result_kinds=["object"],
            max_certainty="exact",
            payload_schema=_obj(
                ["transition_matrix"],
                {
                    "transition_matrix": _matrix(),
                    "query": _enum("stationary", "n_step"),
                    "steps": _int(1, 10000),
                },
            ),
            example_payload={
                "transition_matrix": [["1/2", "1/2"], ["1/3", "2/3"]],
                "query": "stationary",
            },
        )
    )
    specs.append(
        _op(
            public_tool="probability_compute",
            operation="probability_simulation",
            backend="numpy",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            numeric_only=True,
            determinism="seeded_random",
            method_hint="simulation",
            max_certainty="evidence",
            complexity_class="linear",
            result_kinds=["value", "verification"],
            payload_schema=_obj(
                ["experiment", "trials"],
                {
                    "experiment": _enum("coin", "dice", "bernoulli"),
                    "trials": _int(1, 100000),
                    "p": _str(64),
                    "sides": _int(2, 1000),
                    "target": _str(64),
                },
            ),
            example_payload={"experiment": "coin", "trials": 10000, "target": "1"},
        )
    )

    # ----- set_compute -----------------------------------------------------
    specs.append(
        _op(
            public_tool="set_compute",
            operation="set_operations",
            backend="python",
            complexity_class="linear",
            accepted_input_forms=["finite_set"],
            result_kinds=["object"],
            payload_schema=_obj(
                ["kind", "a"],
                {
                    "kind": _enum(
                        "union", "intersection", "difference", "symmetric_difference", "complement"
                    ),
                    "a": _str_array(1000),
                    "b": _str_array(1000),
                    "universe": _str_array(2000),
                },
            ),
            example_payload={"kind": "union", "a": ["1", "2"], "b": ["2", "3"]},
        )
    )
    specs.append(
        _op(
            public_tool="set_compute",
            operation="set_membership",
            backend="python",
            complexity_class="linear",
            accepted_input_forms=["finite_set"],
            result_kinds=["verification"],
            payload_schema=_obj(
                ["element", "set"], {"element": _str(256), "set": _str_array(2000)}
            ),
            example_payload={"element": "2", "set": ["1", "2", "3"]},
        )
    )
    specs.append(
        _op(
            public_tool="set_compute",
            operation="set_relation_check",
            backend="python",
            complexity_class="linear",
            accepted_input_forms=["finite_set"],
            proof_modes=["finite_exhaustive"],
            max_certainty="proved",
            result_kinds=["verification"],
            payload_schema=_obj(
                ["a", "b", "relation"],
                {
                    "a": _str_array(2000),
                    "b": _str_array(2000),
                    "relation": _enum("subset", "proper_subset", "equal", "disjoint"),
                },
            ),
            example_payload={"a": ["1", "2"], "b": ["1", "2", "3"], "relation": "subset"},
        )
    )
    specs.append(
        _op(
            public_tool="set_compute",
            operation="set_identity_check",
            backend="sympy",
            proof_modes=["symbolic", "finite_exhaustive"],
            max_certainty="proved",
            complexity_class="exponential",
            result_kinds=["verification"],
            payload_schema=_obj(
                ["left", "right", "variables"],
                {"left": _str(5000), "right": _str(5000), "variables": _str_array(10)},
            ),
            example_payload={
                "left": "A & (B | C)",
                "right": "(A & B) | (A & C)",
                "variables": ["A", "B", "C"],
            },
        )
    )
    specs.append(
        _op(
            public_tool="set_compute",
            operation="cartesian_product",
            backend="python",
            complexity_class="exponential",
            accepted_input_forms=["finite_set"],
            result_kinds=["object"],
            payload_schema=_obj(
                ["sets"], {"sets": {"type": "array", "maxItems": 6, "items": _str_array(100)}}
            ),
            example_payload={"sets": [["1", "2"], ["a", "b"]]},
        )
    )
    specs.append(
        _op(
            public_tool="set_compute",
            operation="power_set",
            backend="python",
            runs_in_subprocess=True,
            complexity_class="exponential",
            accepted_input_forms=["finite_set"],
            result_kinds=["object"],
            payload_schema=_obj(["set"], {"set": _str_array(16)}),
            example_payload={"set": ["1", "2", "3"]},
        )
    )
    specs.append(
        _op(
            public_tool="set_compute",
            operation="interval_compute",
            backend="sympy",
            complexity_class="polynomial",
            accepted_input_forms=["expression_string"],
            result_kinds=["object", "solution_set"],
            payload_schema=_obj(
                ["kind", "a"],
                {
                    "kind": _enum("union", "intersection", "difference", "complement"),
                    "a": {"type": "object"},
                    "b": {"type": "object"},
                },
            ),
            example_payload={
                "kind": "intersection",
                "a": {"lower": "0", "upper": "2", "lower_closed": True, "upper_closed": True},
                "b": {"lower": "1", "upper": "3", "lower_closed": False, "upper_closed": True},
            },
        )
    )

    # ----- geometry_compute -----------------------------------------------
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="geometry_distance",
            backend="sympy",
            complexity_class="constant",
            payload_schema=_obj(
                ["kind"],
                {
                    "kind": _enum("point_point", "point_line", "point_circle"),
                    "point": _str_array(3),
                    "point2": _str_array(3),
                    "line": {"type": "object"},
                    "circle": {"type": "object"},
                },
            ),
            example_payload={
                "kind": "point_line",
                "point": ["1", "2"],
                "line": {"a": "3", "b": "4", "c": "-5"},
            },
        )
    )
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="geometry_intersection",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["solution_set", "object"],
            payload_schema=_obj(
                ["object1", "object2"],
                {"object1": {"type": "object"}, "object2": {"type": "object"}},
            ),
            example_payload={
                "object1": {"type": "line", "a": "1", "b": "-1", "c": "0"},
                "object2": {"type": "line", "a": "1", "b": "1", "c": "-2"},
            },
        )
    )
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="line_analyze",
            backend="sympy",
            complexity_class="constant",
            result_kinds=["object"],
            payload_schema=_obj(
                ["line1"],
                {"line1": {"type": "object"}, "line2": {"type": "object"}},
            ),
            example_payload={"line1": {"a": "3", "b": "4", "c": "-5"}},
        )
    )
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="circle_analyze",
            backend="sympy",
            complexity_class="constant",
            result_kinds=["object"],
            payload_schema=_obj(["circle"], {"circle": {"type": "object"}}),
            example_payload={"circle": {"center": ["0", "0"], "radius": "5"}},
        )
    )
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="polygon_analyze",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(
                ["vertices"],
                {"vertices": {"type": "array", "maxItems": 200, "items": _str_array(3)}},
            ),
            example_payload={"vertices": [["0", "0"], ["4", "0"], ["4", "3"], ["0", "3"]]},
        )
    )
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="coordinate_transform",
            backend="sympy",
            complexity_class="constant",
            result_kinds=["value", "object"],
            payload_schema=_obj(
                ["kind", "point"],
                {
                    "kind": _enum("translate", "rotate", "to_polar", "to_cartesian"),
                    "point": _str_array(3),
                    "dx": _str(64),
                    "dy": _str(64),
                    "angle": _str(64),
                },
            ),
            example_payload={"kind": "to_polar", "point": ["1", "1"]},
        )
    )
    specs.append(
        _op(
            public_tool="geometry_compute",
            operation="conic_analyze",
            backend="sympy",
            state="experimental",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(
                ["expression", "variables"], {"expression": _str(5000), "variables": _str_array(2)}
            ),
            example_payload={"expression": "x**2/4 + y**2/9 - 1", "variables": ["x", "y"]},
        )
    )

    # ----- trigonometry_compute -------------------------------------------
    for name in ("trig_simplify", "trig_expand", "trig_reduce"):
        specs.append(
            _op(
                public_tool="trigonometry_compute",
                operation=name,
                payload_schema=_EXPR,
                example_payload={"expression": "sin(x)**2 + cos(x)**2", "variables": ["x"]},
            )
        )
    specs.append(
        _op(
            public_tool="trigonometry_compute",
            operation="trig_rewrite",
            payload_schema=_obj(
                ["expression", "target"],
                {
                    "expression": _str(5000),
                    "variables": _str_array(20),
                    "target": _enum("sin", "cos", "tan", "exp"),
                },
            ),
            example_payload={"expression": "tan(x)", "target": "sin"},
        )
    )
    specs.append(
        _op(
            public_tool="trigonometry_compute",
            operation="solve_trig_equation",
            risk="high",
            runs_in_subprocess=True,
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["expression", "variable"],
                {"expression": _str(5000), "variable": _str(64), "right": _str(5000)},
            ),
            example_payload={"expression": "sin(x)", "variable": "x", "right": "0"},
        )
    )
    specs.append(
        _op(
            public_tool="trigonometry_compute",
            operation="trig_identity_check",
            proof_modes=["symbolic", "counterexample"],
            max_certainty="proved",
            result_kinds=["verification"],
            payload_schema=_IDENTITY,
            example_payload={"left": "sin(2*x)", "right": "2*sin(x)*cos(x)", "variables": ["x"]},
        )
    )

    # ----- number_theory_compute ------------------------------------------
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="gcd_lcm_bezout",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(["a", "b"], {"a": _str(128), "b": _str(128)}),
            example_payload={"a": "12", "b": "18"},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="prime_analyze",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["value", "object"],
            payload_schema=_obj(
                ["n"],
                {
                    "n": _str(128),
                    "query": _enum("is_prime", "next_prime", "prev_prime", "factorize"),
                },
            ),
            example_payload={"n": "97", "query": "is_prime"},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="modular_arithmetic",
            backend="sympy",
            complexity_class="polynomial",
            payload_schema=_obj(
                ["kind", "modulus"],
                {
                    "kind": _enum("pow", "inverse", "solve_linear"),
                    "a": _str(128),
                    "b": _str(128),
                    "exponent": _str(128),
                    "modulus": _str(128),
                },
            ),
            example_payload={"kind": "inverse", "a": "17", "modulus": "43"},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="congruence_solve",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["a", "b", "modulus"],
                {"a": _str(128), "b": _str(128), "modulus": _str(128)},
            ),
            example_payload={"a": "3", "b": "2", "modulus": "7"},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="chinese_remainder",
            backend="sympy",
            complexity_class="polynomial",
            payload_schema=_obj(
                ["remainders", "moduli"],
                {"remainders": _str_array(50), "moduli": _str_array(50)},
            ),
            example_payload={"remainders": ["2", "3", "2"], "moduli": ["3", "5", "7"]},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="totient_compute",
            backend="sympy",
            complexity_class="polynomial",
            payload_schema=_obj(["n"], {"n": _str(128), "kind": _enum("euler", "carmichael")}),
            example_payload={"n": "36", "kind": "euler"},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="multiplicative_order",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["value", "verification"],
            payload_schema=_obj(
                ["a", "n"],
                {"a": _str(128), "n": _str(128), "check_primitive_root": {"type": "boolean"}},
            ),
            example_payload={"a": "3", "n": "7"},
        )
    )
    specs.append(
        _op(
            public_tool="number_theory_compute",
            operation="quadratic_residue_check",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["value", "verification"],
            payload_schema=_obj(
                ["a", "p"],
                {"a": _str(128), "p": _str(128), "kind": _enum("is_qr", "legendre", "jacobi")},
            ),
            example_payload={"a": "2", "p": "7", "kind": "legendre"},
        )
    )

    # ----- logic_compute ---------------------------------------------------
    specs.append(
        _op(
            public_tool="logic_compute",
            operation="boolean_simplify",
            backend="sympy",
            complexity_class="exponential",
            payload_schema=_obj(
                ["expression"], {"expression": _str(5000), "variables": _str_array(12)}
            ),
            example_payload={"expression": "(p & q) | (p & ~q)", "variables": ["p", "q"]},
        )
    )
    specs.append(
        _op(
            public_tool="logic_compute",
            operation="truth_table",
            backend="sympy",
            runs_in_subprocess=True,
            complexity_class="exponential",
            proof_modes=["finite_exhaustive"],
            max_certainty="proved",
            result_kinds=["object"],
            payload_schema=_obj(
                ["expression", "variables"], {"expression": _str(5000), "variables": _str_array(10)}
            ),
            example_payload={"expression": "p >> q", "variables": ["p", "q"]},
        )
    )
    specs.append(
        _op(
            public_tool="logic_compute",
            operation="logic_equivalence_check",
            backend="sympy",
            proof_modes=["symbolic", "finite_exhaustive"],
            max_certainty="proved",
            complexity_class="exponential",
            result_kinds=["verification"],
            payload_schema=_obj(
                ["left", "right", "variables"],
                {"left": _str(5000), "right": _str(5000), "variables": _str_array(12)},
            ),
            example_payload={"left": "p >> q", "right": "~p | q", "variables": ["p", "q"]},
        )
    )
    specs.append(
        _op(
            public_tool="logic_compute",
            operation="logic_satisfiability",
            backend="sympy",
            proof_modes=["finite_exhaustive"],
            max_certainty="proved",
            complexity_class="exponential",
            result_kinds=["witness", "verification"],
            runs_in_subprocess=True,
            payload_schema=_obj(
                ["expression", "variables"], {"expression": _str(5000), "variables": _str_array(12)}
            ),
            example_payload={"expression": "p & ~p", "variables": ["p"]},
        )
    )
    specs.append(
        _op(
            public_tool="logic_compute",
            operation="normal_form_convert",
            backend="sympy",
            complexity_class="exponential",
            payload_schema=_obj(
                ["expression", "form", "variables"],
                {
                    "expression": _str(5000),
                    "form": _enum("cnf", "dnf", "nnf"),
                    "variables": _str_array(12),
                },
            ),
            example_payload={"expression": "p >> q", "form": "cnf", "variables": ["p", "q"]},
        )
    )
    specs.append(
        _op(
            public_tool="logic_compute",
            operation="finite_quantifier_check",
            backend="python",
            runs_in_subprocess=True,
            proof_modes=["finite_exhaustive"],
            max_certainty="proved",
            complexity_class="exponential",
            result_kinds=["verification", "witness"],
            payload_schema=_obj(
                ["quantifier", "predicate", "variables"],
                {
                    "quantifier": _enum("forall", "exists"),
                    "predicate": _str(5000),
                    "variables": _str_array(8),
                },
            ),
            example_payload={"quantifier": "forall", "predicate": "x**2 >= 0", "variables": ["x"]},
        )
    )

    # ----- ode_compute -----------------------------------------------------
    specs.append(
        _op(
            public_tool="ode_compute",
            operation="ode_verify_solution",
            backend="sympy",
            proof_modes=["symbolic"],
            max_certainty="proved",
            complexity_class="solver_dependent",
            result_kinds=["verification"],
            payload_schema=_obj(
                ["solution", "variable", "residual"],
                {
                    "solution": _str(5000),
                    "variable": _str(64),
                    "residual": _str(5000),
                    "parameters": _str_array(10),
                },
            ),
            example_payload={
                "solution": "C*exp(x)",
                "variable": "x",
                "residual": "dy - y",
                "parameters": ["C"],
            },
        )
    )
    specs.append(
        _op(
            public_tool="ode_compute",
            operation="ode_solve_symbolic",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["equation", "function", "variable"],
                {"equation": _str(5000), "function": _str(64), "variable": _str(64)},
            ),
            example_payload={"equation": "dy - y", "function": "y", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="ode_compute",
            operation="ode_classify",
            state="experimental",
            runs_in_subprocess=True,
            result_kinds=["object"],
            payload_schema=_obj(
                ["equation", "function", "variable"],
                {"equation": _str(5000), "function": _str(64), "variable": _str(64)},
            ),
            example_payload={"equation": "dy - y", "function": "y", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="ode_compute",
            operation="ode_initial_value_solve",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            result_kinds=["value", "solution_set"],
            payload_schema=_obj(
                ["equation", "function", "variable", "initial_conditions"],
                {
                    "equation": _str(5000),
                    "function": _str(64),
                    "variable": _str(64),
                    "initial_conditions": {"type": "object"},
                },
            ),
            example_payload={
                "equation": "dy - y",
                "function": "y",
                "variable": "x",
                "initial_conditions": {"0": "1"},
            },
        )
    )
    specs.append(
        _op(
            public_tool="ode_compute",
            operation="ode_solve_numeric",
            backend="scipy",
            state="experimental",
            risk="high",
            runs_in_subprocess=True,
            numeric_only=True,
            determinism="deterministic",
            method_hint="numeric_sampling",
            max_certainty="evidence",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(
                ["expression", "variable", "function", "t_span", "y0"],
                {
                    "expression": _str(5000),
                    "variable": _str(64),
                    "function": _str(64),
                    "t_span": _str_array(2),
                    "y0": _str_array(20),
                    "points": _int(2, 10000),
                },
            ),
            example_payload={
                "expression": "y",
                "variable": "t",
                "function": "y",
                "t_span": ["0", "1"],
                "y0": ["1"],
            },
        )
    )

    # ----- complex_compute -------------------------------------------------
    specs.append(
        _op(
            public_tool="complex_compute",
            operation="complex_simplify",
            backend="sympy",
            payload_schema=_EXPR,
            example_payload={"expression": "(1 + I)*(1 - I)", "variables": []},
        )
    )
    specs.append(
        _op(
            public_tool="complex_compute",
            operation="complex_mod_arg",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(["expression"], {"expression": _str(5000)}),
            example_payload={"expression": "1 + I"},
        )
    )
    specs.append(
        _op(
            public_tool="complex_compute",
            operation="complex_to_polar",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(["expression"], {"expression": _str(5000)}),
            example_payload={"expression": "1 + I"},
        )
    )
    specs.append(
        _op(
            public_tool="complex_compute",
            operation="complex_from_polar",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["value"],
            payload_schema=_obj(
                ["modulus", "argument"], {"modulus": _str(2000), "argument": _str(2000)}
            ),
            example_payload={"modulus": "sqrt(2)", "argument": "pi/4"},
        )
    )
    specs.append(
        _op(
            public_tool="complex_compute",
            operation="complex_roots_of_unity",
            backend="sympy",
            complexity_class="polynomial",
            result_kinds=["object"],
            payload_schema=_obj(["n"], {"n": _int(1, 1000)}),
            example_payload={"n": 4},
        )
    )
    specs.append(
        _op(
            public_tool="complex_compute",
            operation="complex_equation_solve",
            backend="sympy",
            runs_in_subprocess=True,
            risk="high",
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["expression", "variable"], {"expression": _str(5000), "variable": _str(64)}
            ),
            example_payload={"expression": "z**2 + 1", "variable": "z"},
        )
    )

    # ----- inequality_compute ---------------------------------------------
    specs.append(
        _op(
            public_tool="inequality_compute",
            operation="inequality_domain_solve",
            backend="sympy",
            runs_in_subprocess=True,
            complexity_class="solver_dependent",
            proof_modes=["symbolic"],
            max_certainty="exact",
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["expression", "relation", "variable"],
                {
                    "expression": _str(5000),
                    "relation": _enum("<", "<=", ">", ">=", "==", "!="),
                    "right": _str(5000),
                    "variable": _str(64),
                },
            ),
            example_payload={"expression": "x**2 - 1", "relation": ">=", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="inequality_compute",
            operation="inequality_reduce",
            backend="sympy",
            runs_in_subprocess=True,
            complexity_class="solver_dependent",
            result_kinds=["solution_set"],
            payload_schema=_obj(
                ["expression", "relation", "variable"],
                {
                    "expression": _str(5000),
                    "relation": _enum("<", "<=", ">", ">=", "==", "!="),
                    "right": _str(5000),
                    "variable": _str(64),
                },
            ),
            example_payload={"expression": "2*x + 1", "relation": ">", "variable": "x"},
        )
    )
    specs.append(
        _op(
            public_tool="inequality_compute",
            operation="inequality_check_symbolic",
            backend="sympy",
            proof_modes=["symbolic"],
            max_certainty="proved",
            complexity_class="solver_dependent",
            result_kinds=["verification"],
            payload_schema=_INEQ,
            example_payload={"left": "x**2 + 1", "relation": ">", "right": "0", "variables": ["x"]},
        )
    )
    specs.append(
        _op(
            public_tool="inequality_compute",
            operation="inequality_counterexample_search",
            backend="mpmath",
            runs_in_subprocess=True,
            proof_modes=["counterexample"],
            max_certainty="disproved",
            determinism="seeded_random",
            method_hint="counterexample",
            result_kinds=["witness", "verification"],
            payload_schema=_INEQ,
            example_payload={
                "left": "x",
                "relation": ">=",
                "right": "x**2",
                "variables": ["x"],
                "samples": 500,
            },
        )
    )
    specs.append(
        _op(
            public_tool="inequality_compute",
            operation="inequality_sample",
            backend="mpmath",
            runs_in_subprocess=True,
            proof_modes=["counterexample"],
            max_certainty="disproved",
            determinism="seeded_random",
            method_hint="numeric_sampling",
            result_kinds=["verification", "witness"],
            payload_schema=_INEQ,
            example_payload={
                "left": "x**2 + 1",
                "relation": ">",
                "right": "0",
                "variables": ["x"],
                "samples": 200,
            },
        )
    )

    return specs


REGISTRY: list[OperationSpec] = _build_specs()

# Index by (public_tool, operation) for fast routing/lookup.
_INDEX: dict[tuple[str, str], OperationSpec] = {(s.public_tool, s.operation): s for s in REGISTRY}


def all_operations() -> list[OperationSpec]:
    return list(REGISTRY)


def get_spec(public_tool: str, operation: str) -> OperationSpec | None:
    return _INDEX.get((public_tool, operation))


def method_hint(public_tool: str, operation: str) -> str | None:
    """Return the default ``Method`` a handler should report on success, if declared."""
    return _METHOD_HINTS.get((public_tool, operation))


def operations_for_tool(public_tool: str) -> list[OperationSpec]:
    return [s for s in REGISTRY if s.public_tool == public_tool]


def public_tools() -> list[str]:
    seen: list[str] = []
    for s in REGISTRY:
        if s.public_tool not in seen:
            seen.append(s.public_tool)
    return seen
