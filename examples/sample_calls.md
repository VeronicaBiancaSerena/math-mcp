# Sample math-mcp calls

Every call goes through a domain-level public tool with the stable shape
`{operation, payload, domains?, assumptions?, limits?}`. Expressions use SymPy-style
syntax (not LaTeX). These examples mirror the acceptance scenarios; they validate that an
agent selects the right tool and operation.

## 1. Identity proof — `sin(x)^2 + cos(x)^2 = 1`
```json
{"tool": "verification_compute",
 "args": {"operation": "check_identity",
          "payload": {"left": "sin(x)**2 + cos(x)**2", "right": "1", "variables": ["x"]}}}
```
→ `certainty=proved`, `method=symbolic`, certificate `symbolic_simplification`.

## 2. Equation solving — `x^2 - 5x + 6 = 0`
```json
{"tool": "algebra_compute",
 "args": {"operation": "solve_equation", "payload": {"expression": "x**2 - 5*x + 6", "variable": "x"}}}
```
→ `result=["2","3"]`, `certainty=exact`.

## 3. Counterexample search — `x^2 >= x` on `[0,1]`
```json
{"tool": "verification_compute",
 "args": {"operation": "search_counterexample",
          "payload": {"left": "x**2", "relation": ">=", "right": "x", "variables": ["x"]},
          "domains": [{"variable": "x", "kind": "real", "lower": "0", "upper": "1"}]}}
```
→ `certainty=disproved`, witness e.g. `x=1/2`.

## 4. Matrix determinant — `[[1,2],[3,4]]`
```json
{"tool": "matrix_compute", "args": {"operation": "det", "payload": {"matrix": [["1","2"],["3","4"]]}}}
```
→ `result="-2"`.

## 5. Z3 constraints — positive ints `x+y=10`, `x>y`
```json
{"tool": "z3_compute",
 "args": {"operation": "z3_satisfiability",
          "payload": {"variables": {"x": "Int", "y": "Int"},
                      "constraints": [{"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
                                      {"op": "gt", "left": {"var": "y"}, "right": {"int": 0}},
                                      {"op": "eq", "left": {"op": "add", "args": [{"var": "x"}, {"var": "y"}]}, "right": {"int": 10}},
                                      {"op": "gt", "left": {"var": "x"}, "right": {"var": "y"}}]}}}
```
→ satisfiable with a model such as `x=6, y=4`.

## 6. Series expansion — `exp(x)` to 5th order
```json
{"tool": "calculus_compute",
 "args": {"operation": "series_expand", "payload": {"expression": "exp(x)", "variable": "x", "point": "0", "order": 5}}}
```

## 7. Groebner basis (experimental — needs `include_experimental`)
```json
{"tool": "algebra_compute",
 "args": {"operation": "groebner_basis", "payload": {"polynomials": ["x**2 + y**2 - 1", "x - y"], "variables": ["x", "y"]}}}
```

## 8. Shortest path — three-node path
```json
{"tool": "graph_compute",
 "args": {"operation": "shortest_path",
          "payload": {"directed": false, "nodes": ["A","B","C"], "edges": [["A","B"],["B","C"]], "source": "A", "target": "C"}}}
```

## 9. Combinatorics — `C(10,3)`
```json
{"tool": "discrete_compute", "args": {"operation": "combinatorics_count", "payload": {"kind": "combination", "n": "10", "k": "3"}}}
```

## 10. Numeric optimization (experimental)
```json
{"tool": "calculus_compute",
 "args": {"operation": "numeric_optimize", "payload": {"expression": "(x-3)**2 + 2", "variables": ["x"], "goal": "min"}}}
```
→ `certainty=evidence` (numeric, not a proof).

## 11. Probability — at least one head in two fair coins
```json
{"tool": "probability_compute",
 "args": {"operation": "event_probability",
          "payload": {"mode": "uniform_finite", "condition": "(a > 0) | (b > 0)", "variables": ["a", "b"]},
          "domains": [{"variable": "a", "kind": "finite", "values": ["0","1"]},
                      {"variable": "b", "kind": "finite", "values": ["0","1"]}]}}
```
→ `result="3/4"`.

## 12. Bayesian update
```json
{"tool": "probability_compute",
 "args": {"operation": "bayes_update", "payload": {"prior": "1/100", "likelihood": "9/10", "false_likelihood": "1/10"}}}
```

## 13. Set identity — distributive law
```json
{"tool": "set_compute",
 "args": {"operation": "set_identity_check", "payload": {"left": "A & (B | C)", "right": "(A & B) | (A & C)", "variables": ["A","B","C"]}}}
```

## 14. Interval algebra — `[0,2] ∩ (1,3]`
```json
{"tool": "set_compute",
 "args": {"operation": "interval_compute",
          "payload": {"kind": "intersection",
                      "a": {"lower": "0", "upper": "2", "lower_closed": true, "upper_closed": true},
                      "b": {"lower": "1", "upper": "3", "lower_closed": false, "upper_closed": true}}}}
```

## 15. Analytic geometry — distance from `(1,2)` to `3x+4y-5=0`
```json
{"tool": "geometry_compute",
 "args": {"operation": "geometry_distance", "payload": {"kind": "point_line", "point": ["1","2"], "line": {"a": "3", "b": "4", "c": "-5"}}}}
```
→ `result="6/5"`.

## 16. Trig identity — `sin(2x) = 2 sin x cos x`
```json
{"tool": "trigonometry_compute",
 "args": {"operation": "trig_identity_check", "payload": {"left": "sin(2*x)", "right": "2*sin(x)*cos(x)", "variables": ["x"]}}}
```

## 17. Number theory — inverse of 17 mod 43
```json
{"tool": "number_theory_compute",
 "args": {"operation": "modular_arithmetic", "payload": {"kind": "inverse", "a": "17", "modulus": "43"}}}
```
→ `result=38`.

## 18. Logic — `(p -> q) ≡ (~p or q)`
```json
{"tool": "logic_compute",
 "args": {"operation": "logic_equivalence_check", "payload": {"left": "p >> q", "right": "~p | q", "variables": ["p","q"]}}}
```

## 19. ODE — verify `y = C*exp(x)` solves `y' = y`
```json
{"tool": "ode_compute",
 "args": {"operation": "ode_verify_solution", "payload": {"solution": "C*exp(x)", "variable": "x", "residual": "dy - y", "parameters": ["C"]}}}
```
(`y`, `dy`, `d2y`, `d3y` denote the solution and its derivatives.)

## 20. Complex — modulus and argument of `1 + I`
```json
{"tool": "complex_compute", "args": {"operation": "complex_mod_arg", "payload": {"expression": "1 + I"}}}
```
→ modulus `sqrt(2)`, argument `pi/4`.

## 21. Inequality — solve `x^2 - 1 >= 0`
```json
{"tool": "inequality_compute",
 "args": {"operation": "inequality_domain_solve", "payload": {"expression": "x**2 - 1", "relation": ">=", "variable": "x"}}}
```
→ `(-oo, -1] ∪ [1, oo)`.
