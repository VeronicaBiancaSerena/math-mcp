# math-mcp

[English README](README.md) | [License](LICENSE)

`math-mcp` は、ローカル・オフライン・監査可能な数学計算／検証用 Model Context Protocol (MCP) サーバーです。

LLM エージェントに、問題全体の推論を丸投げするのではなく、信頼できる数学ツール面を提供することを目的としています。エージェントは問題分解、操作選択、最終説明を担当し、`math-mcp` は制限付きの記号計算、数値計算、有限列挙、グラフ、確率、SMT、検証を実行し、明示的な確実性レベル付きの構造化結果を返します。

```text
LLM / agent  -> 問題分解、計画、operation 選択、説明
math-mcp     -> 計算、検証、反例探索、制約解決、
                proof/evidence メタデータ付き構造化結果の返却
```

## 目的

LLM は計画や説明が得意ですが、計算ミスをしたり、証明と数値的証拠を混同したり、サンプリング結果を過信したりすることがあります。`math-mcp` は、エージェントのための規律あるローカル数学ワークベンチです。

- 可能な場合は厳密な記号計算を行う。
- 記号簡約、SMT/UNSAT、有限全探索などで厳密な証明が可能な場合だけ `proved` を返す。
- 命題が偽なら反例を探索する。
- 数値計算、最適化、シミュレーション、サンプリングは `evidence` として返し、証明に昇格しない。
- operation 名の誤り、schema ミス、未対応 domain、timeout、resource limit などを、エージェントが自己修正しやすい安定した構造化エラーとして返す。

## 特長

- ローカル stdio MCP サーバー。ホスト型サービスは不要。
- 実行時オフライン。Web 検索、依存関係ダウンロード、DB、RAG は使用しない。
- 本番境界は Linux-only。高リスク operation は `bubblewrap` で隔離。
- 18 個の公開 MCP tool: 2 個の utility tool と 16 個の domain-level compute tool。
- registry 上の 99 operation はすべて implemented で、`math_capabilities` から発見可能。
- 単一真実源: `src/math_mcp/operation_registry.py` が capabilities、routing、tests、examples を駆動。
- 統一結果 envelope: `status`, `certainty`, `method`, `result_kind`, `conditions`, `certificate`, `error_code`, metadata。
- エージェントが使いやすい SymPy 形式の式文字列と、Z3 などに使う構造化 AST。
- proof、disproof、exact computation、numeric evidence、unknown、error を厳格に区別。
- CI quality gate: `ruff`, `mypy`, `pytest`, registry/conformance、error-code coverage、sandbox tests、golden cases、agent eval cases。

## これは何ではないか

`math-mcp` は自然言語の数学問題を直接解く black-box solver ではありません。

提供しないもの:

- `solve_math_problem(problem: str)` のような自然言語一括解法 tool;
- LaTeX parser;
- 任意 Python 実行;
- ネットワーク tool や文書 reader;
- Lean、Coq、Isabelle、SageMath、Mathematica との theorem-prover 統合;
- database、memory store、RAG pipeline;
- multi-user HTTP service や Web UI。

自然言語や LaTeX で書かれた問題は、MCP 呼び出し前にエージェントが必要な数式・制約をサポートされた入力形式へ変換してください。

## 必要環境

本番利用の対象は意図的に狭くしています。

- Linux;
- Python 3.11;
- conda、または科学計算 stack をインストールできる環境管理ツール;
- 高リスク operation の sandbox 用 `bubblewrap`;
- MCP Python SDK v1.x (`mcp[cli]>=1.25,<2`)。

conda environment 名は `math-mcp` で、`environment.yml` に定義されています。

Debian/Ubuntu では OS sandbox 依存関係を次のようにインストールします。

```bash
sudo apt-get update
sudo apt-get install -y bubblewrap
```

`bubblewrap` や Linux isolation が利用できない場合、高リスク operation は非隔離で実行されるのではなく、`SANDBOX_UNAVAILABLE` や `PLATFORM_UNSUPPORTED` などの構造化エラーで fail closed します。

## インストール

```bash
git clone https://github.com/<owner>/math-mcp.git
cd math-mcp

conda env create -f environment.yml
conda activate math-mcp

pip install -e .
```

ローカル MCP client から使う場合、editable install を推奨します。sandbox worker は隔離された Python 設定で起動されるため、environment 内から package を import できる必要があります。

stdio server を起動します。

```bash
python -m math_mcp
# または installation 後:
math-mcp
```

ローカル MCP smoke test:

```bash
python examples/mcp_client_smoke.py
```

## MCP client への接続

可能であれば `math-mcp` environment 内の Python executable を直接指定してください。

```bash
/home/<user>/anaconda3/envs/math-mcp/bin/python -m math_mcp
```

Codex CLI の例:

```bash
codex mcp add math-mcp -- /home/<user>/anaconda3/envs/math-mcp/bin/python -m math_mcp
```

Hermes Agent の例:

```yaml
mcp_servers:
  math-mcp:
    command: "/home/<user>/anaconda3/envs/math-mcp/bin/python"
    args: ["-m", "math_mcp"]
    timeout: 120
    connect_timeout: 60
```

Claude Desktop 形式の例:

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

接続後は、まず `math_capabilities(mode="summary")` を呼び、具体的な payload schema が必要になったら `math_capabilities(mode="full")` を呼ぶのがおすすめです。

## 公開 tool surface

server は domain-level tool を公開します。具体的な数学機能は `operation` 引数で選択します。

Utility tools:

| Tool | 目的 |
| --- | --- |
| `ping` | health check。 |
| `math_capabilities` | tools、operations、aliases、schemas、examples、limits、release states を返す。 |

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

default capabilities response は implemented operations を公開します。registry model には experimental / disabled などの状態もありますが、明示的に要求しない限り default discovery には出ません。

## 統一呼び出し形式

すべての compute tool は同じ top-level shape を使います。

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

重要な規則:

- `operation` はその public tool 内の leaf operation name。
- `payload` は operation 固有の field のみを含む。
- `domains`, `assumptions`, `limits` は top-level field。`payload` 内に入れない。
- 式は `sin(x)**2` のような SymPy-style syntax を使う。`\sin^2 x` のような LaTeX は使わない。
- Z3 tools は structured AST constraints を使う。Python 文字列や自然言語の制約は使わない。

## 例

### 記号恒等式の証明

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

期待結果: `certainty="proved"`, `method="symbolic"`, symbolic-simplification certificate。

### 厳密な代数計算

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

期待結果: 厳密な根 `2`, `3`。

### 有界 domain 上の反例探索

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

期待結果: `certainty="disproved"` と `x=1/2` などの witness。

### 有限全探索による検証

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

`domains` は top-level です。agent が `payload.domains` に入れた場合、tool は修正方法を含む構造化エラーを返します。

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

期待結果: satisfiable と具体的な model。

### 数値最適化は証明ではなく evidence

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

期待結果: numeric optimum estimate。`certainty="evidence"`, `method="numeric_optimization"`。

追加例は `examples/sample_calls.md` と `evals/math_agent_cases.jsonl` にあります。

## 結果 envelope と certainty model

compute tool は次のような構造化結果を返します。

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

最重要 field は `certainty` です。

| Certainty | 意味 |
| --- | --- |
| `proved` | 記号簡約、SMT/UNSAT、有限全探索、区間解析などで命題が厳密に証明された。 |
| `disproved` | 厳密な反例または witness が見つかった。 |
| `exact` | 厳密な計算結果。ただし命題証明とは限らない。 |
| `evidence` | 数値サンプリング、最適化、シミュレーション、近似計算。有用だが証明ではない。 |
| `unknown` | tool は判定できなかった。 |
| `error` | 入力不正、未対応 operation、timeout、resource limit、sandbox failure、backend error。 |

反例が見つからなかったサンプリング結果は、証明には昇格しません。

## Discoverability と自己修正

`math_capabilities` には 2 つの mode があります。

```json
{"mode": "summary"}
```

public tools、operation names、aliases の軽量 index を返します。

```json
{"mode": "full"}
```

payload schemas、examples、default limits、risk metadata、proof modes、domain schemas、operation states を返します。

tool 内で曖昧でない直感的 alias も使えます。

```text
algebra_compute(operation="simplify")      -> simplify_expression
trigonometry_compute(operation="simplify") -> trig_simplify
```

未知の operation は backend や sandbox worker に入る前に、`suggested_operations` と `available_operations` を返します。

## Runtime safety

安全境界は API contract の一部です。

- arbitrary `eval` なし;
- arbitrary Python execution なし;
- path を渡して local file を読ませる tool なし;
- runtime network access なし;
- database / persistent memory なし;
- expression parser は whitelist、length limit、node limit、banned-token check、empty builtins を使用;
- Z3 input は structured AST のみ;
- 高リスク operation は `bubblewrap` sandbox で実行し、新しい network namespace、最小 read-only filesystem view、clean environment、process-group timeout、CPU/memory/file-size limits、stdout/stderr truncation を使う;
- isolation を強制できない場合は構造化エラーで fail closed。

そのため `math-mcp` は一般的な CAS や Python notebook よりも意図的に制限されています。自律エージェントから呼ばれる tool として、安全性と予測可能性を優先しているためです。

## Development と quality gates

ローカルで full gate を実行します。

```bash
pytest
ruff check .
mypy src
```

test suite は次をカバーします。

- schema と capabilities generation;
- registry と conformance checks;
- public tool routing;
- domain ごとの operation behavior;
- golden cases;
- parser security と fuzz/property tests;
- sandbox acceptance;
- timeouts と resource limits;
- seed determinism;
- stable error-code coverage;
- backend caveat coverage;
- real MCP stdio smoke testing;
- benchmark metadata;
- agent tool-selection eval cases。

`tests/test_ci_gate.py` は consolidated hard gate です。必須 conflict behavior、必須 test category、全 `ErrorCode`、全 backend caveat reference を検証します。`.github/workflows/ci.yml` は push と pull request で `ruff`, `mypy`, `pytest` を実行します。

unit tests は速度のため、`tests/conftest.py` で `MATH_MCP_FORCE_INPROCESS=1` を設定し、subprocess-bound operation を in-process で走らせます。sandbox acceptance tests は意図的に real sandbox を使います。手動で real subprocess behavior を確認する例:

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

repository には詳細な設計・監査 note があります。

- `math-mcp-implementation-guide.md`: original implementation guide and engineering specification。
- `Builed_Code.md`: as-built delivery and audit synchronization record。
- `V1.md`: discoverability、aliasing、schema correction、constrained verification、constrained optimization plan。
- `score.md`: project audit score and quality assessment。
- `examples/sample_calls.md`: 各 domain の representative calls。

一部の設計文書は現在 Chinese で書かれています。この README と `README.md` が、それぞれ Japanese / English の公開 entry point です。

## Contributing

contributions are welcome。特に、新しい test、より強い validation、明確な example、慎重に scope された数学 operation は歓迎します。

operation 変更時のルール:

1. まず `operation_registry.py` に operation を追加または更新する。
2. public tool shape (`operation`, `payload`, `domains`, `assumptions`, `limits`) を安定に保つ。
3. payload schema、examples、limits、risk、proof modes、certainty metadata、backend caveats を追加する。
4. 必要に応じて unit tests、golden/eval cases、conformance coverage を追加する。
5. numeric sampling、optimization、ODE trajectories、Monte Carlo simulation を proof として扱わない。
6. prose-only failure や例外ではなく、構造化 error を優先する。

## License

MIT License で公開されています。詳細は `LICENSE` を参照してください。

## Acknowledgements

`math-mcp` は Python scientific / formal-methods ecosystem に基づいています: MCP Python SDK, SymPy, mpmath, Z3, numpy, scipy, networkx, pydantic, pytest, ruff, mypy。
