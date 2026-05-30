"""Shared building blocks for operation handlers: ``Outcome``, ``Ctx``, and result builders.

A handler receives a :class:`Ctx` (validated payload + normalized constraints + spec) and
returns an :class:`Outcome` (the core result fields) or raises a
:class:`~math_mcp.errors.MathMcpError`. The dispatcher turns an ``Outcome`` into a
:class:`~math_mcp.schemas.ToolResult`, applying caveats, the audit trace, and timing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from math_mcp.errors import InvalidInput
from math_mcp.operation_registry import OperationSpec, method_hint
from math_mcp.parsing.domain_parser import NormalizedConstraints
from math_mcp.parsing.sympy_parser import load_expression
from math_mcp.runtime import serialization
from math_mcp.schemas import Limits
from math_mcp.status import Certainty, Method, ResultKind, Status


@dataclass
class Outcome:
    """The core result fields a handler produces (JSON-serializable)."""

    status: Status
    certainty: Certainty
    method: Method
    result_kind: ResultKind = "none"
    result: Any = None
    result_latex: str | None = None
    conditions: list[dict[str, Any]] = field(default_factory=list)
    explanation: str | None = None
    certificate: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    backend: str = "none"
    metadata_extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Outcome:
        return cls(**data)


@dataclass
class Ctx:
    """Validated invocation context handed to a handler."""

    public_tool: str
    operation: str
    payload: dict[str, Any]
    limits: Limits
    constraints: NormalizedConstraints
    spec: OperationSpec

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)

    def require(self, key: str) -> Any:
        if key not in self.payload or self.payload[key] is None:
            raise InvalidInput(f"payload is missing required field '{key}'")
        return self.payload[key]

    def require_str(self, key: str) -> str:
        value = self.require(key)
        if not isinstance(value, str):
            raise InvalidInput(f"payload field '{key}' must be a string")
        return value

    def declared_symbols(self) -> set[str] | None:
        """Variable names the payload explicitly declares, or None for auto-symbols."""
        names: set[str] = set()
        raw = self.payload.get("variables")
        if isinstance(raw, list):
            names.update(str(v) for v in raw)
        for key in ("variable", "function"):
            value = self.payload.get(key)
            if isinstance(value, str):
                names.add(value)
        return names or None

    def expression(
        self,
        str_key: str = "expression",
        ast_key: str = "expr_ast",
        allowed_symbols: set[str] | None = None,
    ) -> Any:
        return load_expression(
            self.payload,
            str_key=str_key,
            ast_key=ast_key,
            limits=self.limits,
            allowed_symbols=allowed_symbols,
        )

    def default_method(self) -> Method:
        hint = method_hint(self.public_tool, self.operation)
        if hint is not None:
            return hint  # type: ignore[return-value]
        return "backend"


def condition(
    expression: str,
    *,
    condition_ast: dict[str, Any] | None = None,
    source: str = "backend",
    variables: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "expression": expression,
        "condition_ast": condition_ast,
        "source": source,
        "variables": variables or [],
        "description": description,
    }


def certificate(
    type_: str,
    summary: str,
    *,
    machine_checkable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": type_,
        "summary": summary,
        "machine_checkable": machine_checkable,
        "details": details or {},
    }


# --- result builders -------------------------------------------------------


def value_result(
    result: Any,
    *,
    certainty: Certainty = "exact",
    method: Method = "backend",
    backend: str = "sympy",
    latex: str | None = None,
    result_kind: ResultKind = "value",
    conditions: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    explanation: str | None = None,
    certificate_: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Outcome:
    return Outcome(
        status="success",
        certainty=certainty,
        method=method,
        result_kind=result_kind,
        result=serialization.jsonify(result),
        result_latex=latex,
        conditions=conditions or [],
        explanation=explanation,
        certificate=certificate_,
        warnings=warnings or [],
        backend=backend,
        metadata_extra=metadata or {},
    )


def object_result(result: Any, **kwargs: Any) -> Outcome:
    kwargs.setdefault("result_kind", "object")
    return value_result(result, **kwargs)


def solution_set_result(result: Any, **kwargs: Any) -> Outcome:
    kwargs.setdefault("result_kind", "solution_set")
    return value_result(result, **kwargs)


def verification_result(
    *,
    status: Status,
    certainty: Certainty,
    method: Method,
    result: Any = None,
    backend: str = "sympy",
    latex: str | None = None,
    conditions: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    explanation: str | None = None,
    certificate_: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    result_kind: ResultKind = "verification",
) -> Outcome:
    return Outcome(
        status=status,
        certainty=certainty,
        method=method,
        result_kind=result_kind,
        result=serialization.jsonify(result),
        result_latex=latex,
        conditions=conditions or [],
        explanation=explanation,
        certificate=certificate_,
        warnings=warnings or [],
        backend=backend,
        metadata_extra=metadata or {},
    )
