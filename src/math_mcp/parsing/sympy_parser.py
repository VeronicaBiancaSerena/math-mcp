"""Whitelist-based safe parser for SymPy-style expression strings.

The parser never calls :func:`eval` directly and never exposes ``sympy.__dict__``. The
defense is layered:

1. length limit;
2. character whitelist (digits, identifiers, a fixed operator set, brackets, commas,
   and the decimal point);
3. rejection of ``__`` and a banned-keyword list;
4. identifier validation against a function/constant whitelist plus safe variable names;
5. parsing with empty ``__builtins__`` and a minimal ``local_dict``;
6. a structural screen on the parsed tree (allowed function heads only, no undefined
   functions, bounded symbol count, node count, nesting depth, and exponent magnitude).

``parse_expr`` is treated as a convenience front-end, not a trust boundary: heavy work
still runs under the subprocess sandbox with resource limits.
"""

from __future__ import annotations

import re
from typing import Any

import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from math_mcp.errors import InvalidAst, ParseRejected
from math_mcp.schemas import Limits

# Functions exposed to the parser, mapped to their SymPy implementation.
_ALLOWED_FUNCTIONS: dict[str, Any] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "sec": sp.sec,
    "csc": sp.csc,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "acot": sp.acot,
    "atan2": sp.atan2,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "asinh": sp.asinh,
    "acosh": sp.acosh,
    "atanh": sp.atanh,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "sqrt": sp.sqrt,
    "Abs": sp.Abs,
    "sign": sp.sign,
    "floor": sp.floor,
    "ceiling": sp.ceiling,
    "factorial": sp.factorial,
    "binomial": sp.binomial,
    "re": sp.re,
    "im": sp.im,
    "conjugate": sp.conjugate,
    "arg": sp.arg,
    "Min": sp.Min,
    "Max": sp.Max,
    "gcd": sp.gcd,
    "Mod": sp.Mod,
    "Eq": sp.Eq,
    "Ne": sp.Ne,
    "Lt": sp.Lt,
    "Le": sp.Le,
    "Gt": sp.Gt,
    "Ge": sp.Ge,
    "And": sp.And,
    "Or": sp.Or,
    "Not": sp.Not,
    "Implies": sp.Implies,
    "Xor": sp.Xor,
    "Equivalent": sp.Equivalent,
    "Rational": sp.Rational,
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Matrix": sp.Matrix,
}

# Constants exposed to the parser.
_ALLOWED_CONSTANTS: dict[str, Any] = {
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
    "oo": sp.oo,
    "zoo": sp.zoo,
    "nan": sp.nan,
    "GoldenRatio": sp.GoldenRatio,
    "EulerGamma": sp.EulerGamma,
    "true": sp.true,
    "false": sp.false,
}

# Inert SymPy constructors needed when parsing with ``evaluate=False`` (the transformed
# code calls Add/Mul/Pow/... explicitly). They are safe to expose: building an algebraic
# node performs no I/O. Listing them here also stops them being treated as user symbols.
_PARSE_HELPERS: dict[str, Any] = {
    "Add": sp.Add,
    "Mul": sp.Mul,
    "Pow": sp.Pow,
    "Tuple": sp.Tuple,
    "Symbol": sp.Symbol,
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Rational": sp.Rational,
    "StrictGreaterThan": sp.StrictGreaterThan,
    "GreaterThan": sp.GreaterThan,
    "StrictLessThan": sp.StrictLessThan,
    "LessThan": sp.LessThan,
    "Equality": sp.Equality,
    "Unequality": sp.Unequality,
}

# Allowed function class names after parsing (boolean/relational nodes are not Function
# subclasses, so they are validated implicitly by the character + keyword gates).
_ALLOWED_FUNCTION_CLASSES: set[str] = {
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "asin",
    "acos",
    "atan",
    "acot",
    "atan2",
    "sinh",
    "cosh",
    "tanh",
    "asinh",
    "acosh",
    "atanh",
    "exp",
    "log",
    "sqrt",
    "Abs",
    "sign",
    "floor",
    "ceiling",
    "factorial",
    "binomial",
    "re",
    "im",
    "conjugate",
    "arg",
    "Min",
    "Max",
    "Mod",
}

_BANNED_KEYWORDS = {
    "import",
    "open",
    "exec",
    "eval",
    "lambda",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "compile",
    "input",
    "exit",
    "quit",
    "vars",
    "dir",
    "type",
    "object",
    "super",
    "property",
    "memoryview",
    "bytearray",
    "breakpoint",
    "help",
    "classmethod",
    "staticmethod",
}

# Character whitelist: identifiers, digits, whitespace, and a fixed operator set.
_ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ \t\n+-*/%!()[],.&|~<>="
)

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SAFE_VAR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_NUMBER_RE = re.compile(r"\d+")

_MAX_PAREN_DEPTH = 64
_MAX_NUMBER_DIGITS = 1000
_MAX_ABS_EXPONENT = 10_000


def _reject(message: str) -> ParseRejected:
    return ParseRejected(message)


def _build_local_dict(
    symbol_names: set[str], extra_functions: dict[str, Any] | None
) -> dict[str, Any]:
    local: dict[str, Any] = {}
    local.update(_PARSE_HELPERS)
    local.update(_ALLOWED_FUNCTIONS)
    local.update(_ALLOWED_CONSTANTS)
    if extra_functions:
        local.update(extra_functions)
    for name in symbol_names:
        # Explicit symbols win over auto-symbol creation and shadow nothing dangerous.
        local[name] = sp.Symbol(name)
    return local


def _pre_screen(text: str) -> None:
    if "__" in text:
        raise _reject("expression contains forbidden '__'")
    bad_chars = sorted({c for c in text if c not in _ALLOWED_CHARS})
    if bad_chars:
        raise _reject(f"expression contains forbidden characters: {bad_chars}")
    # A '.' is allowed only as a decimal point inside a number, never as attribute access
    # (e.g. ``pi.evalf``, ``Integer.mro``, ``sin.func``). Require a digit on one side.
    for i, ch in enumerate(text):
        if ch != ".":
            continue
        prev_digit = i > 0 and text[i - 1].isdigit()
        next_digit = i + 1 < len(text) and text[i + 1].isdigit()
        if not (prev_digit or next_digit):
            raise _reject("'.' is only allowed as a decimal point within a number")
    # Paren / bracket depth.
    depth = 0
    for ch in text:
        if ch in "([":
            depth += 1
            if depth > _MAX_PAREN_DEPTH:
                raise _reject("expression nesting depth exceeds limit")
        elif ch in ")]":
            depth -= 1
    for num in _NUMBER_RE.findall(text):
        if len(num) > _MAX_NUMBER_DIGITS:
            raise _reject("numeric literal exceeds digit limit")
    for ident in set(_IDENT_RE.findall(text)):
        if ident in _BANNED_KEYWORDS:
            raise _reject(f"identifier '{ident}' is not allowed")


def _validate_identifiers(
    text: str, allowed_symbols: set[str] | None, extra_names: set[str]
) -> set[str]:
    """Validate identifiers and return the set of symbol names to declare explicitly."""
    symbol_names: set[str] = set()
    for ident in set(_IDENT_RE.findall(text)):
        if ident in _ALLOWED_FUNCTIONS or ident in _ALLOWED_CONSTANTS or ident in _PARSE_HELPERS:
            continue
        if ident in extra_names:
            continue
        if not _SAFE_VAR_RE.match(ident):
            raise _reject(f"identifier '{ident}' is not a valid variable name")
        if allowed_symbols is not None and ident not in allowed_symbols:
            raise _reject(f"identifier '{ident}' is not a declared variable; declare it explicitly")
        symbol_names.add(ident)
    return symbol_names


def _structural_screen(expr: Any, limits: Limits, allowed_undef: set[str]) -> None:
    if isinstance(expr, sp.Basic):
        free: set[Any] = getattr(expr, "free_symbols", set())
        if len(free) > limits.max_variables:
            raise _reject(
                f"expression uses {len(free)} variables, exceeds limit {limits.max_variables}"
            )
        for index, _node in enumerate(sp.preorder_traversal(expr), start=1):
            if index > limits.max_expression_nodes:
                raise _reject("expression node count exceeds limit")
        for func in expr.atoms(AppliedUndef):
            if type(func).__name__ not in allowed_undef:
                raise _reject(f"undefined function '{type(func).__name__}' is not allowed")
        for func in expr.atoms(sp.Function):
            name = type(func).__name__
            if isinstance(func, AppliedUndef):
                continue
            if name not in _ALLOWED_FUNCTION_CLASSES:
                raise _reject(f"function '{name}' is not in the whitelist")
        for power in expr.atoms(sp.Pow):
            exponent = power.exp
            if exponent.is_number and exponent.is_finite:
                try:
                    if abs(float(exponent)) > _MAX_ABS_EXPONENT:
                        raise _reject("exponent magnitude exceeds limit")
                except (TypeError, ValueError):
                    pass


def parse_expression(
    text: str,
    *,
    limits: Limits | None = None,
    allowed_symbols: set[str] | None = None,
    extra_functions: dict[str, Any] | None = None,
) -> Any:
    """Parse ``text`` into a SymPy expression, rejecting anything outside the whitelist.

    ``allowed_symbols`` restricts which free variables may appear (others are rejected);
    when ``None``, any safe variable name is auto-created as a :class:`~sympy.Symbol`.
    """
    if not isinstance(text, str):
        raise _reject("expression must be a string")
    limits = limits or Limits()
    if len(text) == 0:
        raise _reject("expression is empty")
    if len(text) > limits.max_expression_chars:
        raise _reject(f"expression length {len(text)} exceeds limit {limits.max_expression_chars}")

    _pre_screen(text)
    extra_names = set(extra_functions) if extra_functions else set()
    symbol_names = _validate_identifiers(text, allowed_symbols, extra_names)
    local_dict = _build_local_dict(symbol_names, extra_functions)
    global_dict: dict[str, Any] = {"__builtins__": {}}
    transformations = standard_transformations

    try:
        screened = parse_expr(
            text,
            local_dict=local_dict,
            global_dict=global_dict,
            transformations=transformations,
            evaluate=False,
        )
    except ParseRejected:
        raise
    except Exception as exc:  # noqa: BLE001 - any parse failure is a rejection
        raise _reject(f"could not parse expression: {type(exc).__name__}") from exc

    _structural_screen(screened, limits, extra_names)

    try:
        expr = parse_expr(
            text,
            local_dict=local_dict,
            global_dict=global_dict,
            transformations=transformations,
            evaluate=True,
        )
    except ParseRejected:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _reject(f"could not parse expression: {type(exc).__name__}") from exc

    # Cheap re-check after canonicalization.
    if isinstance(expr, sp.Basic):
        for func in expr.atoms(AppliedUndef):
            if type(func).__name__ not in extra_names:
                raise _reject(f"undefined function '{type(func).__name__}' is not allowed")
    return expr


def parse_symbol(name: str) -> Any:
    """Parse and return a single SymPy Symbol from a validated variable name."""
    if not _SAFE_VAR_RE.match(name):
        raise _reject(f"'{name}' is not a valid variable name")
    return sp.Symbol(name)


# ---------------------------------------------------------------------------
# Structured AST input (the long-term primary interface for high-risk ops).
# ---------------------------------------------------------------------------

_AST_BINARY = {"add": sp.Add, "mul": sp.Mul}
_AST_REL = {
    "eq": sp.Eq,
    "ne": sp.Ne,
    "lt": sp.Lt,
    "le": sp.Le,
    "gt": sp.Gt,
    "ge": sp.Ge,
}
_AST_BOOL = {"and": sp.And, "or": sp.Or, "not": sp.Not, "implies": sp.Implies}
_MAX_AST_DEPTH = 64


def expr_from_ast(
    node: Any,
    *,
    limits: Limits | None = None,
    allowed_symbols: set[str] | None = None,
) -> Any:
    """Convert a structured ``expr_ast`` JSON node into a SymPy expression.

    Even though AST input bypasses the string tokenizer, it is validated just as
    strictly: node type whitelist, bounded depth/count, variable-name whitelist, and the
    same function whitelist as the string parser.
    """
    limits = limits or Limits()
    counter = {"n": 0}
    expr = _ast_node(node, limits, allowed_symbols, 0, counter)
    _structural_screen(expr, limits, set())
    return expr


def _ast_node(
    node: Any, limits: Limits, allowed: set[str] | None, depth: int, counter: dict[str, int]
) -> Any:
    if depth > _MAX_AST_DEPTH:
        raise InvalidAst("AST nesting depth exceeds limit")
    counter["n"] += 1
    if counter["n"] > limits.max_expression_nodes:
        raise InvalidAst("AST node count exceeds limit")
    if not isinstance(node, dict):
        raise InvalidAst(f"AST node must be an object, got {type(node).__name__}")

    if "int" in node:
        return sp.Integer(int(node["int"]))
    if "float" in node:
        return sp.Float(str(node["float"]))
    if "rational" in node:
        value = node["rational"]
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return sp.Rational(int(value[0]), int(value[1]))
        return sp.Rational(str(value))
    if "const" in node:
        name = str(node["const"])
        if name not in _ALLOWED_CONSTANTS:
            raise InvalidAst(f"unknown constant '{name}'")
        return _ALLOWED_CONSTANTS[name]
    if "var" in node or "symbol" in node:
        name = str(node.get("var", node.get("symbol")))
        if not _SAFE_VAR_RE.match(name):
            raise InvalidAst(f"invalid variable name '{name}'")
        if allowed is not None and name not in allowed:
            raise InvalidAst(f"variable '{name}' is not declared")
        return sp.Symbol(name)

    def child(key: str) -> Any:
        return _ast_node(node[key], limits, allowed, depth + 1, counter)

    def children() -> list[Any]:
        args = node.get("args", [])
        if not isinstance(args, list):
            raise InvalidAst("'args' must be a list")
        return [_ast_node(a, limits, allowed, depth + 1, counter) for a in args]

    op = node.get("op")
    if op is not None:
        if op in _AST_BINARY:
            return _AST_BINARY[op](*children())
        if op == "sub":
            return child("left") - child("right")
        if op == "div":
            return child("left") / child("right")
        if op == "pow":
            if "args" in node:
                base, exponent = children()
                return sp.Pow(base, exponent)
            return sp.Pow(child("left"), child("right"))
        if op == "neg":
            return -child("arg") if "arg" in node else -children()[0]
        if op in _AST_REL:
            return _AST_REL[op](child("left"), child("right"))
        if op in _AST_BOOL:
            if op == "not":
                return sp.Not(child("arg") if "arg" in node else children()[0])
            return _AST_BOOL[op](*children())
        raise InvalidAst(f"unknown AST op '{op}'")

    if "func" in node:
        name = str(node["func"])
        if name not in _ALLOWED_FUNCTIONS:
            raise InvalidAst(f"function '{name}' is not in the whitelist")
        return _ALLOWED_FUNCTIONS[name](*children())

    raise InvalidAst(f"unrecognized AST node keys: {sorted(node.keys())}")


def load_expression(
    payload: dict[str, Any],
    *,
    str_key: str = "expression",
    ast_key: str = "expr_ast",
    limits: Limits | None = None,
    allowed_symbols: set[str] | None = None,
) -> Any:
    """Load an expression from a payload, preferring structured AST over a string.

    This is the single entry point handlers use so that every operation transparently
    accepts both the convenience string form and the safer ``expr_ast`` form.
    """
    if payload.get(ast_key) is not None:
        return expr_from_ast(payload[ast_key], limits=limits, allowed_symbols=allowed_symbols)
    if str_key in payload and payload[str_key] is not None:
        return parse_expression(
            str(payload[str_key]), limits=limits, allowed_symbols=allowed_symbols
        )
    raise ParseRejected(f"payload is missing '{str_key}' or '{ast_key}'")
