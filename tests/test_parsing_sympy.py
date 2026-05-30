"""Tests for the safe SymPy parser and structured AST loader, with property tests."""

from __future__ import annotations

import pytest
import sympy as sp
from hypothesis import given, settings
from hypothesis import strategies as st

from math_mcp.errors import InvalidAst, ParseRejected
from math_mcp.parsing.sympy_parser import expr_from_ast, load_expression, parse_expression
from math_mcp.schemas import Limits


def test_parse_basic() -> None:
    assert parse_expression("sin(x)**2 + cos(x)**2 - 1") is not None


def test_allowed_symbols_restriction() -> None:
    parse_expression("x + 1", allowed_symbols={"x"})
    with pytest.raises(ParseRejected):
        parse_expression("x + y", allowed_symbols={"x"})


def test_node_limit() -> None:
    limits = Limits(max_expression_nodes=5)
    with pytest.raises(ParseRejected):
        parse_expression("a + b + c + d + e + f + g", limits=limits, allowed_symbols=None)


def test_undefined_function_rejected() -> None:
    with pytest.raises(ParseRejected):
        parse_expression("y(x) + 1")


def test_ast_round_trip() -> None:
    expr = expr_from_ast({"op": "add", "args": [{"var": "x"}, {"int": 1}]})
    assert expr == sp.Symbol("x") + 1


def test_ast_rejects_unknown_op() -> None:
    with pytest.raises(InvalidAst):
        expr_from_ast({"op": "wat", "args": [{"int": 1}]})


def test_ast_rejects_unknown_function() -> None:
    with pytest.raises(InvalidAst):
        expr_from_ast({"func": "system", "args": [{"int": 1}]})


def test_load_expression_prefers_ast() -> None:
    expr = load_expression(
        {"expression": "x", "expr_ast": {"op": "mul", "args": [{"var": "x"}, {"int": 2}]}}
    )
    assert expr == 2 * sp.Symbol("x")


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=-50, max_value=50), st.integers(min_value=-50, max_value=50))
def test_parse_serialize_parse_stable(a: int, b: int) -> None:
    text = f"{a}*x + {b}"
    first = parse_expression(text, allowed_symbols={"x"})
    from math_mcp.runtime.serialization import to_text

    second = parse_expression(to_text(first), allowed_symbols={"x"})
    assert sp.simplify(first - second) == 0


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=65, max_value=200))
def test_deep_nesting_is_rejected(depth: int) -> None:
    # Deeply nested parentheses must trip the depth/node guard (guide §15.4), never blow
    # the recursion stack or reach the backend.
    text = "(" * depth + "x" + ")" * depth
    with pytest.raises(ParseRejected):
        parse_expression(text, allowed_symbols={"x"})


@settings(max_examples=30, deadline=None)
@given(st.lists(st.sampled_from(["__", "import", "lambda", "eval", "globals"]), min_size=1))
def test_dangerous_tokens_rejected(tokens: list[str]) -> None:
    # Any expression carrying a banned token/dunder is rejected (guide §15.4 fuzz).
    text = "x + " + " + ".join(tokens)
    with pytest.raises(ParseRejected):
        parse_expression(text, allowed_symbols={"x"})


@settings(max_examples=40, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=20), min_size=0, max_size=6, unique=True),
    st.lists(st.integers(min_value=0, max_value=20), min_size=0, max_size=6, unique=True),
)
def test_set_algebra_laws(a: list[int], b: list[int]) -> None:
    sa, sb = set(a), set(b)
    # commutativity and idempotence of finite-set operations
    assert sa | sb == sb | sa
    assert sa & sb == sb & sa
    assert sa | sa == sa
