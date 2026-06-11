# math-mcp

[日本語版](README.ja.md) | [License](LICENSE)

`math-mcp` is a local, offline, auditable Model Context Protocol (MCP) server for mathematical computation and verification.

It is designed for LLM agents that need reliable mathematical tools without giving those tools the whole reasoning task. The agent decomposes the problem, chooses operations, and writes the final explanation; `math-mcp` performs bounded symbolic, numeric, finite, graph, probability, SMT, and verification work, then returns structured results with an explicit certainty level.

```text
LLM / agent  -> decompose, plan, choose operations, explain
math-mcp     -> compute, verify, search for counterexamples, solve constraints,
                return structured results with proof/evidence metadata
```

## Why this exists

LLMs are good at planning and exposition, but they can make arithmetic mistakes, confuse proof with evidence, or over-trust numeric samples. `math-mcp` gives an agent a disciplined local math workbench:

- exact symbolic computation where possible;
- SMT/UNSAT, finite exhaustion, and symbolic simplification when a strict proof is available;
- counterexample search when a claim is false;
- numeric or simulation output that is clearly labeled as evidence, never as proof;
- stable machine-readable errors so an agent can recover from bad operation names, schema mistakes, unsupported domains, timeouts, and resource limits.

## Highlights

- Local stdio MCP server: no hosted service is required.
- Offline at runtime: no web search, no downloads, no database, no RAG.
- Linux-only production boundary with high-risk operations isolated by `bubblewrap`.
- 18 public MCP tools: 2 utility tools and 16 domain-level compute tools.
- 99 implemented operations in the registry, all discoverable through `math_capabilities`.
- Single source of truth: `src/math_mcp/operation_registry.py` drives capabilities, routing, tests, and examples.
- Unified result envelope with `status`, `certainty`, `method`, `result_kind`, `conditions`, `certificate`, `error_code`, and metadata.
- SymPy-style expression strings for agent ergonomics, plus structured ASTs for Z3 and selected high-risk paths.
- Strict separation between proof, disproof, exact computation, numeric evidence, unknown, and error.
- CI quality gate with `ruff`, `mypy`, `pytest`, registry/conformance tests, error-code coverage, sandbox tests, golden cases, and agent eval cases.

## What it is not

`math-mcp` deliberately does not try to be a natural-language math solver.

It does not provide:

- `solve_math_problem(problem: str)` style black-box solving;
- LaTeX parsing;
- arbitrary Python execution;
- network tools or document readers;
- theorem-prover integration with Lean, Coq, Isabelle, SageMath, or Mathematica;
- a database, memory store, or RAG pipeline;
- a multi-user HTTP service or web UI.

If a problem is written in natural language or LaTeX, the agent should translate the relevant mathematical expressions into the supported structured input before calling the MCP server.

## Requirements

Production use is intentionally narrow:

- Linux;
- Python 3.11;
- conda or another environment manager capable of installing the scientific stack;
- `bubblewrap` for sandboxed high-risk operations;
- MCP Python SDK v1.x (`mcp[cli]>=1.25,<2`).

The conda environment is named `math-mcp` and is defined in `environment.yml`.

On Debian/Ubuntu, install the OS sandbox dependency with:

```bash
sudo apt-get update
sudo apt-get install -y bubblewrap
```

If `bubblewrap` or Linux isolation is unavailable, high-risk operations return structured errors such as `SANDBOX_UNAVAILABLE` or `PLATFORM_UNSUPPORTED` instead of silently running without isolation.

## Installation

```bash
git clone https://github.com/<owner>/math-mcp.git
cd math-mcp

conda env create -f environment.yml
conda activate math-mcp

pip install -e .
```

Using an editable install is recommended for local MCP clients because sandboxed workers run with isolated Python settings and need the package to be importable from the environment.

Start the stdio server:

```bash
python -m math_mcp
# or, after installation:
math-mcp
```

Run a local MCP smoke test:

```bash
python examples/mcp_client_smoke.py
```

## Connecting from an MCP client

Use the Python executable inside the `math-mcp` environment whenever possible:

```bash
/home/<user>/anaconda3/envs/math-mcp/bin/python -m math_mcp
```

Codex CLI example:

```bash
codex mcp add math-mcp -- /home/<user>/anaconda3/envs/math-mcp/bin/python -m math_mcp
```

Hermes Agent example:

```yaml
mcp_servers:
  math-mcp:
    command: "/home/<user>/anaconda3/envs/math-mcp/bin/python"
    args: ["-m", "math_mcp"]
    timeout: 120
    connect_timeout: 60
```

Claude Desktop-style example:

```json
{
  "mcpServers": {
    "math-mcp": {
      "command": "/home/<user>/anaconda3/envs/math-mcp/bin/python",
      "args": ["-m", "math_mcp"]
    }
  }
}
```

After connection, ask the client to call `math_capabilities(mode="summary")` first, then `math_capabilities(mode="full")` when it needs a concrete payload schema.

## Public tool surface

The server exposes domain-level tools. Concrete mathematical capabilities are selected with the `operation` argument.

Utility tools:

| Tool | Purpose |
| --- | --- |
| `ping` | Health check. |
| `math_capabilities` | Lists tools, operations, aliases, schemas, examples, limits, and release states. |

Compute tools:

| Public tool | Operations |
| --- | --- |
| `algebra_compute` | `simplify_expression`, `expand_expression`, `factor_expression`, `cancel_expression`, `together_expression`, `solve_equation`, `solve_system`, `polynomial_roots`, `groebner_basis` |
| `calculus_compute` | `differentiate`, `integrate`, `limit_expression`, `series_expand`, `numeric_evaluate`, `numeric_optimize`, `constrained_optimize` |
| `verification_compute` | `check_identity`, `check_inequality_sampled`, `search_counterexample`, `check_identity_constrained` |
| `z3_compute` | `z3_satisfiability`, `z3_find_counterexample` |
| `matrix_compute` | `det`, `rank`, `trace`, `transpose`, `inverse`, `rref`, `eigenvals`, `charpoly`, `solve_linear_system`, `matrix_decomposition_numeric` |
| `discrete_compute` | `combinatorics_count`, `finite_enumeration`, `solve_recurrence` |
| `graph_compute` | `is_connected`, `connected_components`, `has_cycle`, `maximum_matching`, `minimum_spanning_tree`, `topological_sort`, `shortest_path` |
| `probability_compute` | `event_probability`, `bayes_update`, `distribution_moments`, `probability_distribution`, `random_variable_transform`, `markov_chain_analyze`, `probability_simulation` |
| `set_compute` | `set_operations`, `set_membership`, `set_relation_check`, `set_identity_check`, `cartesian_product`, `power_set`, `interval_compute` |
| `geometry_compute` | `geometry_distance`, `geometry_intersection`, `line_analyze`, `circle_analyze`, `polygon_analyze`, `coordinate_transform`, `conic_analyze` |
| `trigonometry_compute` | `trig_simplify`, `trig_expand`, `trig_reduce`, `trig_rewrite`, `solve_trig_equation`, `trig_identity_check` |
| `number_theory_compute` | `gcd_lcm_bezout`, `prime_analyze`, `modular_arithmetic`, `congruence_solve`, `chinese_remainder`, `totient_compute`, `multiplicative_order`, `quadratic_residue_check` |
| `logic_compute` | `boolean_simplify`, `truth_table`, `logic_equivalence_check`, `logic_satisfiability`, `normal_form_convert`, `finite_quantifier_check` |
| `ode_compute` | `ode_verify_solution`, `ode_solve_symbolic`, `ode_classify`, `ode_initial_value_solve`, `ode_solve_numeric` |
| `complex_compute` | `complex_simplify`, `complex_mod_arg`, `complex_to_polar`, `complex_from_polar`, `complex_roots_of_unity`, `complex_equation_solve` |
| `inequality_compute` | `inequality_domain_solve`, `inequality_reduce`, `inequality_check_symbolic`, `inequality_counterexample_search`, `inequality_sample` |

The default capabilities response exposes implemented operations. Experimental or disabled operation states are supported by the registry model, but they are hidden from default discovery unless explicitly requested.

## Unified call shape

Every compute tool follows the same top-level shape:

```json
{
  "operation": "simplify_expression",
  "payload": {
    "expression": "sin(x)**2 + cos(x)**2 - 1",
    "variables": ["x"]
  },
  "domains": [],
  "assumptions": [],
  "limits": {
    "timeout_ms": 5000,
    "max_output_chars": 8000
  }
}
```

Important conventions:

- `operation` is the leaf operation name for that public tool.
- `payload` contains operation-specific fields only.
- `domains`, `assumptions`, and `limits` are top-level fields, not nested inside `payload`.
- Expressions use SymPy-style syntax such as `sin(x)**2`, not LaTeX such as `\sin^2 x`.
- Z3 tools use structured AST constraints, not Python or natural-language constraint strings.

## Examples

### Symbolic identity proof

```json
{
  "tool": "verification_compute",
  "args": {
    "operation": "check_identity",
    "payload": {
      "left": "sin(x)**2 + cos(x)**2",
      "right": "1",
      "variables": ["x"]
    }
  }
}
```

Expected result: `certainty="proved"`, `method="symbolic"`, with a symbolic-simplification certificate.

### Exact algebra

```json
{
  "tool": "algebra_compute",
  "args": {
    "operation": "solve_equation",
    "payload": {
      "expression": "x**2 - 5*x + 6",
      "variable": "x"
    }
  }
}
```

Expected result: exact roots `2` and `3`.

### Counterexample search on a bounded domain

```json
{
  "tool": "verification_compute",
  "args": {
    "operation": "search_counterexample",
    "payload": {
      "left": "x**2",
      "relation": ">=",
      "right": "x",
      "variables": ["x"],
      "samples": 1000
    },
    "domains": [
      {"variable": "x", "kind": "real", "lower": "0", "upper": "1"}
    ]
  }
}
```

Expected result: `certainty="disproved"` with a witness such as `x=1/2`.

### Finite exhaustive verification

```json
{
  "tool": "discrete_compute",
  "args": {
    "operation": "finite_enumeration",
    "payload": {
      "predicate": "Eq(x + y, 3)",
      "variables": ["x", "y"],
      "collect_witnesses": true
    },
    "domains": [
      {"variable": "x", "kind": "integer", "lower": "0", "upper": "3"},
      {"variable": "y", "kind": "integer", "lower": "0", "upper": "3"}
    ]
  }
}
```

Note that `domains` is top-level. If an agent puts `domains` inside `payload`, the tool returns a structured correction hint.

### Z3 satisfiability

```json
{
  "tool": "z3_compute",
  "args": {
    "operation": "z3_satisfiability",
    "payload": {
      "variables": {"x": "Int", "y": "Int"},
      "constraints": [
        {"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
        {"op": "gt", "left": {"var": "y"}, "right": {"int": 0}},
        {"op": "eq", "left": {"op": "add", "args": [{"var": "x"}, {"var": "y"}]}, "right": {"int": 10}},
        {"op": "gt", "left": {"var": "x"}, "right": {"var": "y"}}
      ]
    }
  }
}
```

Expected result: satisfiable, with a concrete model.

### Numeric optimization is evidence, not proof

```json
{
  "tool": "calculus_compute",
  "args": {
    "operation": "numeric_optimize",
    "payload": {
      "expression": "(x - 3)**2 + 2",
      "variables": ["x"],
      "goal": "min"
    }
  }
}
```

Expected result: a numeric optimum estimate with `certainty="evidence"` and method `numeric_optimization`.

More examples are in `examples/sample_calls.md` and `evals/math_agent_cases.jsonl`.

## Result envelope and certainty model

Compute tools return a structured result with fields such as:

```json
{
  "ok": true,
  "status": "proved_by_symbolic_simplification",
  "certainty": "proved",
  "method": "symbolic",
  "result_kind": "verification",
  "result": "0",
  "conditions": [],
  "certificate": {
    "type": "symbolic_simplification",
    "summary": "The normalized difference simplifies to zero."
  },
  "metadata": {
    "public_tool": "verification_compute",
    "operation": "check_identity"
  }
}
```

The most important field is `certainty`:

| Certainty | Meaning |
| --- | --- |
| `proved` | A strict proposition result was proved by symbolic simplification, SMT/UNSAT, finite exhaustion, or interval analysis. |
| `disproved` | A strict counterexample or witness was found. |
| `exact` | Exact computation result, but not necessarily a proposition proof. |
| `evidence` | Numeric sampling, optimization, simulation, or approximate computation. Useful, but not proof. |
| `unknown` | The tool could not decide. |
| `error` | Invalid input, unsupported operation, timeout, resource limit, sandbox failure, or backend error. |

Sampling without a counterexample is never promoted to proof.

## Discoverability and self-correction

`math_capabilities` supports two modes:

```json
{"mode": "summary"}
```

returns a compact index of public tools, operation names, and aliases.

```json
{"mode": "full"}
```

returns payload schemas, examples, default limits, risk metadata, proof modes, domain schemas, and operation states.

Common intuitive aliases are supported within a tool. For example:

```text
algebra_compute(operation="simplify")      -> simplify_expression
trigonometry_compute(operation="simplify") -> trig_simplify
```

Unknown operations return `suggested_operations` and `available_operations` without entering a backend or sandboxed worker.

## Runtime safety

The safety model is part of the API contract:

- no arbitrary `eval`;
- no arbitrary Python execution;
- no tool reads local files supplied by path;
- no network access at runtime;
- no database or persistent memory;
- expression parser uses whitelists, length limits, node limits, banned-token checks, and empty builtins;
- Z3 input is structured AST only;
- high-risk operations run in a `bubblewrap` sandbox with a fresh network namespace, minimal read-only filesystem view, clean environment, process-group timeout, CPU/memory/file-size limits, and stdout/stderr truncation;
- if isolation cannot be enforced, the operation fails closed with a structured error.

This means `math-mcp` is intentionally less permissive than a general-purpose CAS or Python notebook. That is a feature: the server is meant to be safe and predictable when called by autonomous agents.

## Development and quality gates

Run the full local gate:

```bash
pytest
ruff check .
mypy src
```

The test suite covers:

- schema and capabilities generation;
- registry and conformance checks;
- public tool routing;
- per-domain operation behavior;
- golden cases;
- parser security and fuzz/property tests;
- sandbox acceptance;
- timeouts and resource limits;
- seed determinism;
- stable error-code coverage;
- backend caveat coverage;
- real MCP stdio smoke testing;
- benchmark metadata;
- agent tool-selection eval cases.

`tests/test_ci_gate.py` is the consolidated hard gate: it checks required conflict behavior, required test categories, every `ErrorCode`, and every backend caveat reference. `.github/workflows/ci.yml` runs `ruff`, `mypy`, and `pytest` on push and pull requests.

Unit tests force subprocess-bound operations in-process for speed through `MATH_MCP_FORCE_INPROCESS=1` in `tests/conftest.py`. Sandbox acceptance tests deliberately exercise the real sandbox. To manually test real subprocess behavior for a subset:

```bash
MATH_MCP_FORCE_INPROCESS=0 pytest tests/test_sandbox.py -q
```

## Project layout

```text
math-mcp/
  README.md
  README.ja.md
  LICENSE
  environment.yml
  pyproject.toml
  src/math_mcp/
    server.py                 # MCP tool registration only
    schemas.py                # request/result models
    status.py                 # status, certainty, method, error-code enums
    operation_registry.py     # single source of truth for operations
    backend_caveats.py        # backend limits and certainty caveats
    schema_check.py           # runtime payload schema gate
    tools/                    # domain handlers and dispatcher
    backends/                 # SymPy/mpmath/Z3/numpy/scipy/networkx adapters
    parsing/                  # safe SymPy parser, domain parser, Z3 AST parser
    runtime/                  # sandboxed subprocess runner, limits, worker, serialization
  tests/
  benchmarks/
  evals/
  examples/
```

## Design documents

The repository includes detailed design and audit notes:

- `math-mcp-implementation-guide.md`: original implementation guide and engineering specification.
- `Builed_Code.md`: as-built delivery and audit synchronization record.
- `V1.md`: discoverability, aliasing, schema correction, constrained verification, and constrained optimization plan.
- `score.md`: project audit score and quality assessment.
- `examples/sample_calls.md`: representative calls for each domain.

Some design documents are currently written in Chinese; the public README files provide English and Japanese entry points.

## Contributing

Contributions are welcome, especially new tests, stronger validation, clearer examples, and carefully scoped mathematical operations.

Rules for operation changes:

1. Add or update the operation in `operation_registry.py` first.
2. Keep the public tool shape stable: `operation`, `payload`, `domains`, `assumptions`, `limits`.
3. Add payload schema, examples, limits, risk, proof modes, certainty metadata, and backend caveats.
4. Add unit tests, golden/eval cases where appropriate, and conformance coverage.
5. Never label numeric sampling, optimization, ODE trajectories, or Monte Carlo simulation as proof.
6. Prefer structured errors over exceptions or prose-only failures.

## License

Released under the MIT License. See `LICENSE`.

## Acknowledgements

`math-mcp` builds on the Python scientific and formal-methods ecosystem: MCP Python SDK, SymPy, mpmath, Z3, numpy, scipy, networkx, pydantic, pytest, ruff, and mypy.
