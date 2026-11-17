# ArchMap P2–P4 交接文档

> 日期：2026-11-16；最后核对：2026-11-18<br>
> 适用版本：ArchMap 1.6.0 / bundle schema 3.6<br>
> 当前阶段：P0、P1、P1.5、P2.0、P2.1、P2.2、P2.3、P2.4 已完成；P3、P4 尚未开始。类焦点页与类内方法图不在产品计划中。
>
> 本文用于新会话接手项目，包含项目现状、代码地图、数据契约、后续规划、设计来源和风险。文档归档边界见 [`docs/README.md`](README.md)；旧 FunctionFlow 文档不再代表当前契约。

---

## 1. 新会话阅读顺序

建议按以下顺序阅读：

1. 本文 `docs/HANDOFF-P2-P4.md`
2. `docs/README.md` — 当前/历史文档边界
3. `README.md`
4. `docs/function-detail-p1.5-plan.md`
5. `docs/archmap-api-contract-model.md` — Provider + Capability API 契约模型与角色规划
6. `docs/archmap-architecture-spec.md` — P2.3 四类物理文件、八角色语义、依赖方向与可见性
7. `docs/archmap-v3-design.md`
8. `archmap/model/contract_model.py` — 语言中立契约 IR
9. `archmap/utility/contract_utility.py` — Python exposure 与协议能力辅助
10. `archmap/utility/role_utility.py` / `archmap/frontends/python/role_utility.py` — Provider Role 判定、owner 归属、组合与类型摘要
11. `archmap/managers/graph_manager.py` / `archmap/utility/graph_utility.py` — 三层投影、apiProviders、类节点、模块边界
12. `archmap/frontends/python/call_utility.py` — 静态调用事实
13. `archmap/frontends/python/detail_utility.py` — FunctionDetail / 源码 / callers / callees
14. `archmap/render/assets/app.js` — 契约卡片、类型卡片、模块页与方法详情页
15. `tests/test_api_contracts.py`、`tests/test_provider_roles.py`、`tests/test_class_layer.py`、`tests/test_build.py`

历史文档 `docs/archmap-2.0-design.md`、`docs/HANDOFF.md` 中关于 FunctionFlow 的章节是历史设计，不是当前默认契约。当前产品已明确移除语句级执行流。

---

## 2. 项目一句话

ArchMap 把 Python 项目转换为**模块优先、Provider 为组件、Capability 为契约、源码为事实来源**的可交互架构浏览器。

产品分工：

```text
架构图 = 结构和关系
源码   = 实现细节
LLM    = 高层语义
```

已批准的模块内职责模型：

```text
config   类型定义、字段、默认值、常量表、枚举
model    运行期数据模型 / DTO / 分析结果
manager  管理 model/config 实例，组织行为，对外暴露 API
entry    主模块 / CLI / 用户入口
adapter  外部系统适配
component UI / 协议组件
contract 抽象类 / Protocol / 接口
utility  纯函数 / 助手
```

一个完整业务模块通常由 `config + model + manager` 组成；不是所有项目都有 config/model，也不是所有模块都有 manager。

默认产物：

```text
.archmap/<project>/
├── architecture.json   # ProjectGraph + ModuleGraph + FunctionDetail + CallSite
├── architecture.html   # 自包含单文件 HTML
├── llm-annotations.json（可选）
└── layout-overrides.json（前端导出）
```

---

## 3. 当前项目状态

### 3.1 已完成

- P0：类语义数据模型
- P1：模块页类组件化、模块边界修复
- P1.5：FunctionFlow 移除、FunctionDetail + Source View + Call Graph
- P2.0：项目页/模块页能力契约重构
- P2.1：API 契约建模与展示
- P2.2：Provider Role、模块组合、类型卡片与角色过滤
- P2.3：架构规范落盘、config/model/utility/managers/entry 迁移、facade manager 所有权纠偏、providerVisibility / ownerProviderId 与 utility 隐藏
- P2.4：唯一主模块、删除模块 I/O、功能模块 0..N、主流程 DAG、dispatch 候选与 composition 低置信度虚线

### 3.2 当前已实现能力

- Python AST 源码发现、模块归属、类/函数/方法索引；
- 类元数据：
  - `classKind`
  - `isAbstract`
  - `bases`
  - `decorators`
  - `methodKind`
  - `visibility`
- 模块角色：`main` / `service` / `adapter` / `test` / `other`；
- API 契约模型：Provider + Capability、`apiExposure`、`apiProviders`；
- Provider Role：config / model / manager / entry / adapter / component / contract / utility；
- `moduleComposition` / `providerRoleCounts` 与 config/model `typeSummary`；
- `providerVisibility`、`ownerProviderId`、`publicModuleComposition` / `publicProviderRoleCounts`；
- 每个领域只暴露 facade manager；阶段函数作为内部 utility 归属到对应 manager；
- utility 默认 internal，不进入默认项目页/模块页；事实层保留 FunctionDetail / CallSite；
- 物理代码按 `config/model/manager/utility` 四类组织，旧模块路径保留 import shim；
- config/model 序列化方法不再进入模块 API；
- 协议能力：context manager / async context manager / callable / iterable；
- 构造签名与 Magic Method 排除；
- 模块提供接口投影 `providedApis`（按 Provider 分组）；
- 项目页模块能力卡片：
  - 默认不绘制模块依赖线；
  - 显示职责、角色、Provider/Capability、类/Provider/API 数量；
  - 主模块视觉强调；
  - 可选“关系”模式查看保留的模块调用证据；
- 模块页：
  - 顶部提供接口条；
  - 已移除的模块输入/输出端口；
  - 类节点；
  - 模块级自由函数；
  - 类方法不再平铺。
- 类详情面板：
  - 类类型、抽象标记、构造签名；
  - 提供接口列表；
  - 内部方法只显示数量，不展开方法图。
- 方法详情页：
  - 人类备注、LLM 语义；
  - 签名、返回、异常；
  - 源码切片、行号、调用行高亮；
  - Callers / Callees；
  - 点击调用邻域继续下钻。
- 独立 CallSite 静态调用提取；
- 模块/项目级调用边聚合；
- 自包含 HTML；
- 语义指纹；
- 浏览器冒烟测试。

### 3.3 当前未实现

- P3 类型契约与继承 API；
- P4 API/type/provider/surface impact 与 trace；
- 主模块 user surface 投影与传播；
- 继承/实现的结构化边；
- 多态调用 candidates；
- 组合/聚合关系；
- Provider / API 级 impact / trace；
- 类关系矩阵；
- 继承/实现类型关系视图；
- 序列协议（`__len__`、`__getitem__`、切片、ArkTS index signature）延期；
- 完整语法高亮（当前源码是纯文本 + 行号 + 调用行高亮）。

### 3.4 当前验收数据

最近一次自举（P2.3 后）：

```text
project:       archmap_v3
modules:       5
classes:       24
functions:     158
methods:       39
call sites:    1699
resolvedCalls: 296
macroEdges:    164
providedApis:  16
apiProviders:  9
providerRoles: config=2, model=13, manager=6, entry=2, contract=1, utility=119
publicProviders: config=2, model=13, manager=6, entry=2, contract=1
HTML:          ~2.4 MB
JSON:          ~3.2 MB
```

`examples/archmap_v3.archmap.json` 已更新为 5 个逻辑模块，并排除旧 import shim；自举只分析 `config/model/utility/managers/entry/frontends` 中的规范源码。

`student_system` 历史验收数据（P2.1/P2.2 阶段，未随 P2.3 规范迁移重新自举）：

```text
modules:       5
classes:       3
functions:     45
methods:       36
call sites:    269
resolvedCalls: 43
providedApis:  13
```

历史类语义验收：

- `MenuSystem`：类节点 + 模块级辅助函数；
- `MenuSystem` 模块边界：1 进 / 1 出；
- `Spinner`：1 个类节点；
- `Spinner` 模块边界：1 进 / 1 出；
- 抽象类 `Worker`：不接模块边界，`entryMethodIds=[]`。

测试：

```text
pytest: 48 passed, 1 skipped（默认跳过浏览器测试）
ARCHMAP_RUN_BROWSER=1 pytest tests/test_browser_smoke.py: 1 passed
archmap check: OK
```

P2.1 契约验收：

- `thread_waiting.Spinner` → `with Spinner(message='加载中')`；
- `database.Database` → `with Database(password)` + `Database.actions(client_input)`；
- `menu_system.MenuSystem` → `MenuSystem.run()`；
- 魔术方法、`__init__`、内部下划线方法不进入普通 API；
- 序列协议延期。

---

## 4. 当前架构与流水线

```text
entry.cli_entry.main
  → managers.pipeline_manager.PipelineManager.build_architecture
  → utility.pipeline_utility.build_architecture
  → utility.config_utility.load_config
  → managers.frontend_manager.FrontendManager.get
  → frontends.python.python_manager.PythonFrontend
  → frontends.python.*_utility stage functions
  → managers.graph_manager.GraphManager.build_bundle
  → managers.validate_manager.ValidationManager.validate
  → managers.render_manager.RenderManager.render
```

### 4.1 语言前端

`archmap/frontends/base.py`：

```python
class LanguageFrontend(Protocol):
    def analyze(project_root, config_path=None) -> Any: ...
    def build_call_sites(analysis) -> list[Any]: ...
    def build_function_details(analysis, call_sites) -> list[dict]: ...
    def build_contracts(analysis) -> ContractModel: ...
```

Python 前端：

```text
archmap/frontends/python/__init__.py
  → analysis.analyze_project
  → callsites.collect_call_sites
  → details.build_function_details
  → frontends.python.capabilities.build_capabilities
```

ArkTS 未来应实现相同接口，不应修改 HTML 渲染核心。

### 4.2 关键代码地图

| 文件 | 职责 |
|---|---|
| `archmap/config.py` | 配置加载 |
| `archmap/discover.py` | 源码发现、模块归属 |
| `archmap/analysis.py` | AST 索引、类/函数/方法元数据 |
| `archmap/callresolver.py` | 调用目标解析 |
| `archmap/callsites.py` | 独立 CallSite 提取 |
| `archmap/details.py` | FunctionDetail、源码切片、callers/callees、API exposure |
| `archmap/contracts.py` | 语言中立的 Provider/Capability 契约模型 |
| `archmap/frontends/python/capabilities.py` | Python exposure、协议能力与构造签名，按 Provider Role 过滤能力 |
| `archmap/frontends/python/roles.py` | Provider Role 判定、模块组合来源与 config/model 类型摘要 |
| `archmap/graph.py` | ProjectGraph、ModuleGraph、类节点、apiProviders、moduleComposition、聚合边、指纹 |
| `archmap/validate.py` | bundle 交叉引用与数据校验 |
| `archmap/render.py` | 单文件 HTML 模板注入 |
| `archmap/cli.py` | build / check / method / serve / diff |
| `archmap/render/assets/app.js` | 三层页面、类详情、方法详情 |
| `archmap/render/assets/app.css` | 页面样式 |
| `archmap/frontends/` | 语言前端抽象 |

旧模块路径（`archmap/analysis.py`、`archmap/graph.py`、`archmap/contracts.py` 等）现在都是兼容 shim，只转发到新目录。自举配置默认排除 shim 文件。

已删除：

- `archmap/flow.py`
- `archmap/layout.py`

不要重新引入语句级 FunctionFlow 作为主视图。

---

## 5. 当前数据契约

Bundle 顶层：

```json
{
  "schemaVersion": "3.6",
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

### 5.1 Provider / Capability API 契约

`moduleGraphs[]` 同时提供扁平 `providedApis` 和按 Provider 分组的 `apiProviders`：

```json
{
  "role": "main",
  "providedApiCount": 1,
  "apiProviders": [
    {
      "providerId": "cls:thread_waiting.Spinner",
      "providerKind": "class",
      "providerName": "Spinner",
      "moduleId": "async",
      "apiCount": 1,
      "apis": [
        {
          "id": "api:cls:thread_waiting.Spinner:context_manager",
          "kind": "context_manager",
          "display": "with Spinner(message='加载中')",
          "signature": "with Spinner(message='加载中')",
          "providerId": "cls:thread_waiting.Spinner",
          "providerKind": "class",
          "providerName": "Spinner",
          "moduleId": "async",
          "exposure": "public",
          "exposureSource": "protocol",
          "exposureConfidence": "high",
          "functionId": null,
          "evidenceFunctionIds": [
            "fn:thread_waiting.Spinner.__init__",
            "fn:thread_waiting.Spinner.__enter__",
            "fn:thread_waiting.Spinner.__exit__"
          ],
          "constructorFunctionId": "fn:thread_waiting.Spinner.__init__",
          "isEntry": false
        }
      ]
    }
  ]
}
```

规则：

- `function` / `method` 能力对应真实函数 ID；
- `context_manager` 等协议能力没有单一 `functionId`，但保留 `evidenceFunctionIds`；
- 构造函数、dunder、下划线内部方法不进入普通方法 API；
- `__init__` 只作为类 `usage.constructor`；
- `projectGraph.layout.mode = "module-cards"`，项目页默认不渲染依赖路径；
- 契约模型详细说明见 [`archmap-api-contract-model.md`](archmap-api-contract-model.md)。

### 5.1.1 Provider Role 与模块组合

Provider 节点、`apiProviders` 条目和 API capability 增加：

```json
{
  "providerRole": "manager",
  "roleSource": "structure",
  "roleConfidence": "high"
}
```

模块图增加：

```json
{
  "moduleComposition": {
    "config": [],
    "model": [],
    "manager": ["cls:..."],
    "entry": ["fn:..."],
    "adapter": [],
    "component": [],
    "contract": [],
    "utility": []
  },
  "providerRoleCounts": {
    "config": 0,
    "model": 0,
    "manager": 1,
    "entry": 1,
    "adapter": 0,
    "component": 0,
    "contract": 0,
    "utility": 0
  }
}
```

config/model 类节点增加 `typeSummary`：

```json
{
  "typeSummary": {
    "kind": "config",
    "fieldCount": 2,
    "fields": [
      {"name": "host", "annotation": "str", "default": "'localhost'", "kind": "field"},
      {"name": "port", "annotation": "int", "default": "8080", "kind": "field"}
    ]
  }
}
```

校验不变量：config/model 的 `providedApis` 必须为空；`moduleComposition` 必须恰好覆盖模块内全部类与模块级自由函数；`providerRoleCounts` 必须与组合一致。

### 5.2 Class 节点

`moduleGraphs[].nodes` 中 `kind: "class"`：

```json
{
  "id": "cls:menu_system.MenuSystem",
  "kind": "class",
  "name": "MenuSystem",
  "qualifiedName": "menu_system.MenuSystem",
  "classKind": "service",
  "isAbstract": false,
  "bases": [],
  "decorators": [],
  "methodCount": 18,
  "publicMethodIds": [],
  "entryMethodIds": [],
  "exitMethodIds": [],
  "internalMethodCount": 10,
  "usage": {
    "constructor": {
      "functionId": "fn:menu_system.MenuSystem.__init__",
      "signature": "MenuSystem(sockets)"
    },
    "protocols": []
  },
  "providedApis": [],
  "providedApiCount": 1,
  "methods": []
}
```

方法摘要包含：

- `id`
- `name`
- `qualifiedName`
- `ownerClassId`
- `methodKind`
- `visibility`
- `isAbstract`
- `apiExposure`
- `apiExposureSource`
- `apiExposureConfidence`
- `signature`
- `note`
- `file` / `line` / `endLine`
- `functionDetailId`

### 5.3 FunctionDetail

```json
{
  "id": "fn:menu_system.MenuSystem.run",
  "ownerClassId": "cls:menu_system.MenuSystem",
  "methodKind": "public_api",
  "visibility": "public",
  "apiExposure": "public",
  "apiExposureSource": "docstring",
  "apiExposureConfidence": "high",
  "signature": "def run(self)",
  "returns": "",
  "raises": [],
  "note": "",
  "source": {
    "text": "...",
    "startLine": 334,
    "endLine": 360,
    "truncated": false,
    "language": "python"
  },
  "sourceHash": "sha256:...",
  "callers": [],
  "callees": [],
  "callerCount": 0,
  "calleeCount": 3
}
```

### 5.4 CallSite

```json
{
  "id": "call:fn:...:line:column:ordinal",
  "fromFunctionId": "fn:...",
  "toFunctionId": "fn:...",
  "file": "menu_system.py",
  "line": 340,
  "column": 9,
  "calleeText": "self.print_menu",
  "callText": "self.print_menu()",
  "kind": "call",
  "resolved": true,
  "external": false,
  "recursive": false,
  "confidence": "high",
  "candidates": [],
  "argumentCount": 0
}
```

### 5.5 边

- `moduleGraphs[].edges`：类/自由函数组件级聚合边；
- `moduleGraphs[].methodEdges`：方法级调用边；
- `projectGraph.edges`：模块级聚合边；
- 当前 `primaryType`：`call` / `data` / `control`。

P3/P4 需要增加结构关系类型：`inherits`、`implements`、`composes`、`aggregates` 等。不要把它们伪装成 `call`。

---

## 6. 项目约束

新会话必须继续遵守：

1. 工作区根目录是当前项目根目录。
2. 不注册插件，不实现插件清单，不实现 `lib/dsh-plugin.js`。
3. Python 运行时只用标准库。
4. HTML 必须自包含：无 CDN、外部字体、外部图片、网络请求。
5. 不恢复语句级 FunctionFlow 作为主视图。
6. 类不是执行流节点；类本身没有 ENTRY/EXIT。
7. 抽象类/接口不进入主流程执行节点。
8. 源码是方法实现的最终事实来源；LLM 注解是侧车，不写回源码。
9. 布局覆盖只影响项目页/模块页，不影响语义指纹。
10. 类焦点页和类内方法图不在产品计划中；类只作为 Provider 展示构造签名与提供接口。
11. 序列协议（`__len__` / `__getitem__` / 切片 / ArkTS index signature）延期，未写入契约前不得用启发式实现。
12. P2.2 Provider Role 是 P3/P4 的前置层；不得跳过角色直接做类型/影响分析。
13. config/model 展示为类型卡片，不把 `as_dict()` 等序列化方法自动当作模块 API。
14. 用户交互面必须数据驱动，支持配置覆盖与 confidence，不得硬编码 `menu.run`、`init_connection` 等具体项目函数。
15. 角色判定与用户交互面识别不得只依赖名称后缀或单一项目结构。
16. config/model Provider 的 `providedApis` 必须为空，通过 `typeSummary` 展示类型契约。
17. 角色判定优先级不得倒置；显式配置必须高于注释、结构和命名。
18. utility 默认 internal，不进入默认项目页/模块页或模块 API；事实层必须保留。
19. 项目页角色计数使用 `publicProviderRoleCounts`，不得把 internal utility 计入公开能力。

---

### 7.0 P2.0：项目页/模块页能力契约（已完成）

P2.0 已落地：

- `ModuleConfig.role`；
- `moduleGraphs[].providedApis` / `providedApiCount` / `role`；
- `projectGraph.modules[].role` / `providedApiCount`；
- 项目页能力卡片布局 `layout.mode = "module-cards"`，默认不绘制依赖线；
- 项目页“关系”按钮可临时显示保留的模块内部调用边；
- 模块页顶部 `PROVIDED API` 条；
- 模块详情与项目页模块详情可点击接口 chips 下钻到 Method Detail；
- 校验器检查 `providedApis` 的 function/owner 交叉引用与计数一致性。

P2.0 不新增第二套事实源：`providedApis` 从现有类方法、抽象方法和自由函数派生。

## 7. P2.1：API 契约建模与展示（已完成）

### 7.1 产品决策

类焦点页和类内方法图**不再计划**。类被视为 Provider，产品只关心：

- 模块对外提供什么能力；
- 类构造与使用方式；
- 类/函数提供哪些公开能力；
- 每个能力的暴露级别和证据。

类内部方法只在 Method Detail 的源码与 callers/callees 中查看。

### 7.2 已实现模型

```text
Provider     class / function
Capability   function / method / context_manager / async_context_manager / callable / iterable
Exposure     public / internal
Source       docstring / comment / decorator / config / entrypoint / protocol / naming
```

数据字段：

- `apiExposure`
- `apiExposureSource`
- `apiExposureConfidence`
- `moduleGraphs[].providedApis`
- `moduleGraphs[].apiProviders`
- `classNode.usage`
- `classNode.providedApis`
- `functionNode.providedApis`

### 7.3 Exposure 规则

优先级：

```text
config 覆盖
  > decorator
  > docstring / comment 标签
  > entrypoint
  > protocol
  > naming
```

默认：

- `_name` → internal；
- 非下划线无标注 → public，来源 `naming`；
- `__init__` → 不进入方法 API，只保留构造签名；
- `__enter__` / `__exit__` → 合成 context manager；
- `__aenter__` / `__aexit__` → async context manager；
- `__call__` → callable；
- `__iter__` → iterable；
- 其他 dunder → 默认不进入 API。

标签词表可通过 `contract.publicTags` / `contract.internalTags` 扩展。

### 7.4 明确延期：序列协议

以下能力不在 P2.1 实现：

```text
__len__
__getitem__
__setitem__
__contains__
__reversed__
切片 / 索引签名
ArkTS 的 length / index signature
```

原因：需要类型与形状语义，静态启发式容易误报。后续在 P3/P4 或独立 protocol 阶段处理。

### 7.5 UI

- 项目页模块卡片展示 Provider + Capability chips；
- 模块页类卡片展示构造签名与 providedApis；
- 模块页右栏按 apiProviders 分组；
- 类右栏只展示提供接口，内部方法仅显示数量；
- 方法/函数能力点击进入 Method Detail；
- 协议能力点击选中对应 Provider 类节点；
- 不新增类焦点页路由。

### 7.6 验收

- `contracts_demo` 覆盖 context manager、callable、iterable、序列协议延期、internal/private、config override 和 entrypoint；
- `Spinner` 产出 `with Spinner(message='加载中')`，不产出 `__init__` / `__enter__` / `__exit__`；
- `Database` 产出 context manager + `Database.actions(client_input)`；
- `MenuSystem` 产出 `MenuSystem.run()`；
- `pytest`: 40 passed, 1 skipped；
- 浏览器冒烟测试通过；
- `archmap check` 通过。

详细契约见 [`archmap-api-contract-model.md`](archmap-api-contract-model.md)。

## 8. P2.2：Provider Role 与模块组合（已完成）

### 8.1 目标

当前 P2.1 已经能表达“类/函数提供什么能力”，但还缺少“Provider 是什么角色”。这导致 config/model 的序列化方法被误当成模块 API。

P2.2 已增加：

- Provider Role：`config` / `model` / `manager` / `entry` / `adapter` / `component` / `contract` / `utility`；
- `roleSource` / `roleConfidence`；
- `module.composition`；
- 模块 API 按角色过滤；
- config/model 以类型卡片展示，不把 `as_dict()` 等序列化方法当模块 API；
- manager/entry/component/contract 才展示方法能力。

### 8.2 角色定义

| 角色 | 含义 | 典型例子 |
|---|---|---|
| `config` | 类型定义、字段、默认值、常量表、枚举 | `ProjectConfig`、`ModuleConfig`、默认标签表 |
| `model` | 运行期数据记录、DTO、分析结果 | `FunctionInfo`、`ClassInfo`、`AnalysisResult`、`CallSite` |
| `manager` | 管理 model/config 实例，组织行为，对外 API | `CallResolver`、`PythonFrontend`、`MenuSystem`、`Database` |
| `entry` | 主模块、CLI、用户入口 | `cli.py`、`main.py`、ArkTS `@Entry` |
| `adapter` | 外部系统适配 | TCP、数据库、文件、HTTP、解析器 |
| `component` | UI/协议组件 | `Spinner` context manager |
| `contract` | 抽象类、Protocol、接口 | `LanguageFrontend`、`Worker` |
| `utility` | 纯函数/助手 | `get_display_width`、`module_name_for` |

### 8.3 判定优先级

```text
config.providerRoles 显式覆盖
  > 注释 / 装饰器 / JSDoc 标注
  > 结构规则
  > 命名弱提示
```

结构规则建议：

- dataclass / NamedTuple / TypedDict / 大量字段 + 少量方法 → `model`；
- 只有类级常量、默认值、枚举、类型声明 → `config`；
- 有实例状态、公开方法、调用其他项目类、被 entry/其他模块调用 → `manager`；
- 配置的 entrypoint 或主模块 → `entry`；
- 主要封装外部 IO 库 → `adapter`；
- `Protocol` / ABC → `contract`；
- 纯函数、无状态 → `utility`。

`Manager` 后缀只能作为低权重提示，不能作为主规则。

### 8.4 数据模型

```json
{
  "providerRole": "manager",
  "roleSource": "structure",
  "roleConfidence": "medium",
  "moduleComposition": {
    "config": ["cls:..."],
    "model": ["cls:..."],
    "manager": ["cls:..."],
    "entry": ["fn:..."],
    "adapter": ["cls:..."],
    "component": ["cls:..."],
    "contract": ["cls:..."],
    "utility": ["fn:..."]
  }
}
```

### 8.5 API 展示规则

- `manager` / `entry` / `component` / `contract`：展示方法/协议能力；
- `config` / `model`：展示类型卡片、字段摘要、默认值，不展示 `as_dict()` 等序列化方法为模块 API；
- `adapter`：展示适配器入口能力；
- `utility`：展示函数签名；
- 模块页按角色分组 Provider；
- 项目页模块卡片显示 `CONFIG / MODEL / MANAGER / ENTRY` 数量与 manager API chips。

### 8.6 开发者 API 与用户交互面

必须区分两个概念：

```text
developer API   模块之间调用的代码契约
user surface    最终用户能感知或操作的交互面
```

同一能力可以同时是两者：

- `MenuSystem.run()`：menu 模块 manager 的开发者 API，同时是 TUI 键盘菜单交互面；
- `init_connection(port=12345)`：entry-network 的函数 API，同时是 CLI 输入提示交互面。

建议后续字段：

```json
{
  "audiences": ["developer", "end_user"],
  "surfaces": ["cli_input", "tui_menu", "keyboard_event", "network_endpoint"]
}
```

并增加独立的 `userSurfaces[]` 投影：

```json
{
  "kind": "cli_input",
  "display": "选择服务器/客户端并输入服务器 IP",
  "moduleId": "entry-network",
  "evidenceFunctionIds": ["fn:TcpConnect.init_connection"],
  "entrypointIds": ["fn:main.__main__"],
  "confidence": "medium"
}
```

主模块规则：

- 主模块默认不展示 developer API；
- 主模块展示 `entry` + `userSurfaces`；
- `MenuSystem.run()` 属于 menu 模块 manager API，同时作为用户交互面被项目入口引用；
- 客户端路径和服务器路径可以有不同的 surface 集合；
- 不同项目的用户交互面不同，必须数据驱动、支持配置覆盖。

自动识别（P4 实现）：

- `input()` / `print()` / `sys.stdout.write` → CLI/TUI surface；
- keyboard listener / event handler → keyboard surface；
- socket / HTTP server → network surface；
- ArkTS `@Entry` / `@Component` / `@Builder` / `TextInput` / `Button` → UI surface；
- 沿调用图从 entrypoint 传播 surface，带 confidence，不硬编码具体项目函数名。

### 8.7 ArchMap 自身的目标划分

```text
config/
  ProjectConfig, ModuleConfig, 默认值, 标签词表, role 枚举
model/
  FunctionInfo, ClassInfo, ModuleInfo, AnalysisResult,
  CallSite, ResolvedCall, ApiCapability, ClassUsage, ContractModel
managers/
  AnalysisManager, CallManager, DetailManager,
  ContractManager, GraphManager, ValidateManager, RenderManager
frontends/
  LanguageFrontend contract + Python/ArkTS adapters
entry/
  cli.py, pipeline.py
render/
  assets/
```

### 8.8 验收

- `FunctionInfo.as_dict()`、`ClassUsage.as_dict()`、`ContractModel.capabilities_by_*()` 不再作为模块 API；
- `ProjectConfig` / `ModuleConfig` 显示为 config 类型；
- `FunctionInfo` / `ClassInfo` / `AnalysisResult` 显示为 model 类型；
- `CallResolver` / `PythonFrontend` / `MenuSystem` / `Database` 显示为 manager；
- `LanguageFrontend` 显示为 contract；
- 模块组合信息正确；
- 通用 fixture 覆盖 config/model/manager/entry/adapter/component/contract/utility；
- `student_system` 作为集成验收；
- 自举构建中 config/model 序列化方法不再作为模块 API；
- schemaVersion 升级为 3.3，校验器覆盖角色、组合与 API 泄漏。

实现状态（2026-11-17）：

- 已新增 `archmap/frontends/python/roles.py`；
- 已实现 8 种角色、`roleSource` / `roleConfidence`、`contract.providerRoles` 显式覆盖；
- 已把角色挂到类节点、自由函数节点、`apiProviders`、API capability 与自由函数 FunctionDetail；
- 已实现 `moduleComposition` / `providerRoleCounts` 与 config/model `typeSummary`；
- 已在 UI 中增加角色计数、类型卡片和字段表；
- `roles_demo` 覆盖 8 种角色、装饰器覆盖、配置覆盖与 API 过滤；
- 默认测试 48 passed, 1 skipped；浏览器测试 1 passed。

### 8.9 风险

- config 与 model 边界可能模糊，需要显式配置兜底；
- dataclass 不一定都是 model，也可能是 config 或 DTO；
- manager 不能仅靠后缀判断；
- 不能把 `as_dict()` 一律当内部方法，某些项目可能确实把它作为公开序列化 API；
- 角色变化会影响模块 API 列表，需要语义指纹覆盖角色字段。

---

## 9. P2.3：架构规范落盘与 ArchMap 自身重构（已完成）

### 9.1 目标

让 ArchMap 自己成为 `config + model + manager + entry` 模型的示范项目，同时保持外部行为、CLI 和 bundle 契约不变。

### 9.2 目标目录

```text
archmap/
  config/
    project_config.py
    contract_config.py
    graph_config.py
  model/
    analysis_model.py
    call_model.py
    contract_model.py
    frontend_contract.py
    graph_model.py
  managers/
    pipeline_manager.py
    frontend_manager.py
    graph_manager.py
    validate_manager.py
    render_manager.py
  frontends/
    python/
      python_manager.py
      analysis_utility.py
      call_utility.py
      detail_utility.py
      contract_utility.py
      role_utility.py
      discovery_utility.py
  utility/
    graph_utility.py
    validate_utility.py
    render_utility.py
    config_utility.py
    cli_utility.py
    pipeline_utility.py
  entry/
    cli_entry.py
  render/
    assets/
```

### 9.3 迁移步骤

1. P2.2 角色投影已完成，不改文件结构；
2. 抽出 model 模块，保留旧 import shim；
3. 抽出 managers，逐个迁移并通过测试；
4. 把 `pipeline.py` 定位为 application manager，`cli.py` 定位为 entry；
5. 更新 `examples/archmap_v3.archmap.json`，让自举图显示 config/model/manager/entry；
6. 最后移除兼容 shim。

### 9.4 验收

- 所有测试通过；
- CLI、bundle schema、HTML 行为不变；
- 自举图中 config/model/manager/entry 划分清晰；
- `FunctionInfo.as_dict()` 等不再显示为模块 API；
- README 与交接文档同步。

### 9.5 风险

- 文件迁移会影响 import 路径和测试；
- 不应为了目录美观破坏零依赖和自包含 HTML；
- 先做角色投影可以降低重构风险。

### 9.6 实现记录（2026-11-17）

- 新增 [`archmap-architecture-spec.md`](archmap-architecture-spec.md)，冻结四类物理文件、八角色逻辑语义、依赖方向与可见性规则；迁移细节见 [`p2.3-migration-plan.md`](p2.3-migration-plan.md)；
- 将实现迁移为 `config/model/utility/managers/entry` 目录；
- 保留旧模块路径作为 import shim；
- 自举配置更新为 5 个逻辑模块并排除 shim；
- 新增 `providerVisibility`、`ownerProviderId`、`publicModuleComposition`、`publicProviderRoleCounts`；
- 每个领域收敛为 facade manager：PipelineManager、FrontendManager、PythonFrontend、GraphManager、ValidationManager、RenderManager；
- Python 前端阶段函数统一归为 `PythonFrontend` 的内部 utility；
- Graph/Validate/Render/Pipeline 阶段函数归为对应 facade manager 的 utility；
- utility 默认 internal，不进入默认项目页/模块页；事实层继续保留 FunctionDetail / CallSite；
- `analyze_project`、`collect_call_sites`、`build_bundle`、`validate_bundle`、`render_html` 等不再作为公开独立卡片；
- schemaVersion 升级为 3.6，包版本升级为 1.6.0；
- 校验器新增 public composition、visibility、ownerProviderId、utility API 泄漏检查；
- 全量测试和浏览器测试通过。

---

## 9.7 P2.4：主模块、功能模块与主流程（已完成）

### 目标

- 修正“所有模块都有输入输出”的旧语义。
- 每个项目恰好一个主模块，功能模块 0..N。
- 主模块页展示函数级主流程，功能模块只暴露能力。
- 支持动态分发的 dispatch 节点和显式候选契约。

### 数据契约

- `projectGraph.mainModuleId` / `primaryFlowId` / `mainFlows`。
- `moduleGraph.moduleKind = main | functional`。
- 节点：entry / orchestrator / provider / interface / dispatch。
- 边：call / call_path / composition。
- composition 必须 `confidence=low`、虚线；dispatch 节点记录 `candidateSetComplete` / `candidateSource` / `unresolvedReason`。
- 模块 I/O 字段、boundaryNodes、module_input/module_output 边全部移除。

### 候选发现

优先级：`mainFlow.dispatches` 配置 > 源码 `# archmap:dispatch` 注释 > argparse/静态注册表 > P3 多态 > unresolved。自动发现默认不宣称完整。

### 验收

```text
pytest:                 58 passed, 1 skipped
browser smoke:          1 passed
schemaVersion:          3.6
modules:                6
main flow:              23 nodes / 24 edges
dispatch:               args.func / 5 declared candidates / complete
```

详细文档见 [`p2.4-main-module-flow.md`](p2.4-main-module-flow.md)。

## 10. P3：继承、接口、多态与继承 API

> P3 不再做类层次页面或类内方法图；重点是类型契约、继承 API 和多态调用证据。

### 10.1 目标

在 P2.1 API 契约基础上增加“类型/契约”语义：

- `inherits`：类 → 基类；
- `implements`：类 → 接口/Protocol；
- 抽象方法契约；
- 多态调用 candidates；
- 继承来的公开 API 纳入类 `providedApis`；
- 类型关系与调用/依赖关系分视图展示。

### 10.2 设计来源

- CortexPlexus：`get_class_hierarchy` 方向性继承/实现遍历，`get_implementations`，避免兄弟节点污染；
- codeglass：`TypeHierarchyResult` 含 `bases`、`subclasses`、`is_abstract`；
- Emerge：inheritance graph 与 dependency graph 分开；
- Sourcetrail / Understand：UML/类型层级视图与调用图分开；
- Python 语义：`abc.ABC`、`ABCMeta`、`typing.Protocol`、`@abstractmethod`。

### 10.3 数据模型

Class 节点增加或完善：

```json
{
  "bases": ["ABC"],
  "baseClassIds": [],
  "subclassIds": [],
  "implementsIds": [],
  "abstractMethodIds": []
}
```

结构边：

```json
{
  "from": "cls:...",
  "to": "cls:...",
  "kind": "inherits",
  "confidence": "high",
  "evidence": {"file": "...", "line": 12}
}
```

多态调用：

```json
{
  "resolved": false,
  "polymorphic": true,
  "candidates": ["fn:repo.StudentRepository.load", "fn:repo.TeacherRepository.load"],
  "confidence": "medium"
}
```

### 10.4 实施任务

1. 以 P2.2 的 Provider Role 为前提：区分 config/model 类型契约与 manager/contract 行为契约。
2. 解析类引用和导入，把 `bases` 字符串解析为 `baseClassIds`。
3. 增加全局类索引和 base/subclass 双向关系。
4. 增加 `inherits` / `implements` 结构边。
5. 把继承/实现的公开能力合入 Provider API，并标记 `declaredOn` / `inheritedFrom` / `implementedFrom`。
6. manager/contract 的继承 API 进入模块 API；config/model 的继承关系只作为类型关系展示。
7. 类右栏展示继承 API 与类型关系区块（不新增类焦点页）。
8. 多态调用解析：
   - `self.abstract_method()`；
   - `cls.method()`；
   - 已知类型注解的变量；
   - 没有唯一实现时返回 candidates。
9. 抽象方法不生成执行流；具体模板方法仍可生成 FunctionDetail。
10. 继承来的方法调用解析（当前 `EchoWorker.run -> self.label()` 仍是 unresolved）。

### 10.5 验收标准

- `class_demo` 中 `EchoWorker` 继承 `Worker`，产生 `inherits` 边；
- `Worker` 抽象方法列表正确；
- 抽象类不接模块边界；
- 调用抽象方法时产生 candidates，而不是伪造唯一目标；
- 类型关系视图不出现兄弟节点污染；
- 不影响 ModuleGraph 和 Method Detail。

### 10.6 风险

- Python 动态类型导致多态解析天然不确定；
- 继承/接口关系不能硬塞进现有 `call/data/control` 三种边；
- 导入路径解析仍是限制，当前 `from service import ...` 和 `app.service` 的差异会造成 unresolved。

---

## 11. P4：角色感知关系、API/类型/交互面影响分析与架构查询

> P4 以 Provider / Capability 为中心，不做全量类关系图。

### 11.1 目标

从“方法清单”升级为“角色化的可查询架构知识图”：

- 角色感知的 `composes` / `aggregates` / `uses` / `instantiates`；
- manager → model/config 的资源关系；
- entry → manager 的调用与用户入口路径；
- API / type / provider / surface 级 impact analysis；
- 调用路径 trace；
- 用户交互面（user surface）投影与传播；
- 按 config/model/manager/entry 分组的 DSM；
- 项目级依赖视图切换。

### 11.2 设计来源

- CodeScope 资料中提到的 `COMPOSES` / `AGGREGATES` / `INHERITS` 方向值得借鉴；但公开 PyPI `codescope` 实际主要是 Adonis/Scope 调用图，本次未确认其完整关系 API，因此应把组合/聚合视为我们自己的 UML 扩展，而不是已验证实现事实。
- UML 类图：组合、聚合、继承、依赖。
- Structure101 / Lattix：DSM/依赖矩阵，避免“边界到所有节点”的启发式污染。
- cgviz：impact analysis、trace path、view modes。
- CortexPlexus：`get_dependencies`、`get_impact_analysis`、DI/实体关系。
- Emerge：dependency graph、inheritance graph、complete graph 分视图。

### 11.3 数据模型

结构关系：

```json
{
  "kind": "composes",
  "from": "cls:OrderService",
  "to": "cls:OrderRepository",
  "confidence": "medium",
  "evidence": {"file": "services.py", "line": 42}
}
```

候选提取依据：

- manager 的 `__init__` 中 `self.repo = Repo(...)` → `composes`；
- 类型注解 `repo: Repo` + 非 Optional → `composes`；
- `repo: Repo | None` / `Optional[Repo]` → `aggregates`；
- 参数/局部变量类型 → `uses`；
- `Repo()` → `instantiates`。

角色感知示例：

```text
entry    -> manager    calls / entrypoint_path
manager  -> model      composes / aggregates
manager  -> config     uses
manager  -> adapter    uses / depends
manager  -> manager    calls / collaboration
model    -> config     uses
entry    -> surface    produces user interaction
```

用户交互面单独投影：

```json
{
  "kind": "cli_input",
  "display": "选择服务器/客户端并输入服务器 IP",
  "moduleId": "entry-network",
  "evidenceFunctionIds": ["fn:TcpConnect.init_connection"],
  "entrypointIds": ["fn:main.__main__"],
  "confidence": "medium"
}
```

自动识别线索：

- `input()` / `print()` / `sys.stdout.write` → CLI/TUI；
- keyboard listener / event handler → keyboard event；
- socket / HTTP server → network；
- ArkTS `@Entry` / `@Component` / `@Builder` / `TextInput` / `Button` → UI；
- 沿 entrypoint 调用路径传播，带 confidence，支持配置覆盖。

### 11.4 查询能力

建议提供按需查询而不是全量展开：

- `provider_dependencies(providerId)`；
- `api_impact(capabilityId, depth)`；
- `type_impact(configId/modelId, depth)`；
- `provider_impact(providerId, depth)`；
- `surface_impact(surfaceId, depth)`；
- `trace_calls(fromId, toId, depth)`；
- `type_hierarchy(classId, direction)`；
- `implementations(interfaceId)`。

这些可以只作为 bundle 数据和 CLI/前端视图，不需要引入图数据库。

### 11.5 可视化方向

- 类右栏类型关系区块：继承/实现/组合/聚合；
- 模块页视图切换：调用关系 / 类型关系 / 全部关系；
- 主模块右栏展示 user surfaces；
- 项目级 DSM 按 config/model/manager/entry/adapter 分组；
- 边点击显示证据列表；
- impact 视图高亮反向依赖闭包；
- 不展示全量类关系图。

### 11.6 验收标准

- `OrderService -> OrderRepository` 类型注解产生 `composes` 或 `aggregates`；
- 可选类型产生 `aggregates`；
- 构造调用产生 `instantiates`；
- manager → model/config 关系与 entry → manager 关系可区分；
- `api_impact` / `type_impact` / `surface_impact` 返回反向依赖闭包与深度；
- 结构关系与调用关系可分开筛选；
- 用户交互面按 entrypoint 路径产生，并带 confidence；
- 不伪造无源码证据的边。

### 11.7 风险

- 动态类型和运行时装配合降低静态关系可信度；
- 组合/聚合与普通依赖边界模糊，需要置信度和证据；
- 数据/边规模增长会放大 HTML 体积；
- 不能为了追求“全图”破坏已确立的按需下钻体验。

---

## 12. 设计来源与置信度

| 来源 | 可借鉴内容 | 置信度/备注 |
|---|---|---|
| Sourcetrail | 类节点可展开成员、聚焦邻域、边 bundle、源码浏览 | 高；已归档，但文档和源码可查 |
| CodeViz AI | 类节点 + 方法 membership、ELK 层级布局、collapse | 高；实际检查过 parser/layout |
| cgviz | 统一 node/edge kind、focus、view modes、impact/trace | 高；实际检查过 README 和 DB 模型 |
| codeglass (PyPI) | `Symbol.parent`、`TypeHierarchyResult`、`is_abstract` | 高；实际下载检查过包源码 |
| CortexPlexus | `get_class_hierarchy`、`get_implementations`、impact | 中高；README 明确列出工具 |
| Emerge | dependency / inheritance / complete graph 分离 | 高；README 明确列出 |
| Understand | 多图分离、Butterfly、CFG/类图/UML | 中；商业工具，未做源码验证 |
| Structure101 / Lattix | DSM 思想、显式依赖矩阵 | 中；商业工具，方向性参考 |
| CodeScope `COMPOSES/AGGREGATES/INHERITS` | 组合/聚合/继承分类 | 低；公开 PyPI `codescope` 未确认该完整 API |

原则：**不要因为某个名称听起来合理就直接实现；先验证它是否真实、是否适合当前架构。**

---

## 13. 当前已知问题

1. 静态调用解析仍不完整：
   - 动态 `getattr`；
   - `**kwargs` 分发；
   - 运行时注册表；
   - 继承来的方法调用；
   - 跨包导入路径差异。
2. 抽象/接口检测是基础 AST 规则，不是完整 Python 类型系统。
3. `ClassInfo.bases` 仍是原始字符串，没有解析为类 ID。
4. 方法详情源码目前纯文本展示，没有完整语法高亮。
5. 单函数源码有 24000 字符上限，超长会 truncated。
6. 方法详情页没有“调用路径搜索”，目前只有 callers/callees 列表。
7. 类焦点页和类内方法图已明确不在产品计划中；类卡片只展示构造签名与提供接口。
8. 旧 schema 3.0/3.1 bundle 不再通过 `archmap check`。
9. 旧 FunctionFlow 注解的 `sourceHash` 会过期，需要重新生成。
10. 旧函数级布局覆盖 `override.functions` 不再生效。
11. `config.py` 中部分旧 `maxSteps` / `maxDataDeps` 配置已失去主要用途，后续可清理。
12. 浏览器测试默认跳过，只有当 `ARCHMAP_RUN_BROWSER=1` 时执行。
13. P2.0 已清理自举配置中的 `flow-build` / `layout-routing` 空模块，并把 `callsites.py` / `details.py` 归入 Python 前端模块。
14. 旧 `docs/archmap-2.0-design.md`、`docs/HANDOFF.md`、`docs/v1-acceptance-report.md` 已加归档说明；维护时不要把其中的 FunctionFlow 设计重新写回当前契约。
15. 模块层次/子模块（`parentId`）尚未建模，当前模块配置仍是扁平的。
16. P2.1 明确延期序列协议：`__len__` / `__getitem__` / `__contains__` / 切片 / ArkTS index signature；后续不得遗忘。
17. 用户交互面（user surface）尚未建模；主模块默认仍按普通模块展示 developer API。
19. Provider Role 自动判定仍是启发式，模糊类型应使用 `contract.providerRoles` 显式覆盖。
20. 角色化、可见性、owner 归属和物理文件规范已影响模块 API、指纹和 UI；后续 P3/P4 必须保持 bundle schema 3.6 与默认视图行为稳定。

---

## 14. 常用命令

```bash
# 全量测试
python3 -m pytest -q

# 浏览器测试
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py

# 构建（自举配置已清理为 4 个有效源码模块）
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self

# 校验
python3 -m archmap check .archmap/self/architecture.json

# 查看单个方法
python3 -m archmap method . --file archmap/graph.py --function build_bundle

# 本地预览
python3 -m archmap serve .archmap/self
```

---

## 15. 新会话建议开工顺序

1. 先跑全量测试和浏览器测试，确认当前基线。
2. P2.3 已完成，下一步进入 P3：继承/实现边、继承 API、多态 candidates。
3. P3 在角色与可见性之上做类型契约、manager 接口和继承 API，不做类焦点页。
4. P4 先做角色感知关系提取和 API/type/provider impact，再做 user surface 传播与可选 DSM。
5. 序列协议继续延期；若要实现，先更新契约文档和通用 fixture。
6. 规范模式的源码识别与发现规则在 P3 前或 P3 中按 `archmap-architecture-spec.md` 落地，兼容模式保留。

不要跳过 P3/P4 的既有前置约束。
不要同时开始 P3、P4。
不要重新引入 FunctionFlow。
不要新增类焦点页或类内方法图。
