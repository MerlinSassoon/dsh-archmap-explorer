# ArchMap v3 数据与扩展设计

> 本文档记录 v3.8 基础数据契约及 P5.1-P5.5 增量修订，并作为实现和后续 ArkTS 扩展的依据。当前 bundle schema 为 5.0；历史文档已归档到 [`docs/旧文档/`](旧文档/README.md)。发生冲突时，以本文档、[根 README](../README.md) 和当前 bundle schema 为准。
>
> **P5 补充（2026-11-18）**：P5 主流程执行流首版已实现，新增 `projectGraph.executionFlows` / `primaryExecutionFlowId`，bundle schema 4.1；P5.2 增加可选 `executionEntrypoints`，用于将主执行流起点与分析入口解耦；执行流边界见 [`p5-main-execution-flow.md`](p5-main-execution-flow.md)。<br>
>
> **P5.1 补充（2026-11-18）**：移除执行流 `merge` 合成节点，改为多边直接 fan-in；卡片改为内嵌端口行样式。详见 [`p5.1-execution-card-style.md`](p5.1-execution-card-style.md) 与 [`p5.1-execution-flow-fan-in-plan.md`](p5.1-execution-flow-fan-in-plan.md)。<br>
>
> **P5.3 补充（2026-11-18）**：`return` 成为无出边的终止节点，`exit` 按真实隐式结束路径按需生成；执行边实线只表示确定直接关系、虚线只表示推断/不完整/间接关系；`free_function` 统一表示主模块本地 callable，通过 `callableKind` 区分函数与方法。<br>
>
> **P5.4 补充（2026-11-18）**：bundle schema 升级到 4.1。执行边只保留连接关系 `next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`；`break` / `continue` / `return` 仅作为节点终止类型且无出边；`loop_complete` 是循环唯一结构化离开出口。执行卡片改用 human note，不再渲染 signature。<br>
>
> **P5.5 补充（2026-11-18）**：主流程页独立为 `#/flow` 项目级视图，只展示 `executionFlows`；主模块与功能模块统一进入 `#/module/<id>` 能力页。`mainFlows` 数据保留，但不再作为默认 UI 调用总览展示。<br>
>
> **当前状态（2026-11-18）**：P0/P1/P1.5/P2.0/P2.1/P2.2/P2.3/P2.4/P3/P4/P5/P5.1/P5.2/P5.3/P5.4/P5.5 已完成。类焦点页与类内方法图不在产品计划中；后续扩展以增量扫描、ArkTS surface 和更精细类型推断为主。
>
> **P6 计划（2026-11-18）**：项目模型重构已批准，目标为取消主模块、项目级主流程、单一 executionFlows 投影和纵向能力模块。实施契约、阶段与验收以 [`p6-project-model-plan.md`](p6-project-model-plan.md) 为准。<br>
> **P6.2 已实施（2026-11-18）**：bundle schema 升级为 5.0；移除 `mainModuleId`、`moduleKind`、`mainFlows`、`primaryFlowId`；所有模块统一为普通能力模块；execution flow 移除语义 `entry` 节点；`moduleGraphs[].edges` 调用视图数据移除。本文以下 P5/P2.4 段落中涉及主模块与 mainFlows 的内容为历史契约说明，当前契约以本节及 schema 5.0 为准。

## 1. 三层投影

### ProjectGraph

项目页是模块能力概览，不是依赖网络：

- 模块是项目页一等节点，包含名称、人工备注、Provider Role 和提供接口。
- 所有模块都是普通能力模块；不存在主模块或 `moduleKind`。
- 模块不再拥有输入/输出端口，`boundaryNodes` 与 module_input/module_output 边已移除。
- 模块卡片同时展示 Provider Role 数量；模块间依赖证据仍不默认绘制。
- `providedApis` 来自 Provider + Capability 契约投影，包含公开方法、抽象契约方法和协议能力。
- 项目页默认不绘制 `projectGraph.edges`；模块间调用/数据证据保留，供可选“关系”模式与后续查询使用。
- 默认几何由 Python 以能力卡片网格生成（`layout.mode = "module-cards"`），前端只负责渲染与用户拖拽覆盖。
- P6.2 起 `projectGraph.mainFlows` / `primaryFlowId` 已删除；项目级执行视图只保留 `executionFlows` / `primaryExecutionFlowId`。

### ExecutionFlow

`mainFlows` 已在 schema 5.0 删除；当前主流程页面只使用 `executionFlows`。

- 节点类型：`exit` / `free_function` / `interface` / `branch` / `multi_branch` / `loop` / `break` / `continue` / `return` / `dispatch`；
- 不生成语义 `entry` 节点；入口由 flow 元数据和标准流程卡片表达；
- 边只表达控制连接：`next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`；
- 执行流保留原子 callable / interface 节点；具体分类不依赖主模块；
- 项目级分析不修改 Provider Role、visibility 或 API 分类；
- dispatch 节点保存候选数量、候选来源、是否完整和 unresolved 原因；
- **执行流边界**：只展开 entrypoint 自身控制骨架；调用目标均作为原子节点，不继续穿透实现；
- 内部实现路径保留在 Method Detail、callSites 和 trace/impact 中。

### ModuleGraph

所有普通能力模块统一使用模块能力页展示提供接口、Provider、类节点和模块级自由函数节点；主流程作为独立 `#/flow` 页面展示：

- 顶部提供接口条来自 `moduleGraphs[].providedApis`，接口 chips 可下钻到 Method Detail。
- `moduleGraphs[].apiProviders` 按 Provider 分组展示模块公开能力，并携带 `providerRole` / `roleSource` / `roleConfidence`。
- `moduleGraphs[].moduleComposition` 按角色列出类与模块级自由函数 Provider；`providerRoleCounts` 提供事实层计数。
- `publicModuleComposition` / `publicProviderRoleCounts` 只包含 `providerVisibility = "public"` 的 Provider，供默认 UI 使用。
- 类节点是模块内的一等组件，带 `classKind`、`isAbstract`、`usage`、`providedApis` 和方法摘要。
- 类卡片只展示构造签名与提供接口；类内方法图和类焦点页不在产品计划中。
- 类方法归属 `class` 节点，不直接平铺为模块页函数节点；方法级关系保存在 `methodEdges` 和全局 `callSites` 中。
- `moduleGraphs[].edges` 已删除；模块能力页不默认绘制调用边。
- 方法节点属于类组件的子级语义；类本身不拥有执行流。
- 模块不再包含输入/输出边界；抽象类/接口只作为契约 Provider，不进入主流程执行节点。
- 函数节点只展示函数名和人工备注，不展示步骤数、调用数等生成统计。
- 双击自由函数或点击类方法进入 Method Detail 页面。
- 类内部方法只显示数量，不展开方法图；公开能力点击进入 Method Detail。

### API 契约模型

P2.1 引入语言中立的 Provider + Capability 模型：

- **Provider**：类或自由函数；
- **Capability**：`function` / `method` / `context_manager` / `async_context_manager` / `callable` / `iterable`；
- **Exposure**：`public` / `internal`；
- **Exposure Source**：`docstring` / `comment` / `decorator` / `config` / `entrypoint` / `protocol` / `naming`；
- **Evidence**：函数 ID、文件、行号、注释或装饰器。

规则：

- `__init__` 不作为 API 行，只作为类 `usage.constructor`；
- `__enter__` / `__exit__` 合成 `context_manager`；
- `__aenter__` / `__aexit__` 合成 `async_context_manager`；
- `__call__` 合成 `callable`；
- `__iter__` 合成 `iterable`；
- 其他 dunder 默认不进入 API；
- `_name` 默认 internal；
- 非下划线无标注默认 public，来源 `naming`。

明确延期：`__len__` / `__getitem__` / `__contains__` / 切片 / ArkTS index signature 等序列协议。

详细说明见 [`archmap-api-contract-model.md`](archmap-api-contract-model.md)。

### Provider Role（P2.2 已实现）

Capability 之上增加 Provider 级角色：

```text
config / model / manager / entry / adapter / component / contract / utility
```

职责与展示：

- `config`：类型定义、字段、默认值、常量表、枚举；展示类型卡片；
- `model`：运行期数据记录、DTO、分析结果；展示类型卡片；
- `manager`：管理 model/config 实例，组织行为，对外 API；
- `entry`：CLI、用户入口或入口函数 Provider；
- `adapter`：外部系统适配，展示适配器入口能力；
- `component`：UI/协议组件；
- `contract`：抽象类、Protocol、接口；
- `utility`：纯函数/助手，展示函数签名。

角色判定优先级：

```text
contract.providerRoles 显式覆盖
  > 注释 / 装饰器 / JSDoc 标注
  > 结构规则
  > 命名弱提示
```

Provider 节点、`apiProviders` 与 API capability 均带：

```json
{
  "providerRole": "manager",
  "roleSource": "structure",
  "roleConfidence": "high",
  "providerVisibility": "public",
  "ownerProviderId": null
}
```

模块图输出 `moduleComposition` / `providerRoleCounts`，以及只含公开 Provider 的 `publicModuleComposition` / `publicProviderRoleCounts`。`config` / `model` 的 `providedApis` 必须为空，其字段通过 `typeSummary` 展示；`utility` 默认 internal，不进入默认项目页/模块页，但仍保留在 FunctionDetail 与 CallSite 事实层。内部阶段函数通过 `ownerProviderId` 指向其 facade manager。

### 类型关系与继承 API（P3 已实现）

P3 把 Python 基类表达式解析为 canonical 类型关系，并进入 ProjectGraph 与 ModuleGraph：

```json
{
  "id": "type:cls:app.impl.EchoWorker:implements:cls:app.base.Worker",
  "kind": "implements",
  "fromClassId": "cls:app.impl.EchoWorker",
  "toClassId": "cls:app.base.Worker",
  "moduleId": "impl",
  "targetModuleId": "base",
  "confidence": "high",
  "evidence": {"file": "app/impl.py", "line": 5}
}
```

- 只有解析到项目内 canonical class ID 才生成关系；第三方/条件导入基类保留在 `unresolvedBases`。
- `implements` 表示抽象类/Protocol/interface 目标，具体类目标使用 `inherits`。
- 类节点携带 `baseClassIds`、`subclassIds`、`mroClassIds`、`abstractMethodNames` 和有效 `isAbstract`。
- 继承 Capability 仍归属于子类 Provider，但携带 `inherited=true`、`declaredInProviderId`、`inheritedFromProviderId`、`overridesCapabilityId` 和真实 evidence function IDs。
- 抽象/Protocol 方法调用不产生唯一调用边，而是生成 `polymorphic=true`、`resolved=false`、`candidates[]` 和 `dispatchKind=polymorphic` 的 CallSite。
- 多态 candidates 进入主流程时使用 `candidateSource=polymorphic` 的 dispatch 节点和 `composition(low)` 虚线。
- 本地候选集默认不标记完整，因为项目外实现不可知。

### 结构关系扩展（P4 已实现）

`typeRelations` 在 `inherits/implements` 之外新增：

- `instantiates`：AST 构造调用；
- `uses`：参数、返回值和字段类型注解；
- `aggregates`：构造注入或字段持有；
- `composes`：构造函数内实例化并赋给实例字段。

每条关系带 `source`、`fromProviderId`/`toProviderId`、Provider Role、可见性、confidence 与 `evidenceFunctionIds`。无法解析的项目内类不生成结构边。

### User Surface（P4 已实现）

需要区分：

```text
developer API   模块之间调用的代码契约
user surface    最终用户能感知或操作的交互面
```

独立投影：

```json
{
  "kind": "cli_input",
  "display": "CLI 输入 · run_cli()",
  "moduleId": "main",
  "evidenceFunctionIds": ["fn:app.main.run_cli"],
  "entrypointIds": ["fn:app.main.main"],
  "confidence": "high",
  "source": "io_primitive"
}
```

识别线索：

- `input()` / `print()` / `sys.stdout.write` → CLI；
- keyboard listener / event handler → keyboard event；
- socket / HTTP server → network；
- `open` / 文件读写 → file IO；
- ArkTS `@Entry` / `@Component` / `TextInput` / `Button` → UI；
- 沿 entrypoint 调用路径传播，带 confidence；
- 支持 `userSurface.overrides` 配置覆盖，不硬编码具体项目函数名。

入口模块可展示 `entry` + `userSurfaces`；其他能力模块仍以 developer API 为主。

### Impact / Trace / DSM（P4 已实现）

- Impact：比较两个 bundle 的函数、API、结构关系与 surface 变化，沿 caller/结构关系反向传播；
- Trace：沿静态调用、多态 candidates 和结构关系做有界出向/入向查询；
- DSM：按 module 或 provider 聚合依赖权重和关系类型；
- 三者都是只读查询结果，不写入默认 bundle；
- 必须支持 `maxDepth` / `maxNodes` / `truncated`，不静默截断。

### FunctionDetail / CallSite

P1.5 起，默认产品不再生成语句级 FunctionFlow：

- 每个函数/方法生成 `FunctionDetail`，包含源码切片、签名、备注、返回/异常、callers/callees、`apiExposure` 和 `sourceHash`。
- 每次静态调用生成 `CallSite`，记录文件、行、列、调用文本、解析状态和置信度；多态调用额外记录 `polymorphic`、`dispatchKind` 和候选函数集合。
- `methodEdges` 和模块/项目边由 CallSite 聚合，不再从执行流节点反推调用。
- 方法详情页以源码、人类备注、LLM 语义和调用邻域为主视图。
- 旧 FunctionFlow 仅保留在历史设计文档中，不再是默认 bundle 或 UI 的一部分。

## 2. 宏观边契约

宏观边不是模糊的“混合箭头”，而是可验证的关系聚合：

```json
{
  "id": "e:project:1",
  "from": "entry-network",
  "to": "database",
  "primaryType": "call",
  "relations": ["call", "data"],
  "role": "internal",
  "confidence": "high",
  "evidence": [
    {
      "fromFunctionId": "fn:main.server",
      "toFunctionId": "fn:database.Database.actions",
      "file": "main.py",
      "line": 15
    }
  ]
}
```

- `call`：由已解析的跨函数调用聚合。
- `data`：调用步骤携带参数/返回值等数据证据时附加。
- 主流程 `call` / `call_path` 表示真实静态调用或其压缩路径；`composition` 表示动态分发/组合推断，必须低置信度虚线。
- `primaryType` 只决定默认视觉样式，`relations` 保留全部证据。
- 没有证据的关系不生成边。

## 3. 模块识别

优先级：

1. 配置中的 `modules[].include`。
2. Python 包/命名空间。
3. 单模块兜底。

禁止把每个文件机械地当成一个界面模块。源码文件只作为函数节点详情中的证据。

## 4. 人工备注

- Python 函数优先取 docstring 第一段。
- 其次取函数体首部或定义上方的连续注释块。
- 备注参与语义指纹。
- LLM 注解放在侧车文件，不参与代码语义指纹，不覆盖人工备注。

## 5. LLM 注解侧车

```json
{
  "version": 1,
  "model": "...",
  "generatedAt": "...",
  "nodes": {
    "fn:app.main.main": {
      "summary": "...",
      "details": "...",
      "sourceHash": "sha256:..."
    }
  }
}
```

v1 只读取并在详情面板展示，不调用 LLM。`sourceHash` 不匹配时显示过期提示。

## 6. 默认布局与用户覆盖

- 后端输出 ProjectGraph、ModuleGraph 的默认坐标与边路径。
- 前端不做宏观 rank/x/y/自动布局。
- 项目页、模块页类/函数节点和展开模块内部节点拖拽写入 `localStorage` 覆盖层，键为 `archmap-v3-layout-v1`。
- 覆盖文件由前端导入/导出为 `layout-overrides.json`。
- 覆盖项按稳定 ID 保存，忽略过期或无效键。
- 覆盖不进入语义指纹。
- P1.5 后不再存在函数级执行流布局覆盖；方法详情页以源码和调用关系为主。
- 类焦点页不纳入产品计划，因此不新增类页布局覆盖命名空间。
- 方法详情页和源码面板遵循系统 `prefers-color-scheme`。

## 7. 语言前端接口

`archmap/model/frontend_contract.py` 定义 `LanguageFrontend`：

- 负责源码发现、解析、符号解析、模块投影、CallSite 提取、FunctionDetail 和 ContractModel 构建。
- `archmap/utility/graph_utility.py`、`archmap/utility/validate_utility.py`、`archmap/utility/render_utility.py` 及对应 Manager 不依赖 Python AST。
- 注册由 `FrontendManager` 显式持有，不是插件系统。
- Python 前端使用标准库 `ast`，v1 运行时零第三方依赖。

### ArkTS 接入要求

后续 `frontends/arkts` 需要：

- 将文件、类、函数、调用和注释转换为与 Python 相同的 canonical IR。
- 实现 `build_contracts`：`export`、`public` / `private` / `protected`、JSDoc `@public` / `@internal`、getter/setter、`Symbol.iterator` 等映射为 canonical capability。
- 实现 Provider Role 映射：`interface` / `type` / `enum` / const object → config；data class → model；有公开方法的 class → manager；`@Entry` / `@Component` → entry/component。
- 用户交互面映射：`@Entry` / `@Component` / `@Builder` / `TextInput` / `Button` / router / network API。
- `@Entry` / `@Component` 作为 entrypoint，不默认当作公开 API。
- ArkTS 没有 Python 的 `__enter__` / `__exit__`，不伪造 context manager。
- 序列协议（length / index signature）与 Python 一起延期。
- 使用可选解析器依赖，不污染 Python v1 的零依赖边界。
- 不要求修改布局、校验、渲染或路由核心。

## 8. 产物

```json
{
  "schemaVersion": "5.0",
  "kind": "archmap.bundle",
  "project": {},
  "entrypoints": [],
  "projectGraph": {},
  "moduleGraphs": [],
  "functionDetails": [],
  "callSites": [],
  "diagnostics": [],
  "stats": {}
}
```

JSON Schema：`docs/schema/archmap-v3-bundle.schema.json`。

单文件 HTML 内联 bundle、CSS 和 JS，无 CDN、外部字体、外部图片或网络请求。
