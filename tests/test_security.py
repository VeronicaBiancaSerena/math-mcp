"""Security tests for the safe expression parser, including property-based fuzzing."""

from __future__ import annotations

import contextlib

import pytest
from conftest import call
from hypothesis import given, settings
from hypothesis import strategies as st

from math_mcp.errors import ParseRejected
from math_mcp.parsing.sympy_parser import parse_expression

MALICIOUS = [
    '__import__("os").system("id")',
    'open("/etc/passwd").read()',
    "globals()",
    "locals()",
    "lambda x: x",
    "().__class__",
    "sympy.__dict__",
    "http://example.com",
    'eval("1+1")',
    "exec('x=1')",
    "getattr(x, 'y')",
    "x.__class__.__bases__",
]


@pytest.mark.parametrize("evil", MALICIOUS)
def test_malicious_expressions_rejected(evil: str) -> None:
    with pytest.raises(ParseRejected):
        parse_expression(evil)


@pytest.mark.parametrize("evil", MALICIOUS)
def test_malicious_via_tool_is_invalid_input(evil: str) -> None:
    result = call("algebra_compute", "simplify_expression", {"expression": evil})
    assert result.ok is False
    assert result.status in ("invalid_input", "unsupported")


def test_dunder_rejected() -> None:
    with pytest.raises(ParseRejected):
        parse_expression("x.__class__")


def test_huge_exponent_rejected() -> None:
    with pytest.raises(ParseRejected):
        parse_expression("2**100000000")


def test_overlong_expression_rejected() -> None:
    with pytest.raises(ParseRejected):
        parse_expression("1+" * 5000 + "1")


def test_normal_expressions_accepted() -> None:
    for ok in [
        "sin(x)**2 + cos(x)**2",
        "(x**2 - 1)/(x - 1)",
        "exp(x)",
        "sqrt(x + 1)",
        "Rational(1, 3)",
        "1 + I",
    ]:
        parse_expression(ok)


@settings(max_examples=150, deadline=None)
@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789(). +-*/", max_size=40))
def test_fuzz_parser_never_executes(text: str) -> None:
    # Whatever the input, the parser either returns a SymPy object or raises
    # ParseRejected — it must never execute code or raise an unexpected exception.
    with contextlib.suppress(ParseRejected):
        parse_expression(text)


@settings(max_examples=60, deadline=None)
@given(st.text(alphabet="abcdefghijklmnop0123456789", max_size=8).map(lambda s: f"{s}__{s}"))
def test_fuzz_dunder_always_rejected(text: str) -> None:
    with pytest.raises(ParseRejected):
        parse_expression(text)
