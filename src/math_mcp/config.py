"""Static server configuration and environment-derived flags.

This module holds constants only; it must not import heavy math backends so it can be
imported cheaply by tests, the registry, and the sandbox worker.
"""

from __future__ import annotations

import os

SERVER_NAME = "math-mcp"

# Bumped when the wire shape of ToolResult / capabilities changes.
SCHEMA_VERSION = "1.0"

# Bumped when the set/shape of advertised operations changes.
CAPABILITIES_VERSION = "1.0"

# Environment variable that opts into verbose audit traces. Even when enabled the
# trace must never contain secrets, unauthorized file contents, or full prompts.
DEBUG_TRACE_ENV = "MATH_MCP_DEBUG_TRACE"

# Opt-out used only by the test suite / non-Linux developer machines so unit tests
# can exercise pure-Python logic without a real bubblewrap sandbox. It never relaxes
# the production gate: ``runs_in_subprocess`` operations still demand a working
# sandbox unless this flag is explicitly set for local development.
ALLOW_NO_SANDBOX_ENV = "MATH_MCP_ALLOW_NO_SANDBOX"

# Force the platform/sandbox gate to behave as if unsupported (test hook).
FORCE_PLATFORM_UNSUPPORTED_ENV = "MATH_MCP_FORCE_PLATFORM_UNSUPPORTED"

# Test-only: run subprocess-bound operations in-process to keep the unit suite fast.
# The dedicated sandbox acceptance tests never set this — they exercise real isolation.
FORCE_INPROCESS_ENV = "MATH_MCP_FORCE_INPROCESS"


def debug_trace_enabled() -> bool:
    """Return True when verbose audit tracing is explicitly enabled."""
    return os.environ.get(DEBUG_TRACE_ENV, "") not in ("", "0", "false", "False")


def allow_no_sandbox() -> bool:
    """Return True when the developer explicitly allows running without a sandbox.

    Production deployments must leave this unset so that subprocess-bound operations
    refuse to run when network isolation or resource limits cannot be enforced.
    """
    return os.environ.get(ALLOW_NO_SANDBOX_ENV, "") not in ("", "0", "false", "False")


def force_inprocess() -> bool:
    """Return True when subprocess-bound operations should run in-process (test hook)."""
    return os.environ.get(FORCE_INPROCESS_ENV, "") not in ("", "0", "false", "False")
