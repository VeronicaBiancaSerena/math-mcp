"""Generate the ``math_capabilities`` response from the operation registry.

This module never keeps a second copy of the operation list, limits, or examples; it
projects :data:`math_mcp.operation_registry.REGISTRY` into the public capabilities shape.
"""

from __future__ import annotations

from typing import Any

from math_mcp.config import CAPABILITIES_VERSION, SCHEMA_VERSION, SERVER_NAME
from math_mcp.operation_registry import (
    OperationSpec,
    operations_for_tool,
    public_tools,
)

# Utility (non-compute) tools. They expose no operations.
UTILITY_TOOLS: dict[str, str] = {
    "ping": "Health check for the local math MCP server.",
    "math_capabilities": "List supported domains, operations, input limits, and examples.",
}


def operation_to_capability(spec: OperationSpec) -> dict[str, Any]:
    """Serialize one operation spec, deriving ``proof_capable`` from ``proof_modes``."""
    data = spec.model_dump(mode="json")
    # proof_capable is a compatibility summary, never a hand-written field.
    data["proof_capable"] = spec.proof_capable
    return data


def _state_visible(state: str, include_experimental: bool, include_disabled: bool) -> bool:
    if state in ("implemented", "deprecated"):
        return True
    if state == "experimental":
        return include_experimental
    if state == "disabled":
        return include_disabled
    return False


def get_capabilities(
    include_experimental: bool = False,
    include_disabled: bool = False,
) -> dict[str, Any]:
    """Return the structured capabilities document.

    Default visibility exposes only ``implemented`` and still-callable ``deprecated``
    operations. ``experimental`` and ``disabled`` operations require the explicit flags.
    """
    tools: dict[str, Any] = {}

    for name, summary in UTILITY_TOOLS.items():
        tools[name] = {"kind": "utility", "summary": summary, "operations": {}}

    for tool_name in public_tools():
        operations: dict[str, Any] = {}
        for spec in operations_for_tool(tool_name):
            if not _state_visible(spec.state, include_experimental, include_disabled):
                continue
            operations[spec.operation] = operation_to_capability(spec)
        tools[tool_name] = {"kind": "compute", "operations": operations}

    return {
        "server": SERVER_NAME,
        "schema_version": SCHEMA_VERSION,
        "capabilities_version": CAPABILITIES_VERSION,
        "public_tools": tools,
    }
