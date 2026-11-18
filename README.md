# ArchMap v4.0

> 版本：ArchMap 1.9.0 / bundle schema 5.0<br>
> 最后更新：2026-11-18

把 Python 项目转换为**模块优先、可逐层下钻、源码可读**的架构图：

```text
项目页（主流程入口 + 模块能力卡片）
  ├─ 主流程页（入口函数控制骨架；本地调用/功能接口原子化）
  └─ 模块能力页（提供接口 + 类节点 + 模块级自由函数）
       └─ 方法详情页（源码 + 人类备注 + LLM 语义 + callers/callees）
```

ArchMap 负责“结构和关系”，源码负责“实现细节”，LLM 负责“高层语义”。
默认产物是独立 CLI + 自包含单文件 HTML，不注册插件、不依赖 CDN、不需要第三方运行时依赖。

## 当前状态

```text
P0    类语义数据模型                          已完成
P1    模块页类组件化与模块边界修复            已完成
P1.5  FunctionDetail + Source View + CallGraph 已完成
P2.0  项目页/模块页能力契约重构              已完成
P2.1  API 契约建模与展示                     已完成
P2.2  Provider Role 与模块组合                已完成
P2.3  架构规范、自身代码迁移、旧 shim 清理    已完成
P2.4  主模块/功能模块/主流程 DAG              已完成
P3    继承、接口、多态与继承 API              已完成
P4    结构关系、User Surface、Impact/Trace/DSM 已完成
P5    主流程执行流（首版）                 已完成
P5.1  执行流直接 fan-in 与项目节点卡片样式  已完成
P5.2  主流程执行入口归一化                  已完成
P5.3  终止节点与本地调用语义统一            已完成
P5.4  bundle schema 4.1 与执行卡注释回归     已完成
P5.5  主流程页与模块能力页分离               已完成
P6.0  项目模型重构计划与配置指南             已完成
P6.1  共享动态分发解析                       已完成
P6.2  schema 5.0、取消主模块与 mainFlows     已完成
```

当前产品边界：

- 所有模块都是普通能力模块；schema 5.0 不再有主模块或 `moduleKind`。
- 主流程是项目级视图，不属于任何模块。
- 主流程只展开入口函数控制骨架；调用目标作为原子执行步骤，不穿透实现。
- 模块能力页只展示 Provider/Capability 与结构关系，不默认展示调用边。
- 项目页提供标准主流程入口；主流程页只展示有界执行流。
- `mainFlows` / `primaryFlowId` 已从 schema 5.0 删除。
- execution flow 不再生成语义 `entry` 节点；入口由 flow 元数据和入口卡片表达。
- P5 执行流不会恢复旧语句级 FunctionFlow；边界见 [`docs/p5-main-execution-flow.md`](docs/p5-main-execution-flow.md)。
- 类焦点页和类内方法图不在当前产品计划中。
- 旧语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
- 旧 Python import 兼容 shim 已删除；源码只使用 canonical 目录。

## 快速开始

```bash
# 在当前环境中直接运行
python -m archmap build .

# 分析 student_system 样例
python3 -m archmap build Projects/student_system \
  --config examples/student_system.archmap.json \
  --out yield/student_system

# 分析 ArchMap 自身
python3 -m archmap build . \
  --config examples/archmap_v3.archmap.json \
  --out .archmap/self

# 校验产物
python -m archmap check yield/student_system/architecture.json

# 查看单个函数/方法详情
python -m archmap method Projects/student_system \
  --file student_system/managers/menu_manager.py \
  --function run

# 本地预览
python -m archmap serve yield/student_system
```

产物：

```text
yield/student_system/
├── architecture.json       # projectGraph + moduleGraphs + functionDetails + callSites
├── architecture.html       # 自包含交互页面
├── llm-annotations.json    # 可选输入
└── layout-overrides.json   # 前端可导出
```

## 页面视图

- **项目页**：展示独立主流程入口卡片与全部模块能力卡片；模块卡片包含职责、模块角色、Provider Role 数量、Provider/Capability、类/Provider/API 数量；默认不绘制模块依赖线，依赖证据仍保留在 bundle 中，可通过“关系”按钮查看。双击模块卡片进入能力页，主流程入口进入 `#/flow`。
- **主流程页**：只展示 P5 横向有界执行流；支持多 flow 选择、拖拽布局、节点详情和源码下钻。不再显示调用总览或模块能力契约。
- **模块能力页**：所有能力模块统一展示提供接口、Provider Role、类/自由函数与类型关系；不默认展示调用连线；config/model Provider 以类型卡片展示字段摘要。
- **类节点详情**：展示类类型、抽象/接口标记、构造签名和提供接口；P3 还展示继承/实现、MRO、继承 API 和 override 来源；P4 展示 `instantiates/uses/aggregates/composes` 结构关系。内部方法只显示数量，不展开类内方法图。
- **方法详情页**：左侧/右侧展示人类备注、LLM 语义、签名、返回/异常、源码切片、callers/callees、override / overridden-by、多态调用邻域和 User Surface 标签；点击调用者可继续下钻；页面背景跟随系统浅色/深色模式。
- 所有页面使用 Hash 路由和平级切换，不使用弹窗：`#/project`、`#/flow[/<id>]`、`#/module/<moduleId>`、`#/module/<moduleId>/function/<functionId>`。
- 项目页、模块页和执行流节点支持无固定边界拖拽；布局默认坐标由 Python 生成，浏览器只保存用户覆盖；可用“适应画布”或“重置布局”找回节点。
- P5 执行流只展开 entrypoint 的控制骨架；项目内 callable 和 canonical interface 均为原子节点，双击进入源码。
- 不生成或渲染函数内部完整 CFG、逐语句执行流图；函数实现以源码为最终事实来源。

## P5 主流程执行流（首版已实现）

P5 把主模块默认流程从“函数级调用/模块组合 DAG”升级为**有界执行流图**：

- 只展示 selected entrypoint 函数内部的控制骨架；
- 主模块本地调用（自由函数与类方法统一为同一原子语义）、功能模块公开接口都作为原子执行步骤，不展开；双击进入 Method Detail / 源码页面；
- 使用封闭节点集合：`exit` / `free_function` / `interface` / `branch` / `multi_branch` / `loop` / `break` / `continue` / `return` / `dispatch`；P6.2 起不再生成语义 `entry` 节点，`free_function` 通过 `callableKind` 区分函数与方法；
- `return` 是终止节点，不生成出边；`exit` 只用于隐式落空等真正到达结束锚点的路径；
- `break` / `continue` 是循环内部终止标记，不生成出边；循环节点通过 `loop_complete` 作为唯一结构化离开边界；
- bundle schema 5.0 的执行边只允许 `next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`；
- 汇合不再生成 `merge` 节点，多条路径直接 fan-in 到同一个真实后继节点或 `exit`；
- 执行流实线只表示静态确定的直接控制/执行关系；虚线只表示推断、不完整或间接关系；
- 执行流卡片不渲染函数签名，正文展示人类备注；完整签名在 Method Detail / 节点详情中查看；
- 横向主脊布局，分支上下展开，循环节点通过 `循环体` 端口连接循环体，不再绘制回边 lane；
- 节点使用项目执行流卡片：彩色标题栏、深色主体、内嵌端口行、贝塞尔曲线；端口行无方框和独立背景，卡片外不再挂边标签胶囊；
- 节点位置可在浏览器中拖拽覆盖，关联曲线实时重算并持久化；
- 不生成逐语句节点、列表操作节点、`try/except` 异常控制、数据流边或图内下钻；
- 项目级执行视图只保留 `projectGraph.executionFlows` 和 `primaryExecutionFlowId`；`mainFlows` 已在 schema 5.0 删除；
- 动态分发统一由共享 resolver 处理；新配置使用顶层 `dispatchHints`，旧 `mainFlow.dispatches` 仅作迁移兼容；
- P5 使用 schema 4.0/4.1；P6.2 升级为 schema 5.0。

P5 的防误解与防滑坡边界、student_system 目标快照、数据契约和验收标准见 [`docs/p5-main-execution-flow.md`](docs/p5-main-execution-flow.md)。

## 配置

```json
{
  "projectName": "my-project",
  "language": "python",
  "include": ["src/**/*.py"],
  "exclude": ["**/__pycache__/**"],
  "mainModule": "orders",
  "entrypoints": ["app.main:main"],
  "executionEntrypoints": ["app.main:App.run"],
  "modules": [
    {
      "id": "orders",
      "name": "订单与结算",
      "kind": "main",
      "include": ["src/orders/**"],
      "note": "订单主流程组合根",
      "color": "#f59e0b",
      "role": "main"
    },
    {
      "id": "payments",
      "name": "支付能力",
      "kind": "functional",
      "include": ["src/payments/**"],
      "note": "支付 Provider 与公开接口",
      "color": "#60a5fa",
      "role": "service"
    }
  ]
}
```

模块识别优先级：显式配置 → 包/命名空间 → 单模块兜底。文件仅作为源码证据，不直接作为页面模块。

`entrypoints` 是项目分析根，用于入口角色、User Surface 传播、调用关系和主流程事实。`executionEntrypoints` 可选，只用于选择 P5 主执行流的叙事起点；省略时回退到 `entrypoints`。它支持类方法（例如 `gomoku.cli:GameCli.run`），适合配置入口只是薄启动包装、真正用户旅程从类方法开始的项目。执行流节点仍只展开该有效入口自身的控制骨架，不递归展开 callee。

主模块解析顺序：

1. 显式配置 `mainModule`；
2. 拥有主 entrypoint 的模块；
3. 兼容字段 `role=main`；
4. 第一个模块作为 fallback，并产生诊断。

## 模块能力契约

模块配置支持可选的 `role`：

```json
{
  "id": "database",
  "name": "数据访问",
  "role": "service"
}
```

当前模块角色：`main` / `service` / `adapter` / `test` / `other`。显式配置优先；未配置时，包含入口函数的模块视为 `main`，其余为 `service`。

每个 `moduleGraph` 会从已有事实派生 `providedApis` 和按 Provider 分组的 `apiProviders`：

- 公开类方法（含抽象契约方法）；
- 公开模块级自由函数；
- `context_manager` / `async_context_manager` / `callable` / `iterable` 协议能力；
- P3 继承/实现能力会以 inherited capability 进入子类 `providedApis`；
- 构造函数、dunder 和下划线内部方法不进入普通方法 API；
- `__init__` 只作为构造签名，`__enter__` / `__exit__` 合成上下文管理器能力。

暴露级别由 `apiExposure` 表达，来源包括 `docstring` / `comment` / `decorator` / `config` / `entrypoint` / `protocol` / `naming`。支持在 `contract` 配置中扩展标签词表和显式覆盖。

详细契约模型见 [docs/archmap-api-contract-model.md](docs/archmap-api-contract-model.md)。

**延期项**：`__len__`、`__getitem__`、`__contains__`、切片、ArkTS index signature 等序列协议不在当前实现范围，避免启发式误报。

## Provider Role 与模块组合

P2.2 在 Capability 之上增加 Provider 级职责：

```text
config    类型定义、字段、默认值、常量表、枚举
model     运行期数据模型 / DTO / 分析结果
manager   管理 model/config 实例，组织行为，对外 API
entry     主模块 / CLI / 用户入口
adapter   外部系统适配
component UI / 协议组件
contract  抽象类 / Protocol / 接口
utility   纯函数 / 助手
```

角色判定优先级：

```text
contract.providerRoles 显式覆盖
  > 注释 / 装饰器 / JSDoc 标注
  > 结构规则
  > 命名弱提示
```

每个 Provider 节点、`apiProviders` 条目和 API capability 都携带：

```json
{
  "providerRole": "manager",
  "roleSource": "structure",
  "roleConfidence": "high",
  "providerVisibility": "public",
  "ownerProviderId": null
}
```

模块图额外输出：

```json
{
  "moduleComposition": {
    "config": ["cls:app.config.AppConfig"],
    "model": ["cls:app.model.Order"],
    "manager": ["cls:app.manager.OrderManager"],
    "entry": ["fn:app.main.main"],
    "adapter": [],
    "component": [],
    "contract": [],
    "utility": ["fn:app.util.helper"]
  },
  "providerRoleCounts": {
    "config": 1,
    "model": 1,
    "manager": 1,
    "entry": 1,
    "adapter": 0,
    "component": 0,
    "contract": 0,
    "utility": 1
  }
}
```

展示规则：

- `manager` / `entry` / `component` / `contract`：展示方法/协议能力；
- `config` / `model`：展示类型卡片、字段摘要和默认值，不把 `as_dict()` 等序列化方法当作模块 API；
- `adapter`：展示适配器入口能力；
- `utility`：展示函数签名，但默认 internal，不进入项目页/模块页默认视图。

显式角色覆盖示例：

```json
{
  "contract": {
    "providerRoles": {
      "app.model.Order": "model",
      "app.config.AppConfig": "config"
    }
  }
}
```

## 继承、实现与多态（P3）

P3 把类名基类字符串解析为项目内 canonical 类型关系：

- `inherits`：具体类基类；
- `implements`：抽象类 / Protocol / interface 目标；
- `baseClassIds` / `subclassIds` / `mroClassIds` / `abstractMethodNames` 进入类节点；
- 子类 `providedApis` 可以包含 inherited capability，并以 `declaredInProviderId`、`inheritedFromProviderId` 保留来源；
- 子类覆盖方法以 `overridesCapabilityId` 记录 override；
- 抽象/Protocol 方法调用生成 `polymorphic=true` 的 CallSite candidates，不伪造唯一 `toFunctionId`；
- 多态候选进入主流程时使用 `candidateSource=polymorphic` 的 dispatch 节点和低置信度 composition 虚线；
- `projectGraph.typeRelations` 与 `moduleGraphs[].typeRelations` 提供结构关系数据，类详情展示 hierarchy 与 inherited API。

P3 不新增类焦点页，不把类放进主流程，也不让主流程穿透功能模块内部实现。

## 结构关系、User Surface、Impact/Trace 与 DSM（P4）

P4 在 P3 canonical 类型关系之上继续增加：

- `instantiates`：构造调用证据；
- `uses`：参数、返回值和字段类型注解证据；
- `aggregates`：构造注入或字段持有关系；
- `composes`：构造函数内实例化并赋给实例字段的所有权关系；
- 每条结构关系携带 `source`、Provider Role、可见性和 `evidenceFunctionIds`；
- `userSurfaces` 从 entrypoint 调用路径与 IO/事件 primitive 识别，并支持配置覆盖；
- `impact` 对两个 bundle 做反向影响传播；
- `trace` 支持出向/入向、静态调用和多态候选；
- `dsm` 输出 module/provider 级依赖结构矩阵。

User Surface 识别线索包括 `input()` / `print()` / 文件 IO / socket / HTTP / keyboard event / 配置显式覆盖。它是静态启发式投影，不等同于完整运行时 UX 分析。

Impact/Trace/DSM 是按需查询结果，不写入默认 `architecture.json`；bundle 只保存静态事实与 User Surface 投影。

## 代码架构规范

P2.3 起，ArchMap 自身源码遵循“物理代码单元 + 逻辑 Provider Role”两层规范。

物理代码单元：

```text
<domain>/<domain>_config.py     静态定义、默认值、常量、枚举
<domain>/<domain>_model.py      数据结构、DTO、结果、契约接口
<domain>/<domain>_manager.py    状态、生命周期、行为编排、入口代理
<domain>/<domain>_utility.py    无状态内部辅助逻辑
```

逻辑角色仍然是：

```text
config / model / manager / entry / adapter / component / contract / utility
```

关键规则：

- `contract` 默认物理归入 model 文件，逻辑角色保持独立；
- `entry`、`adapter`、`component` 默认物理归入 manager 文件，逻辑角色由入口/外部 IO/协议生命周期派生；
- `utility` 是无状态内部实现，默认 `providerVisibility = "internal"`，不进入项目页/模块页；
- utility 仍保留在 `functionDetails`、`callSites` 和 impact/trace 事实层中；
- 项目页角色计数只使用 `publicProviderRoleCounts`；
- 每个领域只暴露少量 facade manager；Python 前端的 `analyze_project`、`collect_call_sites` 等阶段函数是 `PythonFrontend` 的内部 utility；
- 内部 utility 通过 `ownerProviderId` 归属到 facade manager，不生成独立卡片；
- 依赖方向为 `config ← model ← manager`、`utility ← manager`、`entry → manager`。

当前目录：

```text
archmap/
├── config/        project_config.py / contract_config.py / graph_config.py ...
├── model/         analysis_model.py / call_model.py / contract_model.py ...
├── utility/       graph_utility.py / validate_utility.py / render_utility.py ...
├── managers/      pipeline_manager.py / frontend_manager.py / graph_manager.py ...
├── entry/         cli_entry.py
├── frontends/     python/python_manager.py + internal utility stages
└── render/assets/
```

旧模块路径的 import shim 已在 P2.3 最终清理中删除。外部脚本需要使用 canonical 路径：

```text
archmap.managers.*
archmap.frontends.*
archmap.model.*
archmap.utility.*
archmap.entry.*
```

详细规范见 [docs/archmap-architecture-spec.md](docs/archmap-architecture-spec.md)。

## 人工备注与 LLM 注解

- Python 函数备注优先取 docstring 第一段，其次取函数体首部紧邻注释块。
- 备注和源码参与 `sourceHash`；LLM 文本不写回源码，放在独立侧车文件：

```json
{
  "version": 1,
  "nodes": {
    "fn:app.main.main": {
      "summary": "程序主入口",
      "details": "加载数据并编排后续步骤。",
      "sourceHash": "sha256:..."
    }
  }
}
```

构建时自动读取输出目录或项目 `.archmap/llm-annotations.json`，也可使用 `--annotations`。`sourceHash` 不匹配时页面会标记注解已过期。

## 调用关系与宏观边

函数/方法级调用统一由独立 CallSite 提取，不再依赖语句级执行流：

- `callSites`：每次调用的文件、行、列、调用文本、`usageKind`、解析状态、外部/未解析标记和多态 candidate 信息。
- `functionDetails[].callers` / `callees`：函数级入/出调用邻域。
- `moduleGraphs[].methodEdges`：类内和模块内的方法级调用关系。
- `moduleGraphs[].edges`：类/函数组件级聚合边。
- `projectGraph.edges`：模块级聚合边。
- `projectGraph.typeRelations`：继承/实现/组合/聚合/使用/实例化关系。
- `projectGraph.userSurfaces`：用户交互面投影。

宏观边包含：

- `primaryType`：`call` / `data` / `control`。
- `relations`：同一对节点可同时具有调用和数据证据。
- `role`：普通内部关系；不再生成模块输入输出边界边。
- P6.2 已删除 `mainFlows` 调用投影及其 composition 边；动态分发候选只保留在 execution flow 节点详情中。
- P5 主执行流只展开 entrypoint 自身控制骨架；调用目标作为原子节点，不穿透其内部 utility。
- `evidence`：具体函数、文件和行号。
- `confidence`：解析置信度。

没有静态证据的关系不会生成边。

## CLI

```bash
python -m archmap build <project> [--out DIR] [--config FILE] [--split] [--json] [--annotations FILE]
python -m archmap check <architecture.json>
python -m archmap method <project> [--file FILE] [--function NAME] [--json]
python -m archmap serve <directory> [--port 8765]
python -m archmap diff <before.json> <after.json>

# P4 查询
python -m archmap impact <before.json> <after.json> [--json]
python -m archmap trace <architecture.json> --from <function-id> [--direction inbound]
python -m archmap surfaces <architecture.json> [--module ID] [--json]
python -m archmap dsm <architecture.json> [--level module|provider] [--json]
```

## 测试

```bash
# 全量测试（浏览器测试默认跳过）
python -m pytest -q

# 浏览器冒烟测试
ARCHMAP_RUN_BROWSER=1 python -m pytest -q tests/test_browser_smoke.py
```

当前基线：

```text
pytest:         101 passed, 1 skipped
browser smoke:  1 passed（显式开启）
```

测试覆盖：

- 三层 bundle 契约和交叉引用。
- 唯一主模块、0..N 功能模块与无 I/O 端口不变量。
- P5 有界执行流：entrypoint 控制骨架、原子本地调用/接口、分支/多分支/循环/break/continue/return、终止 return 与按需 exit。
- `mainFlows` 调用 DAG、分支、dispatch 候选和 composition 虚线数据语义。
- 继承/实现结构边、C3 MRO、有效抽象性、继承 API、override 和多态 candidates。
- 类型关系 validator 不变量与 polymorphic dispatch 低置信度 composition。
- `instantiates/uses/aggregates/composes` 结构关系与角色元数据。
- User Surface 识别、entrypoint 传播和配置覆盖。
- Impact / Trace / DSM 查询、CLI JSON 输出与截断边界。
- 类节点、方法归属、抽象类边界。
- FunctionDetail、源码切片、sourceHash。
- CallSite 提取、callers/callees、模块级聚合边。
- API exposure、协议能力合成、Provider 分组和契约校验。
- Provider Role 判定、模块组合、config/model 类型卡片与 API 过滤。
- 宏布局几何、执行流正交布局、指纹稳定性和布局无关性。
- 自包含 HTML、方法详情页和 LLM 注解嵌入。
- CLI build/check/method 闭环。

浏览器交互已使用 Firefox Headless + geckodriver 验证：项目页主流程入口、独立主流程页、模块能力页、方法详情页、类方法详情、Hash 刷新恢复、P3 继承 API、P4 surface/结构关系和无运行时错误。

### 当前验收数据

ArchMap 自举：

```text
modules:              6
classes:              31
functions:            272
methods:              71
callSites:            3850
resolvedCalls:        653
typeRelations:        57
structuralRelations:  57
userSurfaces:         0
executionFlows:       1
executionNodes:       4
executionEdges:       3
diagnostics:          0
self build/check:     OK
```

student_system：

```text
modules:              7
classes:              7
functions:            52
methods:              40
callSites:            265
resolvedCalls:        50
typeRelations:        4
structuralRelations:  4
userSurfaces:         14
executionFlows:       1
executionNodes:       9
executionEdges:       10
diagnostics:          0
build/check:          OK
```

P3/P4 fixtures：

```text
inheritance_demo:     4 typeRelations / 2 polymorphicCalls / diagnostics 0
p4_demo:              9 structuralRelations / 2 userSurfaces / diagnostics 0
```

## ArkTS 扩展

`archmap/frontends/` 提供语言适配层：

- `archmap/model/frontend_contract.py` 定义 `LanguageFrontend` 契约。
- `LanguageFrontend` 负责发现、解析、符号解析、CallSite 提取、FunctionDetail 和 API 契约能力构建。
- `archmap/utility/graph_utility.py`、`archmap/utility/validate_utility.py`、`archmap/utility/render_utility.py` 及对应 Manager 与语言无关。
- 语言实例由 `FrontendManager` 显式注册，不是插件系统。
- ArkTS 阶段新增 `frontends/arkts`，可使用可选解析器依赖；当前 Python 后端仍保持标准库零依赖。

ArkTS 接入时需要：

- 将文件、类、函数、调用和注释转换为与 Python 相同的 canonical IR；
- 实现 `build_contracts`：`export`、`public` / `private` / `protected`、JSDoc `@public` / `@internal`、getter/setter、`Symbol.iterator` 等映射为 canonical capability；
- 实现 Provider Role 映射：`interface` / `type` / `enum` / const object → config；data class → model；有公开方法的 class → manager；`@Entry` / `@Component` → entry/component；
- 把 `@Entry` / `@Component` / `@Builder` / `TextInput` / `Button` / router / network API 映射为 User Surface；
- `@Entry` / `@Component` 作为 entrypoint，不默认当作公开 API；
- ArkTS 没有 Python 的 `__enter__` / `__exit__`，不伪造 context manager；
- 序列协议（length / index signature）与 Python 一起延期；
- 不要求修改布局、校验、渲染或路由核心。

## 文档导航

### 当前权威文档

| 文档 | 内容 |
|---|---|
| [`README.md`](README.md) | 产品定位、快速开始、配置、CLI、验收数据和已知边界 |
| [`docs/archmap-v3-design.md`](docs/archmap-v3-design.md) | v3.8 数据契约：三层投影、P3 类型关系、P4 结构关系/Surface/Impact/Trace、CallSite、布局和语言前端边界 |
| [`docs/archmap-architecture-spec.md`](docs/archmap-architecture-spec.md) | 物理代码单元、八角色语义、依赖方向、主模块/主流程边界与可见性规范 |
| [`docs/archmap-api-contract-model.md`](docs/archmap-api-contract-model.md) | Provider + Capability API 契约模型、Exposure、协议能力、继承 API 与延期项 |
| [`docs/p2.4-main-module-flow.md`](docs/p2.4-main-module-flow.md) | 唯一主模块、功能模块、主流程 DAG、dispatch 候选与 composition 契约 |
| [`docs/p5-main-execution-flow.md`](docs/p5-main-execution-flow.md) | P5 有界主流程执行流：封闭节点、原子函数/接口、防误解与防滑坡边界、schema 4.1 实现与验收 |
| [`docs/p5.1-execution-card-style.md`](docs/p5.1-execution-card-style.md) | P5.1 执行流项目节点样式：卡片结构、内嵌端口、端口语义与实现位置 |
| [`docs/p5.1-execution-flow-fan-in-plan.md`](docs/p5.1-execution-flow-fan-in-plan.md) | 汇入与边束的分层设计：直接 fan-in 已实现，视觉边束与模块级边束为未来方向 |
| [`docs/约定编程skill.md`](docs/约定编程skill.md) | 项目无关的约定编程 Skill：分层架构、契约、功能备注、测试与提交检查清单 |
| [`docs/schema/archmap-v5-bundle.schema.json`](docs/schema/archmap-v5-bundle.schema.json) | 当前 bundle JSON Schema 5.0：无主模块、无 mainFlows、无执行流 entry 节点 |
| [`docs/schema/archmap-v4-bundle.schema.json`](docs/schema/archmap-v4-bundle.schema.json) | 历史 bundle JSON Schema 4.1，供 P5 产物追溯 |
| [`docs/schema/archmap-v4.0-bundle.schema.json`](docs/schema/archmap-v4.0-bundle.schema.json) | 历史 bundle JSON Schema 4.0，供旧产物追溯 |
| [`docs/HANDOFF-P5.5.md`](docs/HANDOFF-P5.5.md) | P5.5 当前交接：已完成边界、下一步共享动态分发解析与数据契约收缩计划 |
| [`docs/p6-project-model-plan.md`](docs/p6-project-model-plan.md) | P6 已批准实施计划：取消主模块、项目级主流程、schema 5.0、纵向能力模块与分阶段验收 |
| [`docs/p6-project-model-discussion.md`](docs/p6-project-model-discussion.md) | P6 讨论背景：问题分析、目标模型、Provider 归属与调用视图清理 |
| [`docs/project-config-generation-guide.md`](docs/project-config-generation-guide.md) | 规范化项目配置生成指南：模块划分、入口/流程区分、Provider 归属与常见误配 |
| [`docs/schema/archmap-v3-bundle.schema.json`](docs/schema/archmap-v3-bundle.schema.json) | 历史 bundle JSON Schema 3.8 |

### 历史归档

P2/P3/P4 过程交接、分支说明、迁移计划、旧验收记录、旧设计、旧原型和旧 schema 已封存到：

- [`docs/旧文档/README.md`](docs/旧文档/README.md)

历史文档只用于追溯需求演进，不代表当前契约。

## 文档维护规则

1. 当前产品状态只写入根 `README.md` 和 `docs/` 下的当前权威文档；历史材料只进入 `docs/旧文档/`，不反向修改为“当前设计”。
2. 数据契约以 `docs/archmap-v3-design.md`、`docs/p2.4-main-module-flow.md`、`docs/p5-main-execution-flow.md` 和 `docs/schema/archmap-v4-bundle.schema.json` 为准。
3. P1.5 之后的实现页统一称 **Method Detail**；不要再把 FunctionFlow 写回主产品路径。
4. 新增 P5 及以后能力时，先更新数据契约和当前文档，再更新根 README 的使用说明与验收数据。
5. 文档中的示例命令若引用自举配置，应同时核对 `examples/archmap_v3.archmap.json` 是否仍与源码模块一致。
6. 文档总入口统一为根 `README.md`，不再维护独立的 docs 索引文件。
7. 所有新增代码必须遵守 [`docs/约定编程skill.md`](docs/约定编程skill.md)；模块、类、函数、方法和测试都必须有功能备注。

## 已知边界

- 仅实现 Python 前端。
- 静态调用解析无法覆盖动态 `getattr`、`**kwargs` 分发、运行时注册表等。
- 方法详情默认内嵌源码切片，单函数源码有长度上限；超大函数会标记为 truncated。
- 宏布局的局部重叠和边界启发式仍需要持续校验。
- P2.1 只合成 context manager、async context manager、callable、iterable；序列协议延期。
- 类焦点页和类内方法图不在当前产品计划中。
- User Surface 已建模为独立投影，但当前是静态 primitive + entrypoint 可达性启发式，配置覆盖优先。
- 方法详情页是 P1.5 的主入口；旧语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
- P4 的结构关系仍以静态证据为边界；复杂泛型、字符串注解别名和运行时注入可能产生低置信度或遗漏。
- User Surface 为启发式投影，不等同于完整 UX/运行时交互分析。
- Impact/Trace 受 `maxDepth` / `maxNodes` 限制，必须关注 `truncated`。
- 继承解析只覆盖项目内 canonical class；第三方、条件导入和结构性 Protocol 实现不伪造关系。
- 多态 candidates 只覆盖项目内已解析后代，`candidateSetComplete=false`。
- 模块层次/子模块（`parentId`）尚未建模，当前模块配置是扁平的。
- ArkTS 前端尚未实现。
- P5 执行流只提取 entrypoint 控制骨架，不展开主模块本地调用或功能模块接口；更多内部逻辑通过 Method Detail / 源码查看。
- P5 明确不实现逐语句节点、列表操作节点、`try/except` 异常控制、数据流边和图内下钻；这些是产品边界，不是待补延期项。
- 旧 `docs/旧文档/archmap-2.0-design.md` 和 `docs/旧文档/HANDOFF.md` 中的 FunctionFlow 内容是历史设计，不是当前契约。
- 当前 bundle schema 为 5.0；4.1/4.0 旧产物需要重新 build，历史 schema 仅用于追溯。
