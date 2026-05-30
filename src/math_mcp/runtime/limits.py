"""Limit normalization, platform gating, and rlimit application.

The project is Linux-only by design: there is no macOS/Windows degraded mode. Resource
limits (CPU, address space, file size, open files) are applied to backend worker
processes via ``resource.setrlimit`` in a ``preexec_fn``.
"""

from __future__ import annotations

import contextlib
import math
import os
import platform
import resource
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from math_mcp.config import FORCE_PLATFORM_UNSUPPORTED_ENV
from math_mcp.errors import InvalidLimits, PlatformUnsupported
from math_mcp.schemas import Limits


def normalize_limits(raw: Any) -> Limits:
    """Coerce a raw limits dict into a validated :class:`Limits`."""
    if raw is None:
        return Limits()
    if isinstance(raw, Limits):
        return raw
    if not isinstance(raw, dict):
        raise InvalidLimits(f"limits must be an object, got {type(raw).__name__}")
    try:
        return Limits.model_validate(raw)
    except ValidationError as exc:
        raise InvalidLimits(f"invalid limits: {exc.error_count()} error(s)") from exc


def is_linux() -> bool:
    if os.environ.get(FORCE_PLATFORM_UNSUPPORTED_ENV, "") not in ("", "0", "false", "False"):
        return False
    return platform.system() == "Linux"


def ensure_linux() -> None:
    """Raise :class:`PlatformUnsupported` on any non-Linux platform."""
    if not is_linux():
        raise PlatformUnsupported(
            f"math-mcp supports Linux only; detected platform '{platform.system()}'"
        )


def rlimit_preexec(limits: Limits) -> Callable[[], None]:
    """Build a ``preexec_fn`` that applies resource limits in the child process.

    The limits are inherited across ``exec`` and into the sandbox namespace, so applying
    them to the launcher (bubblewrap or python) covers the backend worker too.
    """
    cpu_seconds = max(1, math.ceil(limits.cpu_time_ms / 1000))
    address_space = limits.memory_mb * 1024 * 1024
    file_size = limits.file_size_mb * 1024 * 1024

    def _apply() -> None:  # pragma: no cover - runs only in the child process
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        with contextlib.suppress(ValueError, OSError):
            # Some environments refuse an AS cap; CPU/FSIZE still bound the worker.
            resource.setrlimit(resource.RLIMIT_AS, (address_space, address_space))

    return _apply


def apply_rlimits_in_process(limits: Limits) -> None:  # pragma: no cover - child only
    """Apply rlimits to the current process (used by the worker as defense in depth)."""
    rlimit_preexec(limits)()
