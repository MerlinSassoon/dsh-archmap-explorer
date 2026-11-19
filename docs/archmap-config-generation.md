---
name: archmap-config-generation
description: 从源码事实生成、维护和校验 ArchMap 项目模块配置，覆盖模块归属、Provider Role、能力面、入口、executionOnlyCallables、flowScopes、dispatchHints 与预算校验。
whenToUse: 创建或修改 archmap.config.json、划分模块、声明 Provider Role、选择入口与执行流 callable、配置 scope 或 dispatch 候选时使用。
user-invocable: true
---

# ArchMap 配置生成 Skill（archmap-config-generation）

> 适用对象：为 Python 项目生成或维护 `archmap.config.json` 的 AI 编码模型、脚本和维护者<br>
> 适用版本：ArchMap 2.5.0 / bundle schema 6.4<br>
> 输入：项目源码、现有 README / 领域文档、可选旧配置<br>
> 输出：可被 `archmap build` 和 `archmap check` 稳定验证的模块配置

本指南是配置生成规范。代码结构规范见
[`archmap-code-conventions.md`](archmap-code-conventions.md)；数据契约见
[`archmap-v3-design.md`](archmap-v3-design.md)。

## 0. 强制原则

生成配置前必须理解：

```text
配置不是第二套业务结构。
配置只显式声明源码中已经存在、或需要维护者明确承认的边界。
```

不得：

- 为让图上出现更多卡片而拆空模块；
- 为隐藏误判而批量写 `providerRoles`；
- 把普通内部 helper 写入 `executionOnlyCallables`；
- 伪造 entrypoint、dispatch candidate 或 scope root；
- 手写 `flowCards`、layout 节点或 generated bundle 数据；
- 输出旧字段或旧语义。

配置生成的目标顺序：

```text
源码事实正确
  > 模块边界唯一
  > 能力面稳定
  > 执行流可分析
  > 配置字段最少
  > 诊断可解释
```

## 1. 先区分核心概念

| 概念 | 回答的问题 | 不是什么 |
|---|---|---|
| `include` / `exclude` | 分析哪些源码 | 模块划分 |
| `modules` | 哪些源码属于同一业务能力 | 页面或调用图 |
| `modules[].role` | 模块职责类型 | 入口类型、Provider Role |
| Provider Role | 类/函数承担什么能力职责 | 模块类型、flow 节点 |
| `apiExposure` | 单 callable 是 public 还是 internal | Provider Role |
| `defaultFreeFunctionSurface` | 模块级自由函数的默认能力面 | 类方法表面 |
| `executionOnlyCallables` | 哪些 callable 只参与执行流 | 隐藏 helper 的开关 |
| `entrypoints` | 项目静态分析根 | 主模块 |
| `executionEntrypoints` | 哪些函数/方法生成主执行流 | 模块配置 |
| `flowScopes` | 哪些编排 callable 生成一级接口 scope | 无限递归下钻 |
| `dispatchHints` | 动态分发的候选集合 | 确定调用边 |
| `dispatchCandidates` | 哪些完整候选集生成候选旅程 | 主流程控制边 |

当前固定语义：

- 所有模块都是普通能力模块；
- 模块 role 只能是 `service` / `adapter` / `component` / `test` / `other`；
- Provider Role 只能是 `config` / `model` / `manager` / `adapter` / `component` / `contract` / `utility`；
- `entry` 是 execution flow 节点类型，不是 Provider Role，也不是模块 role；
- flow card 是项目页卡片，不是模块或 Provider；
- 每条 execution flow 恰好一个标准 `entry` 节点；
- 模块能力为空时后端保留模块与 layout，前端不渲染能力卡；
- 项目页不生成模块间依赖线，跨模块调用保留在调用事实层。

## 2. 固定生成算法

严格按以下顺序生成配置。不要在未完成前一步时先猜字段。

```text
1. 确定项目根、源码根、include / exclude
2. 枚举全部目标源码文件，建立 file → module 唯一归属
3. 按业务能力确定模块 ID、名称、role、note、颜色
4. 枚举类与模块级自由函数，识别物理代码单元与 Provider Role
5. 识别 entrypoints 与 executionEntrypoints
6. 判断 executionOnlyCallables
7. 判断每个模块的 defaultFreeFunctionSurface
8. 为少量例外生成 apiExposure / providerRoles
9. 识别动态分发，生成 dispatchHints
10. 按需配置 flowScopes / dispatchCandidates
11. 生成配置并执行 build/check
12. 审计能力面、诊断和布局覆盖
```

每一步都必须以源码事实为证据。无法证明时保留 `auto` / internal / unresolved，而不是伪造确定结构。

## 3. 源码范围与文件归属

### 3.1 include / exclude

```json
{
  "include": ["src/**/*.py"],
  "exclude": [
    "**/__pycache__/**",
    "**/.venv/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/build/**",
    "**/dist/**"
  ]
}
```

规则：

- `include` 必须覆盖要分析的源码；
- `exclude` 必须排除缓存、构建、虚拟环境和不应纳入的生成代码；
- 测试是否纳入要明确：纳入则建立独立 test 模块，不纳入则在 exclude 中排除；
- 分析范围与模块 include 是两层概念：项目 include 决定分析集合，模块 include 决定归属。

### 3.2 每个文件唯一 owner

- 项目 include 覆盖的每个 `.py` 文件必须恰好属于一个模块；
- 模块 include 不得重叠；
- 不得存在未归属文件；
- 不得用“先建一个兜底模块”掩盖归属问题。

### 3.3 归属决策顺序

```text
1. 显式业务归属
2. 定义文件所在业务目录
3. 主要 manager 的构造参数、字段或生命周期
4. 主要消费者的业务域
5. 仍无法判断：先补领域文档和显式归属，不创建 shared/common
```

## 4. 模块设计

### 4.1 按业务能力划分

推荐：

```text
orders          订单能力
payments        支付能力
inventory       库存能力
network         网络与协议
database        数据访问
application     业务编排
```

禁止：

```text
config/
model/
utility/
shared/
common/
misc/
contracts/
```

`config`、`model`、`utility`、`contract` 是物理代码单元或 Provider Role，不是模块本身。

### 4.2 模块 role

```text
service     业务服务、应用服务或能力 facade
adapter     外部系统适配边界
component   UI、协议组件、生命周期组件
test        独立测试或验证脚本
other       确有职责但无法归入以上类型的普通模块
```

禁止：

```text
main
entry
functional
```

入口文件可以位于任意普通模块中；入口身份只由项目级配置和 execution flow 表达。

### 4.3 模块粒度

模块应围绕清晰的能力中心组织。拆分条件：

- 有独立状态或生命周期；
- 有独立策略或变化原因；
- 有独立测试边界；
- 对外契约可独立描述；
- 与其他能力只有少量共享逻辑。

不要一个文件一个模块，也不要整个项目一个模块。

### 4.4 空能力模块

允许模块有源码边界但排除 executionOnly 和 internal Provider 后没有可见能力。

正确行为：

- 后端保留该模块、layout 和真实源码归属；
- 前端不渲染空能力模块卡片；
- 默认布局把空模块追加到可见卡片之后；
- 直接访问其模块页路由会返回项目页。

不要为了“让卡片出现”给它硬塞伪 Provider。

## 5. Provider Role 与能力面

### 5.1 七角色配置速查

| 源码形态 | 推荐 Role | 备注 |
|---|---|---|
| 常量、默认值、枚举、配置对象 | `config` | 以类型摘要展示 |
| dataclass、DTO、结果、值对象、事件 payload | `model` | 以字段摘要展示 |
| ABC、Protocol、纯接口 | `contract` | 不写具体实现 |
| 无状态纯函数、解析、格式化、算法 | `utility` | 默认 internal |
| 管理状态、生命周期、多步行为 | `manager` | 可提供公开方法 |
| DB/HTTP/socket/SDK/文件适配 | `adapter` | 外部系统边界 |
| UI、协议对象、context manager、callable/iterable | `component` | 协议或生命周期组件 |

### 5.2 角色判定

```text
contract.providerRoles 显式覆盖
  > 注释 / 装饰器 / 文档标签
  > 物理代码单元强提示
  > 结构规则
  > 命名弱提示
```

结构判定口诀：

```text
行为义务 → contract
外部系统 → adapter
协议/UI/生命周期 → component
状态与编排 → manager
静态参数 → config
运行期数据 → model
无状态内部逻辑 → utility
```

### 5.3 providerRoles 使用规则

优先依赖现有结构/命名推断：`Store/Repository/Client` 通常为 adapter，`Controller/Service/Manager` 通常为 manager，`Handler/Server/Cli` 通常为 component。只有推断仍与真实职责不符时才写显式 role。

只在以下情况写显式 role：

- 结构推断与真实业务职责明显不符；
- 同一物理代码单元中存在多种职责，需要明确能力边界；
- 项目框架惯例使自动推断无法识别；
- 已有领域文档对角色有明确约定。

不要：

- 给所有自由函数批量写 `utility` 来隐藏；
- 用 role override 代替 `defaultFreeFunctionSurface` / `apiExposure`；
- 把 `entry` 写入 providerRoles；
- 将 `providerVisibility` 当作能力隐藏的唯一开关。

### 5.4 apiExposure

单 callable 的公开/内部例外：

```json
{
  "contract": {
    "apiExposure": {
      "src.app.internal_helper": "internal",
      "src.network.codec.encode": "public"
    }
  }
}
```

优先级：

```text
executionOnlyCallables
  > apiExposure=internal
  > 显式 Provider Role = utility
  > 显式 public 标签 / config public exposure
  > 显式非 utility Provider Role
  > defaultFreeFunctionSurface=internal
  > defaultFreeFunctionSurface=capability
  > 跨模块调用证据（仅 auto）
  > internal
```

注意：

- `_name` 默认 internal；
- 非下划线、无标注默认 public，但不自动等于模块能力；
- `__init__` 只作为构造签名；
- 协议能力由 `__enter__` / `__exit__` / `__call__` / `__iter__` 等合成；
- 序列协议当前不进入能力模型。

## 6. 模块级自由函数

### 6.1 三种表面

```text
capability  进入模块能力面，可作为公开 API
internal    模块内部实现，不进入能力面，不承担执行流身份
execution   只用于执行流入口/编排，不进入能力面
```

### 6.2 defaultFreeFunctionSurface

```json
{
  "id": "terminal-ui",
  "role": "component",
  "defaultFreeFunctionSurface": "internal"
}
```

允许值：

```text
auto        默认；强证据才升级为 capability
internal    未显式公开的自由函数默认 internal
capability  未显式 internal 的自由函数默认 capability
```

规则：

- 只影响模块级自由函数，不影响类方法；
- `executionOnlyCallables` 始终最高优先级；
- `apiExposure` 可做单函数例外；
- `auto` 下的强证据包括显式 public API 标签、config public exposure、跨模块调用；
- 不确定时使用 `auto` 或 `internal`，不要默认 `capability`。

### 6.3 判定表

| 事实 | 推荐配置 |
|---|---|
| 稳定对外 API，有明确 consumer | `capability` 或单函数 public |
| 只被同模块调用 | `internal` |
| 解析/渲染/格式化 helper | `internal` |
| 只在 execution flow 中出现 | `executionOnlyCallables` |
| 跨模块调用但模块有大量内部 helper | `auto` + 单函数 public |
| 整个模块自由函数都是内部实现 | `defaultFreeFunctionSurface: "internal"` |
| 整个模块自由函数都是公开 API | `defaultFreeFunctionSurface: "capability"` |

不构成 capability 证据的信号：

- 函数名没有下划线；
- 带控制流；
- 调用项目内类；
- 位于能力模块；
- Python 能 import。

## 7. 入口与执行流配置

### 7.1 entrypoints 与 executionEntrypoints

```json
{
  "entrypoints": ["src.app.main:main"],
  "executionEntrypoints": ["src.app.cli:AppCli.run"]
}
```

- `entrypoints` 是项目分析根；
- `executionEntrypoints` 是主流程叙事起点；
- 省略 `executionEntrypoints` 时回退到 `entrypoints`；
- 支持自由函数和类方法；
- 引用格式为 `module.path:qualname`；
- 入口状态不参与 Provider Role 或模块 role 判定。

### 7.2 executionOnlyCallables

当 callable 属于模块源码，但只作为流程入口或流程内部编排单元：

```json
{
  "id": "app",
  "name": "应用入口与编排",
  "include": ["src/app/**"],
  "role": "service",
  "executionOnlyCallables": [
    "src.app.main:main",
    "src.app.main:run_client",
    "src.app.main:run_server",
    "src.app.cli:AppCli.run"
  ],
  "defaultFreeFunctionSurface": "internal"
}
```

规则：

- 支持自由函数和类方法；
- 仍保留在源码、CallSite、FunctionDetail 和执行流中；
- 不进入 `providedApis`、`apiProviders`、`moduleComposition`、Provider 计数和能力卡；
- 方法所属类 Provider 保留，只从类 API 中移除该方法；
- 被其他模块调用的 callable 要复核是否其实是公开能力；
- 不得把整个模块从 `modules` 删除来代替 callable 级声明；
- 不得为 executionOnly callable 再配置 Provider Role；
- 不得把普通内部 helper 写入该字段，内部 helper 使用 internal exposure。

`executionOnly` 与 `internal` 的区别：

```text
executionOnly → 执行流入口/编排单元，出现在主流程
internal      → 模块内部实现，不承担流程入口语义
```

## 8. 一级接口 scope

配置：

```json
{
  "flowScopes": {
    "enabled": true,
    "roots": ["src.app.main:server", "src.app.main:client"],
    "autoDetect": true,
    "maxScopesPerFlow": 6,
    "maxNodesPerScope": 24,
    "maxEdgesPerScope": 32
  }
}
```

字段语义：

| 字段 | 含义 | 默认 |
|---|---|---|
| `enabled` | 是否生成一级接口 scope | 配置对象存在时默认 true |
| `roots` | 显式 scope root，`module:qualname` 或 canonical function id | `[]` |
| `autoDetect` | 是否从主流程可见 free_function 中保守发现候选 | `false` |
| `maxScopesPerFlow` | 每条 flow 的 scope 上限 | `6`，上限 20 |
| `maxNodesPerScope` | 单 scope 节点上限 | `24`，上限 80 |
| `maxEdgesPerScope` | 单 scope 边上限 | `32`，上限 120 |

硬性约束：

- scope root 必须是 `free_function` 编排 callable；
- `interface` 节点永远不能生成 scope；
- `executionOnlyCallables` 可成为显式 root；
- 自动候选必须同模块、至少触达一个外部能力接口、至少有一个控制结构、未超预算且非直接递归；
- 显式 roots / executionOnly 优先级高于自动候选；
- scope 深度固定为 1，scope 内不递归生成 scope；
- 预算截断必须写入 scope diagnostics；
- 路由为 `#/flow/<flowId>/scope/<nodeId>`。

## 9. 动态分发与候选旅程

### 9.1 dispatchHints

```json
{
  "dispatchHints": [
    {
      "function": "src.app.main:main",
      "expression": "handlers[mode]",
      "occurrence": 1,
      "candidates": [
        "src.app.handlers:handle_a",
        "src.app.handlers:handle_b"
      ],
      "complete": true,
      "reason": "config"
    }
  ]
}
```

字段：

| 字段 | 含义 |
|---|---|
| `function` | 发生动态分发的函数引用 |
| `expression` | 可读的分发表达式，用于定位和展示 |
| `occurrence` | 同一函数内同类分发第几次出现，从 1 开始 |
| `candidates` | 候选函数引用 |
| `complete` | 是否确认候选集完整 |
| `reason` | 配置来源或完整性说明 |

规则：

- 先尝试用显式调用、策略对象或映射表消除动态分发；
- 无法消除时再写 hint；
- 不完整候选必须 `complete: false` 并说明原因；
- 不得用 hint 把 unresolved 调用伪装成确定边；
- 新配置使用顶层 `dispatchHints`，不要生成 `mainFlow.dispatches`。

### 9.2 dispatchCandidates

```json
{
  "dispatchCandidates": {
    "enabled": true,
    "completeOnly": true,
    "maxScopesPerDispatch": 16,
    "maxScopesPerFlow": 32,
    "maxNodesPerScope": 24,
    "maxEdgesPerScope": 32
  }
}
```

字段语义：

| 字段 | 含义 | 默认 |
|---|---|---|
| `enabled` | 是否生成候选旅程 | `false` |
| `completeOnly` | 只接受完整候选集 | `true` |
| `maxScopesPerDispatch` | 单个 dispatch 的候选 scope 上限 | `16`，上限 40 |
| `maxScopesPerFlow` | 单 flow 候选 scope 总上限 | `32`，上限 100 |
| `maxNodesPerScope` | 单候选 scope 节点上限 | `24`，上限 80 |
| `maxEdgesPerScope` | 单候选 scope 边上限 | `32`，上限 120 |

规则：

- 默认关闭，仅在需要浏览完整候选旅程时开启；
- dispatch 节点仍是主流程原子路由边界；
- 每个候选以真实 `free_function` 为 root 生成 depth=1 scope；
- 候选 scope 内不递归生成 dispatch group；
- 截断写入 `dispatchGroups[].diagnostics` 和 `omittedCandidateIds`；
- 路由为 `#/flow/<flowId>/dispatch/<nodeId>/candidate/<candidateScopeId>`。

## 10. 标准配置模板

```json
{
  "projectName": "example",
  "language": "python",
  "include": ["src/**/*.py"],
  "exclude": [
    "**/__pycache__/**",
    "**/.venv/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**"
  ],
  "entrypoints": ["src.app.main:main"],
  "executionEntrypoints": ["src.app.cli:AppCli.run"],
  "modules": [
    {
      "id": "app",
      "name": "应用入口与编排",
      "include": ["src/app/**"],
      "note": "入口、启动关闭与顶层业务编排。",
      "color": "#f59e0b",
      "role": "service",
      "defaultFreeFunctionSurface": "internal",
      "executionOnlyCallables": [
        "src.app.main:main",
        "src.app.cli:AppCli.run"
      ]
    },
    {
      "id": "orders",
      "name": "订单能力",
      "include": ["src/orders/**"],
      "note": "订单模型、订单管理与库存适配协作。",
      "color": "#60a5fa",
      "role": "service"
    }
  ],
  "dispatchHints": [],
  "flowScopes": {
    "enabled": false,
    "roots": [],
    "autoDetect": false,
    "maxScopesPerFlow": 6,
    "maxNodesPerScope": 24,
    "maxEdgesPerScope": 32
  },
  "dispatchCandidates": {
    "enabled": false,
    "completeOnly": true,
    "maxScopesPerDispatch": 16,
    "maxScopesPerFlow": 32,
    "maxNodesPerScope": 24,
    "maxEdgesPerScope": 32
  },
  "contract": {
    "providerRoles": {},
    "apiExposure": {},
    "publicTags": ["公开API", "公开 API", "public API", "@public"],
    "internalTags": ["内部API", "内部 API", "internal API", "@internal"]
  },
  "limits": {
    "maxFunctions": 2000,
    "maxStepsPerFunction": 300,
    "maxDataDepsPerFunction": 200
  }
}
```

模板只包含当前字段。项目没有对应需求时，可省略可选域；不要携带旧字段。

## 11. 生成后验证

### 11.1 命令

```bash
python3 -m archmap build <project> --config <config> --out <output>
python3 -m archmap check <output>/architecture.json
```

### 11.2 Bundle 级检查

- `schemaVersion == "6.4"`；
- `stats.providerRoles` 只包含七角色；
- 不存在 `providerRole == "entry"`；
- 每条 execution flow 恰好一个 `entry` 节点；
- `projectGraph.flowCards` 数量与 execution flows 一致；
- `projectGraph.layout.nodes` 同时包含 flow cards 和 module cards；
- 空能力模块仍在 `projectGraph.modules` 与 `layout.nodes` 中，但不在 `capabilityModuleIds` 中；
- flow card 的 `flowId` 可解析；
- `executionOnlyCallables` 与 internal 自由函数不出现在 `providedApis` / `apiProviders` / 角色计数中；
- 每个自由函数 detail 有 `functionSurface` 与 `functionSurfaceSource`；
- `freeFunctionSurfaceCounts` 与三个自由函数 ID 列表一致；
- executionOnly callable 仍有 `functionDetails` 和 execution flow 引用；
- scope / dispatch group 的交叉引用、深度、候选覆盖和预算诊断通过校验；
- diagnostics 为 0，或每条 warning 都有明确原因。

### 11.3 机器审计

```bash
# 1. 检查仍被识别为 manager 的自由函数
jq '.moduleGraphs[]
  | {moduleId,
     managerFunctions: [
       .nodes[]
       | select(.kind == "function" and .providerRole == "manager")
       | .id
     ]}' <output>/architecture.json

# 2. 检查公开自由函数 API
jq '[.moduleGraphs[].providedApis[]
  | select(.providerKind == "function")
  | {providerId, display, providerRole}]' <output>/architecture.json

# 3. 检查自由函数表面与空能力模块
jq '{capabilityFunctions: [.moduleGraphs[].capabilityFreeFunctionIds[]],
     internalFunctions: [.moduleGraphs[].internalFreeFunctionIds[]],
     executionFunctions: [.moduleGraphs[].executionFreeFunctionIds[]],
     emptyModules: [.projectGraph.modules[]
       | select(.capabilitySurface.hasProviders == false)
       | .id]}' <output>/architecture.json
```

期望：

- 被识别为 manager 的自由函数都能解释为真实对外能力；
- 解析、渲染、格式化 helper 不在公开自由函数 API 中；
- executionOnly callable 都能在 execution flow 中找到；
- 空能力模块不出现在前端渲染集合中；
- 没有重复归属、未归属文件或跨模块重复模型。

### 11.4 人工检查

- 项目页没有无意义模块卡片；
- flow card 与 module card 同层展示；
- 模块页不依赖调用连线才能理解；
- 每个公开 API 能追溯到 Provider；
- 每个 config/model 有明确模块归属；
- 没有为了生成成功而设置兜底模块；
- 生成产物未被手工修改。

## 12. 常见错误配置

| 错误 | 后果 | 正确做法 |
|---|---|---|
| `mainModule` | 旧主模块语义，产生 deprecation warning | 删除；使用项目级 entrypoints |
| `kind: "main"` / `kind: "functional"` | 旧模块类型，产生 deprecation warning | 删除；使用模块 `role` |
| 模块 `role: "entry"` | 入口语义混入模块职责 | 使用 service/adapter/component/test/other |
| `providerRoles: {"X": "entry"}` | 无效 Provider Role | 删除；用 entrypoints 定义流程入口 |
| 建 `contracts` / `shared` / `common` 模块 | 模块边界失效 | 模型/配置归入其服务的业务模块 |
| 模块 include 重叠 | 文件归属歧义 | 保证每文件恰好一个模块 |
| 把内部 helper 写进 `executionOnlyCallables` | 产生“不在执行流”警告且语义错误 | 用 internal exposure 或模块默认 internal |
| 给 executionOnly callable 配 Provider Role | 能力面语义冲突 | 只保留 executionOnly 声明 |
| 用 `providerRoles=utility` 批量隐藏 helper | 角色字段被当成隐藏开关 | 用 `defaultFreeFunctionSurface=internal` 或 `apiExposure=internal` |
| 默认面 capability 但想隐藏单个 helper | 默认面无法表达单函数例外 | 给该 helper 配 `apiExposure=internal` |
| 删除模块代替 callable 声明 | 误伤模块边界与其他能力 | 在所属模块内写 executionOnlyCallables |
| 伪造 entrypoint 或 dispatch candidate | 产生无法验证的架构事实 | 保留 unresolved 或补源码证据 |
| 手工伪造 flowCards / layout | 与 execution flow 不一致 | 由构建流程派生 |
| 把模块调用边当作模块边界 | 模块页又变成调用图 | 调用关系保留在 CallSite / Method Detail |

## 13. AI 输出契约

生成或修改配置后，AI 必须汇报：

```text
配置变更：
  - <新增/删除的模块及文件归属>
  - <entrypoints / executionEntrypoints>
  - <executionOnlyCallables>
  - <defaultFreeFunctionSurface / apiExposure / providerRoles>
  - <flowScopes / dispatchHints / dispatchCandidates>

证据：
  - <源码文件与能力边界依据>
  - <动态分发或未解析边界>

验证：
  - build:
  - check:
  - diagnostics:
  - 空能力模块:
  - 自由函数表面审计:

风险：
  - <仍无法静态解析的调用或需要人工确认的归属>
```

## 14. Definition of Done

配置只有同时满足以下条件才算完成：

1. 每个目标源码文件恰好属于一个模块。
2. 模块 include 不重叠，exclude 合理。
3. 模块 role 只使用五种普通角色。
4. Provider Role 只使用七角色，`entry` 未出现在角色字段中。
5. 自由函数表面只有 capability/internal/execution 三种，且与事实一致。
6. executionOnlyCallables 只包含真实流程入口或编排 callable。
7. entrypoints / executionEntrypoints 可解析且语义清楚。
8. 动态分发候选完整性被显式标记。
9. flowScopes / dispatchCandidates 只在需要时启用，预算和截断可解释。
10. `archmap build` 成功，`archmap check` 通过，diagnostics 为 0 或有明确原因。
11. 项目页、flow 页、模块页和 Method Detail 能按预期导航。
12. 配置没有旧字段、伪事实或手工 bundle 修补。
