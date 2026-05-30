"""Pydantic input/output models shared across the server.

``ToolResult`` is the single structured envelope every compute tool returns.
``OperationRequest`` owns the cross-cutting ``domains``/``assumptions``/``limits``
fields so operation-specific payload models never duplicate them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from math_mcp.status import Certainty, ErrorCode, Method, ResultKind, Status


class Certificate(BaseModel):
    """A lightweight, structured proof/counterexample certificate.

    The first delivery does not require every certificate to be machine-checkable, but
    a certificate must be structured rather than a free-form natural-language essay.
    """

    type: Literal[
        "symbolic_simplification",
        "smt_unsat",
        "finite_exhaustion",
        "interval_bound",
        "counterexample",
    ]
    summary: str
    machine_checkable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ResultCondition(BaseModel):
    """A side condition, branch condition, or domain premise attached to a result.

    ``expression`` is the human-facing form; ``condition_ast`` is the machine-readable
    form and must be supplied whenever the condition is expressible as a structured AST.
    """

    expression: str
    condition_ast: dict[str, Any] | None = None
    source: Literal["backend", "domain", "assumption", "branch", "piecewise"] = "backend"
    variables: list[str] = Field(default_factory=list)
    description: str | None = None


class ToolResult(BaseModel):
    """Unified structured result for every compute operation."""

    ok: bool
    status: Status
    certainty: Certainty
    method: Method
    result_kind: ResultKind = "none"
    result: Any | None = None
    result_latex: str | None = None
    conditions: list[ResultCondition] = Field(default_factory=list)
    explanation: str | None = None
    backend: str = "none"
    duration_ms: int
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: ErrorCode | None = None
    certificate: Certificate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Limits(BaseModel):
    """Per-call resource limits. Defaults double as the global hard caps' baseline."""

    model_config = ConfigDict(extra="forbid")

    timeout_ms: int = Field(default=5000, ge=1, le=60000)
    cpu_time_ms: int = Field(default=5000, ge=1, le=60000)
    memory_mb: int = Field(default=512, ge=64, le=8192)
    file_size_mb: int = Field(default=16, ge=1, le=1024)
    max_output_chars: int = Field(default=8000, ge=256, le=100000)
    max_expression_chars: int = Field(default=5000, ge=1, le=50000)
    max_expression_nodes: int = Field(default=2000, ge=1, le=50000)
    max_variables: int = Field(default=20, ge=1, le=100)
    max_matrix_rows: int = Field(default=50, ge=1, le=500)
    max_matrix_cols: int = Field(default=50, ge=1, le=500)
    max_graph_nodes: int = Field(default=10000, ge=1, le=1000000)
    max_graph_edges: int = Field(default=50000, ge=0, le=5000000)
    max_samples: int = Field(default=1000, ge=1, le=100000)
    precision_digits: int = Field(default=50, ge=15, le=200)
    seed: int | None = None


class DomainSpec(BaseModel):
    """Structured domain for a single variable. Never a natural-language string."""

    model_config = ConfigDict(extra="forbid")

    variable: str
    kind: Literal["real", "integer", "rational", "complex", "finite", "boolean"]
    lower: str | None = None
    upper: str | None = None
    lower_closed: bool = True
    upper_closed: bool = True
    values: list[str] | None = None


class AssumptionSpec(BaseModel):
    """Controlled predicates attached to a variable (e.g. ``positive``, ``integer``)."""

    model_config = ConfigDict(extra="forbid")

    variable: str
    predicates: list[str] = Field(default_factory=list)


class OperationRequest(BaseModel):
    """The validated form of a public-tool call.

    Operation-specific payload models do not duplicate top-level ``domains``,
    ``assumptions`` or ``limits``; this model owns those cross-cutting fields.
    """

    model_config = ConfigDict(extra="forbid")

    operation: str
    payload: dict[str, Any]
    domains: list[DomainSpec] = Field(default_factory=list)
    assumptions: list[AssumptionSpec] = Field(default_factory=list)
    limits: Limits = Field(default_factory=Limits)


class ExpressionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str
    variables: list[str] = Field(default_factory=list)


class IdentityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: str
    right: str
    variables: list[str] = Field(default_factory=list)
    sample_points: int = Field(default=25, ge=0, le=10000)


class InequalityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: str
    relation: Literal["==", "!=", "<", "<=", ">", ">="]
    right: str
    variables: list[str]
    samples: int = Field(default=1000, ge=1, le=100000)
