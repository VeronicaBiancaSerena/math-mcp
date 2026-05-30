"""Serialize backend (mostly SymPy) objects into JSON-safe, stable strings.

Results are returned to agents as strings/LaTeX rather than opaque objects so they are
deterministic across SymPy versions and never carry executable state. The subprocess
worker also relies on these helpers: it may only return JSON, never pickled objects.
"""

from __future__ import annotations

from typing import Any

import sympy as sp


def to_text(obj: Any) -> str:
    """Render a SymPy object (or anything) to a stable plain-text string."""
    try:
        return str(sp.sstr(obj))
    except Exception:
        return str(obj)


def to_latex(obj: Any) -> str | None:
    """Render a SymPy object to LaTeX, or ``None`` if it cannot be rendered."""
    try:
        return str(sp.latex(obj))
    except Exception:
        return None


def jsonify(obj: Any) -> Any:
    """Recursively convert a value into a JSON-serializable structure.

    SymPy atoms and expressions become strings; containers are walked; primitives pass
    through. This guarantees the subprocess JSON channel never needs pickle.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(_key(k)): jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [jsonify(v) for v in obj]
    if isinstance(obj, sp.Basic):
        return to_text(obj)
    return to_text(obj)


def _key(k: Any) -> str:
    if isinstance(k, sp.Basic):
        return to_text(k)
    return str(k)


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate ``text`` to ``max_chars``; return (text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True
