# math-mcp

A local, offline, auditable **mathematical reasoning MCP server**. The LLM does the
decomposition, planning, and final proof prose; `math-mcp` does deterministic
computation, numerical verification, counterexample search, and constraint solving — and
always reports *how certain* a result is.

```text
LLM            -> decompose, plan, explain, write the proof
math-mcp       -> compute exactly, verify, find counterexamples, solve constraints,
                  return structured results with a proof/evidence level
```

## Design boundaries

- **Linux-only**, **offline at run time**, **no database**, **no RAG**, **no document
  reading**, **no arbitrary code execution**, **no LaTeX**, **no natural-language solver**.
- Expressions are SymPy-style strings or structured `expr_ast` — never `eval`.
- Numeric sampling is reported as **evidence**, never promoted to a proof. Only symbolic
  simplification, SMT/UNSAT, finite exhaustion, or interval analysis yield `proved`.

## Public tool surface

The server exposes a small set of **domain-level** tools; concrete capabilities are
selected via the `operation` argument and described by `math_capabilities`.

| Utility | Compute |
| --- | --- |
| `ping`, `math_capabilities` | `algebra_compute`, `calculus_compute`, `verification_compute`, `z3_compute`, `matrix_compute`, `discrete_compute`, `graph_compute`, `probability_compute`, `set_compute`, `geometry_compute`, `trigonometry_compute`, `number_theory_compute`, `logic_compute`, `ode_compute`, `complex_compute`, `inequality_compute` |

Unified call shape:

```json
{"operation": "simplify_expression",
 "payload": {"expression": "sin(x)**2 + cos(x)**2 - 1", "variables": ["x"]},
 "limits": {"timeout_ms": 5000}}
```

`operation_registry.py` is the single source of truth: it drives `math_capabilities`,
server routing, and the tests. Operations enter as `experimental` and are promoted to
`implemented` only after passing the quality gates; experimental/disabled operations are
hidden from the default capabilities document.

## Result envelope

Every compute tool returns a `ToolResult` with `status`, `certainty`
(`proved`/`disproved`/`exact`/`evidence`/`unknown`/`error`), `method`, `result_kind`,
structured `conditions`, an optional `certificate`, a stable `error_code` on failure, and
an auditable `metadata` trace. See `src/math_mcp/schemas.py`.

## Setup

```bash
conda env create -f environment.yml
conda activate math-mcp
pip install -e .
```

Run the server (stdio):

```bash
python -m math_mcp        # or: math-mcp
```

Local client smoke:

```bash
python examples/mcp_client_smoke.py
```

## Runtime isolation

High-risk operations (`integrate`, `solve_*`, `z3_*`, `search_counterexample`,
`truth_table`, `power_set`, numeric optimization/ODE, …) run in a **bubblewrap** sandbox
with a fresh network namespace, a minimal read-only filesystem view, a clean environment,
and CPU/memory/file-size/wall-clock limits. If isolation cannot be enforced the server
refuses to run those operations (`error_code=SANDBOX_UNAVAILABLE`); non-Linux platforms
are rejected (`PLATFORM_UNSUPPORTED`). There is no degraded, non-isolated mode in
production.

## Quality gates

```bash
pytest
ruff check .
mypy src
```

- `tests/` covers schemas, capabilities, registry/conformance, per-domain operations,
  golden cases, security/fuzz, sandbox acceptance, timeouts, seed determinism, error
  codes, a real MCP stdio smoke test, benchmarks, and the agent eval set.
- `benchmarks/` records per-operation latency/output size; `evals/` checks agent tool
  selection and the proof-vs-evidence distinction.

> Tip: the unit suite runs subprocess-bound operations in-process for speed via
> `MATH_MCP_FORCE_INPROCESS=1` (set automatically in `tests/conftest.py`). The sandbox
> acceptance tests deliberately do not use this and exercise the real sandbox.

## Registering with a local agent

```bash
codex mcp add math-mcp -- python -m math_mcp
# or use the env's absolute python:
# /home/USER/anaconda3/envs/math-mcp/bin/python -m math_mcp
```

## Project layout

```text
src/math_mcp/
  server.py            # registers the public MCP tools (no math logic)
  schemas.py status.py errors.py
  operation_registry.py  backend_caveats.py  schema_check.py  config.py
  tools/               # per-domain handlers + dispatch + capabilities
  backends/            # sympy / mpmath / z3 / numpy / scipy / networkx adapters
  parsing/             # safe expression parser, domain parser, z3 AST
  runtime/             # limits, sandboxed subprocess runner, worker, timing, serialization
tests/  benchmarks/  evals/  examples/
```

Success is not "the tool solved the whole problem" — it is: the agent reliably calls a
converged tool surface, gets exact computation and honest verification with a proof level,
and bounded, auditable failure modes, all offline.
