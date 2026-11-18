# ArchMap 规范化项目配置生成指南

> 状态：P7.5 当前配置指南<br>
> 版本：ArchMap 2.1.0 / bundle schema 6.0<br>
> 日期：2026-11-18<br>
> 适用范围：为 Python 项目生成或维护 `archmap` 配置的人员、脚本与 LLM

本指南用于避免把以下概念混为一谈：

```text
模块
Provider Role
项目级 entrypoints
execution flow 的 entry 节点
项目页 flow card
```

当前运行时仍接受少数旧字段，但只会作为迁移兼容，不应继续生成。

## 1. 先区分六个概念

| 概念 | 回答的问题 | 不应混淆为 |
|---|---|---|
| `include` / `exclude` | 分析哪些源码文件 | 模块划分 |
| 模块 | 哪些 Provider 属于同一业务能力 | 页面、流程或调用图 |
| Provider Role | 这个类/函数承担什么职责 | 模块类型或流程图节点 |
| `entrypoints` | 项目静态分析的入口根 | 主模块 |
| `executionEntrypoints` | 哪个函数/方法生成执行流 | 模块配置 |
| `dispatchHints` | 动态调用候选如何解析 | 模块 API |

关键边界：

- Provider Role 只有七种：`config` / `model` / `manager` / `adapter` / `component` / `contract` / `utility`；
- `entry` 不是 Provider Role，而是 execution flow 的节点类型；
- flow card 是项目页 item，不是模块，也不是 Provider；
- 每个 execution flow 恰好一个标准 `entry` 节点；
- 入口检测由项目级 `entrypoints` / `executionEntrypoints` 驱动，不依赖 Provider Role。

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

- 每个模块应有明确的能力 facade 或职责中心；
- manager 的配置、模型和内部 utility 应与其放在同一业务模块；
- 对外暴露的类方法、自由函数和协议能力进入该模块的 `providedApis`；
- 内部 utility 保持 internal，不因被 manager 调用就升级为模块 API。

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

### 3.3 入口函数仍可有正常 Provider Role

删除 Provider Role `entry` 不等于删除入口函数。

入口函数仍然可能是：

```text
manager / adapter / component / contract / utility
```

例如：

- `main()` 如果是 public orchestration function，可以按结构规则成为 `manager`；
- `GameCli` 如果是终端 UI 组件，应配置为 `component`；
- 薄启动函数通常是 `utility` 或 internal provider。

约束：

- 不写 `providerRole: "entry"`；
- 不因为函数是 flow entrypoint 就强制改写其 Provider Role；
- 模块页可以展示入口函数的正常 Provider Role，但不展示 `entry` 语义；
- 主流程导航只由项目页 flow card 和 execution flow 承担。

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

- 不要为所有 Provider 批量写 role override；
- 先检查结构推断是否正确；
- 只在推断错误或业务语义必须覆盖时写显式 role；
- 批量 override 会掩盖角色模型缺陷，增加维护成本。

### 5.2 七角色理解

- `manager`：组织行为、维护状态、提供业务 API；
- `adapter`：外部系统适配；
- `component`：UI / 协议组件；
- `config`：静态配置、常量、枚举；
- `model`：运行期数据模型、DTO、结果；
- `contract`：抽象类、Protocol、接口；
- `utility`：无状态内部辅助逻辑。

`entry` 不是 Provider Role。

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
      "role": "service"
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
| 创建空模块占位 | 项目页出现无意义卡片 | 删除空模块或补足真实职责 |
| 把测试脚本混入业务模块 | 生产 API 与测试事实混杂 | 独立 test 模块或排除 |
| 把所有函数都设置 role override | 角色模型失真 | 优先依赖结构与注释 |
| 把模块调用边当作模块边界 | 模块页重新变成调用图 | 调用关系留在 CallSite / Method Detail |
| 将 `executionEntrypoints` 当作模块入口 | 配置语义混乱 | 明确它是项目级流程起点 |

## 8. 生成前检查

生成配置前至少确认：

- 项目根目录和源码目录正确；
- `include` 覆盖目标源码；
- `exclude` 排除缓存、构建、虚拟环境和无关测试；
- 模块 include 是否重叠；
- 是否存在未归属文件；
- 是否出现 `contracts` / `shared` / `misc` 等兜底模块；
- 每个模块是否有可解释的 manager / facade；
- config/model 是否围绕对应 manager；
- 模块 role 是否只使用 `service/adapter/component/test/other`；
- `entrypoints` 是否可解析；
- `executionEntrypoints` 是否指向真正的流程起点；
- 是否错误配置了 `entry` Provider Role；
- role override 是否只用于必要场景。

## 9. 生成后验证

建议依次执行：

```bash
python3 -m archmap build <project> --config <config> --out <output>
python3 -m archmap check <output>/architecture.json
```

数据检查：

- `schemaVersion == "6.0"`；
- `stats.providerRoles` 只有七角色；
- 不存在 `providerRole == "entry"`；
- 每个 `executionFlow` 恰好一个 `entry` 节点；
- 每个 execution flow 节点数大于 0；
- `projectGraph.flowCards` 数量与 execution flows 一致；
- `projectGraph.layout.nodes` 同时包含 flow card 和 module card；
- flow card 的 `flowId` 可解析；
- 模块卡不包含 flow navigation 语义。

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
- `main()` 有 `isFlowEntry=true`，Provider Role 按结构推断；
- 不建立 `contracts` 共享模块；
- `ProtocolMessage` 是 network 模块的 public model；
- `ProtocolCodec` 是 network 模块的 public manager capability；
- `StudentRecord` 是 menu 模块的 public model；
- `DatabaseConfig` 跟随 database manager。

### 10.2 gomoku

```text
terminal       main.py / __main__.py / cli.py
terminal-ui    input_parser.py / renderer.py
application    game.py + GameConfig
domain         board.py + models.py
ai-adapter     ai.py
```

关键点：

- 一张 `GameCli.run()` flow card；
- `GameCli` 为 component Provider；
- 模块 role 不为 entry；
- `GameConfig` 跟随 application manager。

### 10.3 ArchMap 自举

```text
pipeline
python-frontend
graph-projection
validation
rendering
```

关键点：

- 一张 `cli_entry.main()` flow card；
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

## 12. 最终目标

```text
项目级 execution flow
  + flow cards
  + 普通能力模块
  + 七 Provider Role
  + 无主模块
  + 无模块页调用图
```
