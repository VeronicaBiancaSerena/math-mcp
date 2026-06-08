# 本地离线数学推理 MCP 一次性交付实施指南

## 1. 目标

本项目要落地一个本地、离线、可测试、可审计的数学推理工具 MCP，供 Codex、GPT 系列模型、Claude/Opus 类模型或其他 agent 调用。

设计边界很明确：

```text
LLM 负责拆题、规划、解释和最终证明。
math-mcp 负责确定性计算、数值验证、反例搜索、约束求解和结构化返回。
```

本指南不再采用“先 MVP、再第二版、再第三版”的路线。要做的工具直接全部纳入总体交付范围；不建议做的路线直接排除，不进入后续规划。实际对 agent 默认暴露时必须经过 operation 发布状态门禁：未通过质量门禁的能力只能作为 `experimental` 留在 registry 中，不能默认出现在 `math_capabilities`。

## 2. 固定技术决策

### 2.1 使用 Python

使用 Python 编写 MCP server。原因是 Python 的数学后端生态最完整，开发和测试成本最低：

- `SymPy`：符号计算、代数、微积分、矩阵、级数、递推、多项式。
- `mpmath`：高精度数值计算。
- `z3-solver`：SMT 约束求解、可满足性检查、模型/反例提取。
- `numpy` / `scipy`：数值线性代数、优化。
- `networkx`：图论和组合结构。
- `pydantic`：输入输出 schema 和结构化结果。
- `pytest`：单元测试、集成测试、MCP smoke test。

### 2.2 使用 conda 管理环境

使用 conda 管理 Python 版本和大部分科学计算依赖，使用 pip 安装 MCP SDK 相关包。

conda 环境名称必须与项目名称一致，统一使用：

```text
math-mcp
```

也就是说，`environment.yml` 的 `name`、`pyproject.toml` 的 project `name`、本地安装和 Codex MCP 注册文档中的环境名都应保持一致。

### 2.3 使用 MCP Python SDK v1.x 风格

截至 2026-05-29 的核查结果：`modelcontextprotocol/python-sdk` 的 README 标注 v1.x 是当前稳定文档，v2 文档仍是 pre-alpha/in development。因此本文采用 v1.x 稳定风格：

```python
from mcp.server.fastmcp import FastMCP
```

并使用：

```python
mcp.run(transport="stdio")
```

本项目只需要本地 stdio transport，不做 HTTP 服务。

### 2.4 不使用数据库

本项目不引入数据库。数学工具调用是无状态计算：

- 输入是表达式、变量、假设、约束、矩阵、图、搜索范围。
- 输出是结果、状态、反例、证明等级、耗时、错误和警告。

数据库不会提升数学推理可靠性，反而增加状态复杂度、隐私风险和维护成本。

### 2.5 运行期不联网

本 MCP 是本地离线工具。工具执行时不访问网络、不搜索网页、不下载依赖、不读取远程文档。

安装依赖时可能需要网络，但那属于开发/部署动作，不属于 MCP 工具运行期行为。

## 3. 明确放弃的路线

以下内容不纳入本项目，也不作为后续路线保留：

- 数据库：不做 SQLite、PostgreSQL、MongoDB。
- RAG：不做数学 RAG，不做 theorem/lemma 向量库。
- 论文/教材读取：不做 PDF、LaTeX、Markdown、TXT 文档读取工具。
- 网络工具：不做联网搜索，不做网页抓取。
- 自然语言黑盒求解器：不做 `solve_math_problem(problem: str)`。
- 任意 Python 代码执行：不做 `eval_python`、`run_code`。
- 外部大型系统集成：不接 Lean、Coq、Isabelle、SageMath、Mathematica。
- Web UI：不做前端界面。
- 多用户服务：不做权限、账户、HTTP API、鉴权。
- 长期记忆：不保存题库、用户历史、证明片段库。

如需论文上下文，直接把论文相关片段喂给 LLM；不通过 math-mcp 读取。

形式化证明系统不在本项目路线内，不混入 math-mcp。

## 4. 一次性交付范围

本项目直接交付以下全部能力规划，不按产品版本拆分范围；但每个 operation 必须按 10.5 的发布状态门禁逐个从 `experimental` 晋级到 `implemented`。

### 4.0 MCP 公开工具面

为避免 agent 面对几十个相似工具名时选择混乱，MCP 对外只暴露少量领域级工具。后续 4.1 到 4.14 的表格列出的名称是 **operation**，不是全部直接暴露为 MCP tool。

公开 MCP tools：

| MCP tool | 作用 |
| --- | --- |
| `ping` | 健康检查 |
| `math_capabilities` | 返回支持的领域、operation、输入限制、示例 |
| `algebra_compute` | 代数 operation 入口 |
| `calculus_compute` | 微积分与分析 operation 入口 |
| `verification_compute` | 恒等式、采样验证、反例搜索入口 |
| `z3_compute` | Z3 结构化约束入口 |
| `matrix_compute` | 线性代数入口 |
| `discrete_compute` | 递推、组合、小规模枚举入口 |
| `graph_compute` | 图算法入口 |
| `probability_compute` | 概率论入口 |
| `set_compute` | 集合与区间入口 |
| `geometry_compute` | 解析几何入口 |
| `trigonometry_compute` | 三角函数入口 |
| `number_theory_compute` | 数论入口 |
| `logic_compute` | 逻辑与布尔入口 |
| `ode_compute` | 常微分方程入口 |
| `complex_compute` | 复数入口 |
| `inequality_compute` | 不等式入口 |

统一调用形态：

```json
{
  "operation": "simplify_expression",
  "payload": {
    "expression": "sin(x)**2 + cos(x)**2 - 1",
    "variables": ["x"]
  },
  "limits": {
    "timeout_ms": 5000,
    "max_output_chars": 8000
  }
}
```

实现层可以继续保留 `simplify_expression_impl`、`factor_expression_impl` 等小函数，但 MCP server 层只注册领域级入口。

`math_capabilities` 返回结构建议：

```json
{
  "server": "math-mcp",
  "schema_version": "1.0",
  "capabilities_version": "1.0",
  "public_tools": {
    "algebra_compute": {
      "kind": "compute",
      "operations": {
        "simplify_expression": {
          "operation_version": "1.0",
          "state": "implemented",
          "default_limits": {"timeout_ms": 5000, "max_output_chars": 8000},
          "risk": "medium",
          "complexity_class": "solver_dependent",
          "runs_in_subprocess": false,
          "proof_capable": false,
          "proof_modes": [],
          "max_certainty": "exact",
          "numeric_only": false,
          "result_kinds": ["value"],
          "accepted_input_forms": ["expression_string", "expr_ast"],
          "determinism": "deterministic",
          "payload_schema": {
            "type": "object",
            "required": ["expression"],
            "properties": {
              "expression": {"type": "string", "maxLength": 5000},
              "variables": {"type": "array", "items": {"type": "string"}, "maxItems": 20}
            },
            "additionalProperties": false
          },
          "example_payload": {
            "expression": "sin(x)**2 + cos(x)**2 - 1",
            "variables": ["x"]
          },
          "deprecated": false,
          "replacement": null
        }
      }
    }
  }
}
```

上例只展开了一个 compute tool。完整 capabilities 必须同时包含 `ping`、`math_capabilities` 等 utility tool，以及 4.0 中所有计算类 public tools。

每个 operation 的 capability 条目必须包含：

```text
operation_version: 语义版本，例如 1.0
state: implemented | experimental | disabled | deprecated
risk: low | medium | high
complexity_class: constant | linear | polynomial | exponential | solver_dependent
runs_in_subprocess: true | false
proof_capable: true | false
proof_modes: symbolic | smt | finite_exhaustive | interval | counterexample
max_certainty: proved | disproved | exact | evidence | unknown | error
numeric_only: true | false
result_kinds: value | solution_set | witness | verification | object | none
accepted_input_forms: expression_string | expr_ast | z3_ast | matrix | graph | finite_set
determinism: deterministic | seeded_random | nondeterministic
payload_schema: JSON Schema 风格的 payload 结构说明
deprecated: true | false
replacement: null | {"public_tool": "...", "operation": "..."}
```

高风险 operation 包括：积分、方程组、Groebner basis、数值优化、ODE 数值解、仿真、真值表、有限量词枚举、大规模图算法。

`proof_capable` 只是 capabilities 输出中的兼容性摘要，不进入 registry 手写字段。它必须由 `proof_modes` 派生：`proof_modes` 非空时为 `true`，为空时为 `false`。新实现内部不得依赖 `proof_capable` 做可信度判断；agent 和 tests 应优先看 `proof_modes` 和 `max_certainty`。例如 `simplify_expression` 返回精确化简结果，通常是 `max_certainty="exact"`，不是命题证明；数值优化可以有数值结果，但 `max_certainty` 不能高于 `evidence`，除非 operation 明确带有区间证明或 SMT 证明模式。

`max_certainty` 表示 operation 可能达到的最高可信度层级，不表示某次调用一定返回该结论极性。`proved` 和 `disproved` 都属于严格命题结论；既可能证明也可能反证的验证类 operation 可用 `max_certainty="proved"` 表示最高可达严格证明，并通过实际返回的 `certainty`、`status` 和 `certificate` 区分成立、反例和未知。纯反例搜索类 operation 可用 `max_certainty="disproved"` 表示最高严格结论是找到反例。

`complexity_class` 是调度提示，不是理论保证。它用于提示 agent 在大输入、超时或高风险 operation 前先缩小 domain、降低规模或选择更保守的验证方式。

`math_capabilities` 不应手写散落在多个文件中；它必须由 `operation_registry.py` 生成。默认 capabilities 只暴露 `state="implemented"` 和仍可调用的 `state="deprecated"` operation。`experimental` operation 默认隐藏，只能通过显式 `include_experimental=true` 查询；`disabled` operation 默认隐藏，只能通过显式 `include_disabled=true` 查询，并且调用时必须返回 `unsupported` 和稳定 `error_code="UNSUPPORTED_OPERATION"`。

capabilities 暴露 `payload_schema` 的目的不是让 MCP 端完全替代 Pydantic 校验，而是让 agent 在调用前知道每个 operation 的最小必填字段、可选字段、字段类型和边界。实现中仍必须在 handler 入口做强校验，不能相信 agent 根据 schema 生成的 payload 一定正确。

`math_capabilities["public_tools"]` 必须包含 4.0 中的全部公开 MCP tools。`ping` 和 `math_capabilities` 属于 utility tool，可以标记为 `kind="utility"` 且 `operations={}`；其他计算类 public tool 标记为 `kind="compute"` 并暴露 operation 清单。

`math_capabilities` 还支持 `mode` 参数（默认 `"full"`）：`mode="summary"` 返回只含 tool、operation 名清单、alias 的轻量索引，用于低成本发现；full 模式在原结构上追加顶层 `mode` 字段、每个 compute tool 的 `aliases`，以及需要顶层 `domains` 的 operation 的 `requires_domains`/`domain_schema`/`example_request`。详见 §24。

#### 4.0.1 operation 命名规范

顶层 `operation` 必须是该 public tool 下的叶子能力名，`payload` 中不得再嵌套第二个 `operation` 字段。

正确：

```json
{
  "operation": "det",
  "payload": {
    "matrix": [["1", "2"], ["3", "4"]]
  }
}
```

错误：

```json
{
  "operation": "matrix_operation",
  "payload": {
    "operation": "det",
    "matrix": [["1", "2"], ["3", "4"]]
  }
}
```

命名规则：

- operation 名称只需要在同一个 public tool 内唯一，不要求全局唯一。
- operation 名称使用稳定的 snake_case。
- 能独立测试、独立声明 schema、独立声明 `max_certainty` 的能力应拆成独立 operation。
- 算法选择、精度模式、返回格式可以作为 payload 字段，例如 `algorithm`、`mode`、`precision_digits`；数学语义不同的操作不能藏在 payload 字段里。
- 禁止使用 `*_operation`、`*_properties` 这类二级调度名作为公开 operation，除非 payload 中没有任何子操作选择。
- 新增 operation 前必须先进入 `operation_registry.py`，并由 conformance tests 检查 payload schema 不包含名为 `operation` 的子字段。

### 4.1 代数工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `simplify_expression` | SymPy | 化简表达式 |
| `expand_expression` | SymPy | 展开表达式 |
| `factor_expression` | SymPy | 因式分解 |
| `cancel_expression` | SymPy | 有理式约分 |
| `together_expression` | SymPy | 通分 |
| `solve_equation` | SymPy | 求解单个方程 |
| `solve_system` | SymPy | 求解方程组 |
| `polynomial_roots` | SymPy | 多项式根 |
| `groebner_basis` | SymPy | Groebner basis |

### 4.2 微积分与分析工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `differentiate` | SymPy | 求导 |
| `integrate` | SymPy | 积分 |
| `limit_expression` | SymPy | 极限 |
| `series_expand` | SymPy | 级数展开 |
| `numeric_evaluate` | SymPy/mpmath | 高精度数值计算 |
| `numeric_optimize` | scipy | 数值优化 |

### 4.3 验证与反例工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `check_identity` | SymPy + sampling | 检查两个表达式是否恒等 |
| `check_inequality_sampled` | mpmath | 有界域数值采样检查不等式 |
| `search_counterexample` | mpmath/SymPy | 在显式域内搜索反例 |
| `z3_satisfiability` | Z3 | 检查结构化约束是否可满足 |
| `z3_find_counterexample` | Z3 | 用约束求解器寻找反例 |

`z3_satisfiability` 和 `z3_find_counterexample` 属于验证语义，但 public tool 必须是 `z3_compute`，不是 `verification_compute`。`verification_compute` 只负责 SymPy/mpmath 侧的恒等式验证、采样验证和反例搜索。

### 4.4 线性代数工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `det` | SymPy | 行列式 |
| `rank` | SymPy | 矩阵秩 |
| `inverse` | SymPy | 逆矩阵 |
| `rref` | SymPy | 行最简形 |
| `eigenvals` | SymPy | 特征值 |
| `trace` | SymPy | 矩阵迹 |
| `transpose` | SymPy | 转置 |
| `charpoly` | SymPy | 特征多项式 |
| `solve_linear_system` | SymPy | 精确线性方程组 |
| `matrix_decomposition_numeric` | numpy/scipy | LU、QR、SVD、特征值数值计算 |

### 4.5 递推、组合与图工具

`solve_recurrence`、`combinatorics_count` 和 `finite_enumeration` 归属 `discrete_compute`；图相关 operation 归属 `graph_compute`。两类能力同属离散数学领域，但 public tool 不混用。

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `solve_recurrence` | SymPy | 递推式求解 |
| `combinatorics_count` | Python/SymPy | 排列、组合、二项式、多项式系数 |
| `finite_enumeration` | Python | 小规模枚举验证 |
| `is_connected` | NetworkX | 连通性 |
| `connected_components` | NetworkX | 连通分量 |
| `shortest_path` | NetworkX | 最短路 |
| `has_cycle` | NetworkX | 环检测 |
| `topological_sort` | NetworkX | 拓扑排序 |
| `maximum_matching` | NetworkX | 最大匹配 |
| `minimum_spanning_tree` | NetworkX | 最小生成树 |

### 4.6 概率论工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `probability_distribution` | SymPy/scipy | 常见分布的 PMF/PDF/CDF/分位数 |
| `distribution_moments` | SymPy/scipy | 期望、方差、矩、协方差 |
| `event_probability` | SymPy | 离散事件概率、条件概率、独立性检查 |
| `bayes_update` | Python/SymPy | 贝叶斯公式、后验概率 |
| `random_variable_transform` | SymPy/scipy | 简单随机变量变换 |
| `markov_chain_analyze` | numpy/SymPy | 转移矩阵、n 步概率、平稳分布 |
| `probability_simulation` | numpy | 固定随机种子的 Monte Carlo 验证 |

概率工具必须区分精确计算和模拟证据。Monte Carlo 结果只能返回 `certainty="evidence"`、`method="simulation"`，不能返回 `certainty="proved"`。

### 4.7 集合与区间工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `set_operations` | Python/SymPy | 有限集合并、交、差、补、对称差 |
| `set_membership` | Python/SymPy | 元素属于关系判断 |
| `set_relation_check` | Python/SymPy | 子集、真子集、相等、不交 |
| `set_identity_check` | Python/SymPy | 集合恒等式检查 |
| `cartesian_product` | Python | 笛卡尔积 |
| `power_set` | Python | 有限集合幂集，带规模限制 |
| `interval_compute` | SymPy | 区间并交差补、开闭区间处理 |

集合工具只处理有限集合和一维区间集合，不做任意公理集合论证明。

### 4.8 解析几何工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `geometry_distance` | SymPy | 点点、点线、点圆距离 |
| `geometry_intersection` | SymPy | 直线、圆、圆锥曲线交点 |
| `line_analyze` | SymPy | 斜率、截距、平行、垂直、夹角 |
| `circle_analyze` | SymPy | 圆心、半径、切线、交点 |
| `conic_analyze` | SymPy | 圆锥曲线标准化和基本性质 |
| `polygon_analyze` | SymPy | 面积、周长、凸性、重心 |
| `coordinate_transform` | SymPy | 平移、旋转、极坐标/直角坐标转换 |

解析几何工具只做坐标计算和可验证几何量，不做自然语言欧氏几何证明。

### 4.9 三角函数工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `trig_simplify` | SymPy | 三角表达式化简 |
| `trig_expand` | SymPy | 和角、倍角、乘积展开 |
| `trig_rewrite` | SymPy | sin/cos/tan/exp 形式转换 |
| `trig_reduce` | SymPy | 三角多项式规约 |
| `solve_trig_equation` | SymPy | 显式区间内三角方程求解 |
| `trig_identity_check` | SymPy + sampling | 三角恒等式检查 |

三角函数工具与 `check_identity` 有交叉，但保留独立工具有价值：agent 遇到三角题时可以直接调用更聚焦的工具，输出也能标明使用了三角规约。

### 4.10 数论工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `gcd_lcm_bezout` | SymPy/Python | gcd、lcm、扩展欧几里得、Bezout 系数 |
| `prime_analyze` | SymPy | 素数判断、下一个素数、素因数分解 |
| `modular_arithmetic` | SymPy/Python | 模幂、模逆、模线性方程 |
| `congruence_solve` | SymPy | 同余方程和同余方程组 |
| `chinese_remainder` | SymPy | 中国剩余定理 |
| `totient_compute` | SymPy | 欧拉函数、Carmichael 函数 |
| `multiplicative_order` | SymPy | 模 n 乘法阶、原根检查 |
| `quadratic_residue_check` | SymPy | 二次剩余、Legendre/Jacobi 符号 |

数论工具只做整数和有限模运算，不做自然语言数论证明。

### 4.11 逻辑与布尔工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `boolean_simplify` | SymPy | 布尔表达式化简 |
| `truth_table` | Python/SymPy | 真值表生成，带变量数量限制 |
| `logic_equivalence_check` | SymPy | 命题逻辑等价检查 |
| `logic_satisfiability` | SymPy/Z3 | SAT/UNSAT 检查 |
| `normal_form_convert` | SymPy | CNF、DNF、NNF 转换 |
| `finite_quantifier_check` | Python | 有限域上的 forall/exists 枚举检查 |

逻辑工具与 Z3 有交叉，但保留独立工具有价值：命题逻辑、真值表和标准形转换比 Z3 AST 更适合 agent 快速验证。

### 4.12 常微分方程工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `ode_solve_symbolic` | SymPy | 常见 ODE 符号求解 |
| `ode_verify_solution` | SymPy | 验证候选解是否满足 ODE |
| `ode_initial_value_solve` | SymPy/scipy | 初值问题符号/数值求解 |
| `ode_solve_numeric` | scipy | 数值 ODE 求解 |
| `ode_classify` | SymPy | ODE 类型识别 |

ODE 工具必须区分符号解、数值解和候选解验证。数值 ODE 解不能当作解析证明。

### 4.13 复数工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `complex_simplify` | SymPy | 复数表达式化简 |
| `complex_to_polar` | SymPy | 代数形式转极形式 |
| `complex_from_polar` | SymPy | 极形式转代数形式 |
| `complex_roots_of_unity` | SymPy | n 次单位根 |
| `complex_mod_arg` | SymPy | 模、辐角、共轭 |
| `complex_equation_solve` | SymPy | 简单复方程求解 |

复数工具应返回精确表达式和 LaTeX，必要时附数值近似。

### 4.14 不等式专用工具

| 工具名 | 后端 | 作用 |
| --- | --- | --- |
| `inequality_reduce` | SymPy | 一元或简单多元不等式化简 |
| `inequality_domain_solve` | SymPy | 解不等式对应的区间/区域 |
| `inequality_check_symbolic` | SymPy | 基于化简和假设的符号检查 |
| `inequality_counterexample_search` | mpmath/SymPy | 有界域反例搜索 |
| `inequality_sample` | mpmath | 有界域数值采样 |

不等式工具不能包装成“自动证明所有不等式”。只有符号化简、区间求解或 SMT 能严格推出结论时才返回 `certainty="proved"`；采样只返回 `certainty="evidence"`。

## 5. 工具设计原则

### 5.1 工具必须小而准

禁止设计黑盒工具：

```text
solve_math_problem(problem: str) -> str
```

原因：

- 难以审计。
- 难以测试。
- 难以复现。
- agent 会把完整推理任务外包给工具。
- 错误结果不容易定位。

正确做法是把 MCP 暴露面拆成领域级工具，并把具体能力放到 `operation` 中，例如：

```text
verification_compute(operation="check_identity", payload={...})
verification_compute(operation="search_counterexample", payload={...})
z3_compute(operation="z3_satisfiability", payload={...})
matrix_compute(operation="det", payload={...})
graph_compute(operation="shortest_path", payload={...})
```

这些示例中的 `operation` 都是叶子能力名。不要使用 `matrix_operation`、`graph_properties` 这类中间调度名再让 payload 选择子操作。

### 5.2 工具参数稳定且不要过度嵌套

MCP tool 面向 LLM 暴露时，公开参数应稳定：`operation`、`payload`、`domains`、`assumptions`、`limits`。不要让模型构造任意深层嵌套对象。

推荐：

```python
@mcp.tool()
def algebra_compute(
    operation: str,
    payload: dict[str, Any],
    domains: list[dict[str, Any]] | None = None,
    assumptions: list[dict[str, Any]] | None = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    ...
```

内部再转成 Pydantic request model：

```python
request = OperationRequest(
    operation=operation,
    payload=payload,
    domains=domains or [],
    assumptions=assumptions or [],
    limits=limits or {},
)
```

这样既方便 LLM 调用，也保留强校验。

### 5.3 输出必须结构化

每个计算类工具返回统一结构。以下示例对应 `verification_compute(operation="check_identity")` 证明恒等式成功的返回：

```json
{
  "ok": true,
  "status": "proved_by_symbolic_simplification",
  "result": "0",
  "result_latex": "0",
  "certainty": "proved",
  "method": "symbolic",
  "result_kind": "verification",
  "conditions": [],
  "backend": "sympy",
  "duration_ms": 12,
  "warnings": [],
  "error": null
}
```

不要只返回自然语言。自然语言解释可以作为 `explanation` 字段，但不能替代结构化状态。

### 5.4 区分证明、证据、反例和未知

工具返回必须区分：

- 符号化简证明。
- SMT 证明/不可满足证明。
- 找到反例。
- 数值证据。
- 未知。
- 超时。
- 输入不支持。

数值采样没有发现反例，不能说“命题成立”。只能说：

```text
numeric_evidence_only
```

或：

```text
no_counterexample_found
```

### 5.5 所有工具必须可测试

每个工具必须有：

- 正常输入测试。
- 错误输入测试。
- 边界输入测试。
- 输出 schema 测试。
- 至少一个 agent 场景样例。

对可能卡住的工具，还必须有 timeout 测试。

### 5.6 P0 gate

编码时必须先完成以下 P0 gate，才能继续扩展具体数学 operation：

1. `math_capabilities` 可返回公开 tool、operation、limits、示例。
2. `OperationRequest`、`DomainSpec`、`AssumptionSpec`、`Limits`、`ToolResult` schema 通过测试。
3. 表达式 parser 通过安全测试和 fuzz 测试。
4. operation registry 通过命名 conformance：顶层 operation 是叶子能力名，payload schema 不含子 `operation` 字段。
5. domain/assumption 冲突能稳定返回 `CONSTRAINT_CONFLICT`。
6. 子进程 runner 支持 timeout、CPU、内存、输出长度限制，并通过最小 sandbox acceptance test。
7. MCP stdio smoke test 能启动 server 并调用一个简单 algebra operation。

这些 gate 不通过时，不应继续增加新的数学领域工具。

### 5.7 最小垂直切片

正式铺开所有数学领域前，必须先打通一个最小垂直切片。它不是版本划分，也不是只交付一个 MVP，而是完整实现前的工程验收闸门。

最小垂直切片固定为：

```text
operation_registry.py
  -> math_capabilities
  -> algebra_compute(operation="simplify_expression")
  -> 安全 expression parser
  -> SymPy backend
  -> ToolResult
  -> MCP stdio smoke test
  -> benchmark 记录
  -> agent eval case
```

这条链路必须同时证明以下事情：

- `math_capabilities` 的 operation 来自 registry，而不是手写清单。
- `simplify_expression` 的 `payload_schema` 能被测试读取，并能拒绝缺失字段、错误类型和超长表达式。
- registry 中该 operation 声明 `state`、`operation_version`、`complexity_class`、`proof_modes`、`max_certainty` 和 `result_kinds`。
- conformance tests 确认该 operation 是顶层叶子能力名，payload schema 不包含子 `operation` 字段。
- 表达式字符串经过安全 parser，再进入 SymPy backend。
- 成功结果返回统一 `ToolResult`，包含 `certainty`、`method`、`result_kind`、`conditions`、`metadata` 和必要时的 `certificate`。
- smoke test 使用真实 MCP stdio 连接，不只调用 Python 函数。
- benchmark 能记录该 operation 的 latency、输出大小和 backend version。
- eval case 能验证 agent 选择 `algebra_compute` 和 `simplify_expression`。

只有这条最小垂直切片通过后，才开始批量添加其他 operation。这样做是为了先固定调用协议、schema、错误结构、trace、测试形态和性能记录方式，避免后续每个数学领域重复返工。

### 5.8 首批 implemented operation

全量能力仍按 4.1 到 4.14 规划，但首批允许进入 `state="implemented"` 的 operation 固定为高价值、小闭环集合：

```text
algebra_compute(operation="simplify_expression")
verification_compute(operation="check_identity")
verification_compute(operation="search_counterexample")
z3_compute(operation="z3_satisfiability")
matrix_compute(operation="det", payload={"matrix": ...})
matrix_compute(operation="rank", payload={"matrix": ...})
calculus_compute(operation="numeric_evaluate")
```

这些 operation 必须先完整打通 parser、schema、registry、capabilities、ToolResult、subprocess/limits、smoke test、golden test、agent eval 和 benchmark。其他 operation 可以先进入 registry，但在质量门禁通过前必须保持 `state="experimental"`，默认不暴露给 agent。

这个规则不是缩小最终交付范围，而是防止一次性展开十几个数学领域时把协议、错误模型和安全边界做散。

## 6. 项目结构

```text
math-mcp/
  README.md
  environment.yml
  pyproject.toml
  src/
    math_mcp/
      __init__.py
      __main__.py
      server.py
      config.py
      schemas.py
      status.py
      errors.py
      operation_registry.py
      backend_caveats.py
      tools/
        __init__.py
        capabilities.py
        algebra.py
        calculus.py
        verification.py
        z3_tools.py
        matrix.py
        discrete.py
        graph.py
        probability.py
        sets.py
        geometry.py
        trigonometry.py
        number_theory.py
        logic.py
        ode.py
        complex_tools.py
        inequalities.py
      backends/
        __init__.py
        sympy_backend.py
        mpmath_backend.py
        z3_backend.py
        numpy_backend.py
        scipy_backend.py
        networkx_backend.py
      parsing/
        __init__.py
        sympy_parser.py
        domain_parser.py
        z3_ast.py
      runtime/
        __init__.py
        subprocess_runner.py
        limits.py
        timing.py
        serialization.py
  benchmarks/
    basic_latency.py
    operation_matrix.json
  evals/
    math_agent_cases.jsonl
  tests/
    conftest.py
    test_server_smoke.py
    test_capabilities.py
    test_schemas.py
    test_parsing_sympy.py
    test_algebra.py
    test_calculus.py
    test_verification.py
    test_counterexample.py
    test_z3_tools.py
    test_matrix.py
    test_discrete.py
    test_graph.py
    test_probability.py
    test_sets.py
    test_geometry.py
    test_trigonometry.py
    test_number_theory.py
    test_logic.py
    test_ode.py
    test_complex_tools.py
    test_inequalities.py
    test_timeouts.py
    test_security.py
    test_operation_registry.py
    test_conformance.py
    test_error_codes.py
    test_seed_determinism.py
    test_sandbox.py
    test_benchmarks.py
    test_evals.py
    golden/
      algebra_cases.json
      calculus_cases.json
      z3_cases.json
      matrix_cases.json
      discrete_cases.json
      graph_cases.json
      probability_cases.json
      set_cases.json
      geometry_cases.json
      trigonometry_cases.json
      number_theory_cases.json
      logic_cases.json
      ode_cases.json
      complex_cases.json
      inequality_cases.json
  examples/
    sample_calls.md
    mcp_client_smoke.py
  .gitignore
```

职责划分：

- `server.py`：只注册 MCP tools，不写数学逻辑。
- `schemas.py`：Pydantic 输入输出模型。
- `status.py`：状态、确定性等级、方法和错误码枚举。
- `operation_registry.py`：operation 单一真源，生成 capabilities、校验 server 注册、驱动测试样例。
- `backend_caveats.py`：后端能力边界和 caveat 单一真源，供结果 warnings、capabilities 和测试引用。
- `tools/`：MCP 工具语义层，做参数校验、调用 backend、封装结果。
- `tools/capabilities.py`：从 `operation_registry.py` 生成 capabilities 响应，供 agent 查询；不维护第二份 operation 清单、限制或示例。
- `backends/`：具体数学库适配。
- `parsing/`：表达式、域、Z3 AST 解析。
- `runtime/`：timeout、序列化、子进程运行、资源限制。
- `tests/`：完整测试。

## 7. conda 环境

`environment.yml`：

```yaml
name: math-mcp
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - sympy
  - mpmath
  - numpy
  - scipy
  - networkx
  - pytest
  - pytest-asyncio
  - hypothesis
  - ruff
  - mypy
  - pip:
      - "mcp[cli]>=1.25,<2"
      - "pydantic>=2"
      - "z3-solver"
```

创建环境：

```bash
conda env create -f environment.yml
conda activate math-mcp
```

更新环境：

```bash
conda env update -f environment.yml --prune
```

本项目运行期不联网。依赖安装完成后，MCP server 的工具函数不得访问网络。

## 8. pyproject 配置

`pyproject.toml`：

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "math-mcp"
version = "0.1.0"
description = "Local offline MCP server for mathematical computation and verification."
requires-python = ">=3.11"
dependencies = [
  "mcp[cli]>=1.25,<2",
  "pydantic>=2",
  "sympy",
  "mpmath",
  "numpy",
  "scipy",
  "networkx",
  "z3-solver",
]

[project.scripts]
math-mcp = "math_mcp.server:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
  "slow: marks tests as slow",
  "mcp: marks MCP protocol smoke tests",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_configs = true
```

本地安装：

```bash
pip install -e .
```

运行：

```bash
math-mcp
```

或：

```bash
python -m math_mcp
```

## 9. MCP server 骨架

`src/math_mcp/server.py`：

下面代码是最小垂直切片骨架，只展示 `ping`、`math_capabilities` 和 `algebra_compute`。最终交付的 `server.py` 必须按 4.0 注册全部 public MCP tools；每个 public tool 都应复用同一套 request validation、registry lookup、limits normalization 和 `ToolResult` 封装逻辑。

```python
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from math_mcp.schemas import ToolResult
from math_mcp.tools.algebra import algebra_compute_impl
from math_mcp.tools.capabilities import get_capabilities

mcp = FastMCP("math-mcp")


@mcp.tool()
def ping() -> dict[str, str]:
    """Return a health check response for the local math MCP server."""
    return {"status": "ok", "server": "math-mcp"}


@mcp.tool()
def math_capabilities(
    include_experimental: bool = False,
    include_disabled: bool = False,
) -> dict[str, Any]:
    """Return supported math domains, operations, input limits, and examples."""
    return get_capabilities(
        include_experimental=include_experimental,
        include_disabled=include_disabled,
    )


@mcp.tool()
def algebra_compute(
    operation: str,
    payload: dict[str, Any],
    domains: list[dict[str, Any]] | None = None,
    assumptions: list[dict[str, Any]] | None = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run an algebra operation such as simplify, factor, solve, or Groebner basis.

    The operation must be one of the algebra operations returned by math_capabilities.
    Expressions must use the supported math expression syntax, not LaTeX or natural language.
    """
    return algebra_compute_impl(
        operation=operation,
        payload=payload,
        domains=domains or [],
        assumptions=assumptions or [],
        limits=limits or {},
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

`src/math_mcp/__main__.py`：

```python
from math_mcp.server import main

if __name__ == "__main__":
    main()
```

## 10. 状态、错误与 schema

### 10.1 状态枚举

`src/math_mcp/status.py`：

```python
from typing import Literal

Status = Literal[
    "success",
    "failure",
    "timeout",
    "invalid_input",
    "unsupported",
    "unknown",
    "backend_error",
    "output_too_large",
    "counterexample_found",
    "no_counterexample_found",
    "proved_by_symbolic_simplification",
    "proved_by_smt",
    "proved_by_finite_exhaustion",
    "proved_by_interval_analysis",
    "disproved_by_counterexample",
    "numeric_evidence_only",
]

Certainty = Literal[
    "proved",
    "disproved",
    "exact",
    "evidence",
    "unknown",
    "error",
]

Method = Literal[
    "symbolic",
    "smt",
    "finite_exhaustive",
    "interval",
    "counterexample",
    "numeric_sampling",
    "numeric_optimization",
    "simulation",
    "backend",
    "none",
]

ErrorCode = Literal[
    "PARSE_REJECTED",
    "UNSUPPORTED_OPERATION",
    "DOMAIN_UNSUPPORTED",
    "ASSUMPTION_UNSUPPORTED",
    "CONSTRAINT_CONFLICT",
    "BACKEND_TIMEOUT",
    "OUTPUT_TOO_LARGE",
    "RESOURCE_LIMIT_EXCEEDED",
    "BACKEND_INTERNAL_ERROR",
    "INVALID_AST",
    "INVALID_LIMITS",
    "NUMERIC_CONVERGENCE_FAILED",
    "PLATFORM_UNSUPPORTED",
    "SANDBOX_UNAVAILABLE",
]
```

### 10.2 统一结果模型

`src/math_mcp/schemas.py`：

```python
from typing import Any, Literal

from pydantic import BaseModel, Field

from math_mcp.status import Certainty, ErrorCode, Method, Status


class Certificate(BaseModel):
    type: Literal[
        "symbolic_simplification",
        "smt_unsat",
        "finite_exhaustion",
        "interval_bound",
        "counterexample",
    ]
    summary: str
    machine_checkable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ResultCondition(BaseModel):
    expression: str
    condition_ast: dict[str, Any] | None = None
    source: Literal["backend", "domain", "assumption", "branch", "piecewise"] = "backend"
    variables: list[str] = Field(default_factory=list)
    description: str | None = None


class ToolResult(BaseModel):
    ok: bool
    status: Status
    certainty: Certainty
    method: Method
    result_kind: Literal[
        "value",
        "solution_set",
        "witness",
        "verification",
        "object",
        "none",
    ] = "none"
    result: Any | None = None
    result_latex: str | None = None
    conditions: list[ResultCondition] = Field(default_factory=list)
    explanation: str | None = None
    backend: str = "none"
    duration_ms: int
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: ErrorCode | None = None
    certificate: Certificate | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Limits(BaseModel):
    timeout_ms: int = Field(default=5000, ge=1, le=60000)
    cpu_time_ms: int = Field(default=5000, ge=1, le=60000)
    memory_mb: int = Field(default=512, ge=64, le=8192)
    file_size_mb: int = Field(default=16, ge=1, le=1024)
    max_output_chars: int = Field(default=8000, ge=256, le=100000)
    max_expression_chars: int = Field(default=5000, ge=1, le=50000)
    max_expression_nodes: int = Field(default=2000, ge=1, le=50000)
    max_variables: int = Field(default=20, ge=1, le=100)
    max_matrix_rows: int = Field(default=50, ge=1, le=500)
    max_matrix_cols: int = Field(default=50, ge=1, le=500)
    max_graph_nodes: int = Field(default=10000, ge=1, le=1000000)
    max_graph_edges: int = Field(default=50000, ge=0, le=5000000)
    max_samples: int = Field(default=1000, ge=1, le=100000)
    precision_digits: int = Field(default=50, ge=15, le=200)
    seed: int | None = None


class DomainSpec(BaseModel):
    variable: str
    kind: Literal["real", "integer", "rational", "complex", "finite", "boolean"]
    lower: str | None = None
    upper: str | None = None
    lower_closed: bool = True
    upper_closed: bool = True
    values: list[str] | None = None


class AssumptionSpec(BaseModel):
    variable: str
    predicates: list[str] = Field(default_factory=list)


class OperationRequest(BaseModel):
    operation: str
    payload: dict[str, Any]
    domains: list[DomainSpec] = Field(default_factory=list)
    assumptions: list[AssumptionSpec] = Field(default_factory=list)
    limits: Limits = Field(default_factory=Limits)


# Operation-specific payload models do not duplicate top-level domains,
# assumptions, or limits. OperationRequest owns those cross-cutting fields.
class ExpressionRequest(BaseModel):
    expression: str
    variables: list[str] = Field(default_factory=list)


class IdentityRequest(BaseModel):
    left: str
    right: str
    variables: list[str] = Field(default_factory=list)
    sample_points: int = Field(default=25, ge=0, le=10000)


class InequalityRequest(BaseModel):
    left: str
    relation: Literal["==", "!=", "<", "<=", ">", ">="]
    right: str
    variables: list[str]
    samples: int = Field(default=1000, ge=1, le=100000)
```

`backend="none"` 用于 parser、registry、limits 或 sandbox 阶段已经失败、尚未选定具体后端的结果；进入具体 backend 后必须填真实后端名。

`certainty` 和 `method` 是 agent 判断结果可信度的主字段：

```text
proved + symbolic            符号证明
proved + smt                 SMT/UNSAT 证明
proved + finite_exhaustive   有限域穷举证明
proved + interval            区间分析证明
disproved + counterexample   找到反例
exact + backend              精确计算结果，但不是命题证明
evidence + numeric_sampling  数值采样证据
evidence + simulation        Monte Carlo 或仿真证据
unknown + none               未知、未能判定
error + none                 错误、超时、输入无效
```

当需要比较 certainty 强弱，例如 backend caveat 要求降级时，使用以下保守顺序：

```text
proved/disproved   严格命题结论
exact              精确计算结果，但不是命题证明
evidence           数值、采样、仿真或启发式证据
unknown            未能判定
error              工具错误或输入无效
```

`proved` 与 `disproved` 都是严格命题结论，但语义相反，不能互相替换；降级只能向 `exact`、`evidence`、`unknown` 或 `error` 移动，不能从 `unknown` 或 `evidence` 升级为证明。

`result_kind` 是 agent 判断 `result` 语义的主字段：

```text
value         单个精确值或数值近似
solution_set  解集、区间或参数化解
witness       满足约束的模型或反例见证
verification  命题验证结果
object        矩阵、图、分布、表达式树等结构对象
none          无结果，通常用于 error、timeout、unknown
```

`conditions` 用于承载后端返回的条件、分支条件或 domain 前提。SymPy 的 `solve`、`integrate`、`limit`、`Piecewise`、复数辐角、多值根和不等式求解都可能产生条件；这些条件必须结构化返回，不能只放在自然语言 `warnings` 中。若条件无法被严格表达，工具应降低 `certainty`，并在 `warnings` 中说明条件不完整。

`ResultCondition.expression` 是展示字段，`condition_ast` 是机器可读字段。凡是能用 11.1 的结构化 AST 表示的条件，都必须同时提供 `condition_ast`。例如：

```json
{
  "expression": "x != 0",
  "condition_ast": {
    "op": "ne",
    "left": {"var": "x"},
    "right": {"int": 0}
  },
  "source": "backend",
  "variables": ["x"]
}
```

若条件来自多值函数或分支切割，例如 `arg(z) in (-pi, pi]`、`sqrt` 主值、`log` 分支、`Piecewise` 分支，`source` 应分别使用 `branch` 或 `piecewise`，并在 `metadata["branch_conventions"]` 中记录后端采用的约定。

`certificate` 是可选的轻量证明/反例证书字段，用于让 agent 和测试更容易复核工具为什么给出 `proved`、`disproved` 或 `exact`。第一轮不要求所有证书都 machine-checkable，但证书必须结构化，不能只是自然语言长解释。

典型证书：

```json
{
  "type": "smt_unsat",
  "summary": "The negation of the target property is UNSAT under the given constraints.",
  "machine_checkable": false,
  "details": {
    "solver": "z3",
    "query_kind": "unsat_check"
  }
}
```

证书使用规则：

- `proved` 结果应尽量返回 `certificate`，例如 `symbolic_simplification`、`smt_unsat`、`finite_exhaustion` 或 `interval_bound`。
- `disproved` 结果应返回 `counterexample` 证书或在 `result` 中给出结构化反例。
- `evidence` 结果不能伪造证明证书；可以在 `metadata` 中记录采样规模、seed 和失败点。
- `error`、`unknown` 一般不返回证书，只返回 `error_code`、`warnings` 和 trace。

如果需要兼容旧调用，可以在 `metadata["legacy_evidence_level"]` 中附带旧值；新代码不应再依赖单一 `evidence_level` 字段。

`error_code` 是 agent 自动恢复的主字段：

```text
PARSE_REJECTED              parser 拒绝输入
UNSUPPORTED_OPERATION       operation 不存在或不支持
DOMAIN_UNSUPPORTED          domain 无法解释或超出能力
ASSUMPTION_UNSUPPORTED      assumption 无法解释
CONSTRAINT_CONFLICT         domain、assumption 或 payload 约束相互冲突
BACKEND_TIMEOUT             后端超时
OUTPUT_TOO_LARGE            输出超过限制
RESOURCE_LIMIT_EXCEEDED     CPU/内存/规模限制触发
BACKEND_INTERNAL_ERROR      后端内部错误
INVALID_AST                 AST 不合法
INVALID_LIMITS              limits 不合法
NUMERIC_CONVERGENCE_FAILED  数值算法未收敛
PLATFORM_UNSUPPORTED        非 Linux 平台或不受支持的运行环境
SANDBOX_UNAVAILABLE         Linux sandbox、网络隔离或资源限制无法强制启用
```

### 10.3 domain 与 assumption 规范

所有涉及变量范围的工具必须使用结构化 domain，不用自然语言字符串表达关键约束。

推荐 domain：

```json
[
  {
    "variable": "x",
    "kind": "real",
    "lower": "0",
    "upper": "1",
    "lower_closed": true,
    "upper_closed": false
  },
  {
    "variable": "n",
    "kind": "integer",
    "lower": "1",
    "upper": "100"
  },
  {
    "variable": "a",
    "kind": "finite",
    "values": ["1", "2", "3"]
  }
]
```

支持的 `kind` 先限定为：

```text
real
integer
rational
complex
finite
boolean
```

assumption 只使用受控谓词：

```text
positive
negative
nonnegative
nonzero
integer
real
rational
complex
prime
finite
```

如果工具无法严格解释某个 domain 或 assumption，必须返回 `unsupported` 或 `invalid_input`，不能忽略后继续计算。

domain 与 assumption 冲突处理必须稳定：

- 同一变量的 domain kind 冲突，例如 `real` 与 `complex`、`integer` 与 `boolean` 同时出现，返回 `invalid_input` 和 `error_code="CONSTRAINT_CONFLICT"`。
- domain 区间为空，例如 `lower > upper`，或开区间 `(1, 1)`，返回 `invalid_input` 和 `CONSTRAINT_CONFLICT`。
- finite domain 的 `values` 与 `kind` 不一致，例如 boolean 变量给出 `["0", "2"]`，返回 `invalid_input`。
- assumption 与 domain 冲突，例如 domain 为 `[0, 1]` 但 assumption 为 `negative`，返回 `invalid_input` 和 `CONSTRAINT_CONFLICT`。
- payload 约束与 domain 冲突，例如 Z3 变量声明为 `Int` 但 domain 声明为 `real`，返回 `invalid_input`。
- 冲突不得静默降级，也不得只写 warning 后继续调用 backend。

`domain_parser.py` 应先完成 domain/assumption 归一化和冲突检查，再把约束传给 SymPy、Z3 或数值 backend。所有冲突样例必须进入 `tests/test_error_codes.py` 和 `tests/test_conformance.py`。

### 10.4 operation registry

`src/math_mcp/operation_registry.py` 是 operation 单一真源。以下信息不得散落在 server、capabilities 和测试中重复维护：

```python
from typing import Any, Literal

from pydantic import BaseModel, Field

from math_mcp.schemas import Limits
from math_mcp.status import Certainty


class ReplacementSpec(BaseModel):
    public_tool: str
    operation: str


class OperationSpec(BaseModel):
    public_tool: str
    operation: str
    operation_version: str = "1.0"
    state: Literal["implemented", "experimental", "disabled", "deprecated"] = "experimental"
    backend: str
    risk: Literal["low", "medium", "high"]
    complexity_class: Literal[
        "constant",
        "linear",
        "polynomial",
        "exponential",
        "solver_dependent",
    ]
    runs_in_subprocess: bool
    proof_modes: list[
        Literal["symbolic", "smt", "finite_exhaustive", "interval", "counterexample"]
    ] = Field(default_factory=list)
    max_certainty: Certainty
    numeric_only: bool
    result_kinds: list[
        Literal["value", "solution_set", "witness", "verification", "object", "none"]
    ]
    determinism: Literal["deterministic", "seeded_random", "nondeterministic"]
    accepted_input_forms: list[str]
    payload_schema: dict[str, Any]
    default_limits: Limits
    example_payload: dict[str, Any]
    deprecated: bool = False
    replacement: ReplacementSpec | None = None
    disabled_reason: str | None = None
    # V1 可发现性字段（§24）：只为需要顶层 domains 的 operation 设置，capabilities full
    # 模式仅在非默认值时输出，避免给无 domain 的 operation 增噪。
    requires_domains: bool = False
    domain_schema: dict[str, Any] | None = None
    example_request: dict[str, Any] | None = None

    @property
    def proof_capable(self) -> bool:
        return bool(self.proof_modes)
```

operation alias map 也维护在 `operation_registry.py`（`_ALIASES`），由 `resolve_alias`、`aliases_for_tool`、`suggest_operations` 共享，capabilities 与 dispatcher 读取同一份数据，详见 §24。

registry 必须驱动：

- `math_capabilities` 输出。
- server 注册校验。
- capabilities 测试。
- golden/eval 样例校验。
- 文档 operation 清单一致性测试。

任何新增 operation 必须先进入 registry，再实现 tool handler。

`proof_capable` 不应成为手写决策字段。registry 只维护 `proof_modes` 和 `max_certainty`；`proof_capable` 只能作为 `OperationSpec` 的 computed property 或在 capabilities 序列化时由 `proof_modes` 自动派生。

capabilities 序列化示例：

```python
def operation_to_capability(spec: OperationSpec) -> dict[str, Any]:
    data = spec.model_dump()
    data["proof_capable"] = spec.proof_capable
    return data
```

`payload_schema` 使用 JSON Schema 风格子集即可，优先覆盖：

- `type`。
- `required`。
- `properties`。
- 字符串最大长度、数组长度、矩阵尺寸、图节点/边数量等边界。
- 枚举字段，例如 relation、algorithm、mode。

示例：

```python
OperationSpec(
    public_tool="algebra_compute",
    operation="simplify_expression",
    operation_version="1.0",
    state="implemented",
    backend="sympy",
    risk="medium",
    complexity_class="solver_dependent",
    runs_in_subprocess=False,
    proof_modes=[],
    max_certainty="exact",
    numeric_only=False,
    result_kinds=["value"],
    determinism="deterministic",
    accepted_input_forms=["expression_string", "expr_ast"],
    payload_schema={
        "type": "object",
        "required": ["expression"],
        "properties": {
            "expression": {"type": "string", "maxLength": 5000},
            "variables": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
            "expr_ast": {"type": "object"},
        },
        "additionalProperties": False,
    },
    default_limits=Limits(),
    example_payload={
        "expression": "sin(x)**2 + cos(x)**2 - 1",
        "variables": ["x"],
    },
)
```

### 10.5 operation 状态、发布与弃用策略

operation 名称是 agent 的稳定调用接口，不允许因为内部重构直接删除或改名。

`state` 是 operation 发布状态的主字段：

```text
implemented   已实现、已测试、默认出现在 math_capabilities 中，可被 agent 正常调用。
experimental  已进入 registry，但质量门禁未完全通过；默认不出现在 capabilities 中。
disabled      因安全、正确性或依赖问题被禁用；默认不出现在 capabilities 中，调用必须返回 unsupported。
deprecated    旧接口仍可调用，但不建议新 agent 选择；默认出现在 capabilities 中并声明 replacement。
```

发布规则：

- 新 operation 必须先以 `state="experimental"` 进入 registry，补齐 schema、example、limits、测试和 caveat 后才能改为 `implemented`。
- `OperationSpec.state` 默认值必须是 `experimental`，避免遗漏状态字段时把未验收能力暴露给 agent。
- `experimental` operation 可以有实现和测试，但默认不能被 agent 发现；只有显式 `math_capabilities(include_experimental=true)` 才返回。
- `disabled` operation 不能执行后端计算；handler 必须短路返回 `unsupported`、`certainty="error"`、`method="none"` 和 `error_code="UNSUPPORTED_OPERATION"`。
- `implemented` operation 必须通过对应单元测试、conformance、schema example 校验和至少一个 golden 或 eval case。
- 发布状态不等于版本号；破坏性语义变化必须增加 `operation_version`，不能只改 `state`。

规则：

- 不直接删除已有 operation。
- 需要迁移时，在 `OperationSpec` 中设置 `state="deprecated"` 和 `deprecated=True`。
- 必须提供结构化 `replacement`，包含 `public_tool` 和 `operation`。若因安全原因彻底移除且没有替代能力，应使用 `state="disabled"`，而不是 `deprecated`。
- `replacement` 必须指向默认 capabilities 中可发现、可调用的 operation，通常是 `state="implemented"`；不得指向 `experimental` 或 `disabled` operation。
- `math_capabilities` 必须暴露 `deprecated` 和 `replacement`。
- 被弃用 operation 仍应返回结构化结果；若安全原因必须禁用，应改为 `state="disabled"`，并返回 `unsupported` 和稳定 `error_code="UNSUPPORTED_OPERATION"`。
- 测试必须覆盖弃用 operation 仍能被 capabilities 发现，且 replacement 指向默认可发现、可调用的 `public_tool` 与 operation。
- `deprecated=True` 是为了兼容 capabilities 消费端的布尔判断；实现中以 `state` 为主，测试必须验证 `state="deprecated"` 与 `deprecated=True` 保持一致。

### 10.6 backend caveat registry

数学后端都有边界。必须显式维护 `src/math_mcp/backend_caveats.py`，让结果 `warnings`、capabilities 和测试共享同一份 caveat 定义，不能让每个工具自由编写不同说法。

建议模型：

```python
from pydantic import BaseModel

from math_mcp.status import Certainty


class BackendCaveat(BaseModel):
    backend: str
    operation_pattern: str
    caveat: str
    affects_certainty: bool
    recommended_certainty: Certainty | None = None
```

首批必须记录的 caveat：

- SymPy `solve`、`integrate`、`simplify` 可能返回条件结果、部分结果或未化简形式；工具需要保留 assumptions/domain，并在 `conditions` 中结构化返回条件，必要时再在 `warnings` 中说明 caveat。
- Z3 对非线性实数算术、量词和复杂混合理论可能返回 `unknown`；不得把 `unknown` 提升为证明。
- SciPy optimize 主要是数值局部优化或依赖初值的搜索；除非有额外区间证明，不得返回 `certainty="proved"`。
- 数值 ODE 求解是近似轨迹，不是解析证明；默认只能返回 `certainty="evidence"` 或 `exact` 以外的数值结果。
- NetworkX 图算法通常是确定算法，但输入规模过大时可能触发资源限制；资源错误不能被解释为数学命题失败。
- mpmath 采样和高精度计算受精度、采样点和病态函数影响；未找到反例只能是 evidence。

每个 backend adapter 返回结果前都应查询 caveat registry：若 caveat 与本次 operation 匹配，必须把 caveat 附加到 `warnings` 或 `metadata["backend_caveats"]`。

caveat 与 `certainty` 必须自动联动：

- 若匹配 caveat 的 `affects_certainty=true` 且 `recommended_certainty` 低于当前结果的 `certainty`，handler 必须降级 `certainty`，或在 `metadata["certainty_override_reason"]` 中给出结构化理由。
- 数值优化、Monte Carlo、数值 ODE、纯采样未发现反例等 caveat 默认必须把 `max_certainty` 限制为 `evidence`。
- Z3 返回 `unknown` 时必须返回 `status="unknown"`、`certainty="unknown"`，不得因存在模型片段或启发式结果提升为 `proved`。
- SymPy 返回条件解、部分解、`ConditionSet`、`Piecewise` 或带分支约定的结果时，必须填充 `conditions`；如果条件无法结构化，则 `certainty` 最高只能是 `unknown` 或 `evidence`，不能是 `proved`。
- conformance tests 必须构造至少一个会触发 certainty 降级的 caveat 样例，确认降级不是只追加 warning。

## 11. 表达式输入格式

只支持 SymPy 风格字符串，不支持 LaTeX。

支持示例：

```text
sin(x)**2 + cos(x)**2
(x**2 - 1)/(x - 1)
exp(x)
log(x)
sqrt(x + 1)
Rational(1, 3)
Matrix([[1, 2], [3, 4]])
```

不支持：

```text
\frac{x^2 - 1}{x - 1}
自然语言题目
任意 Python 表达式
文件路径
网络 URL
```

不支持 LaTeX 是固定边界，不作为后续路线保留。LaTeX 转换可以由 LLM 在调用工具前完成。

### 11.1 结构化 AST 输入

表达式字符串是为了 agent 易用性保留的输入形式；高风险或需要强安全边界的 operation 应优先支持结构化 AST。

长期主接口是结构化 AST；表达式字符串是便捷接口和兼容接口。所有高风险 operation 的测试必须覆盖 AST 输入，不能只测字符串输入。

推荐 `expr_ast` 形态：

```json
{
  "op": "add",
  "args": [
    {"var": "x"},
    {"int": 1}
  ]
}
```

常用节点：

```text
int
rational
float
symbol
var
const
add
mul
pow
neg
func
rel
bool
matrix
```

优先要求 AST 输入的领域：

- Z3 约束。
- 逻辑与布尔表达式。
- 不等式。
- 集合恒等式。
- 概率事件。

表达式字符串输入必须经过 12 节安全 parser；AST 输入也必须做节点类型、深度、节点数和变量名白名单校验。

## 12. 安全解析

### 12.1 禁止直接 eval

禁止：

```python
eval(expression)
```

禁止把完整 `sympy.__dict__` 暴露给 parser。

### 12.2 SymPy 字符串解析策略

`parsing/sympy_parser.py` 负责统一解析表达式。

安全策略必须按白名单实现，不能只靠黑名单。`parse_expr` 只能在通过本项目自定义词法/AST 校验之后调用。

强制要求：

- 先做长度限制：`max_expression_chars`。
- 再做 tokenizer，只允许数字、标识符、运算符、括号、逗号、方括号。
- 标识符必须属于变量名、常量名或函数白名单。
- 禁止任意属性访问：`.` 一律不允许，除了数字小数点。
- 禁止任意 dunder：包含 `__` 直接拒绝。
- 禁止关键字：`import`、`open`、`exec`、`eval`、`lambda`、`globals`、`locals`、`getattr`、`setattr`、`compile`、`input`。
- 使用空 `__builtins__`。
- 不暴露完整 `sympy.__dict__`。
- 根据 `variables` 显式创建 `Symbol`。
- 只把允许的函数和常量放进 `local_dict`。
- 解析后遍历 SymPy 表达式树，确认节点类型属于允许集合。
- 对变量数量、表达式树节点数、矩阵规模设置上限。
- 对整数字面量位数、浮点位数、指数绝对值、幂塔深度、括号深度、函数嵌套深度设置上限。
- 对 `factorial`、`binomial`、矩阵构造、求和枚举类输入设置 operation-specific 上限，避免合法表达式触发资源耗尽。
- 默认禁用隐式乘法、自动符号创建和未列入白名单的 SymPy transformation。

建议白名单：

```text
sin, cos, tan, asin, acos, atan
sinh, cosh, tanh
exp, log, sqrt, Abs
floor, ceiling
factorial, binomial
pi, E, I
Rational, Integer, Float
Matrix
```

允许的表达式树节点类型应显式列出，例如：

```text
Symbol
Integer
Rational
Float
Add
Mul
Pow
Function
MatrixBase
Relational
Boolean
```

任何未知节点类型必须返回 `invalid_input`，不能透传给后端。

中长期推荐让高风险 operation 优先走 `expr_ast` 到 SymPy 对象的显式转换路径，字符串表达式只作为 agent 易用入口。即使字符串已经通过词法校验，也不能把 `parse_expr` 当成安全边界。

复杂解析和重计算必须在子进程中运行，即使 parser 漏掉异常输入，也要由 timeout、内存限制和输出限制兜底。

### 12.3 Z3 不解析任意字符串

Z3 工具不接受自然语言约束，也不接受 Python 风格约束字符串。

使用结构化 AST。Z3 AST 可以复用 11.1 的表达式节点风格，也可以使用更贴近 SMT 的约束节点；无论哪种形式，都不能使用 `eval`。

```json
{
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    {"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
    {"op": "gt", "left": {"var": "y"}, "right": {"int": 0}},
    {"op": "eq", "left": {"op": "add", "args": [{"var": "x"}, {"var": "y"}]}, "right": {"int": 10}},
    {"op": "gt", "left": {"var": "x"}, "right": {"var": "y"}}
  ]
}
```

这样可以彻底避免 Z3 侧的 `eval` 风险。

## 13. timeout 与资源限制

所有工具都要有 timeout。默认：

```text
timeout_ms = 5000
cpu_time_ms = 5000
memory_mb = 512
file_size_mb = 16
max_output_chars = 8000
max_matrix_size = 50 x 50
max_variables = 20
max_expression_chars = 5000
max_samples = 1000 默认，100000 硬上限
max_expression_nodes = 2000
max_graph_nodes = 10000
max_graph_edges = 50000
```

资源限制按 Linux-only 设计。本项目只支持 Linux + conda + stdio MCP，不支持 macOS、Windows 或跨平台降级运行：

- 必须实现 wall-clock timeout、CPU time limit、memory limit、file size limit 和输出长度限制。
- 必须实现网络隔离；不能强制网络隔离的环境不满足验收条件。
- 必须拒绝 macOS/Windows 运行。启动时若检测到非 Linux 平台，应退出并返回清晰错误；工具层如需结构化表达，应使用 `error_code="PLATFORM_UNSUPPORTED"`。
- 工具不得联网，且不得读取用户未显式传入的本地文件。

### 13.1 子进程隔离

复杂计算应走子进程 runner：

```text
MCP tool
  -> validate request
  -> subprocess_runner.run_backend(task_name, payload, timeout_ms)
  -> normalize result
  -> return ToolResult
```

适合强制子进程隔离的工具：

- `integrate`
- `solve_equation`
- `solve_system`
- `groebner_basis`
- `numeric_optimize`
- `z3_satisfiability`
- `z3_find_counterexample`
- `search_counterexample`
- `matrix_decomposition_numeric`
- `probability_simulation`
- `ode_solve_numeric`
- `truth_table`
- `finite_quantifier_check`
- `power_set`

简单工具也要做输入规模限制：

- `simplify_expression`
- `expand_expression`
- `factor_expression`
- `differentiate`
- `series_expand`

子进程 runner 应实现：

- wall-clock timeout。
- CPU time limit。
- memory limit。
- stdout/stderr 最大长度。
- 返回 JSON，不返回任意 pickle 对象。
- 子进程环境变量清理。
- 禁止网络访问，必须使用 Linux sandbox 或容器网络隔离。

Linux 实现细节：

- 使用独立进程组启动 backend worker，timeout 时 kill 整个进程组，避免子进程遗留。
- 使用 `resource.setrlimit` 设置 `RLIMIT_CPU`、`RLIMIT_AS`、`RLIMIT_FSIZE` 和必要时的 `RLIMIT_NOFILE`。
- worker 只通过 stdin/stdout 传 JSON；stderr 必须截断并归一化为错误摘要。
- worker 环境变量使用 allowlist，只保留必要的 Python/conda 运行变量，不继承密钥、代理、用户 shell 配置。
- 网络隔离必须使用 Linux OS sandbox，例如 `unshare` network namespace、`bubblewrap` 或容器 `--network=none`。若当前环境不能强制网络隔离，server 必须拒绝启动或拒绝执行 backend worker，不能降级为非隔离运行；工具层如需结构化表达，应使用 `error_code="SANDBOX_UNAVAILABLE"`。
- 不允许工具读取用户未显式传入的本地路径；如果后端异常信息包含绝对路径，返回前必须脱敏。

### 13.2 metadata trace

每次工具调用都应在 `ToolResult.metadata` 中返回最小可审计 trace：

```json
{
  "public_tool": "algebra_compute",
  "operation": "simplify_expression",
  "operation_version": "1.0",
  "operation_state": "implemented",
  "backend_versions": {
    "sympy": "x.y.z"
  },
  "limits_requested": {
    "timeout_ms": 5000
  },
  "limits_applied": {
    "timeout_ms": 5000,
    "cpu_time_ms": 5000,
    "memory_mb": 512,
    "file_size_mb": 16,
    "cpu_time_limit_enforced": true,
    "memory_limit_enforced": true,
    "file_size_limit_enforced": true,
    "network_isolated": true
  },
  "proof_method": "symbolic",
  "fallbacks_used": [],
  "input_form": "expression_string",
  "determinism": "deterministic",
  "seed": null
}
```

trace 不应包含完整原题自然语言，也不应记录用户未授权的文件路径或敏感内容。

#### 13.2.1 trace 隐私策略

trace 的默认目标是工程可审计，而不是记录用户问题。默认 trace 必须最小化：

- 不记录完整自然语言 prompt。
- 不记录论文、教材、网页或用户文档内容。
- 不记录用户本地文件绝对路径；如确需定位测试 fixture，只记录仓库内相对标识。
- 不记录 API key、环境变量、conda 路径、home 目录、临时目录中的敏感文件名。
- 不记录完整表达式以外的题面上下文；表达式本身若很长，应按 `max_output_chars` 或单独的 trace 限制截断。
- 不记录 backend stderr 的完整内容；只记录错误类型、截断摘要和 `error_code`。

详细 trace 只能在显式 debug 模式下启用，例如：

```text
MATH_MCP_DEBUG_TRACE=1
```

即使 debug 模式启用，也必须继续遵守“不记录密钥、不记录未授权文件内容、不记录完整论文/教材内容”的边界。debug trace 的存在必须在 `metadata["debug_trace_enabled"]` 中明确标记，便于测试确认默认模式没有泄露敏感上下文。

### 13.3 determinism 与 seed

所有带随机性的 operation 必须显式声明 determinism：

```text
deterministic      相同输入必然得到相同结果
seeded_random      给定 seed 后可复现
nondeterministic   不保证复现，原则上不应用于核心数学验证
```

默认要求：

- 采样、Monte Carlo、随机反例搜索必须支持 `limits.seed`。
- 若用户未提供 seed，工具必须生成 seed 并在 `metadata["seed"]` 返回。
- golden tests 不得依赖未指定 seed 的随机输出。
- `nondeterministic` operation 不得返回 `certainty="proved"`。

### 13.4 timeout 返回

超时必须返回结构化错误：

```json
{
  "ok": false,
  "status": "timeout",
  "certainty": "error",
  "method": "none",
  "result_kind": "none",
  "result": null,
  "backend": "sympy",
  "duration_ms": 5002,
  "warnings": [],
  "error": "Computation exceeded timeout_ms=5000",
  "error_code": "BACKEND_TIMEOUT"
}
```

## 14. 工具细节

本节示例描述具体 operation 的语义。实际 MCP 调用应通过 4.0 中的领域级 tool 进入，例如 `verification_compute(operation="check_identity", payload={...})`。

### 14.1 `check_identity`

输入：

```json
{
  "left": "sin(x)**2 + cos(x)**2",
  "right": "1",
  "variables": ["x"]
}
```

执行：

1. 解析 `left` 和 `right`。
2. 计算 `simplify(left - right)`。
3. 若结果为 `0`，返回 `proved_by_symbolic_simplification`。
4. 若不能证明，做有限采样。
5. 若发现不等，返回 `disproved_by_counterexample`。
6. 若未发现反例，返回 `numeric_evidence_only`。

关键规则：

- 只有符号化简为 0 才能称为 proof。
- 采样不等于证明。

### 14.2 `search_counterexample`

输入采用左右表达式加关系，不用自然语言 claim。实际 MCP 调用中，变量域放在顶层 `domains`，不要塞进 payload：

```json
{
  "operation": "search_counterexample",
  "payload": {
    "left": "x**2",
    "relation": ">=",
    "right": "x",
    "variables": ["x"],
    "samples": 1000
  },
  "domains": [
    {
      "variable": "x",
      "kind": "real",
      "lower": "0",
      "upper": "1",
      "lower_closed": true,
      "upper_closed": true
    }
  ],
  "limits": {
    "timeout_ms": 5000
  }
}
```

关系支持：

```text
==, !=, <, <=, >, >=
```

域必须使用 10.3 中的结构化 `DomainSpec`，不能使用自然语言或自由字符串。`samples` 是 operation-specific 请求值，但必须受 `limits.max_samples` 约束。

找到反例返回：

```json
{
  "ok": true,
  "status": "counterexample_found",
  "certainty": "disproved",
  "method": "counterexample",
  "result_kind": "witness",
  "result": {
    "assignment": {"x": "0.5"},
    "left_value": "0.25",
    "right_value": "0.5",
    "relation": ">="
  },
  "backend": "mpmath",
  "duration_ms": 18,
  "warnings": []
}
```

未找到反例返回：

```json
{
  "ok": true,
  "status": "no_counterexample_found",
  "certainty": "evidence",
  "method": "numeric_sampling",
  "result_kind": "verification",
  "result": null,
  "explanation": "No counterexample was found in the sampled bounded domain. This is not a proof.",
  "backend": "mpmath",
  "duration_ms": 22,
  "warnings": ["numeric sampling is not proof"]
}
```

### 14.3 `z3_satisfiability`

Z3 工具只接受结构化 AST。

输入：

```json
{
  "variables": {
    "x": "Int",
    "y": "Int"
  },
  "constraints": [
    {"op": "gt", "left": {"var": "x"}, "right": {"int": 0}},
    {"op": "gt", "left": {"var": "y"}, "right": {"int": 0}},
    {"op": "eq", "left": {"op": "add", "args": [{"var": "x"}, {"var": "y"}]}, "right": {"int": 10}},
    {"op": "gt", "left": {"var": "x"}, "right": {"var": "y"}}
  ]
}
```

实际 MCP 调用中 timeout 应放入 top-level `limits`，例如 `limits={"timeout_ms": 5000}`，不要混入 Z3 payload。

输出：

```json
{
  "ok": true,
  "status": "success",
  "certainty": "exact",
  "method": "backend",
  "result_kind": "witness",
  "result": {
    "satisfiable": true,
    "model": {
      "x": "6",
      "y": "4"
    }
  },
  "backend": "z3",
  "duration_ms": 9,
  "warnings": []
}
```

对于 `unsat`：

```json
{
  "ok": true,
  "status": "proved_by_smt",
  "certainty": "proved",
  "method": "smt",
  "result_kind": "verification",
  "result": {
    "satisfiable": false
  },
  "backend": "z3",
  "duration_ms": 7,
  "warnings": []
}
```

### 14.4 `matrix_compute`

`det` 的 payload：

```json
{
  "matrix": [["1", "2"], ["3", "4"]]
}
```

支持操作：

```text
det
rank
inverse
rref
eigenvals
trace
transpose
charpoly
```

输出：

```json
{
  "ok": true,
  "status": "success",
  "certainty": "exact",
  "method": "backend",
  "result_kind": "value",
  "result": "-2",
  "backend": "sympy",
  "duration_ms": 4,
  "warnings": []
}
```

矩阵元素建议用字符串表示，保持精确有理数：

```json
[["1/3", "2"], ["0", "5/7"]]
```

实际 MCP 调用为：

```json
{
  "operation": "det",
  "payload": {
    "matrix": [["1", "2"], ["3", "4"]]
  }
}
```

### 14.5 `graph_compute`

`shortest_path` 的 payload：

```json
{
  "directed": false,
  "nodes": ["A", "B", "C"],
  "edges": [["A", "B"], ["B", "C"]],
  "source": "A",
  "target": "C"
}
```

支持操作：

```text
is_connected
connected_components
shortest_path
has_cycle
topological_sort
maximum_matching
minimum_spanning_tree
```

实际 MCP 调用为：

```json
{
  "operation": "shortest_path",
  "payload": {
    "directed": false,
    "nodes": ["A", "B", "C"],
    "edges": [["A", "B"], ["B", "C"]],
    "source": "A",
    "target": "C"
  }
}
```

对不适用操作返回 `unsupported`，例如无向图请求拓扑排序。

### 14.6 `check_identity_constrained`

V1 新增的约束恒等验证 operation（`verification_compute`）。语义分层与字段见 §24.6：参数化/代入走符号证明，无参数化时只在满足约束的确定性网格点上采样，绝不退化为忽略约束的自由变量采样。`metadata.constraint_mode` 记录所用模式。

### 14.7 `constrained_optimize`

V1 新增的约束优化 operation（`calculus_compute`），`max_certainty="evidence"`。`symbolic_lagrange` 处理等式约束并返回 Lagrange 候选临界点，`numeric` 用 SciPy 约束局部搜索并返回约束残差。详见 §24.7。

## 15. 测试要求

本项目必须有测试。测试是交付的一部分，不是附加项。

### 15.1 必跑命令

```bash
pytest
ruff check .
mypy src
```

验收时三者必须通过。

### 15.2 单元测试覆盖

每个工具文件都要有对应测试：

```text
tools/capabilities.py   -> tests/test_capabilities.py
tools/algebra.py        -> tests/test_algebra.py
tools/calculus.py       -> tests/test_calculus.py
tools/verification.py   -> tests/test_verification.py
tools/z3_tools.py       -> tests/test_z3_tools.py
tools/matrix.py         -> tests/test_matrix.py
tools/discrete.py       -> tests/test_discrete.py
tools/graph.py          -> tests/test_graph.py
tools/probability.py    -> tests/test_probability.py
tools/sets.py           -> tests/test_sets.py
tools/geometry.py       -> tests/test_geometry.py
tools/trigonometry.py   -> tests/test_trigonometry.py
tools/number_theory.py  -> tests/test_number_theory.py
tools/logic.py          -> tests/test_logic.py
tools/ode.py            -> tests/test_ode.py
tools/complex_tools.py  -> tests/test_complex_tools.py
tools/inequalities.py   -> tests/test_inequalities.py
```

每个工具至少测试：

- 成功路径。
- 无效输入。
- 不支持输入。
- 输出 schema。
- 超大输出限制。
- timeout 或近似 timeout 行为。
- operation 不存在时返回 `unsupported`。
- domain/assumption 无法解释时返回 `invalid_input` 或 `unsupported`。

### 15.3 安全测试

`tests/test_security.py` 必须覆盖：

```text
__import__("os").system("id")
open("/etc/passwd").read()
globals()
locals()
lambda x: x
().__class__
sympy.__dict__
http://example.com
```

这些输入必须被拒绝，状态为：

```text
invalid_input
```

或：

```text
unsupported
```

### 15.3.1 Sandbox acceptance tests

`tests/test_sandbox.py` 必须验证运行期隔离真的生效，而不是只在文档中声明。

必须覆盖：

- backend worker 尝试创建 TCP socket 连接时失败；若当前 Linux 环境无法强制网络隔离，server 必须拒绝启动或拒绝执行 backend worker。
- backend worker 尝试读取未显式传入的本地绝对路径时失败，错误信息不得泄露完整绝对路径。
- 超时后 worker 进程组被清理，测试结束时无遗留子进程。
- 超大 stdout/stderr 被截断，返回 `output_too_large` 或结构化 backend error，且 stderr 不包含完整环境变量、密钥、home 目录或 conda 路径。
- CPU time、memory、file size limit 至少各有一个触发样例；这些 limit 不能降级为未启用。
- 子进程只通过 JSON 通道返回结果，pickle 或任意二进制对象必须被拒绝。
- 非 Linux 平台启动必须失败，并返回清晰错误，不能进入半支持状态。
- sandbox 不可用时应返回或记录稳定错误 `SANDBOX_UNAVAILABLE`；非 Linux 平台应返回或记录稳定错误 `PLATFORM_UNSUPPORTED`。

这些测试属于验收门禁。任何 sandbox 限制无法强制启用时，本 MCP 不允许作为已验收交付运行。

### 15.4 Fuzz 与 property-based 测试

`tests/test_security.py` 和 `tests/test_parsing_sympy.py` 必须包含 Hypothesis/property-based tests：

- 随机生成包含危险 token 的字符串，确认 parser 拒绝。
- 随机生成超长表达式，确认触发长度限制。
- 随机生成深度嵌套括号，确认触发节点数或深度限制。
- 随机生成合法小表达式，确认 parse -> serialize -> parse 稳定。
- 随机生成有限集合，检查集合运算满足交换律、结合律、分配律。
- 随机生成小矩阵，交叉验证 `det(A*B)=det(A)*det(B)`。

Fuzz 测试不要求覆盖全部数学正确性，但必须覆盖 parser 安全边界和资源限制边界。

### 15.5 差分测试

对关键工具增加 differential tests：

- 代数恒等式：SymPy 符号化简结果与随机数值采样一致。
- 不等式：区间求解结果与边界点/随机点采样一致。
- Z3：小整数域结果与有限枚举一致。
- 矩阵：SymPy 精确结果与 NumPy 数值结果在容差内一致。
- 概率：小型离散概率结果与有限枚举一致。

差分测试发现冲突时，测试应暴露冲突，不应自动选择其中一个结果。

### 15.6 数值证据测试

必须测试工具不会把采样证据说成证明：

```text
search_counterexample 未找到反例 -> certainty 必须是 evidence，method 必须是 numeric_sampling
check_identity 仅采样通过 -> status 必须是 numeric_evidence_only，certainty 必须是 evidence
```

### 15.7 Z3 测试

必须包含：

- SAT 返回模型。
- UNSAT 返回 `proved_by_smt`。
- UNKNOWN 返回 `unknown`。
- timeout 返回 `timeout`。
- 非法 AST 返回 `invalid_input`。

### 15.8 capabilities 测试

`tests/test_capabilities.py` 必须验证：

- `math_capabilities` 返回所有公开 MCP tools。
- `math_capabilities` 返回 `schema_version` 和 `capabilities_version`。
- 每个公开 MCP tool 声明 `kind`，取值为 `utility` 或 `compute`。
- `ping` 和 `math_capabilities` 的 `kind` 必须是 `utility`，且 `operations` 为空。
- 每个计算类公开 tool 有 operation 清单。
- 每个 operation 有最小输入示例。
- 每个 operation 声明 `operation_version` 和 `state`。
- 每个 operation 声明默认 limits。
- 每个 operation 声明 `risk`、`complexity_class`、`runs_in_subprocess`、`proof_modes`、`max_certainty`、`numeric_only`、`result_kinds`、`accepted_input_forms`。
- capabilities 输出中的 `proof_capable` 由 `proof_modes` 自动派生，并与 `bool(proof_modes)` 保持一致。
- 每个 operation 声明 `determinism`。
- 每个 operation 暴露 `payload_schema`。
- `payload_schema.properties` 不包含名为 `operation` 的子字段。
- 每个 operation 暴露 `deprecated` 和结构化 `replacement`；非空 replacement 必须包含 `public_tool` 和 `operation`。
- 默认 capabilities 不暴露 `experimental` 和 `disabled` operation。
- `include_experimental=true` 时可以发现实验 operation，但测试必须标明其不能作为默认 agent 调用候选。
- `include_disabled=true` 时可以发现禁用 operation，且调用必须返回 `unsupported`。
- 文档中的 operation 与 capabilities 输出一致。
- capabilities 输出由 `operation_registry.py` 生成。

### 15.9 registry、error 与 seed 测试

必须包含：

- `tests/test_operation_registry.py`：registry 中每个 operation 都能被对应 public tool 路由。
- `tests/test_error_codes.py`：每类主要错误返回稳定 `error_code`。
- `tests/test_error_codes.py` 必须覆盖 domain/assumption 冲突并触发 `CONSTRAINT_CONFLICT`。
- `tests/test_seed_determinism.py`：所有 `seeded_random` operation 在相同 seed 下可复现。
- 高风险 operation 至少有一个 AST 输入测试。
- 需要返回 `proved` 或 `disproved` 的核心 operation 至少有一个 `certificate` 测试。
- backend caveat registry 中的每个 caveat 至少被一个 operation 或测试样例引用。

### 15.10 Conformance tests

`tests/test_conformance.py` 必须验证实现符合公开协议，不依赖单个数学后端的偶然行为。

必须覆盖：

- 4.0 中声明的公开 MCP tools 全部出现在 `math_capabilities["public_tools"]`。
- `ping` 和 `math_capabilities` 在 capabilities 中标记为 `kind="utility"`，计算类工具标记为 `kind="compute"`。
- `math_capabilities` 中的每个 operation 都能路由到对应 public tool。
- 每个默认暴露的 operation 都有 `operation_version`、`state`、`payload_schema`、`default_limits`、`determinism`、`risk`、`complexity_class`、`proof_modes`、`max_certainty`、`result_kinds`、`accepted_input_forms`。
- 每个 operation 的 `example_payload` 必须通过自己的 `payload_schema`。
- 每个 `payload_schema` 至少包含 `type`；对象 payload 必须声明 `properties`，有必填字段时必须声明 `required`。
- 每个 `state="deprecated"` 的 operation 必须有 `deprecated=True` 和结构化 `replacement`，且 replacement 指向默认 capabilities 中可发现、可调用的 `public_tool` 与 `operation`；未弃用 operation 的 replacement 必须为 null。
- 每个 `state="disabled"` 的 operation 调用必须短路为 `unsupported`，且不得执行 backend。
- 每个 operation 的默认 limits 不得超过全局 hard cap；operation-specific override 必须在 registry 中显式声明。
- 每个 `ErrorCode` 至少有一个测试样例触发。
- 所有计算类 public tool 返回对象都能被 `ToolResult` 校验；`ping` 和 `math_capabilities` 使用各自的 utility schema。
- 所有成功返回必须设置合理的 `result_kind`；条件结果必须使用 `conditions` 字段承载结构化条件。
- payload schema 不得包含名为 `operation` 的子字段；operation 只能出现在 MCP tool 顶层参数中。
- registry 中不得存在手写 `proof_capable` 字段；capabilities 输出中的 `proof_capable` 必须由 `proof_modes` 派生，并与 `bool(proof_modes)` 保持一致。
- `conditions` 中可结构化表达的条件必须包含 `condition_ast`；仅有字符串条件时必须降低 certainty 或给出结构化降级原因。
- domain/assumption 冲突必须返回 `CONSTRAINT_CONFLICT`，不得进入 backend。
- `affects_certainty=true` 的 backend caveat 必须触发 certainty 降级，除非返回 `metadata["certainty_override_reason"]`。
- 默认 trace 不包含完整 prompt、本地绝对路径、环境变量或未授权文件内容。
- debug trace 只有显式开启时才出现，并且仍不能包含密钥或文件内容。

Conformance tests 应该优先从 registry、capabilities 和 schema 自动生成用例，避免手写重复清单。

### 15.11 MCP smoke test

必须有真实 MCP stdio 调用测试。

`tests/test_server_smoke.py` 示例：

```python
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_ping_and_simplify() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "math_mcp"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert "ping" in names
            assert "math_capabilities" in names
            assert "algebra_compute" in names

            result = await session.call_tool(
                "algebra_compute",
                {
                    "operation": "simplify_expression",
                    "payload": {
                        "expression": "sin(x)**2 + cos(x)**2 - 1",
                        "variables": ["x"],
                    },
                },
            )

            assert result.isError is False
            assert result.structuredContent is not None
            assert result.structuredContent["result"] == "0"
```

如果 SDK 版本字段名变化，测试应以当前稳定 SDK 的实际返回对象为准调整，但必须保留真实 stdio smoke test。

### 15.12 Golden tests

使用 JSON fixture 固定典型样例：

`tests/golden/algebra_cases.json`：

```json
[
  {
    "tool": "algebra_compute",
    "input": {
      "operation": "simplify_expression",
      "payload": {
        "expression": "sin(x)**2 + cos(x)**2 - 1",
        "variables": ["x"]
      }
    },
    "expected": {
      "ok": true,
      "status": "success",
      "certainty": "exact",
      "method": "backend",
      "result_kind": "value",
      "result": "0"
    }
  }
]
```

Golden tests 只断言稳定字段：

- `ok`
- `status`
- `certainty`
- `method`
- `result_kind`
- `result`

不要断言 `duration_ms`。

### 15.13 Agent 场景测试

准备 `examples/sample_calls.md`，覆盖这些任务：

1. 恒等式证明：`sin(x)^2 + cos(x)^2 = 1`
2. 方程求解：`x^2 - 5x + 6 = 0`
3. 反例搜索：`x^2 >= x` 在 `[0,1]`
4. 矩阵行列式：`[[1,2],[3,4]]`
5. Z3 约束：正整数 `x,y`，`x+y=10`，`x>y`
6. 级数展开：`exp(x)` 在 0 到 5 阶
7. Groebner basis：小规模多项式系统
8. 图最短路：三节点路径
9. 组合计数：`C(10,3)`
10. 数值优化：简单凸函数最小值
11. 概率计算：抛两枚公平硬币，至少一个正面的概率
12. 贝叶斯更新：给定先验、似然和证据概率计算后验
13. 集合恒等式：验证 `A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)`
14. 区间计算：`[0,2] ∩ (1,3]`
15. 解析几何：两直线交点或点到直线距离
16. 三角恒等式：验证 `sin(2*x) = 2*sin(x)*cos(x)`
17. 数论：求 `17` 在模 `43` 下的逆元
18. 逻辑：验证 `(p -> q)` 与 `(~p or q)` 等价
19. ODE：验证 `y = C*exp(x)` 是 `y' = y` 的解
20. 复数：求 `1 + I` 的模和辐角
21. 不等式：解 `x**2 - 1 >= 0` 的实数解集

这些样例不代替 pytest，但用于验证 agent 是否会正确选择工具。

### 15.14 Agent 调用策略

推荐 agent 调用顺序：

1. 不确定能力或输入格式时，先调用 `math_capabilities`。
2. 需要精确代数、微积分、矩阵、数论结果时，优先调用对应 symbolic operation。
3. 需要判断约束可满足性、整数解或布尔逻辑时，优先调用 `z3_compute` 或有限穷举 operation。
4. 需要证明等级时，优先选择 `proof_modes` 非空且 `max_certainty` 可达到 `proved` 或 `disproved` 的 operation。
5. 数值采样、数值优化、Monte Carlo、数值 ODE 只作为 `certainty="evidence"`，不能写成证明。
6. 工具返回 `unknown`、`timeout` 或 `unsupported` 时，缩小 domain、降低规模、换 backend，或向用户说明无法严格判定。
7. 当同一问题可由多个后端验证时，优先使用 differential check 或第二个 operation 交叉确认。
8. 最终回答必须结合 `certainty`、`method`、`result_kind` 和 `conditions`，显式区分证明、精确计算、条件结果、反例、数值证据和未知。

### 15.15 Benchmarks

必须维护 `benchmarks/`：

```text
benchmarks/basic_latency.py
benchmarks/operation_matrix.json
```

benchmark 至少记录：

- operation。
- operation_version。
- operation_state。
- complexity_class。
- payload 规模。
- p50/p95 latency。
- timeout rate。
- output size。
- subprocess overhead。
- backend version。

benchmark 不作为功能正确性的替代，但用于发现慢 operation、默认 limit 不合理和回归。

### 15.16 Agent eval 集

必须维护：

```text
evals/math_agent_cases.jsonl
```

每条 eval case 至少包含：

```json
{
  "id": "identity_trig_001",
  "prompt": "证明 sin(x)^2 + cos(x)^2 = 1",
  "expected_public_tool": "verification_compute",
  "expected_operation": "check_identity",
  "expected_operation_state": "implemented",
  "expected_certainty": "proved",
  "expected_method": "symbolic",
  "expected_result_kind": "verification",
  "expected_certificate_type": "symbolic_simplification",
  "allow_numeric_evidence": false
}
```

eval 集用于检查 agent 是否选对工具、是否误把 evidence 写成 proof、是否能处理 timeout/unknown。

eval 集必须同时包含负例和恢复场景，不能只覆盖成功调用：

- LaTeX 输入：agent 应先转换为支持的表达式格式，或在无法可靠转换时说明输入格式不支持。
- 自然语言 claim：agent 不应直接把完整题面塞给 math-mcp，应拆成结构化表达式、domain 和 relation。
- 超时：agent 应缩小规模、降低样本数、换 operation，或明确说明无法严格判定。
- Z3 `unknown`：agent 不得写成证明，应报告 unknown 并可尝试有限枚举或缩小理论片段。
- 数值采样未发现反例：agent 必须保持 `certainty="evidence"`，不能写成命题成立。
- 条件解：agent 必须读取 `conditions`，最终回答中说明条件；若条件缺少 `condition_ast`，应降低结论强度。
- unsupported domain：agent 应识别 `DOMAIN_UNSUPPORTED` 或 `CONSTRAINT_CONFLICT`，调整 domain 或向用户说明约束不可用。
- disabled operation：agent 不应反复调用；有 `replacement` 时按替代 operation 迁移，没有 replacement 时根据 capabilities 选择其他可用 operation 或报告不可用。

## 16. 编码工作包

这里使用“工作包”而不是“阶段”。所有工作包都属于同一次完整交付范围。

工作包可以并行开发，但 P0 gate 必须先通过：schema、capabilities、安全 parser、runtime limits、MCP smoke test。

发布状态按 10.5 执行：工作包可以先提交 `experimental` operation，但只有通过对应质量门禁的 operation 才能改为 `implemented` 并默认暴露在 `math_capabilities` 中。首批 `implemented` operation 必须先满足 5.8。

### 16.1 项目骨架

交付：

- `math-mcp/` 项目目录。
- `environment.yml`。
- `pyproject.toml`。
- `src/math_mcp/` 包结构。
- `tests/` 测试结构。
- `benchmarks/` 基准结构。
- `evals/` agent eval 结构。
- `README.md`。

验收：

```bash
conda env create -f environment.yml
conda activate math-mcp
pip install -e .
python -m math_mcp
```

### 16.2 通用 schema 和状态

交付：

- `status.py`
- `schemas.py`
- `errors.py`
- `operation_registry.py`
- `backend_caveats.py`
- `tools/capabilities.py`
- `runtime/timing.py`
- `runtime/serialization.py`

验收：

```bash
pytest tests/test_schemas.py tests/test_capabilities.py tests/test_operation_registry.py tests/test_conformance.py tests/test_error_codes.py
```

### 16.3 安全解析

交付：

- `parsing/sympy_parser.py`
- `parsing/domain_parser.py`
- `parsing/z3_ast.py`

验收：

```bash
pytest tests/test_parsing_sympy.py tests/test_security.py
```

### 16.4 子进程和 timeout

交付：

- `runtime/subprocess_runner.py`
- `runtime/limits.py`

验收：

```bash
pytest tests/test_timeouts.py tests/test_sandbox.py tests/test_seed_determinism.py
```

### 16.5 代数和微积分工具

交付：

- `backends/sympy_backend.py`
- `tools/algebra.py`
- `tools/calculus.py`

验收：

```bash
pytest tests/test_algebra.py tests/test_calculus.py
```

### 16.6 验证和反例工具

交付：

- `tools/verification.py`
- `backends/mpmath_backend.py`

验收：

```bash
pytest tests/test_verification.py tests/test_counterexample.py
```

### 16.7 Z3 工具

交付：

- `backends/z3_backend.py`
- `tools/z3_tools.py`

验收：

```bash
pytest tests/test_z3_tools.py
```

### 16.8 矩阵、组合、图工具

交付：

- `backends/numpy_backend.py`
- `backends/networkx_backend.py`
- `tools/matrix.py`
- `tools/discrete.py`
- `tools/graph.py`

验收：

```bash
pytest tests/test_matrix.py tests/test_discrete.py tests/test_graph.py
```

### 16.9 概率、集合、解析几何、三角工具

交付：

- `backends/scipy_backend.py`
- `tools/probability.py`
- `tools/sets.py`
- `tools/geometry.py`
- `tools/trigonometry.py`

验收：

```bash
pytest tests/test_probability.py tests/test_sets.py tests/test_geometry.py tests/test_trigonometry.py
```

### 16.10 数论、逻辑、ODE、复数、不等式工具

交付：

- `tools/number_theory.py`
- `tools/logic.py`
- `tools/ode.py`
- `tools/complex_tools.py`
- `tools/inequalities.py`

验收：

```bash
pytest tests/test_number_theory.py tests/test_logic.py tests/test_ode.py tests/test_complex_tools.py tests/test_inequalities.py
```

### 16.11 MCP 注册

交付：

- `server.py` 只注册 4.0 中定义的公开 MCP tools。
- 不把每个 operation 都注册成独立 MCP tool。
- 每个 tool 有简洁 docstring。
- `__main__.py` 支持 `python -m math_mcp`。

验收：

```bash
pytest tests/test_server_smoke.py
```

### 16.12 全量质量门禁

交付完成前必须通过：

```bash
pytest
ruff check .
mypy src
```

## 17. MCP tool 文档规范

每个 tool docstring 必须包含：

- 工具做什么。
- 输入格式重点。
- 返回结果的证明等级。
- 何时返回 `certificate`，何时只能返回数值证据。
- 不支持的情况。

示例：

```python
from typing import Any


@mcp.tool()
def verification_compute(
    operation: str,
    payload: dict[str, Any],
    domains: list[dict[str, Any]] | None = None,
    assumptions: list[dict[str, Any]] | None = None,
    limits: dict[str, Any] | None = None,
) -> ToolResult:
    """Run a verification operation such as identity checking or counterexample search.

    The operation must be listed by math_capabilities.
    Returns proof only for symbolic, SMT, interval, or finite-exhaustive checks.
    Numeric sampling is reported as evidence only and must not be treated as proof.
    Expressions must use supported math syntax, not LaTeX or natural language.
    """
    ...
```

agent 依赖这些描述选择工具，docstring 不是形式工作。

## 18. 本地客户端 smoke 脚本

`examples/mcp_client_smoke.py`：

```python
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "math_mcp"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])

            capabilities = await session.call_tool("math_capabilities", {})
            print(capabilities)

            result = await session.call_tool(
                "algebra_compute",
                {
                    "operation": "simplify_expression",
                    "payload": {
                        "expression": "sin(x)**2 + cos(x)**2 - 1",
                        "variables": ["x"],
                    },
                },
            )
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```bash
python examples/mcp_client_smoke.py
```

## 19. Codex 本地注册建议

最终命令形态应类似：

```bash
codex mcp add math-mcp -- python -m math_mcp
```

实际命令以当前 Codex CLI 支持的 MCP 注册语法为准。注册后验证：

```bash
codex mcp list
```

运行期要求：

- Codex 启动 MCP server 时使用 `math-mcp` conda 环境。
- 若 Codex 不能继承 conda 环境，使用环境内 Python 的绝对路径。

示例：

```bash
/home/USER/anaconda3/envs/math-mcp/bin/python -m math_mcp
```

## 20. 验收样题

### 20.1 恒等式

题目：

```text
证明 sin(x)^2 + cos(x)^2 = 1。
```

期望：

- 调用 `verification_compute(operation="check_identity")`。
- 返回 `proved_by_symbolic_simplification`。
- `certainty = proved`。

### 20.2 方程

题目：

```text
解 x^2 - 5x + 6 = 0。
```

期望：

- 调用 `algebra_compute(operation="solve_equation")`。
- 返回 `2` 和 `3`。
- `certainty = exact`。

### 20.3 反例

题目：

```text
判断对所有 x in [0,1]，x^2 >= x 是否成立。
```

期望：

- 调用 `verification_compute(operation="search_counterexample")`。
- 找到 `x = 0.5` 或其他 `(0,1)` 内反例。
- `certainty = disproved`。

### 20.4 矩阵

题目：

```text
计算 [[1,2],[3,4]] 的行列式。
```

期望：

- 调用 `matrix_compute(operation="det")`。
- 返回 `-2`。

### 20.5 Z3

题目：

```text
是否存在正整数 x,y，使得 x+y=10 且 x>y？
```

期望：

- 调用 `z3_compute(operation="z3_satisfiability")`。
- 返回模型，例如 `x=6, y=4`。

### 20.6 级数

题目：

```text
求 exp(x) 在 x=0 的 5 阶展开。
```

期望：

- 调用 `calculus_compute(operation="series_expand")`。
- 返回 `1 + x + x**2/2 + x**3/6 + x**4/24 + x**5/120 + O(x**6)`。

### 20.7 图论

题目：

```text
图 A-B-C 中，A 到 C 的最短路径是什么？
```

期望：

- 调用 `graph_compute(operation="shortest_path")`。
- 返回 `["A", "B", "C"]`。

### 20.8 概率论

题目：

```text
抛两枚公平硬币，至少一个正面的概率是多少？
```

期望：

- 调用 `probability_compute(operation="event_probability")`。
- 返回 `3/4`。
- `certainty = exact`。

### 20.9 集合

题目：

```text
验证 A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)。
```

期望：

- 调用 `set_compute(operation="set_identity_check")`。
- 返回恒等式成立。
- `certainty = proved` 或 `exact`，取决于实现采用符号集合还是有限抽样验证。

### 20.10 解析几何

题目：

```text
求点 (1,2) 到直线 3x + 4y - 5 = 0 的距离。
```

期望：

- 调用 `geometry_compute(operation="geometry_distance")`。
- 返回 `6/5`。
- `certainty = exact`。

### 20.11 三角函数

题目：

```text
验证 sin(2*x) = 2*sin(x)*cos(x)。
```

期望：

- 调用 `trigonometry_compute(operation="trig_identity_check")`。
- 返回 `proved_by_symbolic_simplification`。
- `certainty = proved`。

### 20.12 数论

题目：

```text
求 17 在模 43 下的乘法逆元。
```

期望：

- 调用 `number_theory_compute(operation="modular_arithmetic")`。
- 返回 `38`，因为 `17 * 38 ≡ 1 (mod 43)`。
- `certainty = exact`。

### 20.13 逻辑

题目：

```text
验证 (p -> q) 与 (~p or q) 是否等价。
```

期望：

- 调用 `logic_compute(operation="logic_equivalence_check")`。
- 返回等价。
- `certainty = proved`。

### 20.14 ODE

题目：

```text
验证 y = C*exp(x) 是否满足 y' = y。
```

期望：

- 调用 `ode_compute(operation="ode_verify_solution")`。
- 返回满足。
- `certainty = proved`。

### 20.15 复数

题目：

```text
求 1 + I 的模和辐角。
```

期望：

- 调用 `complex_compute(operation="complex_mod_arg")`。
- 返回模 `sqrt(2)`、辐角 `pi/4`。
- `certainty = exact`。

### 20.16 不等式

题目：

```text
解 x**2 - 1 >= 0 的实数解集。
```

期望：

- 调用 `inequality_compute(operation="inequality_domain_solve")`。
- 返回 `(-oo, -1] ∪ [1, oo)`。
- `certainty = exact` 或 `proved`。

## 21. 质量标准

交付完成必须满足：

- 本地 stdio MCP server 能启动。
- 4.0 中的公开 MCP tools 均已注册。
- operation 不被注册为独立 MCP tool。
- `math_capabilities` 与实际支持的 operation 一致。
- `math_capabilities` 返回 `schema_version` 和 `capabilities_version`。
- 默认 `math_capabilities` 只暴露 `implemented` 和可调用的 `deprecated` operation。
- `operation_registry.py` 是 capabilities、server 路由、测试和文档校验的单一真源。
- 每个 operation 在 registry 中有 `operation_version`、`state`、`payload_schema`、`complexity_class`、`proof_modes`、`max_certainty`、`result_kinds`，并由 tests 校验 example payload。
- operation 是顶层叶子能力名；`payload_schema.properties` 不包含名为 `operation` 的子字段。
- `proof_capable` 不进入 registry 手写字段，只作为 capabilities 兼容摘要由 `proof_modes` 派生，新实现不依赖它做可信度判断。
- operation 弃用只通过 `state="deprecated"`、`deprecated` 和 `replacement` 标记，不直接破坏旧接口。
- backend caveat registry 覆盖 SymPy、Z3、SciPy、mpmath、NetworkX 等主要后端边界。
- `affects_certainty=true` 的 caveat 会触发 certainty 降级，或返回结构化 override reason。
- 所有计算类公开工具返回统一 `ToolResult`。
- 所有计算类工具返回 `certainty`、`method`、`result_kind` 和 `metadata` trace。
- 条件结果通过 `conditions` 结构化返回，不能只写进自然语言 warning。
- 可结构化条件必须包含 `condition_ast`；多值函数和分支约定记录在 `metadata["branch_conventions"]`。
- domain/assumption 冲突返回 `CONSTRAINT_CONFLICT`，不得进入 backend。
- 需要证明或反例的核心结果返回结构化 `certificate`。
- 错误返回包含稳定 `error_code`。
- 所有 `seeded_random` operation 支持 seed 且相同 seed 可复现。
- 所有 operation 在 capabilities 中声明 `determinism`。
- operation 默认 limits 不超过全局 hard cap，operation-specific override 在 registry 中显式声明。
- 所有公开工具和 operation 有测试。
- conformance tests 覆盖 public tool、operation、schema、error code、trace 隐私和弃用策略。
- `pytest` 通过。
- `ruff check .` 通过。
- `mypy src` 通过。
- 只支持 Linux；非 Linux 平台必须拒绝启动，不提供 macOS/Windows 降级运行。
- 不联网。
- 不读论文/教材。
- 不使用数据库。
- 不执行任意 Python 代码。
- 不把数值证据误报为证明。
- timeout、CPU、内存、输出长度可控。
- sandbox acceptance tests 覆盖网络隔离、文件读取隔离、进程清理、输出截断、CPU/memory/file size limit。
- sandbox、网络隔离或 Linux 资源限制不可用时必须拒绝启动或拒绝执行 backend worker，不能非隔离降级运行。
- parser fuzz/property tests 通过。
- 关键工具 differential tests 通过。
- benchmark 脚本和 operation matrix 存在并可运行。
- agent eval 集存在并覆盖主要工具选择场景。
- 错误结构化返回。
- 默认 trace 不泄露完整 prompt、本地绝对路径、论文/教材内容、环境变量或密钥。

## 22. 下一步直接编码顺序

建议实际开工顺序如下，全部属于同一轮完整落地：

1. 创建 `math-mcp/` 项目骨架。
2. 写 `environment.yml` 和 `pyproject.toml`。
3. 写 `status.py`、`schemas.py`、`errors.py`、`operation_registry.py`、`backend_caveats.py`、`tools/capabilities.py`，并固定 `schema_version`、`capabilities_version`、operation `state` 和 `operation_version`。
4. 写安全 parser 和 domain parser。
5. 写 runtime timeout/subprocess runner。
6. 写 SymPy backend。
7. 打通 5.7 的最小垂直切片：`math_capabilities -> algebra_compute(simplify_expression) -> parser -> backend -> ToolResult -> smoke test -> benchmark -> eval`。
8. 按 5.8 完成首批 `implemented` operation：`simplify_expression`、`check_identity`、`search_counterexample`、`z3_satisfiability`、矩阵 `det/rank`、`numeric_evaluate`。
9. 写 mpmath backend、Z3 AST、Z3 backend、矩阵基础 backend，并补齐首批 operation 的 golden、eval、benchmark 和 differential tests。
10. 其他代数、微积分、矩阵 operation 先以 `experimental` 进入 registry，通过门禁后再改为 `implemented`。
11. 写组合、递推、图工具；未通过门禁前保持 `experimental`。
12. 写概率、集合、解析几何、三角工具；未通过门禁前保持 `experimental`。
13. 写数论、逻辑、ODE、复数、不等式工具；未通过门禁前保持 `experimental`。
14. 写 `server.py`，只注册 4.0 中的公开 MCP tools；默认 capabilities 不暴露 `experimental` 和 `disabled` operation。
15. 写所有 pytest，包括 conformance、error code、seed、certificate、backend caveat certainty 降级、operation state、operation 命名、result conditions AST、domain conflict、sandbox acceptance 和 trace 隐私测试。
16. 写 MCP stdio smoke test。
17. 写 `benchmarks/basic_latency.py` 和 `benchmarks/operation_matrix.json`。
18. 写 `evals/math_agent_cases.jsonl`。
19. 跑 `pytest`、`ruff check .`、`mypy src`。
20. 用 Codex/目标 agent 注册并执行验收样题。

这个顺序只是编码依赖顺序，不是版本划分。最终交付必须包含全部工具和测试。

## 23. 成功定义

成功不是“工具替模型解完整数学题”，而是：

```text
agent 能稳定调用本地 math-mcp，
公开 MCP tool 面保持收敛，
具体数学能力通过 operation 调度，
math-mcp 能稳定算、验、找反例，
结果有证明等级，
错误、timeout、CPU、内存和输出可控，
测试覆盖核心行为，
项目保持离线、无数据库、无 RAG、无论文读取。
```

数学推理质量提升应来自更可靠的计算和验证，而不是把工具做成另一个不可审计的回答器。

## 24. V1 可发现性与自纠正优化

V1 不扩大数学能力边界，而是降低 agent 选错 operation、传错 schema 的概率，并让失败可低成本恢复。本节是 V1 的权威说明，与 `V1.md` 一致，落地代码以本节为准。前序章节（§4.0、§10.4、§14）中标注“见 §24”的位置由本节补全。

### 24.1 目标

1. 降低 operation 名称误用率：常见直觉名能被解析为规范名。
2. 提高失败可恢复性：未知 operation 返回推荐修正；缺失/错位 domain 返回明确迁移提示。
3. 降低能力发现成本：提供只列 tool、operation、alias 的 capabilities summary 模式。
4. 明确有限枚举的 domain 写法：在 capabilities 中直接暴露顶层 `domains` 的 schema 与示例。
5. 明确带约束验证/优化的能力边界：不把自由变量采样误报为约束下反例或证明。
6. 严格向后兼容：规范 operation 名、默认 full capabilities 结构、`ToolResult` 主字段不变。

### 24.2 operation alias

per-tool alias map 维护在 `operation_registry.py` 的 `_ALIASES` 中，并由 `resolve_alias`、`aliases_for_tool`、`suggest_operations` 共享同一份数据。

原则：

- alias 只在单个 public tool 内解析，不做跨 tool 自动跳转。
- 规范名永远优先：dispatcher 先用 `get_spec` 直查，未命中才查 alias，因此 alias 不替代规范名。
- alias 必须无歧义且不得与同 tool 的真实 operation 名冲突；导入期 `_validate_aliases()` 强校验。
- 成功调用时，`metadata.operation` 记录规范名，`metadata.requested_operation` 记录原始请求名，alias 命中时再加 `metadata.operation_alias_resolved=true`。
- alias 解析在进入后端/子进程之前完成。

V1 alias 清单：

```text
algebra_compute:
  simplify->simplify_expression, expand->expand_expression, factor->factor_expression,
  cancel->cancel_expression, together->together_expression, solve->solve_equation,
  roots->polynomial_roots, groebner->groebner_basis
trigonometry_compute:
  simplify->trig_simplify, expand->trig_expand, reduce->trig_reduce, rewrite->trig_rewrite,
  solve->solve_trig_equation, identity_check->trig_identity_check, check_identity->trig_identity_check
```

其他 tool 暂不批量加 alias，避免误导；V1 后按真实失败日志再扩展。

### 24.3 capabilities summary mode

`math_capabilities` 新增 `mode` 参数，默认 `"full"` 保持原结构（额外增加顶层 `mode` 字段和每个 compute tool 的 `aliases`，均为追加，不破坏原字段）。

```python
math_capabilities(
    include_experimental: bool = False,
    include_disabled: bool = False,
    mode: str = "full",  # "summary" | "full"
)
```

`mode="summary"` 返回轻量索引，只含 tool、operation 名清单、alias，不含 `payload_schema`、`default_limits`、example：

```json
{
  "server": "math-mcp",
  "schema_version": "1.0",
  "capabilities_version": "1.0",
  "mode": "summary",
  "public_tools": {
    "algebra_compute": {
      "kind": "compute",
      "operations": ["simplify_expression", "expand_expression", "..."],
      "aliases": {"simplify": "simplify_expression", "solve": "solve_equation"}
    }
  }
}
```

Agent 使用建议：不确定有哪些工具/operation 时先拉 `mode="summary"`；选定 operation 后再拉 `mode="full"` 看该 operation 的 schema 和 example。

### 24.4 未知 operation 推荐

未知 operation 仍返回 `ok=false`、`status="unsupported"`、`error_code="UNSUPPORTED_OPERATION"`，且不进入后端或子进程，但 `error` 文案与 `metadata` 增强为可自纠正反馈：

```json
{
  "error": "unknown operation 'simlify' for tool 'algebra_compute'. Did you mean 'simplify_expression'?",
  "metadata": {
    "operation_state": "unknown",
    "suggested_operations": ["simplify_expression"],
    "available_operations": ["simplify_expression", "expand_expression", "..."],
    "suggestion_source": "alias | close_match | keyword | null"
  }
}
```

推荐来源优先级（`suggest_operations`）：1) alias 精确匹配；2) 对 alias 直觉名与规范名做 `difflib` 模糊匹配（可纠正 `simlify`→`simplify`→`simplify_expression` 这类拼写错误）；3) 子串/关键词重叠；4) 无候选时只返回 `available_operations`（至多 20 个）。`suggested_operations` 至多 3 个。这些建议挂在异常的 `extra_metadata` 上，由 dispatcher 合并进错误结果的 `metadata`。

### 24.5 finite_enumeration domain 提示

`domains` 是 compute tool 的顶层参数，不属于 `payload`。需要顶层 domain 的 operation（`finite_enumeration`、`finite_quantifier_check`）在 registry 中通过三个可选字段声明，并在 capabilities full 模式暴露（不需要 domain 的 operation 不带这些字段）：

```text
requires_domains: true
domain_schema: 顶层 domains 数组的 JSON Schema（finite 用 values，integer 用 lower/upper）
example_request: 完整调用示例，domains 位于顶层而非 payload
```

错误提示增强（均为 `DOMAIN_UNSUPPORTED`）：

- 缺少 domain：
  `finite_enumeration requires a finite or bounded-integer domain for 'x'. Pass domains as a top-level argument, e.g. domains=[{"variable":"x","kind":"integer","lower":"0","upper":"3"}].`
- 检测到 `payload.domains` 而顶层 `domains` 为空：
  `finite_enumeration received domains inside payload, but domains must be a top-level argument. Move payload.domains to the tool argument named domains.`

V1 决策：先返回明确错误，不自动搬运 `payload.domains`，避免掩盖客户端调用形状错误。

### 24.6 check_identity_constrained

新增 `verification_compute(operation="check_identity_constrained")`，在约束曲面上验证恒等式，禁止退化为忽略约束的自由变量网格采样。

建议 payload：

```json
{
  "left": "x**2/4 + y**2/3",
  "right": "1",
  "variables": ["x", "y"],
  "constraints": [{"relation": "==", "left": "x**2/4 + y**2/3", "right": "1"}],
  "parameterization": {"variables": ["t"], "substitutions": {"x": "2*cos(t)", "y": "sqrt(3)*sin(t)"}}
}
```

语义分层，并在 `metadata.constraint_mode` 记录所用模式：

1. `parameterized_symbolic`：先验证参数化满足等式约束，再把 substitutions 代入 `left-right` 化简；为 0 则 `proved_by_symbolic_simplification`。
2. `substitution_symbolic`：payload 直接给出 `substitutions`（用约束消元），验证约束后代入化简，证明等级同上。
3. `constrained_sampling`：无参数化/代入时，在确定性有理网格上只保留满足全部约束的点；其中出现不等点则 `disproved_by_counterexample`，未发现则 `numeric_evidence_only`（evidence）。反例必然是可行点，绝不是约束外的无关点。
4. 无可行网格点（如等式约束几乎不会落在网格上）且无参数化/代入：返回 `unsupported`，并建议提供 `parameterization` 或 `substitutions`。

错误码：不支持的约束证明方式 V1 复用 `DOMAIN_UNSUPPORTED`（文案说明是不支持该约束证明方式，`metadata.constraint_mode="unsupported"`），不新增 enum。证明 certificate 包含原始约束、所用 substitution/parameterization、约束满足性摘要、代入后的恒等式。

### 24.7 constrained_optimize

新增 `calculus_compute(operation="constrained_optimize")`，`max_certainty="evidence"`（不承诺全局最优证明）。

建议 payload：

```json
{
  "objective": "x**2 + y**2",
  "variables": ["x", "y"],
  "goal": "min",
  "constraints": [{"relation": "==", "left": "x + y", "right": "1"}],
  "method": "symbolic_lagrange"
}
```

语义分层（`metadata.method_detail` 记录实际路径）：

- `method="symbolic_lagrange"`：仅等式约束。求解 `∇f = Σλ∇g` 与 `g=0`，返回实候选临界点、目标值、候选清单；`certainty="evidence"`，`method="symbolic"`，backend `sympy`。
- `method="numeric"`：SciPy SLSQP 约束局部搜索，返回最优点、目标值、每条约束残差、收敛信息与起点；`certainty="evidence"`，`method="numeric_optimization"`，backend `scipy`。
- 未显式给出 `method` 时：全等式约束默认走 `symbolic_lagrange`，含不等式则走 `numeric`；`symbolic_lagrange` 收到不等式约束直接报 `invalid_input` 并建议改用 `numeric`。

registry `backend="scipy"`，并新增 `scipy:constrained_optimize` 的 backend caveat（`affects_certainty=true`，`recommended_certainty="evidence"`）；symbolic 路径运行时 backend 返回 `sympy`，数值路径返回 `scipy`。V1 不承诺任意多约束全局优化证明。

### 24.8 V1 验收清单

- `algebra_compute(operation="simplify", ...)` 成功，`metadata.operation="simplify_expression"`、`requested_operation="simplify"`、`operation_alias_resolved=true`。
- `trigonometry_compute(operation="simplify", ...)` 成功，`metadata.operation="trig_simplify"`。
- `algebra_compute(operation="simlify", ...)` 返回 `UNSUPPORTED_OPERATION`，`metadata.suggested_operations=["simplify_expression"]`，且 `backend="none"`。
- `math_capabilities()` 默认仍返回 full；`math_capabilities(mode="summary")` 只返回 tool、operation、alias，不含 `payload_schema`、`default_limits`。
- `discrete_compute(finite_enumeration)` 的 capabilities 能看到完整 `example_request`，其中 `domains` 位于顶层。
- 把 `domains` 放进 `payload` 时返回明确迁移提示。
- 椭圆约束下的恒等验证使用参数化/代入，或明确返回 evidence/unsupported；不得按自由变量给无关反例。
- 未知 operation 与 alias 解析路径不进入后端或 sandbox 子进程。

### 24.9 非目标

- 不把 math-mcp 做成自然语言数学求解器，不支持 LaTeX 直接输入。
- 不承诺任意代数簇上的全局恒等证明，不用数值采样冒充证明。
- 不破坏已有规范 operation 名和 full capabilities 结构。
