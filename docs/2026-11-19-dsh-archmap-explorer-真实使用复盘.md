# DSH ArchMap Explorer 0.1.0 真实使用复盘

> 状态：复盘记录，已归档<br>
> 记录日期：2026-11-19<br>
> 复盘对象：`dsh-archmap-explorer@0.1.0` / ArchMap `2.5.0` / bundle schema `6.4`<br>
> 输入样本：真实项目开发会话 `session-91067492-7a27-468e-842c-f9bb7062a027`，项目评价会话 `session-92589220-6508-4433-bb2d-ed2773f6103f`<br>
> 范围说明：本文只记录分析与结论，不包含产品代码修改。

## 1. 样本背景

样本项目是一个简单学生信息管理系统，包含服务器端和命令行客户端，使用 ArchMap 插件、两份 bundled Skill 和 `archmap_build` / `archmap_annotate` 完成开发、构建、校验和 LLM 语义注解。

开发会话的关键事实：

```text
总步骤：76
bash：64 次
archmap_build：7 次
archmap_annotate：3 次
working_directory：2 次
```

评价会话独立检查了项目源码、插件包、渲染层、CLI 查询能力和生成产物，并读取了开发会话的工具调用记录。两条会话的结论与当前代码抽查结果一致。

## 2. 总体结论

插件已经证明了一个真实价值：它能把 AI 产出的项目约束为可分析、可构建、可交付的形状，包括模块边界、Provider Role、执行入口、函数备注、测试要求和自包含架构页面。

但当前仍不是完整的 AI 开发闭环，主要缺口集中在四处：

1. **错误不可见**：构建失败时，真正有价值的 diagnostics 明细没有回到模型。
2. **查询不可用**：`check` / `trace` / `impact` / `surfaces` / `dsm` 仍停留在 CLI，模型只能通过 `bash` 绕过插件。
3. **增量不可用**：注解没有 sourceHash 级增量，代码改动后只能保留过期注解或 `force` 全量重刷。
4. **事实不诚实**：静态分析失败时可能输出 callers=0、空 trace，看起来像确定答案，实际是解析遗漏。

更准确的产品判断是：**插件擅长让 AI 写出“可被 ArchMap 分析的结构”，还没有保证“结构就是用户真正想要的结构”。**

## 3. 已被验证的价值

### 3.1 规范变成可执行约束

两份 Skill 共约 1,485 行，把模块划分、七类 Provider Role、能力面、入口、备注和测试要求写成了可检查规则。样本项目最终形成 4 个模块、65 个函数、2 条执行流、309 个调用点、0 diagnostics，13 个测试通过。

### 3.2 交付形状稳定

项目页、模块能力页、方法详情页和自包含 HTML 形成了一个低成本的审阅面。用户不需要先读完全部源码，就能检查模块数量、入口、能力面和函数备注。

### 3.3 确定性核心与模型边界正确

构建是确定性静态分析；模型只负责语义文本；`nodeId`、`sourceHash`、注解合法性和 HTML 重渲染由 Python 权威处理。这个职责边界应继续保留。

### 3.4 静态事实层有长期价值

`functionDetails`、`callSites`、type relations、user surfaces 和 DSM 都是可查询、可复算的事实。只要解析结果明确表达置信度和 unresolved 状态，它们比让模型口头描述架构更可靠。

## 4. 主要问题清单

### P0-1 构建失败不返回 diagnostics 明细

**证据**

第一次和第二次 `archmap_build` 均返回：

```text
ArchMap build failed with exit code 1
wrote .../architecture.json
skipped HTML because 7 validation error(s) occurred
```

但 7 条 `POLYMORPHIC_CALL_CANDIDATES` 的具体 code、调用点、函数和行号都没有返回。模型只能自己设置 `PYTHONPATH`，执行：

```bash
python3 -m archmap check .archmap/architecture.json
```

**根因**

- CLI 的 `_print_issues()` 把详细 issues 输出到 stdout。
- `lib/python-bridge.js` 的 `summarizeProcessError()` 使用 `result.stderr || result.stdout`，stderr 非空时 stdout 被整体丢弃。
- `lib/index.js` 的 build 返回只暴露 diagnostics 计数，没有 issues 数组。

**影响**

直接导致 10+ 次无效工具调用；模型不得不阅读插件内部实现来理解诊断和配置格式。

### P0-2 查询能力没有暴露为工具

**证据**

插件只注册了：

```text
archmap_build
archmap_annotate
```

开发会话中的 `check`、`trace`、`surfaces`、`dsm` 全部依赖 bash 手动执行。评价会话也确认 `impact` / `trace` 是实际刚需，但未进入工具面。

**影响**

AI 无法在单次工具闭环中回答“改这里会碰到谁”“谁调用了这个方法”“当前能力面是什么”。这会让模型退回读源码和猜依赖。

### P0-3 注解不能按 sourceHash 增量刷新

**证据**

- 开发会话 3 次 `archmap_annotate` 全部为 `force: true`。
- 每次 applied 50、batches 9、skipped 0。
- `lib/index.js` 的非 force 过滤条件只检查 `existingAnnotation` 是否存在，不比较 `existingAnnotation.sourceHash` 与当前 `sourceHash`。

**影响**

代码每次小改都需要全量重刷，tokens 和等待时间不可控；不重刷则页面保留过期注解。

### P0-4 注解分页与截断状态存在缺陷

**证据**

`annotation_context()` 先按 `max_nodes` 截取前 N 个候选，然后插件再过滤已有注解。假设前 50 个节点都已有注解、后面仍有未注解节点，默认非 force 调用会返回“nothing to generate”，后续节点永远轮不到。

同时，context 返回了 `truncated`，但 `archmap_annotate` 的结果没有向调用方暴露 `truncated`、总候选数或剩余节点数。

**影响**

用户可能认为注解已覆盖全部节点，实际仍有节点未处理；这是静默的不完整结果。

### P0-5 调用图存在静默错误

**证据**

在样本项目中：

- `StudentRequestHandler._handle` 对 `server.controller.handle(...)` 的调用未解析。
- `StudentApiController.handle` 的 `callers` 为 0。
- `archmap trace --direction inbound` 只返回自身节点，`paths: []`。

这不是“没有调用者”，而是解析失败。当前输出没有把这种情况与真正的 0 调用者区分开。

**影响**

`callers`、`trace` 和 `impact` 会输出错误答案，且错误没有显著置信度提示。对架构理解工具来说，静默错误比缺失信息更危险。

### P1-1 Protocol 与单实现接收者解析不足，诱发设计退化

**证据**

样本项目最初使用 `StudentStore` Protocol 隔离业务编排与持久化。构建产生 7 条 `POLYMORPHIC_CALL_CANDIDATES`。模型排查后删除了 Protocol，让 manager 只做内存状态，把持久化上移到 controller，直接依赖具体 `JsonStudentStore`。之后 diagnostics 归零。

**影响**

工具把“无候选”作为硬 error，却没有提供保留抽象并表达不完整候选的便捷路径，最终奖励了“删抽象换绿灯”。这是 Goodhart 定律的典型案例。

### P1-2 配置错误静默失败

**证据**

- `apiExposure` 先写成 `fn:student_system...:internal`，没有报错也没有生效。
- 当前 `_api_exposure()` 只识别 `module.qualname`、`qualname`、`module.name`、`name` 等 key 形式。
- `config_utility.py` 对未知顶层字段、未知 `contract` 字段、未匹配 override 没有完整校验。
- 无效 role/exposure 值也可能被直接忽略。

**影响**

配置即约定；静默失败会让用户误以为约定已生效。

### P1-3 Provider Role 推断准确率不足

**证据**

样本项目 10 个类中有 5 个通过手写 `providerRoles` 修正：

```text
JsonStudentStore       -> adapter
StudentApiController   -> manager
StudentRequestHandler  -> component
StudentHttpServer      -> component
StudentCli             -> component
```

当前 `_infer_class_role()` 对“存在 public 方法”的类优先返回 manager，名称后缀规则可能排在后面，导致 Store、Handler、Server、CLI 等角色被过度归为 manager。

**影响**

配置负担增加，普通用户容易把低置信度推断当成事实。

### P1-4 能力面过度暴露

**证据**

样本项目中 `do_GET`、`do_POST`、`do_PUT`、`do_DELETE` 和 `log_message` 等进入公开能力面；19 个 provided APIs 中真正可作为稳定契约的明显更少。

**影响**

Provider、接口数量和能力卡片会被误读为架构承诺；UI 中大量“推断”标签降低信噪比。

### P1-5 Skill 送达依赖宿主 preset

**证据**

开发会话的 request header 工具列表为：

```text
archmap_annotate / archmap_build / bash / read_deepseek_share / read_image / working_directory
```

没有 `skill` 工具，session preset 为 `minimal`。用户输入的 `/archmap-code-conventions /archmap-config-generation` 未展开，模型只能自己从 `node_modules` 中找到并读取两份文档。

**影响**

插件注册了 Skill provider，但实际是否生效取决于宿主 preset 和模型是否主动翻文件。换一个模型或不主动搜索，1,485 行规范等于不存在。

### P2-1 执行流纵深不足

样本项目中 `flowScopes.enabled=false`，服务器 flow 只有 4 个节点，止步于 `run_server`。最值得看的请求链路 `do_GET -> _handle -> controller.handle -> manager -> store` 只能逐个点方法详情拼出来。

这不是违反当前设计，而是当前设计对“降低理解成本”的目标支持不足。

### P2-2 备注多源漂移

同一语义同时存在于：

- 源码 docstring
- `archmap.config.json` 的模块 note
- README 目录说明
- LLM 注解

删除存储契约后，config、README 和重新生成的 LLM 注解仍可能描述已经不存在的结构。`check` 不会发现这类语义漂移。

### P2-3 产物体量与小项目性价比

样本项目约 1,051 行源码，对应：

```text
architecture.json       约 1 MB
architecture.html       约 968 KB
llm-annotations.json    约 40 KB
annotation-proposal.json 约 32 KB
```

小项目仪式感偏重；大型项目需要单独验证构建耗时、页面加载、查询延迟和 HTML 体积。

## 5. 根因归纳

### 5.1 插件层根因

1. 工具输出以“失败摘要”为主，没有把诊断作为一等数据。
2. 工具面只覆盖 build / annotate，没有覆盖查询和验证。
3. 注解编排以“是否有旧注解”判断，而不是以“事实是否仍匹配”判断。
4. Skill 注册只解决了 provider 侧，未验证宿主工具面和斜杠命令链路。

### 5.2 Python 核心根因

1. 动态调用和属性链解析不足，且 unresolved 没有充分暴露给上层。
2. polymorphic 无候选被视为硬错误，缺少“保留抽象 + 显式不完整声明”的低摩擦路径。
3. 角色和能力面推断以结构/命名启发式为主，缺少高置信度显式标注优先级和低置信度可见性。
4. 配置解析宽容但缺少严格校验，错误 key 和无匹配 override 静默丢失。
5. 模块 note 与源码 docstring 没有单一事实源。

### 5.3 产品流程根因

1. “0 diagnostics”被当作唯一成功标准，容易诱导模型修改设计迎合分析器。
2. 注解被当作一次性全量动作，而不是随源码事实变化的增量缓存。
3. Skill 价值依赖模型主动阅读，而不是确定性的工具入口。

## 6. 对后续改进的约束

1. 不能为了提高解析成功率而删除用户的设计抽象。
2. 不能把 unresolved 伪装成确定关系，也不能把确定关系降级成未解析。
3. 模型只能返回语义文本，不得改写源码、bundle 或 sourceHash。
4. 所有路径继续限制在 DSH workspace 内。
5. 新增工具和字段应尽量向后兼容，避免直接破坏 0.1.0 调用方。
6. 改进顺序应先保证“输出诚实、错误可见、查询可用”，再提升解析准确率。
7. 发布内容变化时新增版本标签，不移动已发布标签。

## 7. 复盘结论

当前插件的真实定位应当是：

```text
可用于：约束交付形状、生成可审阅架构面、提供静态事实与语义注解
不可直接用于：把 0 diagnostics 当作设计正确、把 callers=0 当作确定事实、把全量注解当作增量更新
```

下一阶段不应优先扩展图形种类，而应优先补齐四条闭环：

1. 错误可见
2. 查询可用
3. 注解增量
4. unresolved 诚实

完整任务拆分、验收标准和推进节奏见：

- [2026-11-19-dsh-archmap-explorer-改进计划.md](2026-11-19-dsh-archmap-explorer-改进计划.md)
