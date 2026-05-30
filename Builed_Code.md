# Builed_Code.md — math-mcp 交付与审计同步文档

> 本文件是 `math-mcp` 项目的「按实现交付（as-built）+ 审计同步」记录，严格对照
> [`math-mcp-implementation-guide.md`](./math-mcp-implementation-guide.md) 编写。
> 最近一次同步：**2026-05-30**（全量晋级：10 个 experimental → implemented，并固化 CI 硬门禁；详见 §3.8。
> 同日先后完成第二轮审计 §3.7 与本次全量晋级 §3.8）。

---

## 1. 总体状态

| 项目 | 状态 |
| --- | --- |
| 公开 MCP tools | **18 个**（2 个 utility：`ping`、`math_capabilities`；16 个 compute 领域级工具） |
| registry operations | **97 个**（`implemented` **97** / `experimental` 0；无 `disabled`/`deprecated`） |
| operation 功能覆盖 | **97/97 全部可正常返回**（其中 `finite_enumeration`/`finite_quantifier_check` 需配合顶层 `domains`，属指南 §5.2 设计） |
| 测试 | **396 passed**（初始 280；第一轮审计+solve_recurrence+Tier-C +37=317；第二轮审计 +6=323；全量晋级+CI 硬门禁 +73=396） |
| `pytest` / `ruff check .` / `mypy src` | 三者全部通过（mypy：48 个源文件无问题） |
| 运行平台 | Linux-only，conda 环境 `math-mcp`，Python 3.11.15 |
| 后端版本 | sympy 1.14.0 / mpmath 1.4.1 / numpy 2.4.6 / scipy 1.17.1 / networkx 3.6.1 |
| 离线 / 无数据库 / 无 RAG / 无论文读取 / 无任意代码执行 | 全部满足 |

成功定义（指南 §23）已达成：公开工具面收敛、能力经 operation 调度、结果带证明等级、
错误/超时/资源可控、测试覆盖核心行为、全程离线。

---

## 2. 与指南的结构对照

### 2.1 项目结构（指南 §6）

`src/math_mcp/` 下的模块与指南 §6 完全一致，并额外包含若干合理的实现辅助文件：

- 额外文件：`schema_check.py`、`tools/base.py`（`Ctx`/`Outcome`/结果构造器）、
  `tools/dispatch.py`（统一调度：校验→路由→子进程→caveat→`ToolResult`）、
  `tools/versions.py`（后端版本）、`runtime/worker.py`（sandbox worker 入口）。
- 这些是指南要求职责（单一调度、统一封装、子进程 worker）的具体落地，不与指南冲突。

### 2.2 公开工具面（指南 §4.0）

`server.py` 仅注册 18 个公开工具，不把 operation 注册为独立 MCP tool；每个 compute 工具
统一转发到 `tools.dispatch.run_operation`，复用同一套 request validation / registry lookup /
limits normalization / `ToolResult` 封装。`math_capabilities` 由 `operation_registry.py`
经 `tools/capabilities.py` 生成（单一真源），`schema_version="1.0"`、`capabilities_version="1.0"`、
`SERVER_NAME="math-mcp"` 来自 `config.py`。

### 2.3 operation 覆盖（指南 §4.1–§4.14）

指南 §4.1–§4.14 列出的全部 97 个 operation 均已进入 registry、实现 handler，并**全部晋级为
`implemented`**（experimental 归零，见 §3.8）。逐工具计数：

| 公开工具 | operation 数 | implemented | experimental |
| --- | --- | --- | --- |
| algebra_compute | 9 | 9 | 0 |
| calculus_compute | 6 | 6 | 0 |
| verification_compute | 3 | 3 | 0 |
| z3_compute | 2 | 2 | 0 |
| matrix_compute | 10 | 10 | 0 |
| discrete_compute | 3 | 3 | 0 |
| graph_compute | 7 | 7 | 0 |
| probability_compute | 7 | 7 | 0 |
| set_compute | 7 | 7 | 0 |
| geometry_compute | 7 | 7 | 0 |
| trigonometry_compute | 6 | 6 | 0 |
| number_theory_compute | 8 | 8 | 0 |
| logic_compute | 6 | 6 | 0 |
| ode_compute | 5 | 5 | 0 |
| complex_compute | 6 | 6 | 0 |
| inequality_compute | 5 | 5 | 0 |
| **合计** | **97** | **97** | **0** |

首批 `implemented` 集合（指南 §5.8）已全部打通并保持 `implemented`：
`simplify_expression`、`check_identity`、`search_counterexample`、`z3_satisfiability`、
矩阵 `det`/`rank`、`numeric_evaluate`。`solve_recurrence` 于 2026-05-29 修复后晋级 `implemented`
（见 §3.5）；同日数值/证据类 `numeric_optimize`、`probability_simulation`、`ode_solve_numeric`（Tier C）
按门禁晋级（见 §3.6）。

### 2.4 契约层（指南 §10）

- `status.py`：`Status`/`Certainty`/`Method`/`ErrorCode` 枚举与指南 §10.1 一致；额外提供
  `ResultKind` 别名和保守降级排序 `certainty_rank`/`is_weaker_or_equal`（`proved`/`disproved`
  同级、互不替换）。
- `schemas.py`：`ToolResult`/`Limits`/`DomainSpec`/`AssumptionSpec`/`OperationRequest`/
  `Certificate`/`ResultCondition` 与指南 §10.2 一致；跨切字段 `domains/assumptions/limits`
  仅由 `OperationRequest` 持有。
- `operation_registry.py`：`OperationSpec.state` 默认 `experimental`（指南 §10.5）；
  `proof_capable` 为 computed property，由 `proof_modes` 派生，绝不手写。
- `backend_caveats.py`：覆盖 SymPy / Z3 / SciPy / mpmath / NetworkX / numpy 边界；
  `affects_certainty=True` 的 caveat 在非证明方法路径触发 certainty 降级（指南 §10.6）。
- `domain_parser.py`：domain/assumption 归一化与冲突检测，冲突一律
  `CONSTRAINT_CONFLICT`，绝不静默降级（指南 §10.3）。

### 2.5 安全与运行期（指南 §11–§13）

- 表达式只接受 SymPy 风格字符串或结构化 `expr_ast`；白名单 parser，空 `__builtins__`，
  禁 `__`、禁 banned 关键字、节点/深度/位数上限（指南 §12）。
- Z3 仅接受结构化 AST（`z3_ast.py`），无 `eval`（指南 §12.3）。
- 子进程隔离用 **bubblewrap**：`--unshare-all` 网络隔离、最小只读 fs（仅 `sys.prefix`+src+系统库，
  不挂 `/etc`、`/home`）、`--clearenv`+env allowlist、`RLIMIT_CPU/AS/FSIZE/NOFILE`、stdout/stderr
  截断、JSON-only（worker 二进制/pickle 输入结构化拒为 `PARSE_REJECTED`，绝不反序列化）、超时杀进程组、
  stderr 路径脱敏；隔离不可用即拒绝运行（`SANDBOX_UNAVAILABLE` / 非 Linux `PLATFORM_UNSUPPORTED`）（指南 §13）。
- 结果超 `max_output_chars` 时返回结构化 `output_too_large`/`OUTPUT_TOO_LARGE`（不再静默截断）（指南 §10.1/§13）。

### 2.6 §20 验收样题

全部 16 道样题经真实 dispatcher 验证，结果与指南一致：
solve `x²-5x+6`→`['2','3']`；det `[[1,2],[3,4]]`→`-2`；`exp(x)` 5 阶展开；两硬币至少一正→`3/4`；
集合分配律→`proved`；点 `(1,2)` 到 `3x+4y-5=0`→`6/5`；`sin(2x)=2 sinx cosx`→`proved`；
`17` 模 `43` 逆元→`38`；`(p→q)≡(¬p∨q)`→`proved`；`C·exp(x)` 满足 `y'=y`→`proved`；
`1+I`→模 `sqrt(2)`、辐角 `pi/4`；`x²-1≥0`→`Union(Interval(-oo,-1), Interval(1,oo))`。

---

## 3. 本次审计发现的不一致与修正（2026-05-29）

审计方法：逐文件对照指南；契约层、parser、runtime 由人工精读；工具/后端/测试由并行子代理
交叉核对；§20 样题与 parser 安全边界经真实调用实测。共发现并修正 **3 处代码不一致**，并补齐
指南 §15 明确要求但缺失的 **若干测试类别**。

### 3.1 代码修正

| # | 文件 | 指南依据 | 问题 | 修正 |
| --- | --- | --- | --- | --- |
| 1 | `parsing/sympy_parser.py` `_pre_screen` | §12.2「`.` 一律不允许，除了数字小数点」 | 字符白名单允许任意 `.`，导致 `pi.evalf`、`Integer.mro`、`sin.func` 等**属性访问被接受**并返回绑定方法/属性对象 | 新增校验：`.` 只允许作为数字小数点（左右至少一侧为数字），属性访问一律 `PARSE_REJECTED`。`2.5`/`.5`/`1.`/`2.5e3` 仍正常 |
| 2 | `tools/geometry.py` `conic_analyze` | §4.8 圆锥曲线基本性质 | 死分支 `kind = "ellipse" if a==c and b==0 else "ellipse"`，圆被误判为椭圆 | 改为 `"circle" if a==c and b==0 else "ellipse"` |
| 3 | `tools/verification.py` + `tools/trigonometry.py` | §4.3/§4.9 backend 标注「SymPy + sampling」 | `check_identity`/`trig_identity_check` 的「无反例」证据分支用 SymPy `evalf` 确定性网格，却把 `backend` 标为 `"mpmath"`，与文档不符且会误触发 mpmath caveat | 该分支 `backend` 改为 `"sympy"`（method 仍为 `numeric_sampling`，certainty 仍为 `evidence`，status 仍为 `numeric_evidence_only`） |
| 4 | `tools/dispatch.py` `run_operation` | §5.3「所有工具必须返回结构化结果」+ §13.2.1 隐私 | 仅捕获 `MathMcpError`；in-process handler（含生产环境 `runs_in_subprocess=False` 的 implemented op，及测试 in-process 路径）抛出的原始异常会**泄露原始 traceback** | 增加兜底 `except Exception`，转为结构化 `backend_error`/`BACKEND_INTERNAL_ERROR`，只暴露异常类名、不含 message/路径（与 subprocess worker 行为一致） |

### 3.2 补齐的测试（指南 §15 强制要求，原缺失）

| # | 位置 | 指南依据 | 内容 |
| --- | --- | --- | --- |
| 1 | `tests/test_matrix.py::test_det_is_multiplicative` | §15.4 | Hypothesis 验证 `det(A*B)=det(A)·det(B)` |
| 2 | `tests/test_parsing_sympy.py::test_deep_nesting_is_rejected`、`test_dangerous_tokens_rejected` | §15.4 | 随机深嵌套括号触发深度限制；随机危险 token 被拒 |
| 3 | `tests/test_differential.py`（新增文件） | §15.5 | 5 类差分测试：代数符号-vs-数值采样、不等式区间-vs-逐点采样、Z3 小整数-vs-有限枚举（SAT/UNSAT）、矩阵 SymPy-vs-NumPy 容差、概率枚举-vs-比值 |
| 4 | `tests/test_verification.py::test_check_identity_sampling_pass_is_numeric_evidence_only` | §15.6 | `check_identity` 仅采样通过→`numeric_evidence_only`/`evidence`（用 `Abs(x)**2` vs `x**2`，并断言 `backend="sympy"`、无 certificate） |
| 5 | `tests/test_z3_tools.py::test_z3_unknown_is_not_promoted`、`test_z3_timeout_is_structured` | §15.7 | Z3 `unknown` 不被提升为证明；solver 超时返回结构化 `timeout`/`BACKEND_TIMEOUT` |
| 6 | `tests/test_sandbox.py::test_oversized_stdout_is_rejected`（+ worker `_stdout_flood` 诊断） | §15.3.1 | 超大 stdout 被 runner 拒为结构化资源错误，而非静默返回超大输出 |
| 7 | `benchmarks/basic_latency.py` + `tests/test_benchmarks.py` | §15.15 | benchmark 记录新增 `subprocess_overhead_ms`（子进程 worker 单次往返开销） |
| 8 | `tests/test_error_codes.py::test_unexpected_handler_exception_is_structured` | §5.3/§13.2.1 | in-process handler 抛原始异常 → 结构化 `backend_error` 且不泄露 message/路径（对应代码修正 4） |

修正后回归（含 §3.5 `solve_recurrence` 与 §3.6 Tier-C 晋级）：`pytest` 317 passed、`ruff check .` 通过、
`mypy src` 通过；真实 sandbox 路径（`MATH_MCP_FORCE_INPROCESS=0`）下 sandbox 测试与
integrate/solve/z3/solve_recurrence/numeric_optimize/probability_simulation/ode_solve_numeric 经真实 bwrap worker 全部正常。

### 3.3 评估为「可接受、未修改」的事项

下列点经评估**符合指南或属可接受设计**，未做改动，记录备查：

- `inequality_check_symbolic` 可返回 `disproved`，而 registry 声明
  `proof_modes=["symbolic"]`、`max_certainty="proved"`：指南 §4.0 明确允许「既可能证明也可能反证」
  的验证类 operation 用 `max_certainty="proved"` 表示最高可达严格结论，靠实际 `certainty` 区分；
  符号反证本身仍是 `symbolic` 方法。**不构成不一致。**
- `set_identity_check` 反证分支 `method="finite_exhaustive"`、证明分支 `method="symbolic"`：
  registry 同时声明两种 proof_mode，两值均合法；属轻微标注口味问题，非指南违例。
- `event_probability` `ratio` 模式未做 `[0,1]` 范围校验：指南未强制要求该校验，属健壮性增强项，
  不在本次「按文档修正」范围内。

> 注：原先 §3.3 记录的 `solve_recurrence`（experimental）功能缺口已于 2026-05-29 修复并提升为
> `implemented`，详见 §3.5。

### 3.4 工具落实度核验（回应「是否全部落实」）

经真实调用核验：

- **公开 MCP 工具：18/18 全部注册**（2 utility + 16 compute）。
- **operation：97/97 全部进入 registry 且都有 handler、都能路由**（无缺失 handler）。
- **可执行性：97/97 全部能正常返回**。其中 `finite_enumeration`、`finite_quantifier_check`
  需配合顶层结构化 `domains`（指南 §5.2 设计：域是顶层字段，不放 payload），给定有限域后返回
  `proved_by_finite_exhaustion`。**已无遗留功能缺口。**

### 3.5 `solve_recurrence` 修复与晋级（2026-05-29）

**根因（非「不能解后向递推」）：** parser 用普通 `Symbol(var)` 构造递推式，而 handler 调用
`rsolve(..., f(n))` 时用的是另一处 `Symbol(var, integer=True)`，两个 `n` 不相等 → rsolve 报
`'f(n + k)' expected, got 'f(n - 1)'`。SymPy 1.14 的 `rsolve` 本身能正确处理 `f(n-1)` 后向形式。

**方案（`tools/discrete.py`）：**

1. **对齐索引符号**：解析后 `recurrence.subs(Symbol(var), n)`，让递推式与 `f(n)` 用同一个整数
   假设的 `n`（核心修复）。
2. **整数位移校验** `_recurrence_offsets`：每个 `f(...)` 必须是 `n` 的整数位移，否则 `invalid_input`
   （如 `f(2*n)` 给出清晰报错，而非崩溃）。
3. **线性性校验** `_require_linear`：对每个不同的 `f(...)` 代入哑元，检查 Hessian 全为 0（即对
   f-项是仿射的）。拒绝 `f(n-1)*f(n-2)`、`f(n)**2` 等非线性式 —— 因为 rsolve 对它们会**静默给出
   错误的线性解**，若不拦截会误报 `exact`。该检查允许任意（含 `1/n` 等）系数。
4. **诚实的未知/降级**：`rsolve` 抛异常或返回 `None`，或对齐齐次式在无初值时返回退化的 `0`
   （rsolve 找不到通解时的表现），一律返回结构化 `status="unknown"`、`certainty="unknown"`、
   `method="none"`，绝不误报。
5. **成功路径**：返回 `certainty="exact"`、`method="symbolic"`、`result_kind="value"`，附 LaTeX 与
   `metadata.order`。

**registry 调整：** `state` `experimental → implemented`；`accepted_input_forms=["expression_string"]`
（递推式引用用户自定义函数，AST 白名单无法表达）；`result_kinds=["value"]`；`example_payload`
补上初值以便真实可跑。

**测试（指南 §15.2/§5.5/§10.5）：**

- golden：`tests/golden/discrete_cases.json` 新增 `f(n)-2*f(n-1)`、`f(0)=1` → `"2**n"`。
- 单测 `tests/test_discrete.py`：等比带初值（`2**n`）、**斐波那契后向形式数值校验**
  （通项代入 n=0..10 得 `[0,1,1,2,3,5,8,13,21,34,55]`，正是原 bug 用例）、无初值通解含 `C0`、
  缺函数报错、非线性拒绝、非整数位移拒绝、不可解（调和数 `f(n)-f(n-1)-1/n`）返回 `unknown`。
- eval：`evals/math_agent_cases.jsonl` 新增 `solve_recurrence_001`。
- benchmark：`benchmarks/operation_matrix.json` 新增斐波那契递推条目。

### 3.6 Tier-C 数值/证据类 operation 晋级（2026-05-29）

将 3 个**数值/证据语义** operation 由 `experimental` 晋级 `implemented`，前提是钉死 `evidence` 语义、
补差分/容差测试、确保 agent 不把数值结果当证明：

| operation | 后端 | certainty | 关键纪律 |
| --- | --- | --- | --- |
| `numeric_optimize` | scipy | `evidence`/`numeric_optimization` | 局部数值优化非证明；不收敛返回结构化 `NUMERIC_CONVERGENCE_FAILED` |
| `probability_simulation` | numpy | `evidence`/`simulation` | 蒙特卡洛只给证据；seed 可复现并入 trace |
| `ode_solve_numeric` | scipy | `evidence`/`numeric_sampling` | 数值轨迹非解析证明 |

**registry 调整**：上述三者 `state` 改为 `implemented`；并将 `numeric_optimize` 的 `determinism` 由
`seeded_random` 改为 `deterministic`（实测后端是固定起点 Nelder-Mead，无 RNG，原标注不准确）。
caveat 维持：三者均匹配 `affects_certainty=True` 的后端 caveat，非证明方法路径下 certainty 锁定为 `evidence`。

**测试（指南 §15）**：
- golden（仅断言稳定枚举字段，浮点结果不入断言）：`numeric_optimize`/`probability_simulation`/`ode_solve_numeric` 各 1 条。
- 单测：`numeric_optimize` 最小值容差校验（x≈3、value≈2）+ 无界优化触发 `NUMERIC_CONVERGENCE_FAILED` + 缺变量报错；
  `probability_simulation` 估计落在 0.5±0.05 + seed/hits/trials 入 trace + 默认 seed 回填；
  `ode_solve_numeric` 与解析解 `e^t` 逐点差分容差（<1e-3）+ evidence 语义。
- seed：`probability_simulation`（`seeded_random`）自动纳入 `test_seed_determinism` 同 seed 复现校验。
- error code：`NUMERIC_CONVERGENCE_FAILED` 现已被 `test_error_codes` 触发（此前仅在词表中），补齐 §15.10。
- eval：`evals/math_agent_cases.jsonl` 新增 3 条（均 `expected_certainty="evidence"`、`allow_numeric_evidence=true`）。
- benchmark：`operation_matrix.json` 已含 `numeric_optimize`、`numeric_evaluate` 等；`numeric_optimize` 现为 implemented。

三者均经真实 bwrap 子进程（`MATH_MCP_FORCE_INPROCESS=0`、`network_isolated=True`）验证可跑。

### 3.7 第二轮严格审计（2026-05-30）

审计方法：再次逐条对照指南；契约层 / parser / runtime / caveat 由人工精读，工具语义与 §15
测试覆盖由两个并行子代理交叉核对，§20 样题与 capabilities 结构经真实调用实测。本轮在已通过
首轮审计的基础上，又发现并修正 **3 处与指南的不一致 + 1 处加固**，并补齐指南 §15 明确要求但
仍缺失的 **6 项测试**。修正后 `pytest` 323 passed、`ruff check .`、`mypy src` 全部通过。

#### 3.7.1 代码修正

| # | 文件 | 指南依据 | 问题 | 修正 |
| --- | --- | --- | --- | --- |
| A | `tools/z3_tools.py` | §10.3「payload 约束与 domain 冲突，例如 Z3 变量声明为 Int 但 domain 声明为 real，返回 invalid_input」 | Z3 声明的 sort 与顶层 `domains` 的 kind 冲突时**未检测**，照常进入求解器 | 新增 `_check_sort_domain_conflict`：sort↔kind 兼容表（Int↔integer、Real↔real/rational、Bool↔boolean，finite 跳过），不兼容即 `ConstraintConflict`（`invalid_input`/`CONSTRAINT_CONFLICT`，`backend="none"`，不进入 backend）。两个 Z3 handler 入口调用 |
| B | `tools/complex_tools.py` `complex_mod_arg` / `complex_to_polar` | §10.2「多值函数/分支切割（如 `arg(z) in (-pi, pi]`）用 `source="branch"`，并在 `metadata["branch_conventions"]` 记录约定」+ §21「可结构化条件必须含 `condition_ast`」 | 两个返回 `arg(z)` 的 handler **未声明主值分支约定**，全项目从无 `branch_conventions`，也无任何 `condition_ast` | 增加 `source="branch"` 条件，附结构化 `condition_ast`（`-pi < arg <= pi`，用 §11.1 的 and/lt/le/neg/const/var 节点）与 `metadata["branch_conventions"]`；`certainty` 仍为 `exact`（条件可结构化，无需降级） |
| C | `tools/dispatch.py` `_assemble`/`_enforce_output_size` | §10.1 status `output_too_large` + §10.2 `OUTPUT_TOO_LARGE` + §15.2「超大输出限制」+ §15.10「每个 ErrorCode 至少有一个测试样例触发」 | 结果字符串超 `max_output_chars` 时**静默截断**并仅加 warning（`ok=True`），导致 `OUTPUT_TOO_LARGE` 在词表中却**永不产生**、无法满足 §15.10 | 改为超限即抛 `OutputTooLarge` → 结构化 `output_too_large`/`OUTPUT_TOO_LARGE`（`ok=False`），不再返回静默截断的错误结果 |
| D（加固） | `runtime/worker.py` `main` | §5.3 结构化返回 + §15.3.1「pickle 或任意二进制对象必须被拒绝」 | `sys.stdin.read()` 仅捕获 `json.JSONDecodeError`；非 UTF-8 / pickle 二进制输入会触发未捕获的 `UnicodeDecodeError`，worker **崩溃无结构化输出** | 改为 `sys.stdin.buffer.read()` 并捕获 `(JSONDecodeError, UnicodeDecodeError, ValueError)` → 结构化 `PARSE_REJECTED`，绝不反序列化/执行二进制 |

#### 3.7.2 补齐的测试（指南 §15）

| # | 位置 | 指南依据 | 内容 |
| --- | --- | --- | --- |
| 1 | `tests/test_error_codes.py`：`OUTPUT_TOO_LARGE` 进入 `SCENARIOS` | §15.2/§15.9/§15.10 | `expand_expression((x+1)**40)` + `max_output_chars=256` 触发 `OUTPUT_TOO_LARGE`（此前仅词表存在） |
| 2 | `tests/test_error_codes.py::test_z3_sort_vs_domain_conflict` | §10.3 | Z3 `Int` + domain `real` → `CONSTRAINT_CONFLICT`/`invalid_input`、`backend="none"`（对应修正 A） |
| 3 | `tests/test_conformance.py::test_branch_condition_carries_structured_ast` | §10.2/§11.1/§21 | `complex_mod_arg` 的 `source="branch"` 条件含 `condition_ast` 且 `metadata["branch_conventions"]` 存在、`certainty` 不降级（对应修正 B） |
| 4 | `tests/test_conformance.py::test_every_backend_caveat_is_referenced_by_an_operation` | §15.9 | 遍历 `backend_caveats.CAVEATS`，断言每条 caveat 都被至少一个 registry operation 匹配 |
| 5 | `tests/test_sandbox.py::test_worker_rejects_pickle_and_binary_stdin` | §15.3.1 | 直接向 worker stdin 灌 pickle 字节 → 结构化 `PARSE_REJECTED`，从不反序列化（不依赖 bwrap，对应加固 D） |
| 6 | `tests/test_parsing_sympy.py::test_set_algebra_laws` | §15.4 | 在交换律/幂等的基础上补齐**结合律与分配律**（三集合 property 测试） |
| 7 | `tests/test_complex_tools.py::test_mod_arg_declares_principal_branch` + `evals/math_agent_cases.jsonl` `neg_conditional_001` + `tests/test_evals.py` | §10.2/§15.16 | 复数主值分支断言；新增条件解恢复 eval 用例（agent 须读取 `conditions`），eval 覆盖断言加 `conditional` |

#### 3.7.3 评估为「可接受、未修改」的事项（第二轮）

- **`solve_equation`/`solve_system`/`solve_trig_equation`/`limit_expression` 未填充 `conditions`**：经实测，产生条件解的参数化输入（如 `solve(a*x-b, x)` 含 `a≠0`、`∫x**n` 的 Piecewise）都需要**未声明的自由符号**，会被安全 parser 直接 `PARSE_REJECTED`，因此条件解路径在当前白名单模型下不可达；为不可达分支编写脆弱的条件抽取代码属过度设计，故不强行实现。`solve_trig_equation` 返回的 `ImageSet`（周期 `_n`）是**完整解集**而非条件解，标 `exact`/`solution_set` 正确。
- **非成功分支 `result_kind="none"`**（z3 unknown、`inequality_check_symbolic` unknown、`chinese_remainder` 无解、`solve_recurrence` unknown 等）：指南 §10.2 明确 `none` 用于「error、timeout、unknown」，registry 的 `result_kinds` 只枚举**成功形态**，故这些分支符合指南，不构成违例。
- **disabled-operation eval 用例缺失**：registry 现无 `disabled`/`deprecated` operation（§10.5：无能力需要迁移），无法为不存在的 disabled op 编写真实可校验的 eval；故记录为 N/A，不伪造。

> 第二轮所有改动经标准 `pytest`（323 passed）与真实 bwrap 子进程路径（`MATH_MCP_FORCE_INPROCESS=0`：
> sandbox 套件、Z3 sort/domain 冲突、normal Z3 `network_isolated=True`）验证。
> 注：`test_z3_tools.py` 中 z3 `unknown`/`timeout` 两条 monkeypatch 用例按设计仅在默认 in-process
> 路径（conftest `FORCE_INPROCESS=1`）运行，与本轮改动无关。

### 3.8 全量晋级 + CI 硬门禁（2026-05-30）

应要求把剩余 **10 个 `experimental` operation 全部按 §10.5 晋级门禁晋级为 `implemented`**，并把规格
一致性固化为 **CI 硬门禁**，防回归。晋级后 registry：**97 implemented / 0 experimental / 0 deprecated /
0 disabled**；`pytest` **396 passed**、`ruff`、`mypy` 全绿；97/97 经真实 dispatcher 实跑返回正确，
5 个 `runs_in_subprocess` 的晋级 op（groebner_basis、matrix_decomposition_numeric、ode_solve_symbolic、
ode_classify、ode_initial_value_solve）经真实 bwrap worker（`network_isolated=True`）验证。

#### 3.8.1 晋级的 10 个 operation 及其门禁证据

每个 operation 补齐了 golden case + 单元/差分测试 + eval case，并自动纳入 conformance
（`test_implemented_example_runs_and_validates` 对全部 implemented 跑 example 并校验 `result_kind`/`max_certainty`）：

| operation | 公开工具 | golden | 差分/单元测试（指南 §15.5/§15.2） |
| --- | --- | --- | --- |
| groebner_basis | algebra_compute | 基 `["x - y","2*y**2 - 1"]` | 理想等价：每个输入多项式模基约化余 0（`sp.reduced`） |
| matrix_decomposition_numeric | matrix_compute | 枚举字段 | QR/SVD 重构 ≈ 原矩阵（容差 1e-9） |
| distribution_moments | probability_compute | 均值 `5` | 二项 mean=n·p、variance=n·p·(1-p) 闭式对照 |
| probability_distribution | probability_compute | pmf `63/256` | 与 `combinatorics_count` 交叉：pmf(5)=C(10,5)/2¹⁰ |
| random_variable_transform | probability_compute | 均值 `1` | 线性变换 E[2X+1]=1、Var=4（X~N(0,1)） |
| markov_chain_analyze | probability_compute | 枚举字段 | 平稳分布满足 πP=π 且和为 1（numpy 校验） |
| conic_analyze | geometry_compute | ellipse 全字段 | 圆/椭圆/抛物线/双曲线四类判别 |
| ode_solve_symbolic | ode_compute | `Eq(y(x), C1*exp(x))` | 解回代 `ode_verify_solution` → proved |
| ode_classify | ode_compute | 枚举字段 | 分类含 `1st_linear` |
| ode_initial_value_solve | ode_compute | `Eq(y(x), exp(x))` | 满足 IC 且解回代 → proved |

数值类（matrix_decomposition_numeric、markov_chain_analyze、ode_classify）的 golden 只断言稳定枚举字段
（浮点/版本相关结果不入断言）。eval 集新增 10 条（均 `expected_operation_state="implemented"`）。

**测试相应调整：** `test_algebra::test_groebner_hidden_by_default` → `test_groebner_visible_after_promotion`
（断言已可见且 `state="implemented"`）；`test_capabilities::test_experimental_hidden_by_default` 改为
**机制级**校验 `_state_visible`（implemented/deprecated 默认可见、experimental/disabled 需显式 flag），
即使 registry 无 experimental op 仍成立——保住「实验态默认隐藏」的协议保证。

#### 3.8.2 CI 硬门禁

新增 **`tests/test_ci_gate.py`**（单一合并门禁）与 **`.github/workflows/ci.yml`**：

| 门禁 | 指南依据 | 实现 |
| --- | --- | --- |
| §10 全部冲突用例 | §10.3 | 7 个冲突场景（kind 冲突、空区间、开区间单点、boolean 非法值、谓词矛盾、assumption×domain、Z3 sort×domain）逐个断言 `CONSTRAINT_CONFLICT` 且 `backend="none"`（不进入后端） |
| §15 全部测试类别 | §15.2–§15.16 | 断言每个 compute 工具的 `test_*.py`、安全/沙箱/fuzz/差分/反例/registry/error/seed/conformance/smoke/benchmark/eval/timeout 文件均存在且含 `def test_`；golden 目录、eval、operation_matrix 存在 |
| 每个 ErrorCode 触发 | §15.9/§15.10 | 14 个 ErrorCode **全部产生真实 `ToolResult.error_code`**：9 个 in-process 直接触发，BACKEND_INTERNAL_ERROR 经裸异常，4 个 runtime 类（BACKEND_TIMEOUT/RESOURCE_LIMIT_EXCEEDED/SANDBOX_UNAVAILABLE/PLATFORM_UNSUPPORTED）经 monkeypatch 子进程路径抛异常验证 dispatcher 映射；最后 `seen == set(ErrorCode)` |
| 每条 caveat 被引用 | §10.6/§15.9 | 遍历 `backend_caveats.CAVEATS`，断言每条都被至少一个 registry operation（backend + pattern）匹配 |

`.github/workflows/ci.yml` 在 push/PR 上跑 `ruff check .` + `mypy src` + `pytest -q`（含上述门禁）；
ubuntu runner 上 best-effort 安装 bubblewrap（不可用时 sandbox 测试自动 skip，不硬失败）。
新增 ErrorCode / caveat / 删除测试类别而不补覆盖，都会让该门禁失败，尽早暴露下一处边界缺口。

---

## 4. 构建与运行

```bash
conda env create -f environment.yml      # name: math-mcp
conda activate math-mcp
pip install -e .                          # 必须，bwrap worker 经 env site .pth 解析 math_mcp（python -I 忽略 PYTHONPATH）
python -m math_mcp                        # 或 math-mcp（stdio）
python examples/mcp_client_smoke.py       # 本地 stdio 冒烟
```

质量门禁：

```bash
pytest
ruff check .
mypy src
```

本地注册（Codex）：

```bash
codex mcp add math-mcp -- python -m math_mcp
```

---

## 5. 运行/构建关键事实（非显然项）

- conda-forge 提供 sympy/mpmath/numpy/scipy/networkx/pydantic/pytest/ruff/mypy；
  `mcp[cli]` 与 `z3-solver` 来自 **pip**。
- 沙箱：本机 `unshare --net` 非特权失败，但 `bwrap --unshare-net` 可用；worker 只挂
  `sys.prefix`+src+系统库，故读 `/etc/passwd` 失败 = 文件隔离保证。
- `RLIMIT_AS` × OpenBLAS：内存上限会拖垮 numpy/OpenBLAS，除非 worker env 设
  `OPENBLAS_NUM_THREADS=1`（含 OMP/MKL/NUMEXPR）—— 已在
  `runtime/subprocess_runner._clean_env` 处理。
- 测试提速钩子：`MATH_MCP_FORCE_INPROCESS=1`（`tests/conftest.py` 默认设置）让子进程类
  operation 在进程内执行，单元套件约 5–6s；`tests/test_sandbox.py` 忽略该钩子，直接走真实
  bwrap。验证真实调度路径用 `MATH_MCP_FORCE_INPROCESS=0 pytest ...`。
- SymPy 1.14：`sympy.igcdex` 已移除，改用 `from sympy.core.intfunc import igcdex`。
