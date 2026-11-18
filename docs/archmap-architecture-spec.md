# ArchMap 架构与编码规范

> 状态：P2.3 规范已落盘，P2.4/P3/P4 已按该规范完成<br>
> 版本：ArchMap 1.9.0 / bundle schema 4.1<br>
> 日期：2026-11-18<br>
> 适用范围：ArchMap 自身源码、后续语言前端和架构分析扩展。

## 1. 两层分类：物理代码单元与逻辑 Provider Role

ArchMap 使用两层分类，禁止把两者混为一谈：

```text
物理代码单元：config / model / manager / utility
逻辑 Provider Role：config / model / manager / entry / adapter / component / contract / utility
```

物理文件决定代码放在哪里；逻辑角色决定它在架构图中代表什么。

```text
物理代码单元是“存储位置”
Provider Role 是“架构语义”
Visibility 是“是否进入默认架构视图”
```

### 1.1 物理文件规范

```text
<domain>/<domain>_config.py     静态定义、默认值、常量、枚举
<domain>/<domain>_model.py      数据结构、DTO、结果、契约接口
<domain>/<domain>_manager.py    状态、生命周期、行为编排、入口代理
<domain>/<domain>_utility.py    无状态内部辅助逻辑
```

为保持文件系统可控，默认只使用这四个物理类型。

允许的例外：

- `main.py` / `cli.py` / `__main__.py` 作为应用入口文件；
- 当接口非常多时，可以增加 `<domain>_contract.py`，物理上归 `model` 层；
- 当外部适配器非常多时，可以增加 `<domain>_adapter.py`，物理上归 `manager` 层；
- 当 UI/协议组件非常多时，可以增加 `<domain>_component.py`，物理上归 `manager` 层。

例外文件不得改变逻辑角色。

## 2. 八角色的精确语义

判定优先级：

```text
entry > contract > adapter > component > manager > config > model > utility
```

### 2.1 config

被动参数化系统行为的静态定义。

包括：

- 常量；
- 默认值；
- 枚举；
- 配置 schema / 配置对象；
- 标签词表；
- 策略表；
- 环境参数。

不是：

- 运行期数据记录；
- 行为契约；
- 有状态管理器；
- 业务编排。

物理归属：`<domain>_config.py`。

展示：配置类型卡片或静态摘要。

### 2.2 model

承载运行期数据形状和结果的值对象。

包括：

- dataclass / DTO / TypedDict / NamedTuple；
- 分析结果；
- 调用记录；
- 领域实体；
- 值对象；
- 事件 payload。

可以有序列化、校验、转换方法，但不得承担状态管理、外部资源管理或领域编排。

物理归属：`<domain>_model.py`。

展示：类型卡片与字段表。

### 2.3 contract

定义行为义务的抽象契约，不提供具体实现。

包括：

- `abc.ABC`；
- `typing.Protocol`；
- 纯接口类；
- 抽象方法集合。

不是：

- config；
- 运行期 DTO；
- manager 实现。

物理归属：默认 `<domain>_model.py`；接口很多时使用 `<domain>_contract.py`。

展示：独立 contract 卡片；P3 中承载 `inherits` / `implements` 关系。

### 2.4 utility

无状态、无生命周期、无领域编排的内部实现函数。

包括：

- 纯转换；
- 算法；
- AST 遍历；
- 格式化；
- 字符串/路径处理；
- 解析和校验辅助。

强约束：

- utility 默认是 internal；
- utility 不进入默认项目页/模块页；
- utility 不作为模块公开 API；
- utility 仍是事实层数据，供 Method Detail、callSites 和 P4 impact/trace 使用；
- 如果需要模块公开能力，应由 manager 或 entry 暴露，而不是把 utility 直接公开。

物理归属：`<domain>_utility.py`。

### 2.5 manager

管理领域状态、生命周期和行为编排的 Provider。

包括：

- 管理 model/config 实例；
- 组织多步业务；
- 协调多个 Provider；
- 持有领域状态或资源生命周期；
- 对外提供稳定的开发者 API。

不是：

- 数据形状；
- 外部系统适配器；
- 无状态工具；
- 外部输入边界。

物理归属：`<domain>_manager.py`。

展示：manager 卡片与公开方法/协议能力。

### 2.6 entry

外部世界进入系统的最外层触发器。

包括：

- CLI `main()`；
- `if __name__ == "__main__"`；
- HTTP route；
- Celery task；
- 框架启动函数；
- 消息消费者入口。

entry 只做：

- 接收原始外部输入；
- 最小解析、校验、反序列化；
- 委托给 manager；
- 序列化输出。

entry 不持有领域状态，不承担深层业务编排。

物理归属：`main.py`、`cli.py`、`__main__.py`，或逻辑上位于 manager 文件中的入口函数。

展示：入口节点；P4 中作为 user surface 起点。

### 2.7 adapter

外部系统边界的具体实现，把外部接口适配成内部 contract。

包括：

- 数据库 Repository；
- Redis / S3 / HTTP 客户端；
- socket / TCP 连接；
- 文件系统适配器；
- 第三方 SDK 包装；
- 消息队列适配器。

adapter 是 manager 的特化，但逻辑角色保持独立。

物理归属：默认 `<domain>_manager.py`；适配器很多时使用 `<domain>_adapter.py`。

展示：adapter 节点，表示系统外部边界。

### 2.8 component

通过协议或生命周期被消费的、可复用的自包含运行期组件。

包括：

- context manager；
- callable 对象；
- iterable 对象；
- UI widget / screen / controller；
- 通过协议暴露生命周期的组件。

component 不是通用 manager 的同义词。无法明确判断时：

- 业务编排优先判 manager；
- 外部 IO 优先判 adapter；
- 纯逻辑优先判 utility；
- 行为契约优先判 contract。

物理归属：默认 `<domain>_manager.py`；组件很多时使用 `<domain>_component.py`。

展示：component 节点与协议能力。

## 3. 依赖方向

推荐依赖方向：

```text
config ← model ← manager
utility ← manager
contract ← manager
entry → manager
adapter → contract
```

严格规则：

- utility 只依赖标准库、底层 utility 和必要的纯数据模型；
- utility 不依赖 manager；
- config 不依赖 manager；
- model 不依赖 manager；
- manager 可依赖 config/model/contract/utility/adapter；
- entry 只依赖 manager；
- manager 之间通过明确接口或上层编排协作，禁止循环依赖；
- adapter 通过 contract 被 manager 使用。

## 4. 主模块、功能模块与主流程

项目必须区分两类模块：

```text
主模块      唯一组合根，承载入口与顶层编排；其能力页展示 Provider/API/类型关系
功能模块    暴露 Provider/Capability；数量允许为 0..N
```

约束：

- 恰好一个 `moduleKind=main`。
- 不为了满足模块数量虚造功能模块。
- 模块不拥有输入/输出端口；依赖和能力分别由调用证据与 `providedApis` 表达。
- P5 执行流 `flowRole` 独立于 Provider Role，不得因主流程分析改变功能模块 API 分类。
- P5 执行流节点：entry / exit / free_function / interface / branch / multi_branch / loop / break / continue / return / dispatch。
- P5 执行流边只表达控制连接；`mainFlows` 调用投影数据保留但默认不展示。
- dispatch 候选需要显式完整性标记，无法推断时保留 unresolved。
- **主流程边界**：P5 执行流只展开主模块入口函数控制骨架；跨入功能模块时只物化 canonical interface，不穿透其实现。
- 功能模块边界节点 `expandable=false`，无图内下钻；内部 utility 不进入主流程。
- 主流程是项目级执行叙事，全量跨模块调用与内部实现分别由模块关系视图、Method Detail 和 P4 trace 承担。

项目页展示独立主流程入口与全部模块卡片。主模块和功能模块统一使用模块能力页；主流程页只展示执行流，不嵌入模块契约或调用总览。

```text
Project
└─ Module
   ├─ Submodule
   │  ├─ config/model/contract providers
   │  ├─ manager/adapter/component/entry providers
   │  └─ internal utility implementation
   └─ Submodule
```

领域拆分条件：

- 存在独立状态和生命周期；
- 存在独立策略或规则；
- 变更原因不同；
- 测试边界不同；
- 对外契约可独立描述；
- 与其他领域只有少量共享逻辑。

不得仅因为文件数量多而拆子模块。

共享内部工具进入共享 utility 子模块，不强行归属于某个 manager。

## 5. 可见性

```text
providerRole        职责语义
providerVisibility  public / internal
ownerProviderId     内部实现归属的 facade manager / owner provider
presentationGroup   public_surface / internal_implementation
```

默认规则：

- utility 一律 internal；
- entry/manager/adapter/component/contract 的公开 Provider 可进入默认视图；
- config/model 以类型卡片展示；
- internal 实现保留在事实层，不进入项目页/模块页默认视图；
- 项目页角色计数只统计公开 Provider；
- 内部函数仍保留在 `functionDetails` / `callSites` / callers/callees 中，供 P4 impact/trace 使用；
- 单个 facade manager 拥有的阶段函数通过 `ownerProviderId` 归属，不生成独立卡片。

## 5.1 Facade manager 约定

每个领域只暴露少量 facade manager，例如：

```text
PipelineManager
FrontendManager
PythonFrontend
GraphManager
ValidationManager
RenderManager
```

领域的阶段函数应归入对应 facade 的内部 utility：

```text
PythonFrontend
  ├─ analyze_project
  ├─ collect_call_sites
  ├─ build_function_details
  ├─ build_capabilities
  ├─ build_provider_roles
  └─ discover_sources

GraphManager
  └─ build_bundle / collect_calls / find_entrypoints / semantic_fingerprint

ValidationManager
  └─ validate_bundle

RenderManager
  └─ render_html
```

这些函数默认：

```text
providerRole = utility
providerVisibility = internal
ownerProviderId = 对应 facade manager
```

不允许因为它们是 public 函数名而在项目页生成独立 manager 卡片。

## 6. 识别与发现策略

解析器采用双模式：

1. **规范模式**：文件名后缀和目录结构提供确定性的代码单元类型；
2. **兼容模式**：不符合规范时回退到通用 AST 启发式，并输出 diagnostics。

P2.3 先完成代码迁移，不在迁移过程中反复重写识别器。迁移完成后，再根据本规范实现规范模式识别：

```text
path + file suffix → code unit type
class/function shape → provider role refinement
entrypoint/config/contract/protocol evidence → derived role
visibility → default presentation
```

禁止继续使用“有循环 + 调用一个项目类 = manager”这类宽松规则作为主要判定依据。

## 7. P2.3 迁移原则

- 先冻结契约，再迁移代码；
- 先 config/model，再 utility，再 manager，最后 entry；
- 旧 import shim 最终已删除，所有内部引用使用新目录；
- CLI、bundle schema、HTML 行为保持稳定；
- utility 默认不进入主视图；
- 迁移完成后更新自举配置和文档；
- P3/P4 已在 P2.3 验收后完成，并继续遵守本规范。
