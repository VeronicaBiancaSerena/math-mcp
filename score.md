# math-mcp 项目评分

> 评分人：Claude（代码审计）｜日期：2026-05-30（全量晋级 + CI 硬门禁后修订）
> 评分依据：对照 [`math-mcp-implementation-guide.md`](./math-mcp-implementation-guide.md) 的逐文件审计、
> §20 验收样题与全部 97 个 operation 的真实调用实测、`pytest`/`ruff`/`mypy` 三件套结果，
> 以及多轮审计与晋级修复记录（见 [`Builed_Code.md`](./Builed_Code.md) §3）。

---

## 总评：**97 / 100（A）**

当前状态（首轮审计 + 第二轮审计 + 全量晋级 + CI 硬门禁后）。历史参考：

- **初始交付** ≈ **87 / 100（B+）**——§15 多类测试缺失 + 4 处潜在缺陷。
- **首轮审计后** = **95 / 100（A）**——补齐 §15 测试、修 4 缺陷、Tier-C 晋级。
- **第二轮审计后** = **96 / 100（A）**——修 §10.3 / §10.2/§21 / §15.10 三处不一致 + worker 加固。
- **全量晋级 + CI 硬门禁后** = **97 / 100（A）**（本次）——10 个 `experimental` 全部按门禁晋级
  `implemented`（97/97），并把「§10 冲突 / §15 类别 / 每个 ErrorCode / 每条 caveat」固化为 CI 硬门禁。

一句话结论：**架构、安全边界、可审计性达生产级；规格符合度极高且 97/97 全部 implemented 默认可见；
规格一致性已用 CI 硬门禁锁定，防回归。剩余扣分集中在少量历史扣分与可选打磨项。**

---

## 维度评分表

| 维度 | 权重 | 得分 | 简评 |
| --- | --- | --- | --- |
| 1. 规格符合度（vs 指南 §4–§22） | 20 | 20 | 18 工具 + **97/97 operation 全部 implemented 且默认可见**；契约/命名/发布门禁/域冲突/分支约定全合规 |
| 2. 架构与代码质量 | 15 | 14 | 单一真源 registry、统一 dispatch、薄 handler；个别 method 标注口味不一 |
| 3. 安全性 | 15 | 14 | 白名单 parser + bwrap 隔离 + rlimit + JSON-only + 二进制拒绝；扣分系初始 parser 属性访问漏洞（历史，已修） |
| 4. 测试与质量保障 | 15 | 15 | 396 测试；§15 各类齐备 + **CI 硬门禁**（每 ErrorCode 触发、每 caveat 引用、§10 冲突、§15 类别）+ GitHub Actions |
| 5. 正确性 | 15 | 14.5 | §20 全 16 题正确、证明/证据严格区分、10 晋级 op 均有差分/容差校验；扣 0.5 系初始 4 缺陷（历史，已修） |
| 6. 可审计性与可观测性 | 8 | 8 | trace/metadata/error_code/certificate/branch_conventions/隐私策略完备 |
| 7. 文档 | 7 | 6.5 | README + Builed_Code + docstring + examples/eval 齐全；`Builed_Code.md` 系审计期补建（历史） |
| 8. 工程化与可维护性 | 5 | 5 | conda/pyproject、ruff+mypy strict 全绿、Linux-only；git + 标签 + 审计提交链 + CI workflow |
| **合计** | **100** | **97** | |

---

## 各维度详述

### 1. 规格符合度 — 20/20
- **18 个公开 MCP 工具**（2 utility + 16 compute）与 §4.0 一一对应；operation 不被注册为独立 tool（§5.1）。
- 指南 §4.1–§4.14 的 **97 个 operation 全部进入 registry、全部有 handler、全部可运行、且全部为
  `implemented`**（experimental/deprecated/disabled 均为 0）。默认 `math_capabilities` 暴露 97/97。
- 10 个原 `experimental` 按 §10.5 晋级门禁晋级：每个补齐 golden + 单元/差分测试 + eval，并自动纳入
  conformance（`test_implemented_example_runs_and_validates` 跑 example 校验 `result_kind`/`max_certainty`）。
- 契约层（§10.1/§10.2）、命名（§4.0.1）、发布门禁（§10.5，`state` 默认 experimental、`proof_capable` 派生）、
  §10.3 域/payload 冲突、§10.2/§21 分支约定全部落实。**此前唯一扣分（experimental 比例）已消除，给满分。**

### 2. 架构与代码质量 — 14/15
- 职责清晰（§6）：`server.py` 只注册、`tools/dispatch.py` 统一管线、`tools/*` 薄 handler、`backends/parsing/runtime` 各司其职。
- 单一真源 `operation_registry.py` 驱动 capabilities/路由/测试/文档；`Ctx`/`Outcome` 模式易测。
- **扣 1 分**：个别 handler 标注口味不一（如 `set_identity_check` 反证 `finite_exhaustive`、证明 `symbolic`）。

### 3. 安全性 — 14/15
- 白名单 parser（长度→字符→禁 `__`/关键字→标识符白名单→空 `__builtins__`→结构树校验，节点/深度/位数/指数上限）；
  Z3 仅结构化 AST 无 `eval`（§12）。bubblewrap `--unshare-all` 网络隔离 + 最小只读 fs + env allowlist +
  `RLIMIT_CPU/AS/FSIZE/NOFILE` + 超时杀进程组 + stderr 脱敏 + worker 二进制/pickle 输入结构化拒绝（§13/§15.3.1）。
- **扣 1 分（历史）**：初始 parser 允许任意 `.`，`pi.evalf` 等属性访问被接受——§12.2 实打实违反，已修；扣分反映白名单初始非滴水不漏。

### 4. 测试与质量保障 — 15/15
- **396 测试**：conformance（registry 自动生成、覆盖全部 97 implemented example）、capabilities、registry、
  error code、seed、真实 bwrap 沙箱验收（含 worker pickle/二进制拒绝）、安全/Hypothesis fuzz（集合交换/结合/分配律）、
  golden、eval、真实 stdio smoke、差分/容差测试。
- **新增 CI 硬门禁** `tests/test_ci_gate.py`：§10 全部 7 个冲突 → `CONSTRAINT_CONFLICT`（不进后端）；§15 全部测试类别存在；
  14 个 ErrorCode **全部产生真实 `ToolResult.error_code`**；每条 backend caveat 都被某 operation 引用。配 `.github/workflows/ci.yml`
  在 push/PR 跑 ruff+mypy+pytest。新增 ErrorCode/caveat 或删测试类别而不补覆盖即门禁失败。

### 5. 正确性 — 14.5/15
- §20 **全部 16 题正确**；10 个晋级 op 均有独立差分/容差校验（理想等价、QR/SVD 重构、二项闭式、πP=π、解回代验证等）。
- 证明/证据纪律严格：仅 symbolic-0 / SMT-UNSAT / 有限穷举 / 区间 → `proved`；数值/采样只 `evidence`；caveat 自动降级；
  输出超限不再静默截断；多值 `arg` 主值分支显式声明。
- **扣 0.5 分（历史）**：初始 4 处缺陷（conic 死分支、solve_recurrence 不可用、证据分支 backend 误标、裸异常泄露）已修。

### 6. 可审计性与可观测性 — 8/8
- 最小可审计 trace + 隐私策略（§13.2.1）；稳定 `error_code` 全枚举、`certificate`、结构化 `conditions`+`condition_ast`、
  多值 `metadata["branch_conventions"]`。

### 7. 文档 — 6.5/7
- README（含 CI 门禁说明）、`Builed_Code.md`（完整 as-built + 多轮审计/晋级记录）、docstring（§17）、
  `examples/sample_calls.md`（§15.13 全 21 任务）、eval 负例/恢复场景齐全。
- **扣 0.5 分**：`Builed_Code.md` 系首轮审计才创建（初始交付缺该交付物级文档）。

### 8. 工程化与可维护性 — 5/5
- `environment.yml`/`pyproject.toml` 合 §7/§8；ruff+mypy（strict, 48 文件）全绿；Linux-only 边界明确。
- 本地 git 完整提交链 + 标签 `v0.1.0`/`v0.2.0`；新增 `.github/workflows/ci.yml` CI 工作流。

---

## 主要优势
1. **规格符合度满分**：97/97 operation 全 implemented 且默认可见，契约/命名/发布门禁/域冲突/分支约定逐条对齐。
2. **规格一致性被 CI 硬门禁锁定**：§10 冲突 / §15 类别 / 每个 ErrorCode / 每条 caveat 自动校验，结构性防回归。
3. **安全与隔离达生产级**：白名单 parser + bwrap 网络隔离 + rlimit + 二进制拒绝 + 拒绝降级运行。
4. **诚实的可信度模型**：proved/disproved/exact/evidence/unknown 严格区分，采样绝不冒充证明，输出超限报错不截断。
5. **单一真源 + 自动 conformance + 全量差分验证**：registry 驱动一切，10 个数值/符号晋级 op 均有交叉校验。

## 不足与改进点
1. **历史扣分**：初始 parser 属性访问漏洞（-1，安全）、初始 4 缺陷（-0.5，正确性）、`Builed_Code.md` 非初始交付物
   （-0.5，文档）——均已修复/补建，扣分仅反映其曾存在。
2. **架构打磨**：个别 handler 的 `method` 标注口味不一（-1）；可统一约定。
3. **输入健壮性细节**：`event_probability` 的 `ratio` 模式未校验落在 [0,1]；属非门禁增强项。
4. **能力边界**：`solve_recurrence` 变系数高阶递推、SymPy `dsolve`/`classify_ode` 的版本相关输出属后端边界，
   已用 `unknown` 降级与「枚举字段-only」golden 规避脆弱断言；如需更强可加额外验证层。

> 注：原「把规格一致性纳入 CI 硬门禁」的改进建议已在本次落地（`tests/test_ci_gate.py` + `.github/workflows/ci.yml`）。

---

## 审计前后对比

| | 初始交付 | 首轮审计后 | 第二轮审计后 | 全量晋级 + CI 门禁后（当前） |
| --- | --- | --- | --- | --- |
| 测试数 | 280 | 317 | 323 | **396** |
| implemented / experimental | 83 / 14 | 87 / 10 | 87 / 10 | **97 / 0** |
| §15 必需测试类别 | 多类缺失 | 差分等补齐 | + caveat/集合律/pickle/condition_ast | **+ CI 硬门禁锁定** |
| §10 边界条款 | — | — | 冲突/分支/超限全落实 | + Z3 sort×domain 等纳入门禁 |
| 已知潜在缺陷 | 4 处 | 全修 | + worker 二进制崩溃修复 | — |
| 规格一致性防回归 | 无 | conformance | conformance | **CI 硬门禁 + GitHub Actions** |
| 版本控制 | 空 `.git` | git + 标签 | + 审计 commit | + CI workflow |
| 综合评分 | ~87（B+） | 95（A） | 96（A） | **97（A）** |

---

## 评分刻度参考
- 90–100 A：生产可用，规格高度符合，少量可选改进。
- 80–89 B：基础扎实，存在需补齐的完备性/缺陷项。
- 70–79 C：可运行，但有结构性缺口。
- <70：未达交付门槛。

**结论：97/100（A）。** 工程质量优秀、边界清晰、可审计的本地数学推理 MCP。97/97 operation 全部
implemented 且经门禁验证，指南核心与边界条款逐条落实，并以 CI 硬门禁锁定规格一致性；`pytest` 396 /
`ruff` / `mypy` 全绿。剩余扣分仅为少量历史扣分（初始 parser 漏洞、初始缺陷、文档补建时点）与可选打磨项。
