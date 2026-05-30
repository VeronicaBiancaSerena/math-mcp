"""Build Z3 expressions from a structured AST — never from a string via ``eval``.

The Z3 tools accept only declared variables (``Int``/``Real``/``Bool``) and a fixed
operator vocabulary. ``z3`` is imported lazily so importing this module (and the server)
does not pay the Z3 import cost unless a Z3 operation actually runs.
"""

from __future__ import annotations

import re
from typing import Any

from math_mcp.errors import InvalidAst

_SAFE_VAR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_MAX_DEPTH = 64
_MAX_NODES = 5000
_ALLOWED_SORTS = {"Int", "Real", "Bool"}

_NARY = {"and", "or", "add", "mul"}
_BINARY = {"sub", "div", "mod", "implies", "iff", "eq", "ne", "lt", "le", "gt", "ge"}
_UNARY = {"not", "neg"}


def declare_variables(variables: dict[str, str]) -> dict[str, Any]:
    """Create Z3 constants for each declared variable; reject unknown sorts/names."""
    import z3  # noqa: PLC0415 - lazy, heavy import

    if len(variables) > 64:
        raise InvalidAst("too many Z3 variables (max 64)")
    out: dict[str, Any] = {}
    for name, sort in variables.items():
        if not _SAFE_VAR_RE.match(name):
            raise InvalidAst(f"invalid Z3 variable name '{name}'")
        if sort not in _ALLOWED_SORTS:
            raise InvalidAst(f"unsupported Z3 sort '{sort}' for '{name}'")
        if sort == "Int":
            out[name] = z3.Int(name)
        elif sort == "Real":
            out[name] = z3.Real(name)
        else:
            out[name] = z3.Bool(name)
    return out


def build_term(
    node: Any, zvars: dict[str, Any], depth: int = 0, counter: dict[str, int] | None = None
) -> Any:
    """Recursively convert one AST node into a Z3 term."""
    import z3  # noqa: PLC0415

    counter = counter if counter is not None else {"n": 0}
    if depth > _MAX_DEPTH:
        raise InvalidAst("Z3 AST nesting depth exceeds limit")
    counter["n"] += 1
    if counter["n"] > _MAX_NODES:
        raise InvalidAst("Z3 AST node count exceeds limit")
    if not isinstance(node, dict):
        raise InvalidAst(f"Z3 AST node must be an object, got {type(node).__name__}")

    if "var" in node:
        name = str(node["var"])
        if name not in zvars:
            raise InvalidAst(f"undeclared Z3 variable '{name}'")
        return zvars[name]
    if "int" in node:
        return z3.IntVal(int(node["int"]))
    if "real" in node:
        return z3.RealVal(str(node["real"]))
    if "rational" in node:
        value = node["rational"]
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return z3.RealVal(int(value[0])) / z3.RealVal(int(value[1]))
        return z3.RealVal(str(value))
    if "bool" in node:
        return z3.BoolVal(bool(node["bool"]))

    op = node.get("op")
    if op is None:
        raise InvalidAst(f"unrecognized Z3 AST node keys: {sorted(node.keys())}")

    def sub(key: str) -> Any:
        if key not in node:
            raise InvalidAst(f"Z3 op '{op}' missing '{key}'")
        return build_term(node[key], zvars, depth + 1, counter)

    def args() -> list[Any]:
        raw = node.get("args")
        if not isinstance(raw, list) or not raw:
            raise InvalidAst(f"Z3 op '{op}' requires a non-empty 'args' list")
        return [build_term(a, zvars, depth + 1, counter) for a in raw]

    if op in _NARY:
        terms = args()
        if op == "and":
            return z3.And(*terms)
        if op == "or":
            return z3.Or(*terms)
        if op == "add":
            return z3.Sum(*terms) if len(terms) > 1 else terms[0]
        if op == "mul":
            result = terms[0]
            for t in terms[1:]:
                result = result * t
            return result
    if op in _UNARY:
        operand = sub("arg") if "arg" in node else args()[0]
        return z3.Not(operand) if op == "not" else -operand
    if op in _BINARY:
        left, right = sub("left"), sub("right")
        return _binary(op, left, right)
    raise InvalidAst(f"unknown Z3 op '{op}'")


def _binary(op: str, left: Any, right: Any) -> Any:
    import z3  # noqa: PLC0415

    if op == "sub":
        return left - right
    if op == "div":
        return left / right
    if op == "mod":
        return left % right
    if op == "implies":
        return z3.Implies(left, right)
    if op in ("eq", "iff"):
        return left == right
    if op == "ne":
        return left != right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    raise InvalidAst(f"unknown Z3 binary op '{op}'")


def build_constraints(
    variables: dict[str, str], constraints: list[Any]
) -> tuple[dict[str, Any], list[Any]]:
    """Declare variables and build every constraint term."""
    zvars = declare_variables(variables)
    counter = {"n": 0}
    terms = [build_term(c, zvars, 0, counter) for c in constraints]
    return zvars, terms
