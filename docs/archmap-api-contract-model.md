# ArchMap API 契约模型

> 版本：ArchMap 2.6.1 / bundle schema 6.4<br>
> 日期：2026-11-19<br>
> 文档性质：当前 API 契约模型<br>
> 目标：描述模块/类/函数对外提供什么能力，并保持语言中立的 Provider + Capability 模型。

## 1. 产品边界

ArchMap 的契约视图只回答：

```text
模块对外提供什么能力？
类作为 Provider 提供什么能力？
函数的 API 暴露级别是什么？
```

它不回答：

- 类内部方法如何互相调用；
- 类内方法图；
- 语句级执行流；
- 类焦点页。

类焦点页和类内方法图**不在当前产品计划中**。类内部实现只通过 Method Detail 的源码与 callers/callees 查看。

## 2. Provider + Capability

```text
Provider     提供者：class / function
Capability   能力：function / method / context_manager / ...
Exposure     暴露级别：public / internal
Source       判定来源：docstring / comment / decorator / config / entrypoint / protocol / naming
Evidence     证据：函数 ID、文件、行号、注释或装饰器
```

示例：

```json
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
```

### 2.1 Provider Role

仅有 Capability 还不够；还需要表达 Provider 在模块中的职责：

```text
config    类型定义、字段、默认值、常量表、枚举
model     运行期数据记录、DTO、分析结果
manager   管理 model/config 实例，组织行为，对外暴露 API
adapter   外部系统适配
component UI / 协议组件
contract  抽象类、Protocol、接口
utility   纯函数 / 助手
```

Provider 节点与能力字段：

```json
{
  "providerRole": "manager",
  "roleSource": "structure",
  "roleConfidence": "medium"
}
```

模块组合字段：

```json
{
  "moduleComposition": {
    "config": ["cls:..."],
    "model": ["cls:..."],
    "manager": ["cls:..."],
    "adapter": ["cls:..."],
    "component": ["cls:..."],
    "contract": ["cls:..."],
    "utility": ["fn:..."]
  },
  "providerRoleCounts": {
    "config": 0,
    "model": 0,
    "manager": 1,
    "adapter": 0,
    "component": 0,
    "contract": 0,
    "utility": 0
  }
}
```

`roleSource` 取值：`config` / `docstring` / `comment` / `decorator` / `entrypoint` / `structure` / `naming` / `surface`；`roleConfidence` 为 `high` / `medium` / `low`。

`providerVisibility` 取值为 `public` / `internal`：

- utility 恒为 internal；
- 默认项目页/模块页只显示 public Provider；
- internal Provider 仍保留在 FunctionDetail、CallSite 和 impact/trace 事实层；
- `publicModuleComposition` / `publicProviderRoleCounts` 是 UI 使用的公开投影；
- `ownerProviderId` 指向内部 utility 归属的 facade manager；
- 单个 facade manager 的阶段函数不进入 `providedApis` / `apiProviders`。

判定顺序：

```text
config.providerRoles 显式覆盖
  > 注释 / 装饰器 / JSDoc
  > 结构规则
  > 命名弱提示
```

展示与投影规则：

- `manager` / `component` / `contract`：展示方法/协议能力；
- `config` / `model`：展示类型卡片、字段摘要、默认值，不把 `as_dict()` 等序列化方法当模块 API；其 `providedApis` 必须为空；
- `adapter`：展示适配器入口能力；
- `utility`：默认 internal，不进入项目页/模块页默认视图；仅保留为事实层实现细节；
- `typeSummary` 仅对 config/model 类输出，包含 `kind`、`fieldCount` 与字段的 `name` / `annotation` / `default` / `kind`；
- 模块级自由函数与类都进入 `moduleComposition`，类方法不单独作为 Provider。

`FunctionInfo` 属于 `model`；`ProjectConfig` / `ModuleConfig` 属于 `config`；`CallResolver` / `PythonFrontend` / `MenuSystem` / `Database` 属于 `manager`。

入口状态由项目级 entrypoints / execution flow 承担，不修改 Provider Role。execution flow 使用标准 `entry` 节点和原子 callable/interface 节点；动态分发候选保留在 dispatch 节点详情中，完整候选可投影为独立候选 scope。

`defaultFreeFunctionSurface` 控制模块级自由函数的默认能力边界：`auto` 仅在显式公开 API 或跨模块调用等强证据下进入能力面；`internal` / `capability` 声明模块默认面，单函数继续用 `apiExposure` 例外。自由函数 FunctionDetail 输出 `functionSurface` / `functionSurfaceSource`。

`executionOnlyCallables` 声明属于模块源码边界、但不属于能力 Provider 面的 callable。被声明的自由函数/方法不进入 `providedApis`、`apiProviders`、`moduleComposition` 或 Provider 角色计数；仍保留在 `functionDetails`、`callSites` 和执行流节点中。类方法被排除时，其 owner class Provider 保留，但该方法从类 API 中移除。模块新增 `capabilitySurface`；能力为空时后端保留模块与 layout，前端不渲染模块卡。

## 3. 暴露级别判定

优先级：

```text
config 显式覆盖
  > 装饰器标记
  > docstring / 前置注释标签
  > entrypoints
  > protocol 推导
  > 命名规则
```

字段：

```json
{
  "apiExposure": "public | internal",
  "apiExposureSource": "docstring | comment | decorator | config | entrypoint | protocol | naming",
  "apiExposureConfidence": "high | medium | low"
}
```

默认标签词表可通过 `contract.publicTags` / `contract.internalTags` 扩展：

```text
公开API / 公开 API / public API / API: public
内部API / 内部 API / internal API / API: internal
```

默认命名规则：

- `_name` → `internal`
- 非下划线、无标注 → `public`，来源 `naming`
- `__dunder__` → 不进入普通方法 API；由协议能力消费
- `__init__` → 不进入方法 API；作为构造签名

## 4. 支持的 Capability

当前支持的 Capability：

| kind | 来源 | 示例 |
|---|---|---|
| `function` | 自由函数 | `get_display_width(text)` |
| `method` | 非魔术公开方法 | `MenuSystem.run()` |
| `context_manager` | `__enter__` + `__exit__` | `with Spinner(message='加载中')` |
| `async_context_manager` | `__aenter__` + `__aexit__` | `async with ...` |
| `callable` | `__call__` | `CallableThing(label='x')` |
| `iterable` | `__iter__` | `for item in IterableThing()` |

`__init__`、`__enter__`、`__exit__` 等只作为证据，不作为独立公开 API。

## 5. 明确延期：序列协议

以下能力**当前不进入能力模型**，避免靠启发式误报：

```text
__len__
__getitem__
__setitem__
__contains__
__reversed__
切片 / 索引签名
ArkTS 的 length / index signature
```

延期原因：

- 需要类型和形状语义；
- 静态分析难以确认对象是否真的作为序列契约使用；
- 容易产生低置信度噪声。

后续如需支持，应以独立协议扩展形式加入，并具备明确证据、置信度和配置入口。

## 6. 构造签名

`__init__` 不进入 API 列表，但构造签名是使用契约的一部分：

```json
{
  "usage": {
    "constructor": {
      "functionId": "fn:thread_waiting.Spinner.__init__",
      "signature": "Spinner(message: str = '加载中')"
    },
    "protocols": ["context_manager"]
  }
}
```

类卡片展示构造签名；上下文管理器能力使用构造签名合成 `with Spinner(...)`。

## 7. 模块 API Provider

模块级保留扁平 `providedApis` 兼容投影，同时提供分组：

```json
{
  "apiProviders": [
    {
      "providerId": "cls:thread_waiting.Spinner",
      "providerKind": "class",
      "providerName": "Spinner",
      "moduleId": "async",
      "apiCount": 1,
      "apis": ["..."]
    }
  ]
}
```

模块右栏按 Provider 分组展示；项目卡片使用扁平 chips。

### 7.1 模块能力面与组合

模块图携带：

```json
{
  "executionOnlyFunctionIds": ["fn:app.main.client"],
  "capabilitySurface": {
    "hasProviders": false,
    "providerCount": 0,
    "apiCount": 0
  }
}
```

`capabilitySurface.hasProviders=false` 表示排除 executionOnly 与 internal Provider 后，模块没有前端可展示的能力 Provider。该模块仍保留在后端和 layout 中，但项目页/模块页不渲染。

模块组合：

模块除了 `apiProviders`，还应提供按角色分组的组合：

```json
{
  "moduleComposition": {
    "config": ["cls:..."],
    "model": ["cls:..."],
    "manager": ["cls:..."],
    "adapter": ["cls:..."],
    "component": ["cls:..."],
    "contract": ["cls:..."],
    "utility": ["fn:..."]
  }
}
```

项目页模块卡片展示角色数量；模块页按角色分组 Provider。

## 8. 配置

```json
{
  "contract": {
    "publicTags": ["公开API", "public API", "@public"],
    "internalTags": ["内部API", "internal API", "@internal"],
    "apiExposure": {
      "module.Symbol.method": "public"
    },
    "providerRoles": {
      "module.Symbol": "manager"
    },
    "moduleExports": {
      "module-id": ["cls:module.Symbol"]
    }
  },
  "modules": [
    {
      "id": "app",
      "executionOnlyCallables": [
        "app.main:main",
        "app.main:run_client",
        "app.main:run_server"
      ]
    }
  ]
}
```

`executionOnlyCallables` 是模块级配置，不是 Provider Role；显式声明优先于自动角色推断。未知引用、跨模块引用和重复声明必须报错。

## 9. UI 映射

- 项目页模块卡片：显示 `Provider · Capability` chips；
- 项目页模块卡片：显示模块角色与 `providerRoleCounts`；
- 模块页类卡片：config/model 显示类型卡片与字段摘要；行为型角色显示构造签名与 `providedApis` chips；
- 模块页顶部：显示 `moduleComposition` 角色计数；
- 模块页右栏：按 `apiProviders` 分组展示公开能力，并标注 Provider Role；
- 类右栏：config/model 展示 `typeSummary` 字段表；其他角色展示提供接口，内部方法只显示数量；
- 点击方法/函数能力：进入 Method Detail；
- 点击协议能力：选中对应 Provider 类节点并展示能力详情；
- executionOnly callable 不生成模块能力卡；方法详情显示 `execution:entry` / `execution:orchestrator`，不显示 Provider Role；
- `functionSurface=internal` 的自由函数不生成能力卡；方法详情显示 `surface:internal`，不显示 Provider Role；
- `functionSurface=capability` 的自由函数才按 Provider Role 进入模块能力面；
- `capabilitySurface.hasProviders=false` 的模块不渲染项目页模块卡，直接模块路由返回项目页。

## 10. ArkTS 扩展

契约模型语言中立，`graph_utility.py` / `validate_utility.py` / `render_utility.py` 及对应 Manager 不依赖 Python AST。

ArkTS frontend 负责：

| ArkTS 结构 | 契约映射 |
|---|---|
| `export function` | function provider |
| `export class` | class provider |
| `public` 成员 | public method / property capability |
| `private` / `protected` / `#field` | internal |
| JSDoc `@public` / `@internal` | exposure docstring |
| getter / setter | property capability |
| `Symbol.iterator` | iterable capability |
| `Symbol.asyncIterator` | async_iterable capability（延期评估） |
| `@Entry` / `@Component` | entrypoint，不默认作为公开 API |

ArkTS 没有 Python 的 `__enter__` / `__exit__`，因此不伪造 `context_manager`。序列协议同样延期。

## 11. 防过拟合原则

1. 不在 `graph_utility.py` 硬编码具体项目类名。
2. Exposure 规则基于通用标签、命名、配置和 entrypoint。
3. 语言差异在 frontend 内消化，neutral graph 只消费 canonical capability。
4. 测试以通用 `contracts_demo` fixture 为主，`student_system` 只做集成验收。
5. 支持中英文标签和配置扩展。
6. 不自动把全部公开实例属性当作 API。
7. 不把类内部方法图写入产品计划。


## 12. 用户交互面（User Surface）

必须区分：

```text
developer API   模块之间调用的代码契约
user surface    最终用户能感知或操作的交互面
```

示例：

- `MenuSystem.run()`：menu 模块 manager 的开发者 API，同时是 TUI 键盘菜单交互面；
- `NetworkAdapter.init_connection()`：network 模块 adapter 的开发者 API，同时是 CLI 输入提示交互面。

建议字段：

```json
{
  "audiences": ["developer", "end_user"],
  "surfaces": ["cli_input", "tui_menu", "keyboard_event", "network_endpoint"]
}
```

独立投影：

```json
{
  "kind": "cli_input",
  "display": "选择服务器/客户端并输入服务器 IP",
  "moduleId": "network",
  "evidenceFunctionIds": ["fn:student_system.network.network_manager.NetworkAdapter.init_connection"],
  "entrypointIds": ["fn:student_system.app.main.main"],
  "confidence": "medium"
}
```

项目流程规则：

- executionOnly 入口/编排 callable 不展示为模块能力 API；
- 项目页以 flow card 展示入口来源；
- `MenuSystem.run()` 属于 menu 模块 manager API，同时作为用户交互面被项目入口引用；
- 不同项目用户交互面不同，必须数据驱动、支持配置覆盖。

识别线索：

- `input()` / `print()` / `sys.stdout.write` → CLI/TUI；
- keyboard listener / event handler → keyboard event；
- socket / HTTP server → network；
- ArkTS `@Entry` / `@Component` / `@Builder` / `TextInput` / `Button` → UI；
- 沿 entrypoint 调用路径传播，带 confidence，不硬编码具体项目函数名。
