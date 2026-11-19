# ArchMap v3 数据与扩展设计

> 版本：ArchMap 2.5.0 / bundle schema 6.4<br>
> 日期：2026-11-19<br>
> 文档性质：当前数据契约。历史阶段补充已归档到 [`旧文档/archmap-v3-design-阶段补充.md`](旧文档/archmap-v3-design-阶段补充.md)。

## 1. 三层投影

### ProjectGraph

项目页是模块能力概览，不是依赖网络：

- 模块是项目页一等节点，包含名称、人工备注、Provider Role 和提供接口。
- 所有模块都是普通能力模块；不存在主模块或 `moduleKind`。
- 模块不再拥有输入/输出端口，`boundaryNodes` 与 module_input/module_output 边已移除。
- 模块卡片同时展示 Provider Role 数量；模块间依赖边不再生成或绘制。
- `providedApis` 来自 Provider + Capability 契约投影，包含公开方法、抽象契约方法和协议能力。
- `projectGraph.edges` 固定为空数组，仅保留 schema 兼容；项目页不展示模块间依赖或关系线。跨模块调用事实仍保留在 `callSites` 与 `functionDetails` 中。
- 项目页包括 `projectGraph.flowCards` 与 `projectGraph.modules` 两类标准卡片；两者都进入 `projectGraph.layout.nodes`。
- 自由函数默认采用保守能力边界：`defaultFreeFunctionSurface` 支持 `auto` / `internal` / `capability`，单函数用 `apiExposure` 例外；
- `projectGraph.capabilityModuleIds` 给出能力非空、应由前端渲染的模块集合；`capabilitySurface.hasProviders=false` 的模块仍保留在后台模块与 layout 中，但前端不渲染模块卡；默认布局将空模块追加到可见卡片之后，并按可见数量计算网格列数，避免前端过滤后出现网格空洞。
- 默认几何由 Python 以统一卡片网格生成（`layout.mode = "module-cards"` 当前兼容保留，实际同时布局 flow cards 与 module cards），前端只负责渲染与用户拖拽覆盖。
- `projectGraph.mainFlows` / `primaryFlowId` 已删除；项目级执行视图保留 `executionFlows`、`flowCards` / `primaryExecutionFlowId`。
- 模块画布使用 `layout.mode = "module-grid"` 的矩形卡片网格，不再把所有 Provider 节点放进单列 rank。

### ExecutionFlow

`mainFlows` 已在 schema 5.0 删除；当前主流程页面只使用 `executionFlows`。

- 节点类型：`entry` / `exit` / `free_function` / `interface` / `branch` / `multi_branch` / `loop` / `break` / `continue` / `return` / `dispatch`；
- 每条 flow 恰好一个标准 `entry` 节点；入口由项目级 entrypoints 解析生成；
- 边只表达控制连接：`next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`；
- 执行流保留原子 callable / interface 节点；具体分类不依赖主模块；
- 显式声明为 `executionOnlyCallables` 的 callable 仍可作为 flow 节点和无缝源码下钻目标；
- 项目级分析不修改模块边界；
- dispatch 节点保存候选数量、候选来源、是否完整和 unresolved 原因；
- **执行流边界**：主流程只展开 entrypoint 自身控制骨架；调用目标均作为原子节点，不继续穿透实现；
- 一级接口 scope 是显式投影：只展示目标函数直接外部接口和必要控制结构，`depth` 恒为 `1`，scope 内不得再嵌套 scope；scope root 必须是 `free_function` 编排 callable，`interface` 节点是功能模块能力边界，不得生成 scope；`autoDetect` 只从主流程可见、同模块、命中外部接口与控制结构的 `free_function` 中保守发现候选；普通赋值/非调用表达式不生成节点，而通过 branch `armSummaries`、edge `statements` 与 `implicitNext` 保留控制臂语义；多分支只保留条件与隐式循环提示，不展示 case 内部赋值注释；
- 主流程节点通过 `drilldown` 摘要给出 scope 链接和外部接口；完整 scope 存放在 `executionFlows[].scopes`；
- dispatch 节点通过 `drilldown.kind=dispatch` 指向 `executionFlows[].dispatchGroups[]`；group 内每个候选是一级 `archmap.execution-scope`，候选根仍必须是真实 `free_function`；
- 候选集完整性、来源、预算截断和 omitted candidate 均在 dispatch group 中显式记录；
- 内部实现路径保留在 Method Detail、callSites 和 trace/impact 中。

### ModuleGraph

所有普通能力模块统一使用模块能力页展示提供接口、Provider、类节点和模块级自由函数节点；主流程作为独立 `#/flow` 页面展示：

- 顶部提供接口条来自 `moduleGraphs[].providedApis`，接口 chips 可下钻到 Method Detail。
- `executionOnlyCallables` 不进入 `providedApis`、`moduleComposition`、Provider 计数或模块能力节点。
- `functionSurface=internal` 的自由函数同样不进入公开能力面，但仍保留在 functionDetails / callSites / trace 中。
- 类方法被声明为 executionOnly 时，所属类 Provider 保留，但该方法从类能力 API 中移除。
- `capabilitySurface` 为空时，模块页不渲染；直接路由返回项目页。
- `moduleGraphs[].apiProviders` 按 Provider 分组展示模块公开能力，并携带 `providerRole` / `roleSource` / `roleConfidence`。
- `moduleGraphs[].moduleComposition` 按角色列出类与模块级自由函数 Provider；`providerRoleCounts` 提供事实层计数。
- `publicModuleComposition` / `publicProviderRoleCounts` 只包含 `providerVisibility = "public"` 的 Provider，供默认 UI 使用。
- 类节点是模块内的一等组件，带 `classKind`、`isAbstract`、`usage`、`providedApis` 和方法摘要。
- 类卡片只展示构造签名与提供接口；类内方法图和类焦点页不在产品计划中。
- 类方法归属 `class` 节点，不直接平铺为模块页函数节点；方法级关系保存在 `methodEdges` 和全局 `callSites` 中。
- `entryFunctionIds` / `flowEntryFunctionIds` 只作为项目级入口来源事实；入口函数仍按实际职责属于普通 Provider Role。
- `moduleGraphs[].edges` 已删除；模块页不默认展示调用边。
- `moduleGraphs[].edges` 已删除；模块能力页不默认绘制调用边。
- 方法节点属于类组件的子级语义；类本身不拥有执行流。
- 模块不再包含输入/输出边界；抽象类/接口只作为契约 Provider，不进入主流程执行节点。
- 函数节点只展示函数名和人工备注，不展示步骤数、调用数等生成统计。
- 双击自由函数或点击类方法进入 Method Detail 页面。
- 类内部方法只显示数量，不展开方法图；公开能力点击进入 Method Detail。

### API 契约模型

当前 API 契约使用语言中立的 Provider + Capability 模型：

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

### Provider Role

Capability 之上增加 Provider 级角色：

```text
config / model / manager / adapter / component / contract / utility
```

职责与展示：

- `config`：类型定义、字段、默认值、常量表、枚举；展示类型卡片；
- `model`：运行期数据记录、DTO、分析结果；展示类型卡片；
- `manager`：管理 model/config 实例，组织行为，对外 API；
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

### 类型关系与继承 API

当前实现把 Python 基类表达式解析为 canonical 类型关系，并进入 ProjectGraph 与 ModuleGraph：

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

### 结构关系扩展

`typeRelations` 在 `inherits/implements` 之外新增：

- `instantiates`：AST 构造调用；
- `uses`：参数、返回值和字段类型注解；
- `aggregates`：构造注入或字段持有；
- `composes`：构造函数内实例化并赋给实例字段。

每条关系带 `source`、`fromProviderId`/`toProviderId`、Provider Role、可见性、confidence 与 `evidenceFunctionIds`。无法解析的项目内类不生成结构边。

### User Surface

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

入口来源可在项目页 flow card 中展示；能力模块仍以 developer API 为主。

### Impact / Trace / DSM

- Impact：比较两个 bundle 的函数、API、结构关系与 surface 变化，沿 caller/结构关系反向传播；
- Trace：沿静态调用、多态 candidates 和结构关系做有界出向/入向查询；
- DSM：按 module 或 provider 聚合依赖权重和关系类型；
- 三者都是只读查询结果，不写入默认 bundle；
- 必须支持 `maxDepth` / `maxNodes` / `truncated`，不静默截断。

### FunctionDetail / CallSite

默认产品不再生成语句级 FunctionFlow：

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
- 模块 note 优先使用配置覆盖；未配置时回退到模块 docstring 第一段，并通过 `noteSource` 标明来源。
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

ArchMap Python 核心只读取并在详情面板展示注解，不调用 LLM。DSH 插件 `dsh-archmap-explorer@0.1.0` 已通过宿主模型生成同一侧车文件，不改变 bundle 契约。`sourceHash` 不匹配时显示过期提示。

Python 侧提供两条确定性命令：

```bash
python -m archmap annotations context <bundle> --scope functions --max-nodes 50 --json
python -m archmap annotations apply <bundle> --proposal <json> --provider <id> --model <id> --json
```

`annotations context` 从 `functionDetails`、`moduleGraphs` 和 `projectGraph` 生成有界上下文，支持 `project` / `modules` / `functions` / `all`、显式 nodeIds、源码字符上限以及已有注解摘要。`annotations apply` 只接受 bundle 中存在的 nodeId，`sourceHash` 由 Python 从 bundle 读取并校验；默认保留已有注解，`force` 才允许覆盖。成功后合并写入侧车并重新渲染 HTML。

## 6. 默认布局与用户覆盖

- 后端输出 ProjectGraph、ModuleGraph 的默认坐标与边路径。
- 前端不做宏观 rank/x/y/自动布局。
- 项目页、模块页类/函数节点和展开模块内部节点拖拽写入 `localStorage` 覆盖层，键为 `archmap-v3-layout-v1`。
- 覆盖文件由前端导入/导出为 `layout-overrides.json`。
- 覆盖项按稳定 ID 保存，忽略过期或无效键；默认卡片几何或布局命名空间变化时必须提升前端 `geometryVersion`，旧坐标会被丢弃并回退到 Python 默认布局。
- 覆盖不进入语义指纹。
- 不再存在函数级执行流布局覆盖；方法详情页以源码和调用关系为主。
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
  "schemaVersion": "6.4",
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

JSON Schema：`docs/schema/archmap-v6.4-bundle.schema.json`；6.3 / 6.2 / 6.1 / 6.0 等历史 schema 已归档到 `docs/旧文档/schema/`。

单文件 HTML 内联 bundle、CSS 和 JS，无 CDN、外部字体、外部图片或网络请求。
