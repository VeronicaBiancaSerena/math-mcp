"""math-mcp: a local, offline MCP server for deterministic math computation and verification.

The package exposes a small set of domain-level MCP tools (see ``math_mcp.server``).
Concrete capabilities are addressed through the ``operation`` parameter of each tool
and are described by the single source of truth in ``math_mcp.operation_registry``.
"""

from math_mcp.config import CAPABILITIES_VERSION, SCHEMA_VERSION, SERVER_NAME

__all__ = ["SERVER_NAME", "SCHEMA_VERSION", "CAPABILITIES_VERSION", "__version__"]

__version__ = "0.3.0"
