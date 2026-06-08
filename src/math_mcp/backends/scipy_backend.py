"""SciPy-backed numeric helpers: local optimization and numeric ODE integration.

These are numeric and initial-value dependent; results are evidence, not proofs.
"""

from __future__ import annotations

from typing import Any

import sympy as sp


def optimize_expression(
    expr: Any, variables: list[str], goal: str, start: list[float] | None
) -> dict[str, Any]:
    """Locally minimize/maximize a scalar expression numerically (evidence only)."""
    import numpy as np  # noqa: PLC0415
    from scipy.optimize import minimize  # noqa: PLC0415

    symbols = [sp.Symbol(v) for v in variables]
    func = sp.lambdify(symbols, expr, modules="numpy")
    sign = -1.0 if goal == "max" else 1.0

    def objective(point: Any) -> float:
        return float(sign * func(*point))

    x0 = np.array(start, dtype=float) if start else np.zeros(len(variables))
    result = minimize(objective, x0, method="Nelder-Mead")
    optimum = {v: float(x) for v, x in zip(variables, result.x, strict=False)}
    return {
        "converged": bool(result.success),
        "point": optimum,
        "value": float(sign * result.fun),
        "iterations": int(result.nit),
    }


def optimize_constrained(
    expr: Any,
    variables: list[str],
    goal: str,
    constraints: list[dict[str, Any]],
    start: list[float] | None,
) -> dict[str, Any]:
    """Numerically optimize ``expr`` subject to equality/inequality constraints (evidence).

    Each constraint is ``{"relation", "left", "right"}`` with SymPy expressions; it is
    turned into the SciPy form (equality ``g == 0`` or inequality ``g >= 0``). The result
    reports the optimum, objective value, per-constraint residuals, and convergence — it
    is a numeric local search, never a proof of global optimality.
    """
    import numpy as np  # noqa: PLC0415
    from scipy.optimize import minimize  # noqa: PLC0415

    symbols = [sp.Symbol(v) for v in variables]
    obj = sp.lambdify(symbols, expr, modules="numpy")
    sign = -1.0 if goal == "max" else 1.0

    def objective(point: Any) -> float:
        return float(sign * obj(*point))

    scipy_cons = []
    residual_funcs: list[tuple[str, Any]] = []
    for c in constraints:
        relation = c["relation"]
        g = sp.lambdify(symbols, c["left"] - c["right"], modules="numpy")
        residual_funcs.append((relation, g))
        if relation == "==":
            scipy_cons.append({"type": "eq", "fun": (lambda p, g=g: float(g(*p)))})
        elif relation in (">=", ">"):
            scipy_cons.append({"type": "ineq", "fun": (lambda p, g=g: float(g(*p)))})
        elif relation in ("<=", "<"):
            scipy_cons.append({"type": "ineq", "fun": (lambda p, g=g: float(-g(*p)))})
        else:
            raise ValueError(f"unsupported constraint relation '{relation}'")

    x0 = np.array(start, dtype=float) if start else np.zeros(len(variables))
    result = minimize(objective, x0, method="SLSQP", constraints=scipy_cons)
    point = {v: float(x) for v, x in zip(variables, result.x, strict=False)}
    residuals = [{"relation": rel, "residual": float(g(*result.x))} for rel, g in residual_funcs]
    return {
        "converged": bool(result.success),
        "point": point,
        "value": float(sign * result.fun),
        "constraint_residuals": residuals,
        "iterations": int(result.nit),
        "start": x0.tolist(),
    }


def solve_ode_numeric(
    rhs_expr: Any,
    t_var: str,
    y_var: str,
    t_span: tuple[float, float],
    y0: list[float],
    points: int,
) -> dict[str, Any]:
    """Integrate y' = f(t, y) numerically over t_span (evidence only)."""
    import numpy as np  # noqa: PLC0415
    from scipy.integrate import solve_ivp  # noqa: PLC0415

    t_sym, y_sym = sp.Symbol(t_var), sp.Symbol(y_var)
    func = sp.lambdify((t_sym, y_sym), rhs_expr, modules="numpy")

    def rhs(t: float, y: Any) -> list[float]:
        return [float(func(t, y[0]))]

    t_eval = np.linspace(t_span[0], t_span[1], max(2, points))
    sol = solve_ivp(rhs, t_span, [y0[0]], t_eval=t_eval)
    if not sol.success:
        raise RuntimeError("numeric ODE integration failed to converge")
    return {
        "t": sol.t.tolist(),
        "y": sol.y[0].tolist(),
        "converged": bool(sol.success),
    }
