---
name: archmap-code-conventions
description: 约束被 ArchMap 分析的 Python 项目的源码结构、模块边界、七类 Provider Role、能力面、入口执行流、静态可分析性、功能备注与测试。
whenToUse: 新建、修改或重构被 ArchMap 分析的 Python 项目源码，需要让代码结构、能力边界和执行流保持清晰、可配置、可静态分析时使用。
user-invocable: true
---

# ArchMap 代码约定 Skill（archmap-code-conventions）

> 适用对象：编写或改造 Python 项目、并需要生成 ArchMap 模块配置的 AI 编码模型<br>
> 适用版本：ArchMap 2.6.0 / bundle schema 6.4<br>
> 文档性质：执行规范，不是历史说明。AI 在开始编码前必须完整阅读本文。

## 0. 目标与边界

### 0.1 一句话目标

AI 应生成**模块边界清楚、Provider 职责明确、能力面稳定、入口与执行流可分析、配置可由源码事实推导**的 Python 项目。

```text
源码事实
  → 模块与 Provider 结构
  → 模块配置
  → ArchMap 静态分析
  → 可下钻架构视图
```

架构图是源码结构的投影。**不得为了生成更好看的图而制造或隐藏代码结构。**

### 0.2 本 Skill 负责什么

- 被分析项目的目录、模块、类、函数、方法、入口和测试怎么写；
- 物理代码单元与七类 Provider Role 如何区分；
- 公共能力、内部实现、仅执行流 callable 如何划分；
- 模块配置需要哪些源码事实作为依据；
- 如何让调用关系、执行流和动态分发尽量可静态分析；
- 如何验证代码和配置符合 ArchMap 当前契约。

### 0.3 本 Skill 不负责什么

- 不修改 ArchMap 引擎、schema、validator、renderer 或 bundle 内部结构；
- 不通过伪造模块、Provider、空节点或关系来美化结果；
- 不替代项目自身的领域规则、框架约束、安全要求和发布流程；
- 不强行把运行时动态行为伪装成静态确定事实。

当业务框架要求与 ArchMap 友好性冲突时，优先保证代码正确；分析边界通过配置、注释和 diagnostics 显式表达。

如果动态分发暂时无法解析出候选，应保留 Protocol / ABC / 依赖倒置等设计，并通过 `dispatchHints.complete=false` 或 warning 说明不完整；不得为了把 diagnostics 归零而删除抽象、合并模块或改变依赖方向。

---

## 1. 开始前的强制事实盘点

AI 在写代码或改配置前，必须先回答以下问题。无法回答时先调查源码，不允许用“先建一个 utils / shared 模块”开始。

```text
1. 项目类型：CLI / Web / 桌面 / 数据处理 / 库 / 其他
2. 源码根目录与 include / exclude 范围
3. 每个源码文件唯一的业务模块归属
4. 每个模块的能力 facade / 职责中心
5. 每个类、自由函数的物理代码单元与逻辑 Provider Role
6. 哪些能力是 public，哪些是 internal，哪些仅用于执行流
7. entrypoints 与 executionEntrypoints 分别是什么
8. 是否存在动态分发、运行时注册、反射或未解析调用
9. 如何做单元测试与 archmap build/check 验证
```

输出任何代码前，先在内部形成以下映射：

```text
文件 → 模块 → Provider → Capability → 可见性 → 入口/执行流
```

---

## 2. 不可违背的硬性规则

1. 每个纳入分析的源码文件必须恰好属于一个模块，模块 include 不得重叠。
2. 模块按业务能力划分，不按 `config/`、`model/`、`utility/` 技术层划分。
3. 不得创建 `shared`、`common`、`contracts`、`misc` 等兜底模块。
4. 模块 role 只能是 `service` / `adapter` / `component` / `test` / `other`。
5. 不得使用 `main` / `entry` / `functional` 作为模块 role。
6. Provider Role 只能是七种：`config` / `model` / `manager` / `adapter` / `component` / `contract` / `utility`。
7. `entry` 不是 Provider Role；入口语义属于项目级 `entrypoints` / `executionEntrypoints` 和 execution flow。
8. 模块级自由函数必须明确落在 `capability` / `internal` / `execution` 三种表面之一。
9. `executionOnlyCallables` 只用于流程入口或流程内部编排 callable，不得用来隐藏普通 helper。
10. `providerRoles` 只用于修正真实职责，不得作为批量隐藏开关。
11. `config` / `model` 不提供普通业务方法 API；其字段和默认值通过类型摘要展示。
12. 不新增第八种 Provider Role，不把 flow 节点当作 Provider。
13. 关键业务调用尽量静态可解析；动态分发必须有显式候选和完整性声明。
14. 每个新增或修改的模块、类、函数、方法、测试必须有具体功能备注。
15. 不得手工修改生成的 `architecture.json` 或 `architecture.html` 来“修复”分析结果。

---

## 3. 架构模型

### 3.1 两层分类

```text
物理代码单元：config / model / manager / utility
逻辑 Provider Role：config / model / manager / adapter / component / contract / utility
可见性：public / internal / execution（仅模块级自由函数）
```

三者分别回答：

```text
物理代码单元：代码放在哪个文件
Provider Role：它在架构中承担什么职责
可见性：它是否进入模块能力面
```

禁止把“文件类型”“角色类型”“能力可见性”混成一个概念。

### 3.2 物理代码单元

默认目录与文件：

```text
<capability>/
├─ <domain>_config.py      常量、默认值、枚举、配置对象、策略表
├─ <domain>_model.py       dataclass / DTO / TypedDict / 结果 / 值对象 / contract
├─ <domain>_manager.py     状态、生命周期、行为编排、入口代理
└─ <domain>_utility.py     无状态内部辅助逻辑
```

允许的例外：

- `main.py` / `cli.py` / `__main__.py`：应用入口文件；
- `<domain>_contract.py`：接口很多时使用，物理上归 `model` 层；
- `<domain>_adapter.py`：外部适配器很多时使用，物理上归 `manager` 层；
- `<domain>_component.py`：UI/协议组件很多时使用，物理上归 `manager` 层。

例外文件不能改变逻辑角色。禁止用 `helpers.py`、`misc.py`、`common.py`、`utils.py` 作为无职责兜底文件。

### 3.3 七类 Provider Role

| Role | 负责 | 不负责 | 默认呈现 |
|---|---|---|---|
| `config` | 静态参数、常量、默认值、枚举、策略表 | 运行期数据、业务编排 | 类型/配置摘要 |
| `model` | dataclass、DTO、值对象、事件 payload、结果模型 | 状态管理、外部资源、业务编排 | 类型/字段摘要 |
| `contract` | ABC、Protocol、纯接口、抽象方法集合 | 具体实现、DTO | 契约能力与继承关系 |
| `utility` | 无状态转换、算法、AST 遍历、格式化、路径处理 | 模块公开 API、状态、生命周期 | 默认 internal |
| `manager` | 管理 model/config、组织多步行为、暴露稳定业务 API | 数据形状、外部 IO 细节 | 公开能力 |
| `adapter` | 数据库、HTTP、socket、文件、SDK、消息队列适配 | 领域规则、入口解析 | 外部边界能力 |
| `component` | UI、协议对象、context manager、callable/iterable 组件 | 通用 manager、纯工具 | 协议/组件能力 |

角色判定顺序：

```text
显式 contract.providerRoles 覆盖
  > 注释 / 装饰器 / 文档标签
  > 物理代码单元强提示
  > 结构规则（contract > adapter > component > manager > config > model > utility）
  > 命名弱提示
```

判定口诀：

```text
行为义务 → contract
外部系统 → adapter
协议/UI/生命周期 → component
状态与编排 → manager
静态参数 → config
运行期数据 → model
无状态内部逻辑 → utility
```

### 3.4 依赖方向

```text
config ← model ← manager
utility ← manager
contract ← manager
adapter → contract
```

强制约束：

- utility 只依赖标准库、底层 utility 和必要的纯数据模型；
- utility 不依赖 manager；
- config 不依赖 manager；
- model 不依赖 manager；
- manager 可依赖 config/model/contract/utility/adapter；
- 模块之间通过明确接口协作，禁止循环依赖；
- 入口层只做参数解析、启动/关闭、流程编排和结果输出，不承载深层业务规则。

---

## 4. 模块设计

### 4.1 按业务能力划分

推荐：

```text
orders/        订单能力
payments/      支付能力
inventory/     库存能力
network/       网络与协议
database/      数据访问
```

避免：

```text
config/
model/
utils/
shared/
common/
misc/
contracts/
```

拆分模块的合理理由：

- 有独立业务职责；
- 有独立状态或生命周期；
- 有独立策略或变化原因；
- 有独立测试边界；
- 有可独立描述的对外能力；
- 与其他能力只有少量共享逻辑。

不要仅因为文件多就拆模块，也不要因“方便导入”就建共享桶。

### 4.2 模块粒度

一个模块应有清楚的能力中心，通常围绕一个 facade manager 或一个明确的能力边界组织：

```text
network
├─ NetworkAdapter       adapter
├─ ProtocolMessage      model
├─ ProtocolCodec        manager
└─ encoding helper      utility / internal
```

避免“一个文件一个模块”和“整个项目一个模块”两个极端。

### 4.3 入口模块

入口文件可以归入普通业务模块，例如 `app` 或 `cli`。入口模块：

- role 仍是普通角色，例如 `service`；
- 入口状态由项目级 `entrypoints` / `executionEntrypoints` 表达；
- 只负责启动、参数解析、关闭和顶层编排；
- 流程内部编排函数可声明为 `executionOnlyCallables`；
- 不能使用 `role: "entry"`，也不存在主模块语义。

### 4.4 共享对象

一个模型、配置或工具被多个模块使用：

- 为它选择唯一 owner 模块；
- 其他模块通过正常依赖使用；
- 不创建共享模块兜底；
- 如果它有独立职责和生命周期，可以作为独立能力模块；
- 如果只是无状态内部 helper，留在 owner 模块并设为 internal。

---

## 5. Provider 与 Capability

### 5.1 公共能力

公共能力应满足：

- 名称和签名稳定；
- 有完整类型标注；
- 输入、输出、异常和副作用清楚；
- 只暴露完成业务能力所需的接口；
- 有测试覆盖关键成功与失败路径；
- 能从调用方视角解释用途。

模块能力面应保持少而稳定。Python 中“可导入”不等于“架构公开 API”。

### 5.2 内部实现

以下内容默认 internal：

- 私有函数/方法；
- 解析、格式化、渲染、路径处理等辅助逻辑；
- 只被同模块调用的自由函数；
- 无独立生命周期的内部阶段函数；
- 不应被其他模块依赖的实现细节。

内部实现仍保留在 `functionDetails`、`callSites`、Method Detail 和 impact/trace 中，只是不进入模块能力面。

### 5.3 exposure 判定

```text
显式 apiExposure 配置
  > 装饰器 / docstring / 注释标签
  > 入口或协议推导
  > 命名规则
```

- `_name` 默认 internal；
- 非下划线、无标注默认 public，但不自动等于稳定的模块能力；
- `__init__` 只作为构造签名；
- `__enter__` / `__exit__` 合成 context manager 能力；
- `__aenter__` / `__aexit__` 合成 async context manager；
- `__call__` 合成 callable；
- `__iter__` 合成 iterable；
- 其他 dunder 默认不进入普通 API；
- 序列协议 `__len__` / `__getitem__` / `__contains__` / 切片当前不建模。

### 5.4 模块级自由函数

模块级自由函数是能力面噪声的主要来源。生成代码时必须主动分类：

| 表面 | 判定 | 配置方式 |
|---|---|---|
| `capability` | 稳定对外 API、跨模块调用、显式公开标签 | 模块默认 `capability` 或单函数 public exposure |
| `internal` | 仅模块内调用、辅助逻辑、无稳定对外契约 | 模块默认 `internal` 或单函数 internal exposure |
| `execution` | 流程入口或只在 execution flow 中承担的编排单元 | 写入 `executionOnlyCallables` |

effective surface 优先级：

```text
executionOnlyCallables
  > apiExposure=internal
  > 显式 Provider Role = utility
  > 显式 public API 标签 / config public exposure
  > 显式非 utility Provider Role
  > defaultFreeFunctionSurface=internal
  > defaultFreeFunctionSurface=capability
  > 跨模块调用证据（auto）
  > internal
```

不得把以下信号当作 capability 证据：

- 函数名没有下划线；
- 带控制流；
- 调用项目内类；
- 位于能力模块；
- 在 Python 中可 import。

### 5.5 三种自由函数表面不能混用

```text
capability  进入模块能力面，可以有公开 API
internal    模块内部实现，不进入能力面，也不承担执行流入口语义
execution   只作为执行流入口/编排单元，不进入能力面
```

禁止：

- 用 `executionOnlyCallables` 隐藏普通 helper；
- 用 `providerRoles=utility` 批量隐藏 helper；
- 把 internal helper 配成 capability 来“方便出图”；
- 为 executionOnly callable 再配置 Provider Role；
- 让 executionOnly 声明改变文件或模块归属。

---

## 6. 入口、执行流与动态分发

### 6.1 入口配置语义

```json
{
  "entrypoints": ["package.module:main"],
  "executionEntrypoints": ["package.module:Class.run"]
}
```

- `entrypoints` 是项目分析根，用于入口解析、User Surface 传播、调用关系和执行流事实；
- `executionEntrypoints` 用于选择真正要展示的主流程叙事起点；
- 省略 `executionEntrypoints` 时回退到 `entrypoints`；
- 两者都支持类方法，格式为 `module.path:qualname`；
- 入口状态不属于模块 role 或 Provider Role。

### 6.2 入口代码结构

入口函数应尽量薄：

```python
def main() -> int:
    """加载配置、启动应用并返回进程退出码。"""
    config = load_config()
    return App(config).run()
```

职责分离：

```text
入口：参数解析、启动/关闭、退出码
编排：组织业务步骤
manager：实现业务行为
adapter：访问外部系统
model/config：数据和参数
```

### 6.3 executionOnlyCallables

当 callable 属于模块源码，但只作为流程入口或流程内部编排单元：

```json
{
  "id": "app",
  "include": ["src/app/**"],
  "role": "service",
  "executionOnlyCallables": [
    "src.app.main:main",
    "src.app.main:run_client",
    "src.app.main:run_server",
    "src.app.cli:AppCli.run"
  ]
}
```

规则：

- 支持自由函数和类方法，引用格式为 `module.path:qualname`；
- 仍保留源码、callSites、callers/callees 和执行流节点；
- 不进入 `providedApis`、`apiProviders`、`moduleComposition`、Provider 计数或能力卡；
- 类方法被排除时，所属类 Provider 保留，只从类 API 移除该方法；
- callable 被其他模块调用时，应复核它是否其实是真实公开能力；
- 排除后能力为空的模块仍保留真实边界，但前端不展示能力卡。

### 6.4 执行流可分析性

- 优先显式函数/方法调用，避免字符串分发和运行时注册表；
- 分支条件可读，循环、提前返回和异常边界清楚；
- 复杂业务步骤提取为有业务名称的函数或方法；
- 执行流只展开入口自身控制骨架，调用目标原子化，不递归穿透；
- 不要为了“图更深”把函数拆成大量无语义层级。

### 6.5 一级接口 scope

`flowScopes` 只用于配置/executionOnly 编排 callable 的一级外部能力投影：

```json
{
  "flowScopes": {
    "enabled": true,
    "roots": ["src.app.main:server"],
    "autoDetect": true,
    "maxScopesPerFlow": 6,
    "maxNodesPerScope": 24,
    "maxEdgesPerScope": 32
  }
}
```

- scope root 必须是 `free_function` 编排 callable；
- `interface` 节点是黑盒能力边界，不能展开；
- scope 深度固定为 1，不递归生成 scope；
- 自动发现必须保守，显式 roots / executionOnly 优先；
- 预算截断必须进入 diagnostics，不得静默丢节点。

### 6.6 动态分发

先尝试用显式调用、策略对象或映射表消除动态分发。无法消除时使用 `dispatchHints`：

```json
{
  "dispatchHints": [
    {
      "function": "src.app.main:main",
      "expression": "handlers[mode]",
      "occurrence": 1,
      "candidates": ["src.app.handlers:handle_a", "src.app.handlers:handle_b"],
      "complete": true,
      "reason": "config"
    }
  ]
}
```

规则：

- 候选集不完整时 `complete` 必须为 `false` 并说明原因；
- 不得在 UI、bundle 或配置层把 unresolved 调用伪装成确定边；
- 需要把完整候选展开为独立旅程时启用 `dispatchCandidates`，主流程控制边仍保持原子。

---

## 7. 静态分析友好性

### 7.1 推荐写法

- 显式 import；
- 明确类型标注；
- 明确依赖注入；
- 外部系统访问集中在 adapter / manager；
- 入口使用普通 Python 分支、循环和 return；
- 用常量或配置对象代替散落的魔术字符串；
- 对外部输入在系统边界校验。

### 7.2 需要抑制的写法

除非确有业务必要，否则避免：

- `getattr(obj, dynamic_name)` 作为主要业务分发；
- 大量 `**kwargs` 由运行时决定目标；
- 运行时 registry 注册关键入口但无静态证据；
- 依赖 import 副作用修改全局状态；
- 在展示层按字符串猜业务模块；
- 用闭包或装饰器隐藏主要调用路径。

必须使用时，提供显式配置、注释说明和测试。

### 7.3 类型与数据

- 公共函数必须有参数和返回值类型；
- 复杂数据使用 dataclass / TypedDict / Protocol / 明确类型别名；
- 公共接口避免无结构大字典；
- 序列化/反序列化与领域规则分离；
- 数据模型不承担业务编排。

---

## 8. 功能备注与测试

### 8.1 功能备注是硬性要求

每个新增或修改的模块、类、函数、方法、测试和入口都必须有具体、非空、与实现一致的功能备注。

模块备注示例：

```python
"""订单管理能力。

负责创建、取消和查询订单，组织订单模型与库存适配器协作。
不负责支付流程、数据库连接细节和 CLI 参数解析。
"""
```

类备注示例：

```python
class OrderManager:
    """订单业务编排器。

    职责：校验订单、协调库存适配器并维护订单状态。
    生命周期：由应用组装层创建，无长期外部资源。
    边界：不直接访问 HTTP，不负责 CLI 输出。
    """
```

函数备注示例：

```python
def cancel_order(order_id: str, reason: str) -> Order:
    """取消订单并恢复可用库存。

    输入：已校验的订单 ID 和取消原因。
    输出：状态为 cancelled 的订单。
    副作用：调用库存适配器恢复库存。
    约束：已发货订单不能通过此函数取消。
    """
```

禁止只重复函数名、写“处理数据/实现逻辑”、使用占位文本或让 LLM 摘要替代源码备注。

### 8.2 测试要求

- 每个关键业务行为有成功、失败和边界测试；
- 缺陷修复先写可复现测试；
- 时间、随机数、网络和文件系统必须可控；
- 测试验证行为结果，不能只验证“没有抛异常”；
- 测试备注说明验证场景、预期不变量和失败含义。

---

## 9. Python 编码规范

- Python `>=3.10`；
- 优先使用标准库；
- 新增第三方运行时依赖必须有明确理由；
- 使用明确异常类型或错误结果；
- 捕获异常必须有处理动作，禁止空 `except`；
- 资源必须有释放路径；
- 日志不得输出密钥、令牌、密码或完整个人敏感信息；
- 一个函数只承担一个清晰职责；
- 纯计算与 IO 分离；
- 不提交无说明的 TODO、FIXME 或占位实现；
- 不为了减少代码行数牺牲可读性、类型安全或错误处理。

---

## 10. 配置交接要求

源码写完后，必须同步产出/更新模块配置。完整算法、字段语义和校验方式见
[`archmap-config-generation.md`](archmap-config-generation.md)。

AI 至少必须确认：

- 每个文件有唯一模块 owner；
- 模块 include 不重叠且覆盖目标源码；
- 模块 role 合法；
- entrypoints / executionEntrypoints 可解析；
- executionOnlyCallables 只包含真实流程入口或编排 callable；
- 自由函数默认面和单函数 exposure 与源码能力边界一致；
- providerRoles 只用于必要覆盖；
- flowScopes / dispatchCandidates 只在需要时开启并设置预算；
- 不生成旧字段或旧语义。

旧字段禁止出现在新配置中：

```text
mainModule
module.kind
module.role = "entry"
providerRoles.X = "entry"
mainFlows
primaryFlowId
moduleGraphs[].edges
```

---

## 11. AI 工作流

### 11.1 新建项目

```text
1. 识别业务能力与模块边界
2. 为每个模块确定 facade/manager、model、config、utility
3. 设计 entrypoints 与 executionEntrypoints
4. 先写 model/contract，再写 manager/adapter，最后写入口编排
5. 区分 capability / internal / execution 自由函数
6. 补功能备注和测试
7. 生成 archmap 配置
8. 执行 build/check，审查模块、API、flow 和 diagnostics
9. 回写必要文档
```

### 11.2 修改现有项目

```text
1. 阅读 README、当前领域文档和 archmap 配置
2. 判断改动属于哪个模块、哪个 Provider Role
3. 判断是否改变公开 API、数据契约、入口或执行流
4. 判断是否需要 executionOnly、internal exposure 或 dispatchHints
5. 实现代码与测试
6. 更新配置
7. 执行 build/check
8. 更新功能备注和文档
```

### 11.3 重构项目

重构目标是职责更清楚，不是节点更多：

- 合并无意义碎片模块；
- 拆分职责过多的 manager；
- 将内部 helper 从能力面移出；
- 将入口编排与业务实现分离；
- 将外部 IO 收敛到 adapter；
- 消除循环依赖和共享桶；
- 保持业务行为和既有测试通过。

---

## 12. 提交前检查清单

### 模块

- [ ] 模块按业务能力划分。
- [ ] 每个源码文件恰好属于一个模块。
- [ ] 模块 include 不重叠。
- [ ] 没有 shared/contracts/common/misc 兜底模块。
- [ ] 模块 role 只使用 `service/adapter/component/test/other`。

### Provider

- [ ] 每个类有明确 Provider Role。
- [ ] config/model 不泄漏普通业务方法 API。
- [ ] utility 默认 internal。
- [ ] manager/adapter/component/contract 的职责可解释。
- [ ] 每个模块级自由函数已分类为 capability/internal/execution。
- [ ] executionOnly callable 没有进入能力面。
- [ ] providerRoles 覆盖只用于必要场景。

### 入口与流程

- [ ] entrypoints 和 executionEntrypoints 指向正确函数/方法。
- [ ] 入口函数足够薄，编排与业务实现分离。
- [ ] 流程入口与流程内部编排单元正确声明为 executionOnly。
- [ ] 关键调用尽量静态可解析。
- [ ] 动态分发有 dispatchHints 和完整性标记。
- [ ] 启用 dispatchCandidates 时只对完整集合生成候选旅程并设置预算。

### 代码质量

- [ ] 公共接口有类型、错误和副作用说明。
- [ ] 资源有释放路径。
- [ ] 外部输入在边界校验。
- [ ] 纯计算与 IO 分离。
- [ ] 没有隐藏全局状态或循环依赖。
- [ ] 模块、类、函数、方法、测试都有功能备注。

### 验证

- [ ] 单元测试和边界测试通过。
- [ ] `python3 -m archmap build ...` 成功。
- [ ] `python3 -m archmap check .../architecture.json` 通过。
- [ ] diagnostics 为 0，或每条 warning 都有明确原因。
- [ ] 模块卡、能力 API、flow card 和执行流符合预期。
- [ ] 生成产物未被手工修改。
- [ ] 文档、配置和代码同步。

---

## 13. Definition of Done

一个被分析项目的代码改动只有在同时满足以下条件时才算完成：

1. 模块边界按业务能力划分，文件归属唯一。
2. Provider Role、可见性和能力面语义清楚。
3. public / internal / execution 三种表面已正确区分。
4. 入口、编排、业务实现和基础设施分离。
5. 关键调用关系可静态分析，动态部分有显式说明。
6. 每个新增/修改的模块、类、函数、方法和测试都有高质量功能备注。
7. 关键行为、失败路径和边界条件有可重复测试。
8. `archmap build/check` 成功，诊断可解释。
9. 模块配置由少量、可解释的声明构成，不依赖批量角色覆盖。
10. 架构分析结果能够帮助发现真实问题，而不是通过配置或展示层掩盖问题。

## 14. AI 最终交付说明模板

完成改动后，用以下格式汇报：

```text
模块变化：
  - <module>: <新增/修改的职责与文件>

Provider / 能力变化：
  - <provider>: <role / visibility / capability>
  - <free function>: <capability|internal|execution>

入口与流程：
  - entrypoints:
  - executionEntrypoints:
  - executionOnlyCallables:
  - dispatchHints / flowScopes / dispatchCandidates:

静态分析边界：
  - <已知动态分发、未解析调用或外部系统>

验证结果：
  - pytest:
  - archmap build:
  - archmap check:
  - diagnostics:

文档与配置：
  - <更新的 README / 配置 / 领域文档>
```
