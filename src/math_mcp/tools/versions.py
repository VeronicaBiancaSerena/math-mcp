"""Backend version reporting for the audit trace (lazy, cached)."""

from __future__ import annotations

import functools


@functools.cache
def _version(backend: str) -> str:
    try:
        if backend == "sympy":
            import sympy

            return str(sympy.__version__)
        if backend == "mpmath":
            import mpmath

            return str(mpmath.__version__)
        if backend == "numpy":
            import numpy

            return str(numpy.__version__)
        if backend == "scipy":
            import scipy

            return str(scipy.__version__)
        if backend == "networkx":
            import networkx

            return str(networkx.__version__)
        if backend == "z3":
            import z3

            return str(z3.get_version_string())
    except Exception:  # noqa: BLE001 - version reporting must never break a result
        return "unknown"
    return "n/a"


def backend_versions(backend: str) -> dict[str, str]:
    """Return ``{backend: version}`` for the backend(s) used by a result."""
    if backend in ("none", ""):
        return {}
    if backend == "python":
        import platform

        return {"python": platform.python_version()}
    return {backend: _version(backend)}
