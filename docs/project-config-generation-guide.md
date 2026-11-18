# ArchMap 规范化项目配置生成指南

> 状态：P9 当前配置指南<br>
> 版本：ArchMap 2.4.0 / bundle schema 6.3<br>
> 日期：2026-11-19<br>
> 适用范围：为 Python 项目生成或维护 `archmap` 配置的人员、脚本与 LLM
>
> P9 起，模块级自由函数使用“保守自动推断 + `defaultFreeFunctionSurface` 模块默认面 + 显式 exposure / execution 例外”生成；不再需要给每个内部 helper 批量写 `providerRoles=utility`。

本指南用于避免把以下概念混为一谈：

```text
模块
Provider Role
executionOnlyCallables
项目级 entrypoints
execution flow 的 entry 节点
项目页 flow card
```

当前运行时仍接受少数旧字段，但只会作为迁移兼容，不应继续生成。

## 0. P9 能力边界（必读）

### 已支持

- `modules[].defaultFreeFunctionSurface`：`auto` / `internal` / `capability`
- `modules[].executionOnlyCallables`
- `contract.apiExposure` 的 `public` / `internal` 显式覆盖
- `contract.providerRoles` 的七角色显式覆盖
- `capabilitySurface` 与空能力模块前端隐藏
- FunctionDetail 的 `functionSurface` / `functionSurfaceSource`

### 自由函数表面判定优先级

从高到低：

```text
executionOnlyCallables
  > apiExposure=internal
  > 显式 Provider Role = utility
  > 显式 public API 标签 / config public exposure
  > 显式非 utility Provider Role
  > defaultFreeFunctionSurface=internal
  > defaultFreeFunctionSurface=capability
  > 跨模块调用证据
  > internal
```

`auto` 模式的保守规则：

- 无显式 public API 标签、无跨模块调用、无显式非 utility role；
- 自由函数默认 `internal`，不因为函数名 public、带控制流、调用项目类而成为 `manager`。

### 三种默认面

```text
auto
  显式公开证据或跨模块调用 → capability
  其他自由函数 → internal

internal
  未显式声明 public API 的自由函数 → internal
  显式 public API / 非 utility role 仍可覆盖

capability
  未显式声明 internal 的自由函数 → capability
  apiExposure=internal 或 executionOnlyCallables 仍优先
```

### 内部 helper 的正确写法

单个内部 helper 使用：

```json
{
  "contract": {
    "apiExposure": {
      "gomoku.input_parser.column_letters": "internal"
    }
  }
}
```

整个模块的自由函数都是内部实现时使用：

```json
{
  "modules": [
    {
      "id": "terminal-ui",
      "role": "component",
      "defaultFreeFunctionSurface": "internal"
    }
  ]
}
```

不要用 `providerRoles=utility` 作为批量隐藏手段；它只应表达真正的 Provider 职责。

## 1. 先区分九个概念

| 概念 | 回答的问题 | 不应混淆为 |
|---|---|---|
| `include` / `exclude` | 分析哪些源码文件 | 模块划分 |
| 模块 | 哪些 Provider 属于同一业务能力 | 页面、流程或调用图 |
| Provider Role | 这个类/函数承担什么能力职责 | 模块类型或流程图节点 |
| `apiExposure` | 这个 callable 是公开能力还是内部实现 | Provider Role、执行流身份 |
| `defaultFreeFunctionSurface` | 模块级自由函数默认是 capability 还是 internal | 类方法、执行流身份 |
| `executionOnlyCallables` | 哪些 callable 只参与执行流、不属于能力面 | Provider Role、模块归属 |
| `entrypoints` | 项目静态分析的入口根 | 主模块 |
| `executionEntrypoints` | 哪个函数/方法生成执行流 | 模块配置 |
| `dispatchHints` | 动态调用候选如何解析 | 模块 API |

关键边界：

- Provider Role 只有七种：`config` / `model` / `manager` / `adapter` / `component` / `contract` / `utility`；
- `entry` 不是 Provider Role，而是 execution flow 的节点类型；
- flow card 是项目页 item，不是模块，也不是 Provider；
- 每个 execution flow 恰好一个标准 `entry` 节点；
- 入口检测由项目级 `entrypoints` / `executionEntrypoints` 驱动，不依赖 Provider Role。
- `executionOnlyCallables` 只声明 callable 的能力呈现面，不改变模块边界和文件归属。
- `defaultFreeFunctionSurface` 只影响模块级自由函数，不影响类、类方法或 executionOnly callable。
- 模块可以没有可见能力 Provider；后端保留模块与 layout，前端不渲染空能力模块卡。

## 2. 模块划分原则

### 2.1 每个源码文件只能属于一个模块

- 项目 `include` 覆盖的每个 `.py` 文件必须恰好落在一个模块的 include 中；
- 模块 include 不应互相重叠；
- 不应存在落入项目但未归入任何模块的源码；
- 不应为了“先跑起来”创建无法解释的空模块。

### 2.2 模块按业务能力划分，不按技术层划分

正确方向：

```text
database
├─ Database
├─ DatabaseConfig
└─ database utility

network
├─ NetworkAdapter
├─ ProtocolMessage
└─ ProtocolCodec
```

错误方向：

```text
config/
model/
utility/
contracts/
shared/
common/
misc/
```

`config`、`model`、`utility`、`contract` 是 Provider Role，不是模块类型。

### 2.3 模块围绕 manager / facade 组织

- 能力模块应有明确的能力 facade 或职责中心；纯执行流载体可以没有可见能力 Provider；
- manager 的配置、模型和内部 utility 应与其放在同一业务模块；
- 对外暴露的类方法、自由函数和协议能力进入该模块的 `providedApis`；
- 内部 utility 保持 internal，不因被 manager 调用就升级为模块 API。
- 入口函数和流程内部编排函数若只属于执行流，必须写入 `executionOnlyCallables`，不得依赖 `manager` 推断进入能力面。
- executionOnly callable 不进入 `providedApis`、Provider 卡片、能力计数和模块组合。
- 排除 executionOnly callable 后没有可见 Provider 的模块，仍保留真实模块边界；前端不展示其能力卡。

### 2.4 模块 role 只使用普通能力角色

允许：

```text
service / adapter / component / test / other
```

禁止：

```text
main / entry / functional
```

说明：

- 一个模块可以拥有入口源码文件；
- 但这不会使模块 role 变成 `entry`；
- 入口状态由项目级 execution flow 表达，不属于模块配置。

### 2.5 不创建“共享模块”兜底

当一个模型、配置或工具被多个模块使用时：

- 为它选择唯一 owner 模块；
- 其他模块通过依赖使用它；
- 不创建 `shared` / `contracts` / `common` 模块承载它；
- 跨模块使用不改变 owner；
- 如果它本身有独立职责和生命周期，可以作为独立能力模块，而不是“共享桶”。

示例：

```text
async-feedback 模块拥有 Spinner
network / menu 使用 with Spinner(...)
```

这是对异步反馈模块公开能力的正常依赖，不是模型共享，也不需要额外的契约模块。

### 2.6 模块内自由函数的能力边界

模块级自由函数最容易发生误分类。生成配置时必须先判断它属于哪一类：

| 类型 | 判定线索 | P9 配置方式 |
|---|---|---|
| capability | 明确公开 API 标记、跨模块调用、稳定对外契约 | 模块默认 `capability`，或单函数 `apiExposure=public` |
| execution | executionEntrypoints 或只服务执行流入口 | 写入 `executionOnlyCallables` |
| internal | 仅模块内调用、纯解析/渲染/格式化/辅助逻辑 | 模块默认 `internal`，或单函数 `apiExposure=internal` |
| 不确定 | 无跨模块调用、无公开标签、无稳定签名 | 保持 `auto` 并先按 internal 处理 |

不要把以下信号当作 capability 证据：

- 函数名没有下划线；
- 带控制流；
- 调用项目内类；
- 位于能力模块；
- 在 Python 中可导入。

“可导入”不等于“架构公开 API”。

## 3. 模型与配置归属

### 3.1 唯一 owner

每个 `config` / `model` / `contract` Provider 应有唯一归属模块。

判定优先级建议：

1. 显式配置的业务归属；
2. 主要 manager 的构造参数、字段或生命周期；
3. 定义它的文件所属业务包；
4. 主要消费者的业务域；
5. 仍无法判断时，先补文档和显式配置，不创建兜底模块。

### 3.2 跨模块引用是依赖，不是共享

- 一个模型被多个模块引用，不表示它需要多个 owner；
- 一个组件被多个模块调用，不表示它变成共享模型；
- 消费方模块不重复定义同一 Provider；
- 模块页不需要为跨模块调用默认绘制连线。

### 3.3 入口函数与执行流专属 callable

删除 Provider Role `entry` 不等于所有入口函数都必须拥有 Provider Role。

处理规则：

- 如果入口函数同时是真实公开能力，它可以保留普通 Provider Role；
- 如果入口函数只负责流程编排，应写入 `executionOnlyCallables`；
- `executionOnlyCallables` 中的函数/方法不显示 Provider Role，不进入 `providedApis`，模块页不展示能力卡；
- 入口状态仍由项目级 `entrypoints` / `executionEntrypoints` 和 execution flow 表达。

例如：

- `student_system.app.main:main / client / server` 是流程编排，不应推断为 `manager` 能力；
- `GameCli.run` 是执行流入口方法，可以从 `GameCli` 的公开方法 API 中排除；
- `GameCli` 类本身如果是 component Provider，仍可正常出现在模块能力面。

约束：

- 不写 `providerRole: "entry"`；
- 不把流程编排函数硬改成 `utility` 来隐藏；
- 不让 `executionOnlyCallables` 改变模块文件归属；
- 主流程导航只由项目页 flow card 和 execution flow 承担。

### 3.4 executionOnly ≠ internal

必须区分：

```text
executionOnly
  → 进入执行流，只在主流程页和方法详情中出现

internal
  → 模块内部实现，不进入能力面，也不承担流程入口语义
```

错误用法：

```json
{
  "executionOnlyCallables": [
    "gomoku.input_parser:column_letters"
  ]
}
```

如果 `column_letters` 不参与任何执行流，只属于解析模块内部实现，则不应写入 `executionOnlyCallables`。正确方向是把它标记为 internal：单函数使用 `apiExposure=internal`，整个模块的自由函数都是内部实现时使用 `defaultFreeFunctionSurface: "internal"`。

## 4. 入口与流程配置

### 4.1 `entrypoints` 与分析根

`entrypoints` 用于：

- 项目级入口解析；
- User Surface 传播；
- 调用关系与主流程事实。

格式示例：

```json
"entrypoints": ["package.module:main"]
```

### 4.2 `executionEntrypoints` 与执行流

```json
"executionEntrypoints": ["package.module:Class.run"]
```

规则：

- `entrypoints` 是分析根；
- `executionEntrypoints` 可以选择真正的用户旅程方法；
- 有 `executionEntrypoints` 时，flow card 由它解析出的 execution flows 生成；
- 省略或无法解析时回退到 `entrypoints`；
- 不要让 `executionEntrypoints` 承担模块划分职责；
- 入口解析不读取 Provider Role。

### 4.3 标准 flow entry 节点

每条 execution flow 自动包含一个标准 `entry` 节点：

```json
{
  "kind": "entry",
  "functionId": "fn:app.main.main",
  "targetFunctionId": "fn:app.main.main",
  "moduleId": "app",
  "ports": ["out"],
  "expandable": false
}
```

约束：

- 与 `loop` / `branch` / `dispatch` 同级；
- 使用标准执行卡片样式；
- 不写入 `providerRole`；
- 不因为入口节点而把该函数加入 `moduleComposition.entry`。

### 4.4 flow card 与 module card

项目页使用统一卡片网格：

```text
projectGraph.flowCards[]   项目级流程卡片
projectGraph.modules[]     普通能力模块卡片
projectGraph.layout.nodes  同时包含 flow card 与 module card
```

flow card 由 `executionFlows` 派生：

```json
{
  "id": "flow-card:exec-flow:...",
  "kind": "flow",
  "flowId": "exec-flow:...",
  "entrypointId": "fn:app.main.main",
  "name": "main()",
  "moduleId": "app",
  "moduleName": "应用入口与编排",
  "color": "#f59e0b",
  "nodeCount": 4,
  "edgeCount": 3
}
```

构建配置时：

- flow card 必须进入 `projectGraph.layout.nodes`；
- flow card 不属于 `projectGraph.modules`；
- flow card 与模块卡片同层、同网格；
- 不在顶部单独配置主流程入口条。

### 4.5 动态分发配置

规范化配置使用顶层 `dispatchHints`：

```json
"dispatchHints": [
  {
    "function": "app.main:main",
    "expression": "handlers[mode]",
    "occurrence": 1,
    "candidates": ["app.main:handler_a", "app.main:handler_b"],
    "complete": true,
    "reason": "config"
  }
]
```

迁移期可以继续读取 `mainFlow.dispatches`，但新配置生成器不应继续输出旧字段。

### 4.6 执行流专属 callable

当某个 callable 属于模块源码边界，但只作为执行流入口或流程内部编排单元时，使用模块级显式配置：

```json
{
  "modules": [
    {
      "id": "app",
      "name": "应用入口与编排",
      "include": ["src/app/**"],
      "role": "service",
      "executionOnlyCallables": [
        "src.app.main:main",
        "src.app.main:run_client",
        "src.app.main:run_server",
        "src.app.cli:GameCli.run"
      ]
    }
  ]
}
```

引用格式：

```text
module.path:qualname
```

支持：

- 模块级自由函数；
- 类方法。

语义：

- callable 仍保留在 `functionDetails`、`callSites`、callers/callees 和执行流节点中；
- callable 不进入 `providedApis`、`apiProviders`、`moduleComposition`、Provider 角色计数和能力卡；
- 方法所属的类 Provider 不被删除，只从类能力中移除该方法；
- executionOnly callable 的 User Surface 若完全由其证据产生，不进入模块能力页；项目级事实保留；
- 模块排除后没有可见能力 Provider 时，后端保留模块和 layout，前端不渲染空能力模块卡；
- 直接访问空能力模块路由时返回项目页，并提示该模块仅承载执行流。

生成配置时：

- 维护者必须显式列出这些 callable，不依赖自动推断；
- 不得把整个模块从 `modules` 中删除来替代 callable 声明；
- 不得为 executionOnly callable 再配置 `providerRoles`；
- 如果 callable 被其他模块调用，应复核它是否其实是真实能力 API；
- 不得把内部 helper 放进 `executionOnlyCallables`；内部 helper 使用 internal exposure；
- 生成器应先判断 callable 是否出现在 execution flow，再决定是否使用该字段。

### 4.7 模块默认自由函数面

模块配置：

```json
{
  "id": "terminal-ui",
  "name": "终端界面适配",
  "include": ["gomoku/input_parser.py", "gomoku/renderer.py"],
  "role": "component",
  "defaultFreeFunctionSurface": "internal"
}
```

允许值：

```text
auto        默认；只根据强证据把自由函数升级为 capability
internal    模块内自由函数默认 internal
capability  模块内自由函数默认 capability
```

约束：

- 只影响模块级自由函数，不影响类方法；
- `executionOnlyCallables` 优先级最高；
- `apiExposure=internal` 优先于模块默认 `capability`；
- 显式 public API 标签或 config public exposure 优先于模块默认 `internal`；
- 跨模块调用是 `auto` 模式下的 capability 证据；
- 模块默认面不改变文件归属和模块边界；
- 一个模块只有少量公开自由函数时，优先使用模块默认 `internal` + 单函数 public exposure，而不是模块默认 `capability`。

## 5. 角色配置

### 5.1 优先让结构推断生效

Provider Role 判定优先级：

```text
显式覆盖
  > 注释 / 装饰器
  > 结构规则
  > 命名弱提示
```

生成配置时：

- 不要为了隐藏 internal helper 给所有自由函数批量写 `providerRoles=utility`；
- 先检查结构推断是否正确；
- 只在推断错误或业务语义必须覆盖时写显式 role；
- 内部自由函数优先用 `apiExposure=internal` 表达边界，而不是借用角色字段；
- 批量 role override 会掩盖角色模型缺陷，增加维护成本；
- P9 使用 `defaultFreeFunctionSurface` 和 `apiExposure` 表达自由函数边界，替代批量 role override；
- 自由函数不再因控制流、项目调用或 public 命名自动成为 `manager`。

### 5.2 七角色理解

- `manager`：组织行为、维护状态、提供业务 API；
- `adapter`：外部系统适配；
- `component`：UI / 协议组件；
- `config`：静态配置、常量、枚举；
- `model`：运行期数据模型、DTO、结果；
- `contract`：抽象类、Protocol、接口；
- `utility`：无状态内部辅助逻辑。

`entry` 不是 Provider Role。`executionOnlyCallables` 与 `functionSurface=internal` 的 callable 不展示 Provider Role；它们分别由执行流语义和内部实现语义承载。

## 6. 标准配置骨架

```json
{
  "projectName": "example",
  "language": "python",
  "include": ["src/**/*.py"],
  "exclude": [
    "**/__pycache__/**",
    "**/.venv/**",
    "tests/**"
  ],
  "entrypoints": ["src.app.main:main"],
  "executionEntrypoints": ["src.app.main:App.run"],
  "modules": [
    {
      "id": "app",
      "name": "应用入口与编排",
      "include": ["src/app/**"],
      "note": "入口文件与顶层编排；普通能力模块",
      "color": "#f59e0b",
      "role": "service",
      "defaultFreeFunctionSurface": "internal",
      "executionOnlyCallables": [
        "src.app.main:main",
        "src.app.main:run_client",
        "src.app.main:run_server"
      ]
    },
    {
      "id": "network",
      "name": "网络协议",
      "include": ["src/network/**"],
      "note": "网络适配器、协议模型和公开 codec",
      "color": "#fb7185",
      "role": "adapter"
    }
  ],
  "dispatchHints": [],
  "contract": {
    "providerRoles": {
      "src.network.protocol_codec.ProtocolCodec": "manager"
    }
  }
}
```

## 7. 常见错误配置

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 写 `mainModule` | 旧主模块语义，产生 deprecation warning | 删除；入口由项目级配置表达 |
| 写 `kind: "main"` / `kind: "functional"` | 旧模块类型，产生 deprecation warning | 删除；使用模块 `role` |
| 写模块 `role: "entry"` | 模块被错误理解为入口模块 | 使用 service/component/adapter 等普通 role |
| 写 `providerRoles: {"X": "entry"}` | Provider Role 无效，产生 deprecation warning | 删除；用 `entrypoints` 定义 flow entry |
| 建 `contracts` / `shared` 模块 | 模块边界失效，能力归属不清 | 模型/配置归入其服务的业务模块 |
| 把 flow card 放进 `modules` | 页面层级和模块语义混乱 | flow card 只放在 `projectGraph.flowCards` |
| 手工伪造 `flowCards` 但不更新 layout | 项目页卡片缺失或无法拖拽 | 由 execution flow 派生并加入 layout |
| 把 execution flow `entry` 节点当 Provider Role | schema/validator 混淆 | flow 节点与 Provider Role 分开处理 |
| 模块 include 重叠 | 文件归属歧义 | 保证每文件恰好一个模块 |
| 创建无源码边界、无职责的空模块占位 | 模块语义无法解释 | 删除无意义占位；能力为空但承担源码/执行流的模块应保留，并由前端隐藏能力卡 |
| 把测试脚本混入业务模块 | 生产 API 与测试事实混杂 | 独立 test 模块或排除 |
| 把所有函数都设置 role override | 角色模型失真 | 优先依赖结构与注释 |
| 把入口/编排函数硬改成 `utility` | 能力语义错误，函数仍被隐藏得不透明 | 写入 `executionOnlyCallables` |
| executionOnly callable 再配置 Provider Role | 配置冲突，能力面不可预测 | 只保留 executionOnly 声明 |
| 把内部 helper 写进 `executionOnlyCallables` | 产生“不在执行流”警告且语义错误 | 用 `apiExposure=internal` 或模块默认 internal |
| 依赖 public 命名自动成为模块能力 | 出现多余 MANAGER 自由函数卡 | 保持 `auto`，或设置模块默认 internal |
| 用 `providerRoles=utility` 批量隐藏 helper | 角色字段被当成隐藏开关，长期失真 | 用 `defaultFreeFunctionSurface=internal` 或 `apiExposure=internal` |
| 给 terminal-ui 设置 defaultFreeFunctionSurface=capability | 内部解析/渲染 helper 全部变成能力卡 | 设置 internal，单个公开函数用 public exposure |
| 默认面为 capability 却想隐藏单个 helper | 无法通过默认面完成 | 对该 helper 配置 `apiExposure=internal` |
| 用删除模块代替 callable 级声明 | 模块边界、源码归属和其他能力被误伤 | 在模块内声明 `executionOnlyCallables` |
| 空能力模块仍在前端生成卡片 | 项目页出现无意义卡片 | 后端保留，前端按 `capabilitySurface.hasProviders=false` 过滤 |
| 把模块调用边当作模块边界 | 模块页重新变成调用图 | 调用关系留在 CallSite / Method Detail |
| 将 `executionEntrypoints` 当作模块入口 | 配置语义混乱 | 明确它是项目级流程起点 |

## 8. 生成前检查

### 8.1 固定生成算法

生成配置时按以下顺序执行，避免先写字段再猜语义：

```text
1. 按业务能力划分模块，保证每个文件只有一个 owner
2. 识别模块内 class Provider 及其职责
3. 识别 entrypoints / executionEntrypoints
4. 识别模块级自由函数
5. 把执行流入口和流程编排函数写入 executionOnlyCallables
6. 根据模块自由函数整体职责选择 defaultFreeFunctionSurface（多数 internal 模块写 internal，能力 API 模块写 capability 或保留 auto）
7. 对少量例外使用 apiExposure / executionOnlyCallables
8. 最后生成 providerRoles，仅用于结构和业务语义确实需要覆盖的 Provider
```

### 8.2 自由函数审计

生成配置前逐模块回答：

- 这个自由函数是否被其他模块调用？
- 是否有显式 `@public` / public API 文档标签？
- 是否出现在 execution flow 中？
- 是否只被同模块内部函数调用？
- 它的签名是否作为稳定对外契约维护？
- 如果删除 public 命名，是否仍有外部消费者？

无法用证据回答为“公开能力”的，优先按 internal 处理。

### 8.3 生成前检查清单

生成配置前至少确认：

- 项目根目录和源码目录正确；
- `include` 覆盖目标源码；
- `exclude` 排除缓存、构建、虚拟环境和无关测试；
- 模块 include 是否重叠；
- 是否存在未归属文件；
- 是否出现 `contracts` / `shared` / `misc` 等兜底模块；
- 每个能力模块是否有可解释的 manager / facade；纯执行流载体是否为显式设计；
- config/model 是否围绕对应 manager；
- 模块 role 是否只使用 `service/adapter/component/test/other`；
- `entrypoints` 是否可解析；
- `executionEntrypoints` 是否指向真正的流程起点；
- 是否错误配置了 `entry` Provider Role；
- role override 是否只用于必要场景；
- 是否识别出入口函数和流程内部编排单元；
- 流程专属 callable 是否写入 `executionOnlyCallables`；
- 是否错误地给 executionOnly callable 配置了 Provider Role；
- 排除 executionOnly callable 后，哪些模块能力为空；
- 是否出现被推断为 manager 的模块内部自由函数；
- executionOnly 列表中的 callable 是否都真实出现在 execution flow；
- 用于隐藏 helper 的手段是否是 `defaultFreeFunctionSurface=internal` 或 `apiExposure=internal`，而不是批量 role override；
- `defaultFreeFunctionSurface` 是否只影响自由函数，没有误伤类方法；
- `functionSurface` 与 `capabilityFreeFunctionIds` / `internalFreeFunctionIds` / `executionFreeFunctionIds` 是否一致。

## 9. 生成后验证

建议依次执行：

```bash
python3 -m archmap build <project> --config <config> --out <output>
python3 -m archmap check <output>/architecture.json
```

数据检查：

- `schemaVersion == "6.3"`；
- `stats.providerRoles` 只有七角色；
- 不存在 `providerRole == "entry"`；
- 每个 `executionFlow` 恰好一个 `entry` 节点；
- 每个 execution flow 节点数大于 0；
- `projectGraph.flowCards` 数量与 execution flows 一致；
- 后端 `projectGraph.layout.nodes` 同时包含 flow card 和 module card（包括前端不渲染的空能力模块）；空模块在布局顺序中追加到可见卡片之后；
- flow card 的 `flowId` 可解析；
- 模块卡不包含 flow navigation 语义；
- executionOnly / internal free function 不在 `providedApis` / `apiProviders` / 角色计数中；
- 每个自由函数 detail 都有 `functionSurface` 与 `functionSurfaceSource`；
- `freeFunctionSurfaceCounts` 与 `capabilityFreeFunctionIds` / `internalFreeFunctionIds` / `executionFreeFunctionIds` 一致；
- executionOnly callable 仍有 `functionDetails` 和 execution flow 引用；
- 空能力模块仍在后端 `projectGraph.modules` 与 `layout.nodes` 中；
- 空能力模块不在前端项目页渲染，也不会在默认可见网格中留下空位；
- `projectGraph.capabilityModuleIds` 与可见模块一致。

机器审计建议：

```bash
# 查看所有仍被识别为 manager 的自由函数
jq '.moduleGraphs[]
  | {moduleId,
     managerFunctions: [
       .nodes[]
       | select(.kind == "function" and .providerRole == "manager")
       | .id
     ]}' <output>/architecture.json

# 查看公开自由函数 API
jq '[.moduleGraphs[].providedApis[]
  | select(.providerKind == "function")
  | {providerId, display, providerRole}]' <output>/architecture.json

# 查看自由函数表面与空能力模块
jq '{capabilityFunctions: [.moduleGraphs[].capabilityFreeFunctionIds[]],
     internalFunctions: [.moduleGraphs[].internalFreeFunctionIds[]],
     executionFunctions: [.moduleGraphs[].executionFreeFunctionIds[]],
     emptyModules: [.projectGraph.modules[]
       | select(.capabilitySurface.hasProviders == false)
       | .id]}' <output>/architecture.json
```

期望：

- `managerFunctions` 只包含真正的模块能力自由函数；
- 解析/渲染/格式化 helper 不出现在公开自由函数 API 中；
- executionOnly callable 都能在 execution flow 中找到；
- 空能力模块不出现在前端渲染集合 `capabilityModuleIds` 中。

人工检查：

- diagnostics 为 0，或每条 warning 都有明确原因；
- 项目页没有无意义模块卡片；
- flow card 与 module card 同层展示；
- 模块页不依赖调用连线才能理解；
- 每个 API 都能追溯到 Provider；
- 每个 config/model 都有明确模块归属；
- 没有跨模块重复定义的同一模型；
- 没有为了生成成功而设置兜底模块。

## 10. 规范化样例

### 10.1 student_system

```text
app              入口与顶层编排（role=service）
network          NetworkAdapter + ProtocolMessage + ProtocolCodec
database         Database + DatabaseConfig
menu             MenuSystem + StudentRecord + display utility
async-feedback   Spinner
test             表格验证脚本
```

关键点：

- 一张 `main()` flow card；
- app 模块的 `main()` / `client()` / `server()` 声明为 `executionOnlyCallables`；
- app 模块能力面为 0，后端保留模块，前端不显示 app 能力卡；
- 主流程仍包含这三个 callable 的执行节点；
- 不建立 `contracts` 共享模块；
- `ProtocolMessage` 是 network 模块的 public model；
- `ProtocolCodec` 是 network 模块的 public manager capability；
- `StudentRecord` 是 menu 模块的 public model；
- `DatabaseConfig` 跟随 database manager。

### 10.2 terminal-ui 反模式案例

错误理解：

```text
自由函数没有下划线
→ 是 public
→ 带控制流
→ 调用项目类
→ 自动推断为 manager
→ 进入 providedApis
```

正确理解：

```text
column_letters / parse_position / format_move_hint 等
是终端解析与渲染模块的内部实现；
模块能力由 class Provider 提供；
公开命名不等于架构公开 API。
```

P9 推荐写法：

```json
{
  "modules": [
    {
      "id": "terminal-ui",
      "role": "component",
      "defaultFreeFunctionSurface": "internal"
    }
  ]
}
```

如果其中一个函数确实是公开能力，再用单函数例外：

```json
{
  "contract": {
    "apiExposure": {
      "gomoku.input_parser.parse_input": "public"
    }
  }
}
```

### 10.3 gomoku

```text
terminal       main.py / __main__.py / cli.py
terminal-ui    input_parser.py / renderer.py
application    game.py + GameConfig
domain         board.py + models.py
ai-adapter     ai.py
```

关键点：

- 一张 `GameCli.run()` flow card；
- `GameCli.run` 可声明为 executionOnly callable；
- `GameCli` 类仍为 component Provider，其他公开方法仍可提供能力；
- 模块 role 不为 entry；
- `GameConfig` 跟随 application manager。

### 10.4 ArchMap 自举

```text
pipeline
python-frontend
graph-projection
validation
rendering
```

关键点：

- 一张 `cli_entry.main()` flow card；
- `archmap.entry.cli_entry:main` 声明为 executionOnly callable；
- pipeline 模块仍因 `PipelineManager` 等真实 Provider 保留能力卡；
- 不建立 `core-contracts` 技术层模块；
- Provider Role 计数只包含七角色。

## 11. 旧配置迁移表

| 旧配置 / 数据 | 当前处理 | 新写法 |
|---|---|---|
| `mainModule` | deprecation warning，忽略 | 删除；使用项目级 entrypoints |
| `module.kind` | deprecation warning，忽略 | 删除；使用 `module.role` |
| `module.role = "main"` | 归一化为 service | `role: "service"` 或按职责配置 |
| `module.role = "entry"` | 归一化为 service | `role: "service"` / `component` 等 |
| `providerRoles.X = "entry"` | deprecation warning，忽略 | 用 `entrypoints` / `executionEntrypoints` |
| `mainFlow.dispatches` | 兼容读取 | 顶层 `dispatchHints` |
| `projectGraph.mainFlows` | 已删除 | `executionFlows` + `flowCards` |
| `projectGraph.primaryFlowId` | 已删除 | `primaryExecutionFlowId` |
| `moduleGraphs[].edges` | 已删除 | `callSites` / `methodEdges` / Method Detail |
| execution flow 无 entry 节点 | 不再接受 | 标准 `entry` 节点 |
| 入口/编排函数被推断为 manager 并进入 providedApis | 能力面污染 | 在所属模块声明 `executionOnlyCallables` |
| 模块内部 helper 被推断为 manager | 能力面污染 | 用 `defaultFreeFunctionSurface=internal` 或单函数 `apiExposure=internal` |
| `providerRoles: {"fn": "utility"}` 批量隐藏 helper | 角色模型被当成隐藏开关 | 改用模块默认自由函数面或 `apiExposure=internal` |
| 模块能力为空但前端仍显示卡片 | 项目页噪音 | 后端保留模块与 layout，前端过滤空能力模块；空模块默认排到可见卡片之后 |

## 12. 最终目标

```text
项目级 execution flow
  + flow cards
  + 普通能力模块
  + 七 Provider Role
  + 无主模块
  + 无模块页调用图
  + executionOnlyCallables 能力面透明
  + 空能力模块后端保留、前端隐藏
  + 保守自由函数推断 + 模块默认自由函数面 + 少量显式例外
  + 一级 flowScopes 接口下钻（显式 roots、自动 capability、预算与诊断）
```

## 13. P10 接口 scope 配置

P10 起可在配置中声明一级接口 scope：

```json
"flowScopes": {
  "enabled": true,
  "roots": [
    "student_system.app.main:server",
    "student_system.app.main:client"
  ],
  "autoDetect": true,
  "maxScopesPerFlow": 6,
  "maxNodesPerScope": 24,
  "maxEdgesPerScope": 32
}
```

规则：

- `roots` 使用 `module:qualname` 或 canonical function id；
- `executionOnlyCallables` 可自动成为 scope root；
- scope root 必须是 `free_function` 编排 callable；`interface` 是模块能力边界，不能生成 scope；
- `autoDetect=true` 时从主流程可见的 `free_function` 中保守发现同模块本地编排 callable；
- 自动候选必须至少触达一个跨模块外部接口、至少包含一个控制结构、未超 scope 预算且非直接递归；
- 显式 `roots` 和 `executionOnlyCallables` 优先于自动候选；
- interface 节点永远不参与自动发现；
- scope 深度固定为 1，scope 内节点不能再次下钻；
- 预算触顶时优先保留控制骨架和外部接口，并在 `scope.diagnostics` 中显式标记；
- scope 的路由为 `#/flow/<flowId>/scope/<nodeId>`；
- scope 内只展示直接外部能力接口与内部 helper 的接口提示，不伪造 unresolved 调用。

## 14. P9 实现记录

- 模块级自由函数在 `auto` 模式下采用保守推断，不再因控制流、项目调用或 public 命名自动成为 `manager`；
- 新增 `defaultFreeFunctionSurface: auto | internal | capability`；
- 新增 `functionSurface` / `functionSurfaceSource` 到自由函数 FunctionDetail；
- ModuleGraph 输出 `capabilityFreeFunctionIds` / `internalFreeFunctionIds` / `executionFreeFunctionIds` / `freeFunctionSurfaceCounts`；
- schema 升级为 6.2；
- `executionOnlyCallables` 保持最高优先级；
- 空能力模块继续后端保留、前端隐藏。

## 15. P10 实现记录

- bundle schema 升级为 6.3；
- `projectGraph.executionFlows[].scopes[]` 新增一级接口 scope；
- 主流程执行节点新增 `drilldown` 接口摘要和 `interfaceHints` helper 提示；
- 新增 `flowScopes` 配置：enabled / roots / maxScopesPerFlow / maxNodesPerScope / maxEdgesPerScope；
- P10.1 收紧 scope root：只允许 `free_function` 编排节点，interface 节点禁止生成 scope；
- P10.2 普通语句通过 branch `armSummaries` / edge `statements` / `implicitNext` 表达，不新增 statement 节点；多分支不展示 case 内部赋值注释；
- P10.3 新增保守自动发现：主流程同模块 free_function + 外部接口 + 控制结构 + 预算内，显式 roots/executionOnly 优先；
- scope 视图与主流程分离，路由为 `#/flow/<flowId>/scope/<nodeId>`；
- scope 深度硬限制为 1，预算截断进入 scope diagnostics；
- student_system 与 gomoku 样例配置已启用 scope roots。
