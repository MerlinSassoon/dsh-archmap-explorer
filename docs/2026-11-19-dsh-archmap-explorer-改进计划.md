# DSH ArchMap Explorer 改进计划

> 状态：已规划，未开始代码工作<br>
> 记录日期：2026-11-19<br>
> 输入依据：[真实使用复盘](2026-11-19-dsh-archmap-explorer-真实使用复盘.md)<br>
> 目标版本：建议从 `dsh-plugin-v0.1.1` 开始；涉及破坏性行为变化时升级到 `0.2.0`<br>
> 范围约束：本文只定义规划、步骤、验收和发布标准，不代表已经实施。

## 1. 改进目标

### 1.1 产品目标

把插件从“能生成架构图和注解”提升为“AI 能持续依赖的开发反馈工具”：

1. **错误可见**：构建、校验、注解失败都能把可定位、可修正的诊断返回给 AI。
2. **查询可用**：AI 可以在插件工具内部完成 trace、impact、surfaces、dsm 和 method 查询。
3. **注解增量**：代码只改一部分时，只重新注解 sourceHash 已过期的节点。
4. **事实诚实**：解析失败必须显式标记 unresolved、置信度和原因，不能伪装成确定结论。
5. **规范必达**：Skill 内容在支持的 DSH preset 下必须能确定性送达，而不是靠模型主动翻目录。
6. **设计不被工具反向绑架**：静态分析不完整时应允许保留正确设计，通过 warning、候选不完整声明或配置表达，而不是迫使删抽象。

### 1.2 非目标

本阶段不做：

- ArkTS 前端。
- 运行时追踪器。
- 完整逐语句 CFG 或数据流图。
- 用插件替代 DSH 原生 Skill 系统。
- 为了减少 diagnostics 而牺牲用户真实架构。
- 大规模 UI 视觉重做。

## 2. 改进原则

1. **确定性核心不变**：AST、图、校验、sourceHash、渲染仍由 Python 核心负责。
2. **模型只产文本**：模型不得改写源码、bundle、注解身份或 sourceHash。
3. **先诚实，再准确**：先让 unresolved 可见，再逐步提高解析率。
4. **错误分级**：结构破坏是 error；动态解析不完整是 warning 或显式 incomplete；不能全部一票否决。
5. **向后兼容优先**：新增字段和工具为主；行为变化要有迁移说明和测试。
6. **每个 P0 必须有端到端验收**：不能只加单元测试而真实工具链仍不可用。

## 3. 工作包总览

| ID | 优先级 | 工作包 | 主要责任层 | 里程碑 |
|---|---|---|---|---|
| P0-1 | P0 | 构建失败 diagnostics 完整回流 | Node 插件 + CLI | M1 |
| P0-2 | P0 | 增加 `archmap_query` 查询工具 | Node 插件 | M1 |
| P0-3 | P0 | 注解 sourceHash 增量与正确分页 | Node 插件 + Python 注解核心 | M1 |
| P0-4 | P0 | 配置严格校验与 key 规范化 | Python 配置核心 | M1 |
| P0-5 | P0 | unresolved 诚实契约 | Python 图/查询层 + Node 输出 | M1 |
| P1-1 | P1 | 属性链、cast、Protocol 单实现解析 | Python 调用解析 | M2 |
| P1-2 | P1 | polymorphic 诊断分级与反 Goodhart 护栏 | Python 校验 + Skill | M2 |
| P1-3 | P1 | Provider Role 与能力面收敛 | Python role/contract 层 | M2 |
| P1-4 | P1 | Skill 送达 fallback 与 preset 兼容 | Node 插件 + DSH 适配 | M2 |
| P1-5 | P1 | 构建与注解可观测性 | Node 插件 + CLI | M2 |
| P2-1 | P2 | 执行流纵深与请求生命周期 | Python flow 核心 | M3 |
| P2-2 | P2 | 模块备注单一事实源与漂移检查 | Python 分析/校验 | M3 |
| P2-3 | P2 | 性能、体积与查询预算 | 全链路 | M3 |
| P2-4 | P2 | 文档、迁移、发布与回滚 | 文档/发布 | M3 |

## 4. P0：工具闭环与事实诚实

### P0-1 构建失败 diagnostics 完整回流

**问题**

`archmap_build` 失败时只返回摘要计数，详细 issues 丢失。根因包括 stdout/stderr 二选一，以及 build 结果没有结构化 issues 数组。

**实施步骤**

1. 修正 Python 子进程错误汇总逻辑，保留有界范围内的 stdout 和 stderr，而不是 `stderr || stdout`。
2. 明确 CLI build 的输出流约定：至少保证详细 issues 出现在可被插件捕获的位置。
3. 扩展 `archmap_build` 返回契约：
   - `issues`: 有界 issue 数组，包含 `severity/code/message/file/line/functionId/nodeId`。
   - `issueSummary`: 按 code 聚合的数量。
   - `nextActions`: 面向模型的修复建议。
4. 保留现有 `diagnostics: {error,warning,info}` 字段，避免破坏旧调用方。
5. 将失败原因分为：
   - 输入路径/配置错误。
   - schema 或交叉引用结构错误。
   - 可接受的静态分析不完整 warning。
6. 为 `archmap_annotate` 的错误路径补充同样的结构化诊断入口，至少包含失败阶段和可操作原因。

**验收标准**

- 用真实样本的 7 条 `POLYMORPHIC_CALL_CANDIDATES` 重放时，工具结果能直接看到 7 条 code 和调用点。
- 输出有明确上限，避免超大 diagnostics 撑爆上下文。
- 成功构建时 warning 也能被摘要展示。
- Node 测试覆盖：stderr 非空但 stdout 有诊断、stdout 为空、输出超长截断。

**主要文件**

- `lib/python-bridge.js`
- `lib/index.js`
- `archmap/utility/cli_utility.py`
- `tests/node/archmap-plugin.test.mjs`

---

### P0-2 增加 `archmap_query` 查询工具

**问题**

插件只有 build/annotate，模型必须手动拼 `PYTHONPATH=... python3 -m archmap ...` 才能查询。

**建议接口**

优先采用单工具多操作，避免工具数量膨胀：

```text
archmap_query
  operation: check | trace | impact | surfaces | dsm | method
  bundlePath?
  projectPath?
  configPath?
  start?
  direction?
  module?
  level?
  maxDepth?
  maxNodes?
```

也可以拆成 `archmap_check` / `archmap_trace` / `archmap_impact` 等工具，但需要先评估工具面上下文成本。

**实施步骤**

1. 定义统一的有界返回结构：
   - `ok`
   - `operation`
   - `text`
   - `truncated`
   - `data`
   - `warnings`
2. 优先实现 `trace` 和 `impact`，再实现 `check` / `surfaces` / `dsm` / `method`。
3. `trace` 默认输出：
   - 起点、方向、路径、节点数。
   - 解析成功的调用边。
   - unresolved 入边/出边数量。
   - 明确的 `truncated`。
4. `impact` 默认输出前后 bundle 的受影响符号和路径，保留 `maxDepth` / `maxNodes` 预算。
5. 查询工具不产生副作用，不写 bundle，不修改文件。
6. 工具描述中明确告诉模型：优先用 query 工具，不要用 bash 调 Python CLI。

**验收标准**

- 用样本项目查询 `StudentApiController.handle` 的 inbound trace 时，不需要 bash。
- 返回结果明确区分 `resolved paths` 和 `unresolved references`。
- query 结果不超过配置字节/节点预算。
- Node 测试覆盖 trace、impact、超预算截断和非法参数。

**主要文件**

- `lib/index.js`
- `lib/python-bridge.js`
- `archmap/utility/query_utility.py`
- `archmap/utility/cli_utility.py`
- `tests/node/archmap-plugin.test.mjs`

---

### P0-3 注解 sourceHash 增量与正确分页

**问题**

非 force 模式只看是否存在旧注解，不看是否过期；同时 context 先截断后过滤，导致未注解节点可能永远轮不到。

**行为设计**

新增参数：

```text
refreshMode: missing | stale | all
```

建议默认值：

- `missing`：只处理没有注解的节点，最小行为变化。
- `stale`：处理缺失和 sourceHash 过期节点，作为推荐模式。
- `all`：等价于当前 force 全量重刷。

兼容策略：

- 保留 `force` 参数，`force=true` 映射到 `refreshMode=all`。
- 默认值可先在 `0.1.1` 使用 `missing`，在文档中推荐 `stale`；评估迁移后再考虑改为 `stale`。

**实施步骤**

1. Python annotation context 为每个节点返回权威 `currentSourceHash` 和 `existingSourceHash`。
2. 增加节点状态：
   - `missing`
   - `fresh`
   - `stale`
   - `manual-preserved`
3. 在 context 层先按 refreshMode 过滤，再应用 `maxNodes` 截断。
4. 增加分页/续跑能力：
   - 返回 `totalCandidates`、`selectedCount`、`truncated`、`remainingCount`。
   - 必要时支持 `cursor` 或 `startAfterNodeId`。
5. 插件只把需要刷新的节点送模型。
6. 返回结果增加：
   - `missing`
   - `stale`
   - `unchanged`
   - `manualPreserved`
   - `selected`
   - `truncated`
   - `remaining`
7. proposal 写入前保持 nodeId 和 sourceHash 由 Python 权威映射。
8. 清理或忽略 `annotation-proposal.json` 的策略写入文档，不让中间文件进入版本库。

**验收标准**

- 修改一个函数后执行 `refreshMode=stale`，只请求该函数相关节点，batch 数为最小必要值。
- 未修改节点不进入模型请求。
- 当未注解节点超过 `maxNodes` 时，下一次调用能继续处理剩余节点，不会永远停在前 N 个。
- 人工注解默认保留，`refreshMode=all` 才覆盖。
- 测试覆盖 missing/fresh/stale/manual 四类状态和分页。

**主要文件**

- `archmap/utility/annotation_utility.py`
- `lib/index.js`
- `lib/annotations.js`
- `tests/test_annotations.py`
- `tests/node/archmap-plugin.test.mjs`

---

### P0-4 配置严格校验与 key 规范化

**问题**

配置中的错误 key、未知字段、无匹配 override 会被静默忽略，导致“配置写了但没生效”。

**实施步骤**

1. 定义配置校验层，至少覆盖：
   - 顶层未知字段。
   - `contract` 下未知字段。
   - `providerRoles` 值域。
   - `apiExposure` 值域。
   - `defaultFreeFunctionSurface` 值域。
   - 模块 id 重复、include 重叠、entrypoints 非法格式。
2. 统一 target key 规范化：
   - 支持 canonical function id。
   - 支持 `fn:` 前缀。
   - 支持 `module.qualname`。
   - 对模糊简写只在其唯一匹配时接受。
3. override 必须能匹配到分析后的真实目标；匹配不到时报 error 或 warning，并给出最接近的合法 key 候选。
4. `providerRoles` 同样做目标存在性检查。
5. 区分语法错误和语义错误：
   - 语法/值域错误：error。
   - 兼容旧字段：warning + 迁移提示。
6. 在 `archmap_build` 结果中返回配置诊断明细。

**验收标准**

- `fn:...` 写法正确生效。
- 错拼 key 返回明确错误和建议，不再静默。
- 未知顶层字段有明确诊断。
- 现有合法配置保持兼容。
- 测试覆盖 `fn:`、canonical id、唯一简写、歧义简写、无匹配 override。

**主要文件**

- `archmap/utility/config_utility.py`
- `archmap/config/*.py`
- `archmap/utility/analysis_utility.py`
- `archmap/utility/validate_utility.py`
- `tests/test_validation.py`
- `tests/test_api_contracts.py`

---

### P0-5 unresolved 诚实契约

**问题**

当前 unresolved call site 可能表现为 callers=0、trace 空路径；用户无法区分“确实没人调用”和“解析失败”。

**实施步骤**

1. 在 call site / function detail 上明确表达：
   - `resolutionStatus: resolved | unresolved | ambiguous | external`
   - `resolutionReason`
   - `confidence`
   - `candidates`
2. 在 function detail 中增加 unresolved 邻域信息，例如：
   - `unresolvedIncomingCount`
   - `unresolvedOutgoingCount`
   - `unresolvedReferences`
3. 在 method 页面和 query 返回中展示 unresolved 提示。
4. `trace` 输出区分：
   - 成功路径。
   - 因 unresolved 而未纳入的引用。
   - 因预算截断而未展开的节点。
5. `impact` 对 unresolved 影响给出保守上限提示，避免低估。
6. 该工作包先保证“诚实”，不等待完整解析器完成。

**验收标准**

- 样本项目的 controller handle 方法页面不再只显示 callers=0，而是明确提示存在 unresolved inbound reference。
- inbound trace 返回 unresolved 接口/调用点信息。
- `truncated` 和 `unresolved` 不混淆。
- 测试覆盖 resolved、unresolved、ambiguous、external 四类 call site。

**主要文件**

- `archmap/utility/call_utility.py`
- `archmap/utility/detail_utility.py`
- `archmap/utility/query_utility.py`
- `archmap/render/assets/app.js`
- `tests/test_call_sites.py`
- `tests/test_p4_queries.py`

## 5. P1：解析可信度、角色与 Skill

### P1-1 属性链、cast、Protocol 单实现解析

**目标**

在不伪造确定关系的前提下，提升属性链和协议调用的解析率。

**实施步骤**

1. 扩展 `_find_self_attribute_type()` 或抽出通用类型推断层，支持：
   - `self.attr.method()`
   - `local = cast(Type, expr)` 后的 `local.attr.method()`
   - `local = self.factory()` 或构造表达式
   - 构造函数注入字段的注解类型
   - 多层属性链的类型传播
2. 对 Protocol / ABC 接收者：
   - 先找实现类。
   - 唯一实现时返回低/中置信度候选。
   - 多实现时返回候选集合，并标记 `ambiguous`。
   - 无实现时标记 unresolved，不生成假调用者。
3. 把 `subclass_ids` / MRO 一致性加入调用解析前置检查。
4. 为属性链和 Protocol 建立专门 fixture。
5. 不能确定时不硬猜，使用 `confidence` 和 `resolutionStatus` 表达。

**验收标准**

- `server.controller.handle()` 在样本模式中能解析到 `StudentApiController.handle`。
- `StudentStore` Protocol 单实现能被识别为 adapter 候选，不再因无候选导致构建失败。
- 多实现场景返回候选集合和 ambiguous 状态。
- 解析失败的 call site 不产生虚假 callers。
- 新增 fixture 覆盖 cast、属性链、Protocol、ABC、多实现。

**主要文件**

- `archmap/frontends/python/call_utility.py`
- `archmap/frontends/python/type_utility.py`
- `archmap/utility/call_resolution_utility.py`
- `archmap/utility/validate_utility.py`
- `tests/test_dispatch_resolution.py`
- `tests/test_call_sites.py`

---

### P1-2 polymorphic 诊断分级与反 Goodhart 护栏

**目标**

让“静态分析不完整”不再迫使模型改变正确设计。

**实施步骤**

1. 重新定义 `POLYMORPHIC_CALL_CANDIDATES` 的严重级别：
   - 有候选但不完整：warning。
   - 完全无候选且无法解释：warning + 明确原因。
   - 只有 schema/交叉引用破坏才是 error。
2. 增加显式 incomplete contract：
   - `dispatchHints.complete: false`。
   - 或新的通用 `resolutionHints`。
3. 在 Skill 和工具反馈中加入反例：
   - 删除 Protocol。
   - 删除接口/抽象类。
   - 改变依赖方向。
   - 合并模块。
   - 把持久化职责上移。
4. `archmap_build` 失败/警告时返回“保留设计的推荐修复路径”。
5. 增加一个“架构退化检测”诊断：
   - 当用户连续移除 Provider/契约后 diagnostics 改善时，不作为错误，但可在报告或说明中提示审阅。

**验收标准**

- 保留 Protocol 的项目可以生成 HTML，并带有可解释 warning。
- 不再重演“删除 StudentStore 才能构建”的路径。
- 工具反馈中明确说明 warning 可接受、设计不必回退。
- 测试验证 error 只用于结构破坏。

**主要文件**

- `archmap/utility/validate_utility.py`
- `archmap/utility/cli_utility.py`
- `lib/index.js`
- `docs/archmap-code-conventions.md`
- `tests/test_validation.py`

---

### P1-3 Provider Role 与能力面收敛

**目标**

减少 5/10 手工 role 修正，降低能力面噪声。

**实施步骤**

1. 调整角色推断优先级：
   - 显式 decorator/docstring/comment 最高。
   - 结构证据：Protocol/ABC、dataclass、外部 I/O。
   - 名称后缀：Store/Repository/Client、Controller/Manager、Handler/Server/Cli、Model/Config。
   - 最后才是“有 public 方法即 manager”。
2. 扩展且校验角色后缀集合，避免 Handler/Server/Cli 被统一判为 manager。
3. 输出 `roleSource` 和 `roleConfidence`，低置信度 role 在 UI 和 query 中可见。
4. 能力面默认收敛：
   - `do_*`、`log_*`、生命周期钩子、dunder 默认 internal。
   - 显式 `@public` / `@internal` / docstring tag 优先。
   - 支持 provider 级显式导出方法，而不是“非下划线即公开”。
5. 在 Skill 中要求模糊类显式标注角色和公开能力。
6. 增加角色推断 fixture，覆盖 Store、Controller、Handler、Server、Cli、Service、Manager、Adapter。

**验收标准**

- 样本项目的 5 个手工 override 至少减少 4 个，剩余由显式配置表达。
- 17 个能力接口中明显协议方法不再默认进入接口面。
- 角色输出包含置信度和来源。
- 测试覆盖名称后缀优先级和能力面收敛。

**主要文件**

- `archmap/utility/role_utility.py`
- `archmap/frontends/python/contract_utility.py`
- `archmap/frontends/python/analysis_utility.py`
- `archmap/render/assets/app.js`
- `tests/test_provider_roles.py`
- `tests/test_api_contracts.py`

---

### P1-4 Skill 送达 fallback 与 preset 兼容

**目标**

Skill 不再依赖模型主动查找包目录。

**实施步骤**

1. 明确支持矩阵：
   - `standard` preset。
   - `minimal` preset。
   - Web 与 headless/CLI 环境。
2. 当宿主没有 `skill` 工具时，提供插件级 fallback：
   - 新增 `archmap_guide` 工具。
   - 参数：`topic: config-generation | code-conventions | diagnostics | workflow`。
   - 返回权威文档的有界核心片段，并注明完整文档路径。
3. 检查斜杠命令展开链路：
   - Skill 名称是否可作为斜杠命令解析。
   - 未展开时是否能返回明确错误或 fallback。
4. 工具描述中加入关键硬约束，确保即使 Skill 没送达，模型也知道不能删抽象换绿灯。
5. 在 `scripts/prepare.mjs` 和 Node 测试中验证两个 preset 下 Skills 可列出、可获取、正文非空。
6. 文档明确：Skill provider 注册成功不等于模型可见。

**验收标准**

- `minimal` preset 下模型可通过 `archmap_guide` 获取配置和代码约定。
- `standard` preset 下原生 Skill 工具可列出两份 Skill。
- 斜杠命令失效时有可见诊断，不静默进入普通文本。
- Node 测试覆盖缺 `skill` 工具时的 fallback。

**主要文件**

- `lib/index.js`
- `scripts/prepare.mjs`
- `tests/node/archmap-plugin.test.mjs`
- `docs/dsh-plugin.md`
- `README.md`

---

### P1-5 构建与注解可观测性

**实施步骤**

1. `archmap_build` 返回：
   - 各阶段耗时：discovery、analysis、call resolution、graph、validation、render。
   - diagnostics 分类计数。
   - bundle 大小。
2. `archmap_annotate` 返回：
   - 总候选/选中/unchanged/stale/missing。
   - 每批耗时、provider、model、token 输出量（如果宿主提供）。
   - 截断与拒绝数量。
3. 在文本摘要中明确 `truncated=true` 和剩余量。
4. 增加可选的详细日志文件，但不进入默认版本库。

**验收标准**

- 用户能判断“注解为什么只跑了 50 个”。
- 用户能看到构建瓶颈和长耗时阶段。
- 不新增敏感信息或 API Key 记录。

**主要文件**

- `lib/index.js`
- `lib/host-llm.js`
- `archmap/utility/cli_utility.py`
- `archmap/utility/annotation_utility.py`

## 6. P2：产品化与发布

### P2-1 执行流纵深与请求生命周期

**目标**

让主流程视图能回答“一个请求如何走完”，同时不破坏有界执行流设计。

**实施步骤**

1. 评估默认开启 `flowScopes.autoDetect` 的可行性和成本。
2. 为入口增加“请求生命周期”候选：
   - 入口 → handler → controller → manager → adapter。
   - 只投影一层或两层可解释链路。
3. 给 scope 增加更强的根发现规则：
   - controller/handler 的公开处理方法。
   - server 的请求分发入口。
4. 保留预算、truncation diagnostics 和深度固定为 1 的约束。
5. 如不改变主图，可增加“调用邻域摘要”作为 side panel，不新增主画布边。

**验收标准**

- 样本项目能直接看到从服务器入口到 controller 的可解释链路。
- 不出现无限下钻或递归穿透。
- 截断必须显式显示。

**主要文件**

- `archmap/utility/execution_flow_utility.py`
- `archmap/utility/graph_utility.py`
- `archmap/render/assets/app.js`
- `tests/test_flow_scopes.py`

---

### P2-2 模块备注单一事实源与漂移检查

**实施步骤**

1. 模块 note 默认从模块 docstring 提取。
2. config note 仅作为显式 override。
3. 输出 `noteSource`：`docstring | config | empty`。
4. 当 config note 与 docstring 首段均有内容且不一致时产生 warning。
5. 在 UI 中区分“源码备注”和“配置覆盖”。
6. 文档要求 README 不再复制模块 note，改为引用页面/源码。

**验收标准**

- 未配置 note 时自动显示模块 docstring。
- config note 覆盖时能看到来源。
- 删除源码契约后不会继续显示“存储契约”等过期描述而不告警。

**主要文件**

- `archmap/frontends/python/analysis_utility.py`
- `archmap/utility/graph_utility.py`
- `archmap/utility/validate_utility.py`
- `tests/test_render.py`

---

### P2-3 性能、体积与查询预算

**实施步骤**

1. 建立基准项目集：
   - 小项目：学生管理系统。
   - 中项目：ArchMap 自身。
   - 大项目：待选真实 Python 项目。
2. 记录指标：
   - 构建耗时。
   - `architecture.json` / `architecture.html` 大小。
   - 浏览器首屏与交互延迟。
   - trace/impact 查询耗时与返回大小。
   - 注解 batch 数和耗时。
3. 对大 bundle 增加预算和截断策略。
4. 评估按需生成或拆分 bundle 的可行性，但不先改默认契约。
5. 设置回归门槛：新版本相对基线不能出现未解释的显著退化。

**验收标准**

- 至少覆盖小/中/大三档。
- 有可复现的性能基线文档。
- 查询工具不会一次返回超大 JSON。

**主要文件**

- `scripts/`
- `tests/test_build.py`
- `tests/test_render.py`
- `docs/`

---

### P2-4 文档、迁移、发布与回滚

**实施步骤**

1. 更新当前权威文档：
   - `README.md`
   - `docs/dsh-plugin.md`
   - `docs/archmap-code-conventions.md`
   - `docs/archmap-config-generation.md`
   - `docs/archmap-architecture-spec.md`
   - 数据契约与 schema（如字段变化）
2. 增加从 0.1.0 升级到新版的迁移说明：
   - `refreshMode` 默认行为。
   - 配置严格校验变化。
   - 新增 query 工具。
   - polymorphic 诊断级别变化。
3. 发布验收：
   - Python 全量测试。
   - Node 插件测试。
   - `npm run prepare`。
   - `npm pack --dry-run`。
   - 自构建 + `archmap check`。
   - 临时 profile 的 link 安装与真实 Git URL 安装。
   - minimal/standard preset 下的 Skill 可见性。
4. 版本策略：
   - 非破坏性工具扩展：`0.1.1`。
   - 默认行为变化或配置严格化破坏兼容：`0.2.0`。
5. 发布标签必须新增，不移动 `dsh-plugin-v0.1.0`。
6. 准备回滚方案：
   - 回退 npm 版本/tag。
   - 保留旧工具参数兼容。
   - annotation sidecar 结构保持可读。

**验收标准**

- 文档与实现一致。
- 发布标签和安装命令可复现。
- 回滚路径写入发布说明。

## 7. 里程碑与推进节奏

### M0：基线与测试夹具

**目标**：在不改产品行为的前提下冻结现状，建立可重复回归。

产出：

- 记录当前 pytest / npm test / build / check 基线。
- 保存真实样本诊断重放夹具。
- 建立 trace/callers 的回归样例。
- 建立注解 stale/missing/pagination 样例。
- 建立 minimal/standard preset 测试矩阵。

完成门槛：

- 现有测试全部通过。
- 样本项目的 7 条 polymorphic 诊断、callers=0、force 全量注解均可稳定复现。

### M1：P0 工具闭环

范围：P0-1 到 P0-5。

完成门槛：

- Build 失败可看到完整 diagnostics。
- Query 工具可完成 trace/impact/check。
- 注解可按 stale 增量、可正确分页。
- 配置错误 fail loud。
- unresolved 不再伪装成确定答案。
- 样本项目重放时，无需用 bash 手动跑 ArchMap CLI。

### M2：P1 解析、角色、Skill

范围：P1-1 到 P1-5。

完成门槛：

- 属性链、cast、Protocol 单实现有可解释结果。
- polymorphic 不再诱发删抽象换绿灯。
- role override 数量明显下降，能力面噪声下降。
- minimal preset 下 Skill 可确定送达。
- 构建和注解有可观测统计。

### M3：P2 产品化与发布

范围：P2-1 到 P2-4。

完成门槛：

- 执行流纵深有明确改进方案和实现。
- 模块备注单一来源。
- 有性能基线和预算。
- 文档、迁移、发布、回滚齐备。
- 选择 `0.1.1` 或 `0.2.0` 完成发布。

## 8. 测试矩阵

### 8.1 Python 测试

- 配置未知字段、错误 key、无匹配 override。
- `fn:` key 规范化和唯一简写。
- Protocol 单实现、多实现、无实现。
- cast 后属性链、self 属性链、局部变量类型传播。
- unresolved callers 和 trace 邻域。
- polymorphic 严重级别与 incomplete 声明。
- 注解 missing/fresh/stale/manual 状态。
- 注解超 maxNodes 分页。
- 模块 note docstring/config 来源和漂移 warning。

### 8.2 Node 插件测试

- build 失败时 stdout/stderr 合并和 issues 数组。
- `archmap_query` 参数、返回、截断。
- `archmap_annotate` refreshMode 与 counts。
- Skill 在 standard preset 可获取。
- minimal preset 下 `archmap_guide` fallback 可获取。
- workspace 越界、超时、取消、输出上限。

### 8.3 真实链路验收

- 临时 profile link 安装。
- 真实 Git URL 安装。
- 真实 DSH 会话调用 build + query + annotate。
- 修改一个函数后执行 stale 注解。
- 保留 Protocol 的样本项目能构建并带 warning。
- 大项目性能基线。

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 配置严格校验破坏旧配置 | 用户升级失败 | 先 warning 后 error；提供迁移说明和自动修复建议 |
| 默认 refreshMode 改变行为 | 既有调用方意外重新注解 | 默认先保持 missing，推荐 stale；版本说明明确 |
| 属性链解析改进改变图结构 | 快照/测试大面积变化 | 用 fixture 分层验证，保留 confidence 和旧字段 |
| polymorphic 降级为 warning | 漏掉真实结构错误 | 仅对动态解析不完整降级；schema/交叉引用仍为 error |
| Query 工具增加上下文负担 | 工具描述过长 | 采用单工具多 operation，返回有界结果 |
| Skill fallback 与权威文档双份 | 文档漂移 | fallback 直接读取包内 Markdown，不维护第二份正文 |
| 性能优化改变产物 | 数据契约/UI 回归 | 先建基线，默认契约不动，渐进优化 |

## 10. 决策点

在开始实现前需要确认以下决策：

1. `archmap_query` 采用单工具多 operation，还是多个独立工具。
2. `refreshMode` 默认值是 `missing` 还是 `stale`。
3. 配置未知字段是先 warning 一个版本，还是直接 error。
4. `POLYMORPHIC_CALL_CANDIDATES` 是所有情况都降为 warning，还是仅保留“可解释的不完整”为 warning。
5. Provider Role 是否要求模糊类必须显式标注。
6. 模块 note 是否完全禁止 config override，还是保留 override 但显示来源。
7. 下一版本号采用 `0.1.1` 还是 `0.2.0`。

**建议默认方案**

- `archmap_query`：单工具多 operation。
- `refreshMode`：默认 `missing`，UI/文档主推 `stale`。
- 配置严格校验：未匹配 override 立即 error；未知字段首个版本 warning + 迁移提示。
- polymorphic：仅可解释的不完整降为 warning。
- Role：模糊类要求显式标注，低置信度推断仍保留但可见。
- 模块 note：保留 config override，同时显示来源并在冲突时 warning。
- 版本：若默认行为变化明显，使用 `0.2.0`。

## 11. Definition of Done

单次改进只有在以下条件全部满足后才算完成：

1. 行为变化有明确文档和迁移说明。
2. Python / Node / 真实链路测试通过。
3. 工具返回结构化且受预算限制。
4. unresolved、truncated、confidence 不会被吞掉。
5. 不引入模型写源码或伪造 sourceHash 的路径。
6. 现有 0.1.0 合法用法尽量保持兼容。
7. 发布产物通过 `npm pack --dry-run`。
8. 自构建和 `archmap check` 通过。
9. 真实 Git URL 安装与 DSH profile 加载通过。
10. 不移动历史标签。

## 12. 执行顺序摘要

```text
M0 基线
  → P0-1 build diagnostics
  → P0-5 unresolved 诚实契约
  → P0-2 query 工具
  → P0-3 注解增量
  → P0-4 配置严格校验
  → M1 验收

M1 验收
  → P1-1 属性链/Protocol 解析
  → P1-2 诊断分级与反 Goodhart
  → P1-3 role/能力面
  → P1-4 Skill fallback
  → P1-5 可观测性
  → M2 验收

M2 验收
  → P2-1 执行流纵深
  → P2-2 note 单一来源
  → P2-3 性能/体积
  → P2-4 文档/发布/回滚
  → M3 发布
```

本计划落地前不开始代码修改。开始实施时，应先完成 M0 基线确认，再按 P0 → P1 → P2 的顺序推进。

## 13. 实施进度（2026-11-19）

> 分支：`feat/plugin-p0-closed-loop`<br>
> 状态：首批 P0 工具闭环已实施并通过回归；P1 只完成了 Skill fallback。<br>
> 说明：本节记录实际实施状态，未完成项仍按上文计划继续推进。

| ID | 状态 | 实施结果 |
|---|---|---|
| P0-1 | 已完成 | `archmap_build` 合并 stdout/stderr，返回结构化 `issues`、`issueSummary`、`nextActions`；`check --json` 已提供结构化校验 |
| P0-2 | 已完成 | 新增 `archmap_query`，支持 `check/trace/impact/surfaces/dsm/method` |
| P0-3 | 已完成 | 注解支持 `missing/stale/all`，先过滤后截断，返回候选/状态/剩余/truncated；stale machine annotation 可无 force 刷新 |
| P0-4 | 部分完成 | 未知配置 key 产生 warning；无效 role/exposure/value 产生 error；未匹配 override 产生 error；支持 `fn:` target key |
| P0-5 | 部分完成 | function detail 增加低置信度 `unresolvedCallers`；trace 增加 `unresolvedReferences`；UI 方法详情显示“可能的未解析调用者” |
| P1-4 | 已完成 | 新增 `archmap_guide`，在无原生 `skill` 工具时读取同一份 bundled 权威 Markdown |

### 13.1 首批实际修改范围

```text
lib/index.js
lib/python-bridge.js
archmap/utility/cli_utility.py
archmap/utility/annotation_utility.py
archmap/utility/query_utility.py
archmap/utility/config_utility.py
archmap/utility/analysis_utility.py
archmap/frontends/python/analysis_utility.py
archmap/frontends/python/detail_utility.py
archmap/utility/validate_utility.py
archmap/render/assets/app.js
tests/node/archmap-plugin.test.mjs
tests/test_annotations.py
tests/test_cli.py
tests/test_p4_queries.py
tests/test_validation.py
README.md
docs/dsh-plugin.md
```

### 13.2 首批验证结果

```text
python3 -m pytest -q
156 passed, 1 skipped

npm test
10 passed, 0 failed

npm run prepare
prepare: ok

python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
305 functions / 4940 call sites

python3 -m archmap check .archmap/self/architecture.json --json
ok: true / issueCount: 0

npm pack --dry-run
75 files / 215.4 kB package
```

真实样本复核：

```text
StudentApiController.handle
callerCount = 0
unresolvedCallerCount = 1
unresolved calleeText = server.controller.handle
```

这证明“callers=0”不再是无信息结论，查询与页面能同时提示可能未解析的入边。

### 13.3 下一批待办

1. P0-4 将未知配置字段从 warning 迁移为可配置 strict error。
2. P0-5 增加结构化 `resolutionStatus` / `resolutionReason` 到 call site 和 query 输出。
3. P1-1 属性链、`cast` 和 Protocol 单实现解析。
4. P1-2 polymorphic 诊断分级与反 Goodhart 护栏。
5. P1-3 Provider Role 与能力面收敛。
6. P1-5 构建/注解阶段耗时与成本可观测性。

## 14. 下一批计划：P1 静态分析可信度

> 状态：计划已制定，尚未开始实施<br>
> 建议分支：继续使用 `feat/plugin-p0-closed-loop`，不为同一批闭环改造重复建分支<br>
> 目标版本：继续使用当前未发布版本，不提前改版本号<br>
> 核心目标：把“解析失败可见”推进到“常见失败可以正确解析”，并减少错误角色和能力面噪声。

### 14.1 本批目标

1. 完成 P0-5 的收尾：统一 unresolved 的查询、详情和 UI 表达。
2. 完成 P1-1：属性链、`cast`、Protocol 单实现解析。
3. 完成 P1-2：polymorphic 诊断分级，避免“删抽象换绿灯”。
4. 完成 P1-3：Provider Role 与能力面收敛。
5. 保持已有工具、bundle 和配置实体稳定，不为本批新增不必要的新概念。

### 14.2 最小实体约束

本批遵循“如非必要，勿增实体”：

- **不新增工具名**：继续使用 `archmap_build`、`archmap_annotate`、`archmap_query`、`archmap_guide`。
- **不新增 query operation**：继续使用 `check/trace/impact/surfaces/dsm/method`。
- **不新增 bundle 顶层结构**：继续使用 `functionDetails`、`callSites`、`diagnostics`。
- **不新增字段表达同一事实**：unresolved 继续使用现有 `resolved=false`、`external=false`、`confidence`、`candidates`、`calleeText`，不新增重复的 `resolutionStatus`。
- **不新增配置键**：继续使用现有 `providerRoles`、`apiExposure`、`dispatchHints`、`executionOnlyCallables`。
- **不新增持久化文件**：不增加缓存、索引或状态文件。
- **不新增抽象层**：调用解析改动放在现有 `CallResolver` / `type_utility` / `query_utility` 内，不新建独立解析服务。
- **不新增页面**：继续使用方法详情页和查询结果展示 unresolved 信息。
- **不新增永久测试夹具**：优先复用 `class_demo`、`p4_demo`、`roles_demo` 或在 `tmp_path` 动态生成源码；只有现有夹具无法表达语义时才新增最小夹具。

### 14.3 W1：完成 P0-5 unresolved 收尾

**目标**

让同一个 unresolved 事实在 method detail、trace 和 UI 中使用同一套既有字段表达，不再出现“callers=0 看起来像确定结论”的歧义。

**实施步骤**

1. 审计 `callSites`：
   - 确认解析失败时始终满足 `resolved=false`。
   - 确认第三方/内建调用使用 `external=true`，不与项目内 unresolved 混淆。
   - 确认 `confidence` 能表达“低置信度名称匹配”和“确定未解析”的差异。
2. 审计 `functionDetails.unresolvedCallers`：
   - 保留现有 `unresolvedCallerCount`。
   - 确认每个 entry 继续使用现有 `callSiteId`、`calleeText`、`file`、`line`、`confidence`，不新增重复字段。
3. 审计 `build_trace`：
   - 继续返回现有 `unresolvedReferences`、`unresolvedCount`、`unresolvedTruncated`。
   - 确认 inbound 与 outbound 的语义清楚，不把低置信度名称匹配写成调用边。
4. 审计方法详情 UI：
   - 继续使用现有“可能的未解析调用者”区块。
   - 当 `callerCount=0` 且 `unresolvedCallerCount>0` 时，增加明确提示“调用者计数只包含已解析调用”。
5. 增加一致性测试：
   - 一个确定无调用者的函数。
   - 一个存在 unresolved inbound 的函数。
   - 一个 `external=true` 的调用。
   - 断言三种情况下 `callerCount`、`unresolvedCallerCount`、trace 和 UI 数据不混淆。

**验收标准**

- `StudentApiController.handle` 仍然显示 `callerCount=0`、`unresolvedCallerCount=1`，且 UI 有明确未解析提示。
- 不新增 `resolutionStatus` 或其他重复字段。
- trace 的 `unresolvedReferences` 与 function detail 的 `unresolvedCallers` 指向同一 callSiteId。
- 所有测试通过，bundle schema 不需要修改。

### 14.4 W2：P1-1 属性链、cast、Protocol 单实现解析

**目标**

在不伪造确定关系的前提下，让常见类型注入和属性链调用可解析。

#### W2.1 类型来源扩展

在现有 `CallResolver` 内增加最小类型推断，不新增独立模块：

1. `x = cast(Type, expr)`：
   - 将局部变量 `x` 的类型解析为 `Type`。
   - 支持项目中可解析的 canonical class。
2. 注解赋值：
   - `server: StudentHttpServer = ...`
   - `self.controller: StudentApiController = ...`
3. 构造赋值：
   - `server = StudentHttpServer(...)`
   - `self.controller = StudentApiController(...)`
4. 自身属性转局部：
   - `server = self.server`，其中 `self.server` 的类型可解析。
5. 属性链：
   - `server.controller.handle()` 先解析 `server` 类型，再解析 `controller` 字段类型，再解析 `handle` 方法。
6. 无法解析时返回现有 unresolved 结果，不猜目标。

#### W2.2 Protocol / ABC 候选解析

1. 确认 `resolve_type_hierarchy` 在 call-site 构建前完成，并正确回填 `subclass_ids` / MRO。
2. 对 Protocol/ABC 方法调用：
   - 唯一实现类：返回 `polymorphic=true`、`candidates=[实现方法 id]`、`confidence=medium`。
   - 多实现类：返回完整候选集合，保持 `resolved=false`。
   - 无实现：保持 unresolved，不产生候选。
3. 若实现类本身是抽象类，继续向下递归收集具体实现。
4. 不改变现有 `ResolvedCall` / `CallSite` 字段结构。

**验收标准**

- `server.controller.handle()` 在真实样本中解析到 `StudentApiController.handle`，controller 的 `callerCount` 至少为 1。
- Protocol 单实现项目的调用产生候选，不再因 `POLYMORPHIC_CALL_CANDIDATES` 失败。
- 多实现项目返回多个候选，不随便选第一个。
- 所有 unresolved 仍保持低置信度，不生成虚假调用者。
- 测试优先使用 `tmp_path` 动态源码，不新增永久夹具目录。

### 14.5 W3：P1-2 polymorphic 诊断分级与反 Goodhart 护栏

**目标**

让“分析器无法完整解析动态关系”不再阻断一个结构正确的项目。

**实施步骤**

1. 调整 `validate_utility` 的严重级别：
   - `POLYMORPHIC_CALL_CANDIDATES`：没有候选时改为 warning。
   - `POLYMORPHIC_CANDIDATE_MISSING`：候选 id 不存在时仍为 error。
   - `POLYMORPHIC_CALL_RESOLVED`：多态调用错误地声称单一目标时仍为 error。
2. 构建流程行为：
   - warning 不阻断 HTML 生成。
   - `archmap_build` 返回 `ok:true`，但保留 warning issues 和 nextActions。
   - `archmap_query check` 返回 `ok:true`，`warningCount>0`。
3. 工具反馈：
   - 当出现 polymorphic warning 时，提示“可保留抽象并补充 dispatchHints；不建议删除 Protocol/ABC 或改变依赖方向”。
4. 文档：
   - 在代码约定中明确 warning 可接受，设计正确优先于 diagnostics 归零。
   - 不新增配置键或新的 incomplete 字段，优先复用 `dispatchHints.complete:false`。

**验收标准**

- 保留 Protocol 的样本项目能构建并生成 HTML，同时带可解释 warning。
- 删除抽象不再是构建通过的前置条件。
- 结构错误仍会阻断构建。
- 现有 error 测试保持通过。

### 14.6 W4：P1-3 Provider Role 与能力面收敛

**目标**

减少手工 `providerRoles`，降低能力面噪声，同时不引入新的配置实体。

#### W4.1 角色推断顺序

将 `_infer_class_role()` 调整为：

```text
显式 decorator / docstring / comment
  → 结构证据（Protocol/ABC、dataclass、external I/O、异常等）
  → 高置信名称后缀
  → 通用 public-method manager 规则
  → 低置信 utility fallback
```

具体后缀建议：

- adapter：`store / repository / repo / adapter / client / gateway / driver`
- manager：`manager / service / controller / coordinator / orchestrator / resolver / builder / engine / runner / processor`
- component：`component / widget / handler / server / cli / command / console / screen / panel / dialog`
- config/model/utility 沿用现有集合

重点修复：

- `JsonStudentStore` → adapter
- `StudentApiController` → manager
- `StudentRequestHandler` → component
- `StudentHttpServer` → component
- `StudentCli` → component

#### W4.2 能力面收敛

在 `_api_exposure()` 的“名称推断”阶段增加最小内部名称规则：

- `do_*` → internal
- `log_*` → internal
- 已有下划线、dunder、生命周期方法规则保持不变
- 显式 decorator / docstring / config 仍然优先

不新增“能力白名单”配置，不改变现有 public/internal tags。

**验收标准**

- 样本项目 5 个手工 `providerRoles` 至少减少到 1 个以内。
- `do_GET/do_POST/do_PUT/do_DELETE` 和 `log_message` 默认不进入公开能力面。
- 现有 `roles_demo` 预期角色和 source 仍可解释。
- 自构建后的 public manager 集合不出现意外扩大。
- 不新增配置键。

### 14.7 W5：验证、文档与收口

**测试矩阵**

1. Python 单元测试：
   - cast / 注解赋值 / 构造赋值 / 自身属性转局部 / 多层属性链。
   - Protocol 单实现、多实现、无实现。
   - polymorphic warning 和结构 error 的边界。
   - role suffix 优先级。
   - `do_*` / `log_*` 能力面。
   - unresolved detail、trace、UI 数据一致。
2. Node 测试：
   - build 成功但 warnings 时返回 `ok:true`。
   - query check 返回 warningCount。
   - method 查询显示 unresolvedCallerCount。
3. 真实样本重放：
   - 学生管理系统：controller handle inbound 可解析或至少 unresolved 可见。
   - 保留 Protocol 的变体：构建成功且带 warning。
   - 角色 override 数量变化记录。
4. 全量发布前检查：
   - `python3 -m pytest -q`
   - `npm run prepare`
   - `npm test`
   - 自构建 + `archmap check --json`
   - `npm pack --dry-run`

**文档更新**

- `docs/archmap-code-conventions.md`：补充“解析不完整时保留抽象”和 role 标注建议。
- `docs/archmap-config-generation.md`：补充常见 role 推断与 `providerRoles` 使用边界。
- `README.md` / `docs/dsh-plugin.md`：只在工具行为变化时更新，不重复新增说明。
- 本文档追加实施进度，不新建同类计划文档。

### 14.8 实施顺序

```text
M2.0 基线确认
  → W1 unresolved 收尾
  → W3 polymorphic 诊断分级（先解除设计压力）
  → W2 属性链/cast/Protocol 解析
  → W4 Role 与能力面
  → W5 全量回归、真实样本重放、文档收口
```

建议的提交拆分：

```text
1. test: freeze unresolved and polymorphic fixtures
2. fix: classify polymorphic candidates as warnings
3. feat: resolve typed attribute chains and protocol candidates
4. fix: align provider role inference and exposure defaults
5. docs: record P1 analysis-credibility results
```

每个提交都应独立通过相关测试，不与无关重构混合。

### 14.9 风险与缓解

| 风险 | 缓解 |
|---|---|
| 属性链推断产生假阳性 | 只解析可确定类型；候选多时保持 ambiguous，不选第一个 |
| Protocol 单实现被错误合并 | 明显多实现时不返回单候选；保留完整 candidates |
| polymorphic 降为 warning 掩盖结构错误 | 只降级 `POLYMORPHIC_CALL_CANDIDATES`；候选 id 缺失仍 error |
| Role 后缀改动影响自构建角色 | 先跑 roles_demo 和 self-build 快照，再改规则 |
| `do_*` 内部化隐藏真实 API | 仅名称推断层生效，显式 public decorator/docstring/config 优先 |
| 为测试方便新增过多 fixture | 优先 `tmp_path` 动态生成；不新增生产抽象 |

### 14.10 不做/延期

本批不做：

- 新工具、新 query operation、新 bundle 顶层结构。
- ArkTS 前端。
- 运行时追踪。
- 完整数据流分析。
- 执行流纵深和请求生命周期视图。
- 构建/注解成本统计（P1-5，建议单独批次）。
- 新的角色配置系统或能力白名单配置。

### 14.11 完成定义

本批完成必须同时满足：

1. P0-5 的 unresolved 事实在 detail、trace、query、UI 中一致。
2. 属性链、`cast`、Protocol 单实现有可解释解析结果。
3. polymorphic 不完整只产生 warning，不再迫使删除抽象。
4. 样本项目 role override 显著减少，`do_*` / `log_*` 默认 internal。
5. 不新增工具、query operation、bundle 顶层字段或配置键。
6. 全部 Python/Node/自构建/check/pack 验证通过。
7. 文档只更新现有权威文件，不新增重复计划文件。

## 15. 第二批实施记录（2026-11-19）

> 状态：P0-5 收尾、P1-1、P1-2、P1-3 已完成并通过回归。<br>
> 实体约束：未新增工具、query operation、bundle 顶层字段、配置键、页面或永久测试夹具。

| 工作包 | 状态 | 实施结果 |
|---|---|---|
| W1 / P0-5 | 已完成 | 方法详情增加“调用者计数只包含已解析调用”提示；detail 与 trace 继续使用同一 callSiteId，未新增重复状态字段 |
| W2 / P1-1 | 已完成 | 修复 type hierarchy 重置顺序；支持 `cast`、属性链、构造/注解注入和 Protocol 单实现候选 |
| W3 / P1-2 | 已完成 | `POLYMORPHIC_CALL_CANDIDATES` 改为 warning；warning-only 项目继续生成 HTML |
| W4 / P1-3 | 已完成 | 常见角色后缀优先于通用 public-method 规则；`do_*` / `log_*` 默认 internal |
| W5 | 已完成 | 全量 Python/Node/自构建/check/pack 验证通过 |

### 15.1 关键实现

- `type_utility.resolve_type_hierarchy()`：先统一清空派生字段，再解析所有基类，修复父类在子类之后处理时 `subclass_ids` 被清空的问题。
- `CallResolver`：
  - 识别 `cast(Type, value)`。
  - 支持 `local.attr.method()` 和 `cast(Type, value).attr.method()`。
  - 支持从 `__init__` 参数注解、构造赋值和类字段注解推断属性类型。
  - 增加表达式递归保护，避免类型推断循环。
- `validate_utility`：`POLYMORPHIC_CALL_CANDIDATES` 为 warning；候选 id 缺失和错误声称单一目标仍为 error。
- `role_utility`：
  - `Store/Repository/Client` → adapter 名称推断。
  - `Handler/Server/Cli/Command/Console` → component 名称推断。
  - `Controller/Service/Manager` 继续通过结构或既有 manager 规则解析。
  - 移除 `urllib` 被整体视为 I/O adapter 的误判，改为识别实际 I/O callable 名称。
- `analysis_utility._api_exposure()`：`do_*`、`log_*` 默认 internal。
- 方法详情 UI：当 `callerCount=0` 且存在 unresolved 入边时明确提示计数边界。

### 15.2 真实样本复核

学生管理系统去掉全部手工 `providerRoles` 后：

```text
JsonStudentStore       -> adapter
StudentApiController   -> manager
StudentRequestHandler  -> component
StudentHttpServer      -> component
StudentCli             -> component
```

Capability surface：

```text
do_GET/do_POST/do_PUT/do_DELETE -> internal
log_message                     -> internal
```

未解析调用复核：

```text
server.controller.handle -> resolved
StudentApiController.handle callerCount = 1
```

Protocol 单实现复核：

```text
StudentStore.subclassIds = [JsonStudentStore]
self.store.save -> polymorphic candidate = JsonStudentStore.save
```

无实现 Protocol 复核：

```text
build: exit 0
HTML: generated
check: ok=true / errorCount=0 / POLYMORPHIC_CALL_CANDIDATES=warning
```

### 15.3 验证结果

```text
python3 -m pytest -q
161 passed, 1 skipped

npm run prepare
prepare: ok

npm test
11 passed, 0 failed

python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
5 modules / 307 functions / 4981 call sites

python3 -m archmap check .archmap/self/architecture.json --json
ok: true / issueCount: 0

npm pack --dry-run
75 files / 217.5 kB package
```

### 15.4 下一批候选

1. P1-5：构建/注解阶段耗时、成本和截断可观测性。
2. P2-1：执行流纵深与请求生命周期视图。
3. P2-2：模块备注单一事实源与漂移检查。
4. P2-3：性能、体积和查询预算基线。
5. 发布前迁移说明与真实 DSH 会话 live smoke。
