# Builed_Code.md — math-mcp 交付与审计同步文档

> 本文件是 `math-mcp` 项目的「按实现交付（as-built）+ 审计同步」记录，严格对照
> [`math-mcp-implementation-guide.md`](./math-mcp-implementation-guide.md) 编写。
> 最近一次审计与同步：**2026-05-29**（含 `solve_recurrence` 修复并提升为 implemented）。

---

## 1. 总体状态

| 项目 | 状态 |
| --- | --- |
| 公开 MCP tools | **18 个**（2 个 utility：`ping`、`math_capabilities`；16 个 compute 领域级工具） |
| registry operations | **97 个**（`implemented` 87 / `experimental` 10；无 `disabled`/`deprecated`） |
| operation 功能覆盖 | **97/97 全部可正常返回**（其中 `finite_enumeration`/`finite_quantifier_check` 需配合顶层 `domains`，属指南 §5.2 设计） |
| 测试 | **317 passed**（初始 280，审计 + solve_recurrence + Tier-C 晋级累计新增 37 条） |
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

指南 §4.1–§4.14 列出的全部 97 个 operation 均已进入 registry 并实现 handler，逐工具计数：

| 公开工具 | operation 数 | implemented | experimental |
| --- | --- | --- | --- |
| algebra_compute | 9 | 8 | 1（groebner_basis） |
| calculus_compute | 6 | 6 | 0 |
| verification_compute | 3 | 3 | 0 |
| z3_compute | 2 | 2 | 0 |
| matrix_compute | 10 | 9 | 1（matrix_decomposition_numeric） |
| discrete_compute | 3 | 3 | 0 |
| graph_compute | 7 | 7 | 0 |
| probability_compute | 7 | 3 | 4（distribution_moments, probability_distribution, random_variable_transform, markov_chain_analyze） |
| set_compute | 7 | 7 | 0 |
| geometry_compute | 7 | 6 | 1（conic_analyze） |
| trigonometry_compute | 6 | 6 | 0 |
| number_theory_compute | 8 | 8 | 0 |
| logic_compute | 6 | 6 | 0 |
| ode_compute | 5 | 2 | 3（ode_solve_symbolic, ode_classify, ode_initial_value_solve） |
| complex_compute | 6 | 6 | 0 |
| inequality_compute | 5 | 5 | 0 |

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
  截断、JSON-only、超时杀进程组、stderr 路径脱敏；隔离不可用即拒绝运行
  （`SANDBOX_UNAVAILABLE` / 非 Linux `PLATFORM_UNSUPPORTED`）（指南 §13）。

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
