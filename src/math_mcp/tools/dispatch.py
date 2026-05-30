"""Central dispatcher: validate → route → (sandbox?) → caveats → ToolResult.

Every public compute tool funnels through :func:`run_operation`, which owns request
validation, registry lookup, constraint-conflict detection, the subprocess decision,
caveat enforcement, and the audit trace. Handlers (registered with :func:`handler`) only
implement the math.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from math_mcp import backend_caveats
from math_mcp.config import debug_trace_enabled, force_inprocess
from math_mcp.errors import (
    AssumptionUnsupported,
    BackendInternalError,
    DomainUnsupported,
    InvalidInput,
    MathMcpError,
    UnsupportedOperation,
)
from math_mcp.operation_registry import OperationSpec, get_spec
from math_mcp.parsing.domain_parser import NormalizedConstraints, normalize
from math_mcp.runtime.limits import normalize_limits
from math_mcp.runtime.subprocess_runner import run_in_subprocess
from math_mcp.runtime.timing import Stopwatch
from math_mcp.schemas import AssumptionSpec, DomainSpec, Limits, ToolResult
from math_mcp.tools.base import Ctx, Outcome
from math_mcp.tools.versions import backend_versions

Handler = Callable[[Ctx], Outcome]

HANDLERS: dict[tuple[str, str], Handler] = {}

# Tool modules whose import side effect registers handlers.
_TOOL_MODULES = [
    "algebra",
    "calculus",
    "verification",
    "z3_tools",
    "matrix",
    "discrete",
    "graph",
    "probability",
    "sets",
    "geometry",
    "trigonometry",
    "number_theory",
    "logic",
    "ode",
    "complex_tools",
    "inequalities",
]
_loaded = False


def handler(public_tool: str, operation: str) -> Callable[[Handler], Handler]:
    """Register ``fn`` as the handler for ``(public_tool, operation)``."""

    def decorate(fn: Handler) -> Handler:
        HANDLERS[(public_tool, operation)] = fn
        return fn

    return decorate


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    for name in _TOOL_MODULES:
        importlib.import_module(f"math_mcp.tools.{name}")
    _loaded = True


def execute_handler(
    public_tool: str,
    operation: str,
    payload: dict[str, Any],
    limits: Limits,
    constraints: NormalizedConstraints,
) -> Outcome:
    """Run a registered handler in-process (used directly and inside the worker)."""
    _ensure_loaded()
    spec = get_spec(public_tool, operation)
    if spec is None:
        raise UnsupportedOperation(f"unknown operation '{operation}' for tool '{public_tool}'")
    fn = HANDLERS.get((public_tool, operation))
    if fn is None:
        raise UnsupportedOperation(f"operation '{operation}' is registered but has no handler yet")
    return fn(Ctx(public_tool, operation, payload, limits, constraints, spec))


def run_operation(
    public_tool: str,
    operation: str,
    payload: Any,
    domains: Any = None,
    assumptions: Any = None,
    limits: Any = None,
) -> ToolResult:
    """Full pipeline for one operation call; always returns a structured ToolResult."""
    watch = Stopwatch()
    requested_limits = limits if isinstance(limits, dict) else {}
    try:
        norm_limits = normalize_limits(limits)
        payload_dict = _coerce_payload(payload)
        domain_specs = _coerce_domains(domains)
        assumption_specs = _coerce_assumptions(assumptions)

        spec = get_spec(public_tool, operation)
        if spec is None:
            raise UnsupportedOperation(f"unknown operation '{operation}' for tool '{public_tool}'")
        if spec.state == "disabled":
            reason = spec.disabled_reason or "operation is disabled"
            raise UnsupportedOperation(f"operation '{operation}' is disabled: {reason}")

        constraints = normalize(domain_specs, assumption_specs, limits=norm_limits)

        network_isolated: bool | None = None
        ran_in_subprocess = spec.runs_in_subprocess and not force_inprocess()
        if ran_in_subprocess:
            raw = run_in_subprocess(
                public_tool,
                operation,
                payload_dict,
                norm_limits,
                [d.model_dump() for d in domain_specs],
                [a.model_dump() for a in assumption_specs],
            )
            network_isolated = bool(raw.get("network_isolated", False))
            outcome = _outcome_from_raw(raw)
        else:
            outcome = execute_handler(
                public_tool, operation, payload_dict, norm_limits, constraints
            )

        return _assemble(
            spec, outcome, norm_limits, requested_limits, watch, network_isolated,
            ran_in_subprocess,
        )
    except MathMcpError as exc:
        return _error_result(exc, public_tool, operation, watch, requested_limits)
    except Exception as exc:  # noqa: BLE001 - last-resort guard: never leak a raw traceback
        # An in-process handler (runs_in_subprocess=False, or the FORCE_INPROCESS test
        # path) may raise an unexpected backend exception. The subprocess worker already
        # wraps these; mirror that here so every tool returns a structured ToolResult
        # (guide §5.3). Only the exception type is surfaced — never its message, which
        # could carry paths or input content (guide §13.2.1).
        wrapped = BackendInternalError(type(exc).__name__)
        return _error_result(wrapped, public_tool, operation, watch, requested_limits)


def _coerce_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise InvalidInput("payload must be an object")
    return payload


def _coerce_domains(domains: Any) -> list[DomainSpec]:
    if not domains:
        return []
    try:
        return [DomainSpec.model_validate(d) for d in domains]
    except ValidationError as exc:
        raise DomainUnsupported(
            f"invalid domain specification: {exc.error_count()} error(s)"
        ) from exc


def _coerce_assumptions(assumptions: Any) -> list[AssumptionSpec]:
    if not assumptions:
        return []
    try:
        return [AssumptionSpec.model_validate(a) for a in assumptions]
    except ValidationError as exc:
        raise AssumptionUnsupported(
            f"invalid assumption specification: {exc.error_count()} error(s)"
        ) from exc


def _outcome_from_raw(raw: dict[str, Any]) -> Outcome:
    if raw.get("ok"):
        return Outcome.from_json(raw["outcome"])
    error = raw.get("error", {})
    exc = BackendInternalError(error.get("message", "backend worker error"))
    # Preserve the worker's classification when present.
    exc.status = error.get("status", exc.status)
    exc.error_code = error.get("error_code", exc.error_code)
    exc.certainty = error.get("certainty", exc.certainty)
    exc.method = error.get("method", exc.method)
    raise exc


def _assemble(
    spec: OperationSpec,
    outcome: Outcome,
    limits: Limits,
    requested_limits: dict[str, Any],
    watch: Stopwatch,
    network_isolated: bool | None,
    ran_in_subprocess: bool,
) -> ToolResult:
    backend = outcome.backend if outcome.backend != "none" else spec.backend
    has_override = "certainty_override_reason" in outcome.metadata_extra
    certainty, caveat_warnings, caveat_records = backend_caveats.enforce(
        backend, spec.operation, outcome.method, outcome.certainty, has_override=has_override
    )

    warnings = list(outcome.warnings)
    for w in caveat_warnings:
        if w not in warnings:
            warnings.append(w)

    metadata = _trace(spec, outcome, limits, requested_limits, network_isolated, ran_in_subprocess)
    if caveat_records:
        metadata["backend_caveats"] = caveat_records
    metadata.update(outcome.metadata_extra)

    result, truncated = _enforce_output_size(outcome.result, limits)
    if truncated:
        warnings.append("result truncated to max_output_chars")

    return ToolResult(
        ok=True,
        status=outcome.status,
        certainty=certainty,
        method=outcome.method,
        result_kind=outcome.result_kind,
        result=result,
        result_latex=outcome.result_latex,
        conditions=outcome.conditions,  # type: ignore[arg-type]
        explanation=outcome.explanation,
        backend=backend,
        duration_ms=watch.stop(),
        warnings=warnings,
        error=None,
        error_code=None,
        certificate=outcome.certificate,  # type: ignore[arg-type]
        metadata=metadata,
    )


def _enforce_output_size(result: Any, limits: Limits) -> tuple[Any, bool]:
    if isinstance(result, str) and len(result) > limits.max_output_chars:
        return result[: limits.max_output_chars], True
    return result, False


def _trace(
    spec: OperationSpec,
    outcome: Outcome,
    limits: Limits,
    requested_limits: dict[str, Any],
    network_isolated: bool | None,
    ran_in_subprocess: bool,
) -> dict[str, Any]:
    applied: dict[str, Any] = {
        "timeout_ms": limits.timeout_ms,
        "cpu_time_ms": limits.cpu_time_ms,
        "memory_mb": limits.memory_mb,
        "file_size_mb": limits.file_size_mb,
        "cpu_time_limit_enforced": ran_in_subprocess,
        "memory_limit_enforced": ran_in_subprocess,
        "file_size_limit_enforced": ran_in_subprocess,
        "network_isolated": bool(network_isolated) if ran_in_subprocess else False,
    }
    trace: dict[str, Any] = {
        "public_tool": spec.public_tool,
        "operation": spec.operation,
        "operation_version": spec.operation_version,
        "operation_state": spec.state,
        "backend_versions": backend_versions(
            outcome.backend if outcome.backend != "none" else spec.backend
        ),
        "limits_requested": requested_limits,
        "limits_applied": applied,
        "proof_method": outcome.method,
        "fallbacks_used": [],
        "input_form": spec.accepted_input_forms[0] if spec.accepted_input_forms else "unknown",
        "determinism": spec.determinism,
        "seed": limits.seed,
        "debug_trace_enabled": debug_trace_enabled(),
    }
    return trace


def _error_result(
    exc: MathMcpError,
    public_tool: str,
    operation: str,
    watch: Stopwatch,
    requested_limits: dict[str, Any],
) -> ToolResult:
    spec = get_spec(public_tool, operation)
    metadata: dict[str, Any] = {
        "public_tool": public_tool,
        "operation": operation,
        "operation_state": spec.state if spec else "unknown",
        "limits_requested": requested_limits,
        "debug_trace_enabled": debug_trace_enabled(),
    }
    return ToolResult(
        ok=False,
        status=exc.status,
        certainty=exc.certainty,
        method=exc.method,
        result_kind="none",
        result=None,
        backend="none",
        duration_ms=watch.stop(),
        warnings=[],
        error=str(exc),
        error_code=exc.error_code,
        metadata=metadata,
    )
