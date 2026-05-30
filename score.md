# math-mcp 项目评分

> 评分人：Claude（代码审计）｜日期：2026-05-29（含 Tier-C 数值/证据类 operation 晋级与本地 git 落地修订）
> 评分依据：对照 [`math-mcp-implementation-guide.md`](./math-mcp-implementation-guide.md) 的逐文件审计、
> §20 验收样题与 parser/sandbox 的真实调用实测、`pytest`/`ruff`/`mypy` 三件套结果，以及本轮审计修复记录
> （见 [`Builed_Code.md`](./Builed_Code.md)）。

---

## 总评：**95 / 100（A）**

当前（审计修复 + Tier-C 晋级 + 本地 git 落地后）状态。若按**初始交付**（审计前）评估约为 **87 / 100（B+）**，
主要差距来自指南 §15 明确要求但缺失的若干测试类别，以及 4 处潜在缺陷（详见「审计前后对比」）。

一句话结论：**架构、安全边界、可审计性达到生产级；规格符合度极高；初始交付在「测试完备性」与少数潜在缺陷上
有欠账，现已基本补齐。**

---

## 维度评分表

| 维度 | 权重 | 得分 | 简评 |
| --- | --- | --- | --- |
| 1. 规格符合度（vs 指南 §4–§22） | 20 | 19 | 18 工具 + 97 operation 全覆盖、可路由、可运行；契约/命名/发布门禁完全合规 |
| 2. 架构与代码质量 | 15 | 14 | 单一真源 registry、统一 dispatch、清晰分层；`proof_capable` 派生而非手写 |
| 3. 安全性 | 15 | 14 | 白名单 parser + bwrap 网络隔离 + rlimit + JSON-only；初始 parser 有属性访问漏洞（已修） |
| 4. 测试与质量保障 | 15 | 14.5 | 317 测试、conformance 自动生成、真实沙箱验收、每个 ErrorCode 均被触发；初始缺的 §15 多类测试已补 |
| 5. 正确性 | 15 | 14 | §20 全部 16 题正确、证明/证据严格区分；初始有 4 处潜在缺陷（已修） |
| 6. 可审计性与可观测性 | 8 | 8 | trace/metadata/error_code/certificate/隐私策略完备 |
| 7. 文档 | 7 | 6.5 | README + Builed_Code + docstring + examples/eval 齐全 |
| 8. 工程化与可维护性 | 5 | 5 | conda/pyproject、ruff+mypy strict 全绿、Linux-only；本地 git 已落地并打标签 |
| **合计** | **100** | **95** | |

---

## 各维度详述

### 1. 规格符合度 — 19/20
- **18 个公开 MCP 工具**（2 utility + 16 compute）与指南 §4.0 一一对应；operation 不被注册为独立 tool（§5.1）。
- 指南 §4.1–§4.14 列出的 **97 个 operation 全部进入 registry、全部有 handler、全部可运行**（实测 95 直接可跑 +
  2 个需顶层 `domains` 的有限枚举类，符合 §5.2 设计）。
- 契约层与指南 §10 完全一致：`status`/`certainty`/`method`/`ErrorCode` 枚举（§10.1）、`ToolResult`/`Limits`/
  `DomainSpec` 等（§10.2）、命名规范「顶层叶子 operation、payload 无子 `operation`」（§4.0.1）。
- 发布门禁（§10.5）落实：`OperationSpec.state` 默认 `experimental`，capabilities 默认只暴露 implemented/可调用
  deprecated；`proof_capable` 由 `proof_modes` 派生。
- **扣 1 分**：10 个 operation 仍为 `experimental`（ode 符号类 3 个、probability 分布类 4 个、groebner/数值分解/
  conic）——指南允许此发布节奏，但从「整体落地完成度」看，默认对 agent 可见的是 87/97。本轮已将数值/证据类
  `numeric_optimize`、`probability_simulation`、`ode_solve_numeric`（Tier C）按门禁晋级为 `implemented`。

### 2. 架构与代码质量 — 14/15
- 职责清晰：`server.py` 只注册、`tools/dispatch.py` 统一「校验→路由→子进程→caveat→ToolResult」、`tools/*`
  只写数学语义、`backends/*` 适配、`parsing/*`、`runtime/*` 各司其职（指南 §6）。
- 单一真源：`operation_registry.py` 驱动 capabilities、路由、测试与文档校验；`backend_caveats.py` 统一后端边界。
- `Ctx`/`Outcome` 模式让 handler 极薄、易测；`method_hint`、computed `proof_capable` 设计得当。
- **扣 1 分**：个别 handler 标注口味不一（如 `set_identity_check` 反证分支 `method="finite_exhaustive"` 而证明分支
  `method="symbolic"`，同一技术两种标注）。

### 3. 安全性 — 14/15
- Parser 白名单实现（非黑名单）：长度→字符白名单→禁 `__`/banned 关键字→标识符白名单→空 `__builtins__`→
  结构树校验，节点/深度/位数/指数上限齐全（§12）。Z3 仅结构化 AST、无 `eval`（§12.3）。
- 运行期隔离用 **bubblewrap**：`--unshare-all` 网络隔离、最小只读 fs（不挂 `/etc`/`/home`）、`--clearenv`+env
  allowlist、`RLIMIT_CPU/AS/FSIZE/NOFILE`、stdout/stderr 截断与路径脱敏、超时杀进程组、隔离不可用即拒绝运行（§13）。
- **扣 1 分**：初始 parser 字符白名单允许任意 `.`，导致 `pi.evalf`/`Integer.mro` 等**属性访问被接受**并返回绑定方法
  ——这是 §12.2「`.` 一律不允许，除数字小数点」的实打实违反（本轮已修）。说明白名单初始并非滴水不漏。

### 4. 测试与质量保障 — 14.5/15
- 覆盖面广：317 测试，含 conformance（从 registry 自动生成）、capabilities、registry、error code（每个
  `ErrorCode` 均被触发，含本轮补上的 `NUMERIC_CONVERGENCE_FAILED`）、seed 决定性、**真实 bwrap 沙箱验收**、
  安全/Hypothesis fuzz、golden、eval、真实 stdio smoke、差分/容差测试。
- **扣 0.5 分**：指南 §15 明确点名却**初始缺失**的测试类别 ——§15.5 差分测试整类、§15.4 `det(A*B)=det(A)det(B)`
  与深嵌套 fuzz、§15.6 `check_identity→numeric_evidence_only`、§15.7 Z3 `unknown`/timeout、§15.3.1 超大 stdout、
  §15.15 benchmark `subprocess_overhead` ——均在本轮补齐。初始「测试完备性」与指南要求曾有差距。

### 5. 正确性 — 14/15
- §20 **全部 16 道验收样题实测结果与指南一致**（det=-2、6/5、模 sqrt(2)/辐角 pi/4、模逆 38、各 proved 等）。
- 证明/证据纪律严格：仅符号化简到 0 / SMT-UNSAT / 有限穷举 / 区间才 `proved`；采样只 `evidence`；caveat 自动降级
  （`affects_certainty` + 非证明方法）—— 符合 §5.4/§10.6。
- **扣 1 分（审计前更低）**：初始存在 4 处潜在缺陷 ——`conic_analyze` 圆/椭圆死分支、`solve_recurrence` 因符号
  不一致而完全不可用、恒等式证据分支 `backend` 误标 `mpmath`、in-process 路径裸异常泄露 ——均已修复。

### 6. 可审计性与可观测性 — 8/8
- 每次调用返回最小可审计 trace（public_tool/operation/version/state/backend_versions/limits_applied/
  determinism/seed），并落实隐私策略（§13.2.1：不记录完整 prompt、绝对路径、密钥；debug trace 显式开关）。
- 稳定 `error_code` 全枚举、`certificate`（symbolic/smt_unsat/finite_exhaustion/counterexample）、结构化
  `conditions`+`condition_ast` ——错误可恢复、结果可复核。

### 7. 文档 — 6.5/7
- README 精炼准确；`Builed_Code.md` 为完整 as-built+审计记录；每个工具 docstring 含证明等级与不支持情形（§17）；
  `examples/sample_calls.md` 覆盖 §15.13 全部 21 任务；eval 集含负例/恢复场景。
- **扣 0.5 分**：`Builed_Code.md` 系本轮审计才创建（初始交付缺该交付物级文档）。

### 8. 工程化与可维护性 — 5/5
- `environment.yml`/`pyproject.toml` 与 §7/§8 完全一致；`ruff check .`、`mypy src`（strict）全绿；Linux-only 边界
  明确（非 Linux 拒启）。
- 本地 git 仓库已落地（初始导入 + 审计修复 + Tier-C 晋级），并打基线标签 `v0.1.0`、`v0.2.0`；`.gitignore` 排除
  缓存与本地 harness 状态。

---

## 主要优势
1. **规格符合度极高**：97/97 operation 全落地，契约/命名/发布门禁逐条对齐指南。
2. **安全与隔离达生产级**：白名单 parser + bwrap 网络隔离 + rlimit + JSON-only + 拒绝降级运行。
3. **诚实的可信度模型**：proof / disproved / exact / evidence / unknown 严格区分，采样绝不冒充证明，caveat 自动降级。
4. **单一真源 + 自动 conformance**：registry 驱动一切，结构性地避免「文档与实现漂移」。
5. **可审计性**：trace/error_code/certificate/隐私策略完整。

## 不足与改进点
1. **`experimental` 比例**：10/97 仍未晋级（ode 符号类、概率分布类为主），默认不可见；建议按 §10.5 逐个补
   golden/eval/差分测试后晋级。
2. **少数潜在缺陷曾逃过初始测试**：parser 属性访问、裸异常泄露、conic/solve_recurrence 缺陷——根因是初始测试未
   完全覆盖 §15 要求；已补齐，但建议把「§15 各类测试齐备」纳入 CI 硬门禁防回归。
3. **输入健壮性细节**：`event_probability` 的 `ratio` 模式未校验结果落在 [0,1]；可作为非门禁增强项。
4. **变量系数递推边界**：`solve_recurrence` 对变系数高阶递推（rsolve 退化返回 0 的情形）已降级为 `unknown`，但这是
   SymPy 能力边界，文档已标注；如需更强可引入额外验证。

---

## 审计前后对比

| | 初始交付 | 当前 |
| --- | --- | --- |
| 测试数 | 280 | 317 |
| implemented / experimental | 83 / 14 | 87 / 10 |
| §15 必需测试类别 | 差分/det 乘性/深嵌套/Z3 unknown·timeout/numeric_evidence_only/超大 stdout/subprocess_overhead **缺失** | 全部补齐 |
| 已知潜在缺陷 | parser 属性访问、裸异常泄露、conic 死分支、solve_recurrence 不可用 | 全部修复 |
| 数值/证据类 operation（Tier C） | experimental，默认不可见 | `numeric_optimize`/`probability_simulation`/`ode_solve_numeric` 已晋级 `implemented` |
| 版本控制 | 空 `.git`、无历史 | 本地 git + 标签 `v0.1.0`/`v0.2.0` |
| 综合评分 | ~87（B+） | **95（A）** |

---

## 评分刻度参考
- 90–100 A：生产可用，规格高度符合，少量可选改进。
- 80–89 B：基础扎实，存在需补齐的完备性/缺陷项。
- 70–79 C：可运行，但有结构性缺口。
- <70：未达交付门槛。

**结论：95/100（A）。** 这是一个工程质量优秀、边界清晰、可审计的本地数学推理 MCP；初始交付的「测试完备性
欠账」与少数潜在缺陷已在本轮审计中修复，数值/证据类 operation 已按门禁晋级，本地 git 亦已落地。剩余扣分集中在
仍保留的 10 个 `experimental` operation 与少量可选健壮性增强。
