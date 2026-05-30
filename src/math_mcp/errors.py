"""Typed exceptions that carry a stable ``error_code`` and target ``status``.

Tool handlers and backends raise these; the shared dispatcher converts them into a
structured :class:`~math_mcp.schemas.ToolResult`. This keeps error mapping in one place
instead of every backend hand-rolling its own error dict.
"""

from __future__ import annotations

from math_mcp.status import Certainty, ErrorCode, Method, Status


class MathMcpError(Exception):
    """Base class for structured, agent-recoverable tool errors.

    Attributes mirror the fields the dispatcher needs to build a ToolResult:
    ``status``, ``error_code``, ``certainty`` and ``method``.
    """

    status: Status = "failure"
    error_code: ErrorCode = "BACKEND_INTERNAL_ERROR"
    certainty: Certainty = "error"
    method: Method = "none"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ParseRejected(MathMcpError):
    status: Status = "invalid_input"
    error_code: ErrorCode = "PARSE_REJECTED"


class InvalidAst(MathMcpError):
    status: Status = "invalid_input"
    error_code: ErrorCode = "INVALID_AST"


class UnsupportedOperation(MathMcpError):
    status: Status = "unsupported"
    error_code: ErrorCode = "UNSUPPORTED_OPERATION"


class DomainUnsupported(MathMcpError):
    status: Status = "unsupported"
    error_code: ErrorCode = "DOMAIN_UNSUPPORTED"


class AssumptionUnsupported(MathMcpError):
    status: Status = "unsupported"
    error_code: ErrorCode = "ASSUMPTION_UNSUPPORTED"


class ConstraintConflict(MathMcpError):
    status: Status = "invalid_input"
    error_code: ErrorCode = "CONSTRAINT_CONFLICT"


class InvalidLimits(MathMcpError):
    status: Status = "invalid_input"
    error_code: ErrorCode = "INVALID_LIMITS"


class InvalidInput(MathMcpError):
    """Generic input validation failure that is not a parser/AST/limits problem."""

    status: Status = "invalid_input"
    error_code: ErrorCode = "BACKEND_INTERNAL_ERROR"


class BackendTimeout(MathMcpError):
    status: Status = "timeout"
    error_code: ErrorCode = "BACKEND_TIMEOUT"


class OutputTooLarge(MathMcpError):
    status: Status = "output_too_large"
    error_code: ErrorCode = "OUTPUT_TOO_LARGE"


class ResourceLimitExceeded(MathMcpError):
    status: Status = "failure"
    error_code: ErrorCode = "RESOURCE_LIMIT_EXCEEDED"


class BackendInternalError(MathMcpError):
    status: Status = "backend_error"
    error_code: ErrorCode = "BACKEND_INTERNAL_ERROR"


class NumericConvergenceFailed(MathMcpError):
    status: Status = "failure"
    error_code: ErrorCode = "NUMERIC_CONVERGENCE_FAILED"


class PlatformUnsupported(MathMcpError):
    status: Status = "failure"
    error_code: ErrorCode = "PLATFORM_UNSUPPORTED"


class SandboxUnavailable(MathMcpError):
    status: Status = "failure"
    error_code: ErrorCode = "SANDBOX_UNAVAILABLE"
