"""Generate the ``math_capabilities`` response from the operation registry.

This module never keeps a second copy of the operation list, limits, or examples; it
projects :data:`math_mcp.operation_registry.REGISTRY` into the public capabilities shape.

Two modes (V1 §4/§24):

* ``mode="full"`` (default) — the complete, backward-compatible document with every
  operation's ``payload_schema``, ``default_limits``, and example.
* ``mode="summary"`` — a lightweight index of tool names, operation names, and aliases
  only. It carries no ``payload_schema`` / ``default_limits`` so an agent can cheaply
  discover *what* exists, then request ``mode="full"`` for the operation it picked.
"""

from __future__ import annotations

from typing import Any

from math_mcp.config import CAPABILITIES_VERSION, SCHEMA_VERSION, SERVER_NAME
from math_mcp.operation_registry import (
    OperationSpec,
    aliases_for_tool,
    operations_for_tool,
    public_tools,
)

# Utility (non-compute) tools. They expose no operations.
UTILITY_TOOLS: dict[str, str] = {
    "ping": "Health check for the local math MCP server.",
    "math_capabilities": "List supported domains, operations, input limits, and examples.",
}

# Optional V1 fields that are only meaningful for operations that take a top-level
# ``domains`` argument; they are dropped from a capability entry when unset so the full
# document stays stable for operations that take no domains.
_OPTIONAL_DOMAIN_FIELDS = ("requires_domains", "domain_schema", "example_request")


def operation_to_capability(spec: OperationSpec) -> dict[str, Any]:
    """Serialize one operation spec, deriving ``proof_capable`` from ``proof_modes``."""
    data = spec.model_dump(mode="json")
    # proof_capable is a compatibility summary, never a hand-written field.
    data["proof_capable"] = spec.proof_capable
    # Keep the V1 domain-help fields only when the operation actually uses them.
    for key in _OPTIONAL_DOMAIN_FIELDS:
        if not data.get(key):
            data.pop(key, None)
    return data


def _state_visible(state: str, include_experimental: bool, include_disabled: bool) -> bool:
    if state in ("implemented", "deprecated"):
        return True
    if state == "experimental":
        return include_experimental
    if state == "disabled":
        return include_disabled
    return False


def _summary(include_experimental: bool, include_disabled: bool) -> dict[str, Any]:
    """Lightweight capabilities index: tool, operation names, and aliases only."""
    tools: dict[str, Any] = {}
    for name in UTILITY_TOOLS:
        tools[name] = {"kind": "utility", "operations": []}
    for tool_name in public_tools():
        operations = [
            spec.operation
            for spec in operations_for_tool(tool_name)
            if _state_visible(spec.state, include_experimental, include_disabled)
        ]
        tools[tool_name] = {
            "kind": "compute",
            "operations": operations,
            "aliases": aliases_for_tool(tool_name),
        }
    return {
        "server": SERVER_NAME,
        "schema_version": SCHEMA_VERSION,
        "capabilities_version": CAPABILITIES_VERSION,
        "mode": "summary",
        "public_tools": tools,
    }


def get_capabilities(
    include_experimental: bool = False,
    include_disabled: bool = False,
    mode: str = "full",
) -> dict[str, Any]:
    """Return the structured capabilities document.

    Default visibility exposes only ``implemented`` and still-callable ``deprecated``
    operations. ``experimental`` and ``disabled`` operations require the explicit flags.
    ``mode="summary"`` returns the lightweight discovery index instead of the full schema.
    """
    if mode == "summary":
        return _summary(include_experimental, include_disabled)

    tools: dict[str, Any] = {}

    for name, summary in UTILITY_TOOLS.items():
        tools[name] = {"kind": "utility", "summary": summary, "operations": {}}

    for tool_name in public_tools():
        operations: dict[str, Any] = {}
        for spec in operations_for_tool(tool_name):
            if not _state_visible(spec.state, include_experimental, include_disabled):
                continue
            operations[spec.operation] = operation_to_capability(spec)
        tools[tool_name] = {
            "kind": "compute",
            "operations": operations,
            "aliases": aliases_for_tool(tool_name),
        }

    return {
        "server": SERVER_NAME,
        "schema_version": SCHEMA_VERSION,
        "capabilities_version": CAPABILITIES_VERSION,
        "mode": "full",
        "public_tools": tools,
    }
