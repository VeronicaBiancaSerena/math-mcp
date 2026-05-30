"""Analytic geometry: distances, intersections, lines, circles, polygons, transforms."""

from __future__ import annotations

from typing import Any

import sympy as sp

from math_mcp.errors import InvalidInput
from math_mcp.parsing.sympy_parser import parse_expression
from math_mcp.runtime.serialization import to_latex, to_text
from math_mcp.tools.base import Ctx, Outcome, object_result, solution_set_result, value_result
from math_mcp.tools.dispatch import handler

_X, _Y = sp.symbols("x y")


def _num(ctx: Ctx, raw: Any) -> Any:
    return parse_expression(str(raw), limits=ctx.limits)


def _point(ctx: Ctx, raw: Any) -> tuple[Any, Any]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise InvalidInput("a point must be a list [x, y]")
    return _num(ctx, raw[0]), _num(ctx, raw[1])


@handler("geometry_compute", "geometry_distance")
def geometry_distance(ctx: Ctx) -> Outcome:
    kind = str(ctx.require("kind"))
    if kind == "point_point":
        (x1, y1) = _point(ctx, ctx.require("point"))
        (x2, y2) = _point(ctx, ctx.require("point2"))
        dist = sp.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    elif kind == "point_line":
        (px, py) = _point(ctx, ctx.require("point"))
        line = ctx.require("line")
        a, b, c = _num(ctx, line["a"]), _num(ctx, line["b"]), _num(ctx, line["c"])
        dist = sp.Abs(a * px + b * py + c) / sp.sqrt(a**2 + b**2)
    elif kind == "point_circle":
        (px, py) = _point(ctx, ctx.require("point"))
        circle = ctx.require("circle")
        (cx, cy) = _point(ctx, circle["center"])
        r = _num(ctx, circle["radius"])
        dist = sp.Abs(sp.sqrt((px - cx) ** 2 + (py - cy) ** 2) - r)
    else:
        raise InvalidInput(f"unsupported distance kind '{kind}'")
    dist = sp.simplify(dist)
    return value_result(dist, latex=to_latex(dist), certainty="exact", method="symbolic")


def _object_equation(ctx: Ctx, obj: Any) -> Any:
    kind = str(obj.get("type", "line"))
    if kind == "line":
        a, b, c = _num(ctx, obj["a"]), _num(ctx, obj["b"]), _num(ctx, obj["c"])
        return a * _X + b * _Y + c
    if kind == "circle":
        (h, k) = _point(ctx, obj["center"])
        r = _num(ctx, obj["radius"])
        return (_X - h) ** 2 + (_Y - k) ** 2 - r**2
    if kind == "conic":
        return parse_expression(
            str(obj["expression"]), limits=ctx.limits, allowed_symbols={"x", "y"}
        )
    raise InvalidInput(f"unsupported geometry object type '{kind}'")


@handler("geometry_compute", "geometry_intersection")
def geometry_intersection(ctx: Ctx) -> Outcome:
    eq1 = _object_equation(ctx, ctx.require("object1"))
    eq2 = _object_equation(ctx, ctx.require("object2"))
    solutions = sp.solve([eq1, eq2], [_X, _Y], dict=True)
    points = [
        {"x": to_text(sol[_X]), "y": to_text(sol[_Y])}
        for sol in solutions
        if _X in sol and _Y in sol
    ]
    return solution_set_result(points, certainty="exact", method="symbolic")


@handler("geometry_compute", "line_analyze")
def line_analyze(ctx: Ctx) -> Outcome:
    line1 = ctx.require("line1")
    a1, b1, c1 = _num(ctx, line1["a"]), _num(ctx, line1["b"]), _num(ctx, line1["c"])
    info: dict[str, Any] = {
        "slope": to_text(sp.simplify(-a1 / b1)) if b1 != 0 else "undefined (vertical)",
        "y_intercept": to_text(sp.simplify(-c1 / b1)) if b1 != 0 else None,
    }
    line2 = ctx.get("line2")
    if line2 is not None:
        a2, b2 = _num(ctx, line2["a"]), _num(ctx, line2["b"])
        info["parallel"] = bool(sp.simplify(a1 * b2 - a2 * b1) == 0)
        info["perpendicular"] = bool(sp.simplify(a1 * a2 + b1 * b2) == 0)
    return object_result(info, certainty="exact", method="symbolic")


@handler("geometry_compute", "circle_analyze")
def circle_analyze(ctx: Ctx) -> Outcome:
    circle = ctx.require("circle")
    (cx, cy) = _point(ctx, circle["center"])
    r = _num(ctx, circle["radius"])
    info = {
        "center": [to_text(cx), to_text(cy)],
        "radius": to_text(r),
        "area": to_text(sp.simplify(sp.pi * r**2)),
        "circumference": to_text(sp.simplify(2 * sp.pi * r)),
    }
    return object_result(info, certainty="exact", method="symbolic")


@handler("geometry_compute", "polygon_analyze")
def polygon_analyze(ctx: Ctx) -> Outcome:
    vertices = ctx.require("vertices")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise InvalidInput("polygon requires at least 3 vertices")
    points = [sp.Point(*_point(ctx, v)) for v in vertices]
    poly = sp.Polygon(*points)
    if not isinstance(poly, sp.Polygon):
        raise InvalidInput("degenerate polygon")
    centroid = poly.centroid
    info = {
        "area": to_text(sp.Abs(poly.area)),
        "perimeter": to_text(poly.perimeter),
        "centroid": [to_text(centroid.x), to_text(centroid.y)],
        "is_convex": bool(poly.is_convex()),
    }
    return object_result(info, certainty="exact", method="symbolic")


@handler("geometry_compute", "coordinate_transform")
def coordinate_transform(ctx: Ctx) -> Outcome:
    kind = str(ctx.require("kind"))
    (px, py) = _point(ctx, ctx.require("point"))
    if kind == "translate":
        dx, dy = _num(ctx, ctx.get("dx", "0")), _num(ctx, ctx.get("dy", "0"))
        result: Any = [to_text(px + dx), to_text(py + dy)]
    elif kind == "rotate":
        angle = _num(ctx, ctx.require("angle"))
        nx = px * sp.cos(angle) - py * sp.sin(angle)
        ny = px * sp.sin(angle) + py * sp.cos(angle)
        result = [to_text(sp.simplify(nx)), to_text(sp.simplify(ny))]
    elif kind == "to_polar":
        r = sp.sqrt(px**2 + py**2)
        theta = sp.atan2(py, px)
        result = {"r": to_text(sp.simplify(r)), "theta": to_text(sp.simplify(theta))}
    elif kind == "to_cartesian":
        r, theta = px, py
        result = {
            "x": to_text(sp.simplify(r * sp.cos(theta))),
            "y": to_text(sp.simplify(r * sp.sin(theta))),
        }
    else:
        raise InvalidInput(f"unsupported transform kind '{kind}'")
    return object_result(result, certainty="exact", method="symbolic", result_kind="object")


@handler("geometry_compute", "conic_analyze")
def conic_analyze(ctx: Ctx) -> Outcome:
    expr = parse_expression(
        ctx.require_str("expression"), limits=ctx.limits, allowed_symbols={"x", "y"}
    )
    poly = sp.Poly(expr, _X, _Y)
    coeffs = {str(m): to_text(c) for m, c in zip(poly.monoms(), poly.coeffs(), strict=False)}
    a = poly.coeff_monomial(_X**2)
    b = poly.coeff_monomial(_X * _Y)
    c = poly.coeff_monomial(_Y**2)
    discriminant = sp.simplify(b**2 - 4 * a * c)
    if discriminant < 0:
        kind = "circle" if a == c and b == 0 else "ellipse"
    elif discriminant == 0:
        kind = "parabola"
    else:
        kind = "hyperbola"
    return object_result(
        {"type": kind, "discriminant": to_text(discriminant), "coefficients": coeffs},
        certainty="exact",
        method="symbolic",
    )
