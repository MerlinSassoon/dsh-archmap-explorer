# ArchMap v3 数据与扩展设计

> 本文档冻结 v3.5 数据契约，并作为实现和后续 ArkTS 扩展的依据。与 `archmap-2.0-design.md`、旧 `docs/HANDOFF.md` 冲突时，以本文档、[`README.md`](../README.md) 和 [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md) 为准。
>
> **当前状态（2026-11-17）**：P0/P1/P1.5/P2.0/P2.1/P2.2/P2.3 已完成；P3、P4 尚未开始。类焦点页与类内方法图不在产品计划中；结构关系和用户交互面是后续契约。

## 1. 三层投影

### ProjectGraph

项目页是模块能力概览，不是依赖网络：

- 模块是项目页一等节点，包含名称、人工备注、输入、输出、角色和提供接口。
- 模块角色为 `main` / `service` / `adapter` / `test` / `other`；显式配置优先，否则含入口函数的模块为 `main`。
- 模块卡片同时展示 Provider Role 数量；模块间依赖证据仍不默认绘制。
- `providedApis` 来自 Provider + Capability 契约投影，包含公开方法、抽象契约方法和协议能力。
- 项目边界节点保留在数据中，但默认不以画布节点渲染。
- 项目页默认不绘制 `projectGraph.edges`；模块间调用/数据证据保留，供可选“关系”模式与后续查询使用。
- 默认几何由 Python 以能力卡片网格生成（`layout.mode = "module-cards"`），前端只负责渲染与用户拖拽覆盖。

### ModuleGraph

模块页展示模块提供接口、模块输入/输出、类节点和模块级自由函数节点：

- 顶部提供接口条来自 `moduleGraphs[].providedApis`，接口 chips 可下钻到 Method Detail。
- `moduleGraphs[].apiProviders` 按 Provider 分组展示模块公开能力，并携带 `providerRole` / `roleSource` / `roleConfidence`。
- `moduleGraphs[].moduleComposition` 按角色列出类与模块级自由函数 Provider；`providerRoleCounts` 提供事实层计数。
- `publicModuleComposition` / `publicProviderRoleCounts` 只包含 `providerVisibility = "public"` 的 Provider，供默认 UI 使用。
- 类节点是模块内的一等组件，带 `classKind`、`isAbstract`、`usage`、`providedApis` 和方法摘要。
- 类卡片只展示构造签名与提供接口；类内方法图和类焦点页不在产品计划中。
- 类方法归属 `class` 节点，不直接平铺为模块页函数节点；方法级关系保存在 `methodEdges` 和全局 `callSites` 中。
- 方法节点属于类组件的子级语义；类本身不拥有执行流。
- 模块输入/输出边界只连接类节点或显式自由函数入口，并通过 `viaMethodIds` 保留方法级证据；抽象类/接口不接模块边界。
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
- `entry`：主模块、CLI、用户入口；
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

### User Surface（P4 规划）

需要区分：

```text
developer API   模块之间调用的代码契约
user surface    最终用户能感知或操作的交互面
```

主模块默认不展示 developer API，而展示 `entry` + `userSurfaces`。例如：

- `MenuSystem.run()`：menu 模块 manager API，同时是 TUI 键盘菜单交互面；
- `init_connection(port=12345)`：entry-network 函数 API，同时是 CLI 输入提示交互面。

用户交互面必须由调用图、IO 原语、entrypoint 路径和显式配置共同确定，带 confidence，不硬编码具体项目函数。

### FunctionDetail / CallSite

P1.5 起，默认产品不再生成语句级 FunctionFlow：

- 每个函数/方法生成 `FunctionDetail`，包含源码切片、签名、备注、返回/异常、callers/callees、`apiExposure` 和 `sourceHash`。
- 每次静态调用生成 `CallSite`，记录文件、行、列、调用文本、解析状态和置信度。
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
- `control`：主要用于项目/模块输入输出边界，不用于伪造跨模块控制流。
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

`archmap/frontends/base.py` 定义 `LanguageFrontend`：

- 负责源码发现、解析、符号解析、模块投影、CallSite 提取、FunctionDetail 和 ContractModel 构建。
- `graph.py`、`validate.py`、`render.py` 不依赖 Python AST。
- 注册使用显式 `FRONTENDS` 字典，不是插件系统。
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
  "schemaVersion": "3.5",
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
