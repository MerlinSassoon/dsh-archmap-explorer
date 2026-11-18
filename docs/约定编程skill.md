# ArchMap 被分析项目代码生成 Skill

> 版本：3.1（被分析项目专用版）<br>
> 最后更新：2026-11-19<br>
> 目标：约束 AI 生成或改造**由 ArchMap 分析的 Python 项目代码**，使项目天然具备清晰的模块边界、Provider 职责、能力契约、入口执行流和可静态分析性。<br>
> 适用对象：AI 编码助手、项目维护者、代码审查者、ArchMap 配置生成者。

## 0. 定位

### 0.1 一句话定位

本 Skill 不是 ArchMap 引擎开发手册，而是**被分析项目的源码工程规范**：

```text
源码结构是事实源
  → 模块配置是源码结构的显式声明
  → 架构分析是源码事实的投影
  → 架构图是分析结果的可视化
```

AI 的首要任务不是“生成一张好看的图”，而是生成**结构正确、边界清楚、配置成本低、值得被分析的代码**。架构图和模块配置是良好代码结构的自然结果。

### 0.2 成功标准

一次 AI 生成的代码应同时满足：

1. 维护者能解释每个模块的职责和边界。
2. 每个源码文件有唯一模块归属。
3. 类与自由函数有明确的 Provider 职责。
4. 公共能力与内部实现边界清楚。
5. 入口、流程编排、业务逻辑和基础设施分离。
6. 调用关系尽量静态可解析。
7. 模块配置可以使用少量、可解释的声明生成。
8. `archmap build/check` 能稳定通过，诊断可解释。
9. 生成的结构有助于发现真实架构问题，而不是掩盖问题。
10. 即使不使用 ArchMap，代码本身仍然是清晰、可测试、可维护的 Python 代码。

### 0.3 非目标

本 Skill 不负责：

- 修改 ArchMap 引擎、schema、validator、renderer 或 bundle 内部结构；
- 通过伪造模块、Provider 或关系来美化架构图；
- 强制所有项目使用同一个目录模板；
- 替代项目自身的产品文档、框架规范、安全要求和发布流程；
- 把动态语言的所有运行时行为都强行静态化。

当代码正确但分析结果不完整时，应通过配置或诊断表达边界，而不是改写业务事实来迎合工具。

## 1. AI 使用协议

### 1.1 开始前必须确认

AI 在写代码前必须回答：

```text
项目类型：Web / CLI / 桌面 / 数据处理 / 库 / 其他
模块边界：按什么业务能力划分
文件归属：每个新增文件属于哪个模块
物理代码单元：config / model / manager / utility / adapter / component / entry
逻辑 Provider Role：七角色中的哪一个
可见性：公开能力 / 内部实现 / 仅执行流
入口：entrypoints 与 executionEntrypoints 是什么
副作用：文件、网络、数据库、全局状态、用户 IO
验证：单测、样例、archmap build/check
```

无法回答时，不允许用“先写一个万能模块”或“先全部放 utils”开始实现。

### 1.2 规则优先级

```text
项目自身的领域规则、框架约束和安全要求
  > ArchMap 当前分析契约与配置规范
  > 本 Skill
  > 个人编码偏好
```

如果项目框架要求与 ArchMap 友好性冲突，优先保持代码正确和框架可用，再用配置显式说明分析边界。

### 1.3 AI 交付说明

每次代码改动应说明：

- 新增或修改了哪些模块；
- 每个文件属于哪个模块；
- 每个 Provider 的角色和公开能力；
- 哪些 callable 仅用于执行流；
- 哪些自由函数是 internal；
- 是否存在动态分发、运行时注册或分析盲区；
- 实际执行的测试和 `archmap build/check` 结果。

## 2. 核心原则

### 2.1 业务能力优先

模块按业务能力划分，而不是按技术类型堆叠。

推荐：

```text
orders/       订单能力
payments/     支付能力
inventory/    库存能力
notifications/ 通知能力
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

`config`、`model`、`utility` 是代码单元或 Provider Role，不是业务模块本身。

判断是否可以拆成独立模块：

- 有独立业务职责；
- 有独立状态或生命周期；
- 有独立策略或变化原因；
- 有独立测试边界；
- 有可独立描述的对外能力；
- 与其他能力只有少量共享逻辑。

不要仅因为文件多就拆模块，也不要因为“方便导入”就建共享桶。

### 2.2 源码只是事实，不要为图造结构

禁止：

- 为增加模块卡片而拆出空模块；
- 为增加节点而创建无职责类；
- 为减少误报而把所有函数改成 internal；
- 为让 flow 好看而改写业务控制流；
- 在展示层或配置层重新定义业务事实。

如果架构图暴露了问题，应修正模块边界、职责分配或调用关系，而不是隐藏问题。

### 2.3 可静态分析性

优先选择显式、可追踪的代码：

- 显式 import；
- 显式函数/方法调用；
- 明确依赖注入；
- 明确类型；
- 明确入口；
- 有限的动态分发。

不是要求完全禁止动态特性，而是要求动态部分有边界、有配置、有证据。

### 2.4 简单结构优先

清晰的分层和少量 facade 通常优于深层抽象。禁止为了“架构感”创建没有真实职责的接口、基类、适配器或管理器。

## 3. 模块设计

### 3.1 文件唯一归属

- 每个纳入分析的源码文件必须恰好属于一个模块；
- 模块的 include 范围不得重叠；
- 不得存在未被任何模块覆盖的源码；
- 跨模块引用不改变 Provider 的归属；
- 测试文件应进入独立 test 模块或被明确排除。

### 3.2 模块 role

ArchMap 当前接受普通能力模块 role：

```text
service / adapter / component / test / other
```

禁止：

```text
main / entry / functional
```

模块是否拥有入口文件，不改变模块 role。入口由项目级配置表达，不由模块 role 表达。

### 3.3 模块粒度

一个模块应有清楚的能力中心：

```text
正确：
network
  ├─ NetworkAdapter
  ├─ ProtocolMessage
  └─ ProtocolCodec

database
  ├─ Database
  ├─ DatabaseConfig
  └─ connection helper
```

避免：

```text
一个文件一个模块
或
整个项目一个模块
```

模块过大时，优先按业务能力拆分；模块过碎时，优先合并到同一能力域。

### 3.4 共享模型与工具

一个模型、配置或工具被多个模块使用时：

- 为它选择唯一 owner 模块；
- 其他模块通过正常依赖使用它；
- 不创建 `shared` / `contracts` / `common` 兜底模块；
- 如果它本身有独立职责和生命周期，可以作为独立能力模块；
- 如果它只是无状态内部工具，保持在 owner 模块内并设为 internal。

### 3.5 入口模块

入口文件可以归入一个普通能力模块，例如 `app` 或 `cli`。该模块可以主要承载执行流，也可以同时拥有真实 capability Provider。

入口模块不得使用 `role: "entry"`，也不得创建特殊主模块语义。

## 4. 物理代码单元与七类 Provider Role

### 4.1 物理代码单元

```text
config     静态定义、默认值、常量、枚举、配置对象
model      数据结构、DTO、结果、值对象、契约接口
manager    状态、生命周期、行为编排、入口代理、外部适配
utility    无状态内部辅助逻辑
entry      应用入口或 CLI
adapter    外部系统适配实现
component  协议、UI 或生命周期组件
```

推荐文件名：

```text
<domain>_config.py
<domain>_model.py
<domain>_manager.py
<domain>_utility.py
```

可根据项目框架和领域语言调整命名，但文件名应表达职责，避免 `helpers.py`、`misc.py`、`common.py`。

### 4.2 七类 Provider Role

| Role | 负责什么 | 不应承担什么 | 默认呈现 |
|---|---|---|---|
| `config` | 常量、默认值、枚举、配置对象、策略表 | 运行期记录、行为编排 | 类型/配置摘要 |
| `model` | dataclass、DTO、值对象、事件 payload、结果模型 | 状态管理、外部资源、业务编排 | 类型/字段摘要 |
| `contract` | ABC、Protocol、纯接口、抽象方法集合 | 具体实现、DTO | 契约能力 |
| `utility` | 无状态转换、解析、格式化、算法、内部辅助 | 模块公开 API、状态管理 | 默认 internal |
| `manager` | 管理 model/config、组织多步行为、协调 Provider、暴露稳定 API | 数据形状、外部 IO 细节 | 公开能力 |
| `adapter` | 数据库、HTTP、socket、文件、SDK、消息队列适配 | 领域规则、入口解析 | 外部边界能力 |
| `component` | UI、协议对象、context manager、callable/iterable 组件 | 通用 manager、纯工具 | 协议/组件能力 |

`entry` 不是 Provider Role。入口状态属于项目级执行流语义。

### 4.3 角色判定顺序

```text
显式 providerRoles 配置
  > 注释 / 装饰器 / 文档标签
  > 结构规则
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

### 4.4 角色禁区

- 不新增第八种 Provider Role；
- 不把 `entry` 写入 Provider Role；
- 不为隐藏 helper 批量写 `providerRoles: "utility"`；
- `config` / `model` 不应提供普通方法 API，字段和默认值通过类型摘要呈现；
- utility 默认内部实现，不作为模块公开能力；
- 不因为自由函数名没有下划线、带控制流或调用项目类就把它视为 manager。

## 5. 依赖关系与边界

### 5.1 推荐依赖方向

```text
config ← model ← manager
utility ← manager
contract ← manager
adapter → contract
```

规则：

- utility 只依赖标准库、低层 utility 和必要的纯数据模型；
- utility 不依赖 manager；
- config 不依赖 manager；
- model 不依赖 manager；
- manager 可以依赖 config/model/contract/utility/adapter；
- adapter 通过 contract 被 manager 使用；
- 模块之间通过明确接口协作，禁止循环依赖；
- 入口层只做输入解析、参数校验、流程编排和结果输出，不承载深层业务规则。

### 5.2 跨模块依赖

- 跨模块调用是依赖，不是共享；
- 消费方不得重复定义同一 Provider；
- 模型归属到其主要生命周期或主要消费能力域；
- 模块配置不应为了消除依赖而错误合并模块；
- 默认不需要在模块能力页展示调用边，调用事实由分析结果保留。

### 5.3 状态与副作用

- 有状态对象必须明确生命周期和所有者；
- 资源必须在明确位置释放；
- 纯计算与 IO 分离；
- 外部输入在系统边界校验；
- 构造函数不执行不可撤销的外部副作用；
- 禁止通过全局可变状态隐藏依赖。

## 6. Provider 与 Capability 设计

### 6.1 公共能力

公共能力应：

- 有稳定的名称和签名；
- 有完整类型标注；
- 有明确输入、输出、异常和副作用；
- 只暴露完成业务能力所需的接口；
- 可以从调用方视角说明用途；
- 有对应测试。

不要求每个 public 方法都成为模块 API；模块能力面应保持少而稳定。

### 6.2 内部实现

以下内容默认是 internal：

- 私有函数或方法；
- 解析、格式化、渲染、路径处理等辅助逻辑；
- 只被同模块调用的自由函数；
- 无独立生命周期的内部阶段函数；
- 不应被其他模块依赖的实现细节。

内部实现仍应保留在源码和调用事实中，方便方法详情和影响分析，但不进入模块能力面。

### 6.3 exposure 判定

推荐顺序：

```text
显式 apiExposure 配置
  > 装饰器 / docstring / 注释标签
  > 入口或协议推导
  > 命名规则
```

- `_name` 默认 internal；
- 非下划线、无标注默认 public，但不等同于稳定的模块能力；
- `__init__` 作为构造签名，不作为普通方法 API；
- `__enter__` / `__exit__` 合成 `context_manager`；
- `__aenter__` / `__aexit__` 合成 `async_context_manager`；
- `__call__` 合成 `callable`；
- `__iter__` 合成 `iterable`；
- 其他 dunder 默认不单独进入普通 API。

可以继续实现 `__len__` / `__getitem__` 等 Python 序列协议，但当前 ArchMap 不把它们作为独立能力展示；不要依赖这些协议进入架构图。

### 6.4 模块级自由函数

自由函数最容易造成能力面噪声。生成代码时应主动区分：

| 类型 | 典型特征 | 建议 |
|---|---|---|
| capability | 稳定对外 API、跨模块调用、显式公开标签 | 作为模块能力 |
| internal | 只在模块内使用的解析/格式化/辅助逻辑 | 默认 internal |
| execution | 只作为流程入口或流程内部编排 | 写入 `executionOnlyCallables` |

判定优先级：

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

三种模块默认自由函数面：

```text
auto         有强证据才成为 capability，否则 internal
internal     未显式公开的自由函数默认 internal
capability   未显式 internal 的自由函数默认 capability
```

### 6.5 executionOnly、internal 与 capability 的区别

```text
capability  进入模块能力面，可以有公开 API
internal    模块内部实现，不进入能力面，不承担流程入口语义
execution   只作为执行流入口/编排单元，不进入能力面
```

禁止：

- 用 `executionOnlyCallables` 隐藏普通内部 helper；
- 用 `providerRoles=utility` 批量隐藏 helper；
- 把 internal helper 配置成 capability 来“方便出图”；
- 为 executionOnly callable 再配置 Provider Role；
- 让 `executionOnlyCallables` 改变文件或模块归属。

## 7. 入口与执行流设计

### 7.1 入口配置

```json
{
  "entrypoints": ["package.module:main"],
  "executionEntrypoints": ["package.module:Class.run"]
}
```

- `entrypoints` 是项目分析根；
- `executionEntrypoints` 用于选择一个或多个真正要展示的执行流起点；
- 省略 `executionEntrypoints` 时回退到 `entrypoints`；
- 入口状态不进入模块 role 或 Provider Role。

### 7.2 入口代码结构

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

### 7.3 仅用于执行流的 callable

如果某个 callable 属于模块源码，但只作为流程入口或流程内部编排单元，应在模块配置中声明：

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

- 支持自由函数和类方法；
- callable 仍保留源码、调用关系和执行流事实；
- 不进入模块 `providedApis`、Provider 卡片、能力计数或模块组合；
- 类方法被排除时，所属类 Provider 保留，只从类 API 中移除该方法；
- callable 被其他模块调用时，应复核它是否其实是真实公开能力；
- 排除所有能力后为空的模块仍保留真实边界，但不需要展示能力卡。

### 7.4 执行流可分析性

为了让执行流清晰：

- 入口应调用有业务名称的编排函数或 manager；
- 避免在一个入口中混入大量低层 IO 和业务细节；
- 优先使用显式调用，避免通过字符串、反射或全局注册表隐式分发；
- 分支条件应清晰可读；
- 循环、提前返回和异常边界应易于理解；
- 复杂业务步骤应提取为有名称的函数或方法。

执行流只展开入口自身的控制骨架；调用目标会作为原子步骤，不继续穿透实现。不要为了“图更深”把一个函数拆成大量无语义层级。

## 8. 配置生成与维护

### 8.1 配置应来自代码事实

生成模块配置前按以下顺序：

```text
1. 按业务能力划分模块，保证每个文件唯一 owner
2. 识别类 Provider 及其职责
3. 识别项目入口与执行流入口
4. 识别模块级自由函数
5. 将流程入口/编排单元写入 executionOnlyCallables
6. 为模块选择 defaultFreeFunctionSurface
7. 对少量例外使用 apiExposure 或 executionOnlyCallables
8. 最后才写必要的 providerRoles 覆盖
```

### 8.2 标准配置骨架

```json
{
  "projectName": "example",
  "language": "python",
  "include": ["src/**/*.py"],
  "exclude": ["**/__pycache__/**", "**/.venv/**"],
  "entrypoints": ["src.app.main:main"],
  "executionEntrypoints": ["src.app.cli:AppCli.run"],
  "modules": [
    {
      "id": "app",
      "name": "应用入口与编排",
      "include": ["src/app/**"],
      "role": "service",
      "defaultFreeFunctionSurface": "internal",
      "executionOnlyCallables": ["src.app.main:main"]
    },
    {
      "id": "network",
      "name": "网络协议",
      "include": ["src/network/**"],
      "role": "adapter"
    }
  ],
  "dispatchHints": [],
  "contract": {}
}
```

### 8.3 动态分发

静态解析无法覆盖的情况下，使用显式 `dispatchHints`：

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

规则：

- 先尝试使用显式调用或策略对象消除动态分发；
- 无法消除时再配置；
- 候选集不完整时必须明确标记；
- 不得伪造完整候选集；
- 不得在 UI 或配置层强行把未解析调用变成确定边。

### 8.4 配置禁区

禁止生成旧字段或旧语义：

```text
mainModule
module.kind
module.role = "entry"
providerRoles.X = "entry"
mainFlows
primaryFlowId
moduleGraphs[].edges
```

禁止用大量 `providerRoles` 覆盖替代合理的代码分层。

## 9. 静态分析友好性

### 9.1 推荐写法

- 明确 import 模块和符号；
- 使用有类型标注的函数和方法；
- 使用明确的依赖注入；
- 将外部系统访问集中在 adapter/manager；
- 将入口控制流写成普通 Python 分支、循环和返回；
- 用稳定字符串常量和配置文件代替散落的魔术字符串；
- 对外部输入在边界处校验。

### 9.2 需要抑制的写法

以下写法会增加分析盲区，除非确有业务必要，否则应避免：

- `getattr(obj, dynamic_name)` 进行主要业务分发；
- 到处都是 `**kwargs` 并由运行时决定目标；
- 运行时 registry 注册关键入口但无静态证据；
- 依赖导入副作用修改全局状态；
- 在展示层根据字符串猜测业务模块；
- 通过闭包或装饰器隐藏主要调用路径。

必须使用时，应提供显式配置、注释说明和相应测试。

### 9.3 类型与数据

- 公共函数必须有参数和返回值类型；
- 复杂数据使用 dataclass / TypedDict / Protocol / 明确类型别名；
- 公共接口避免无结构大字典；
- 序列化/反序列化与领域规则分离；
- 数据模型不承担业务编排。

## 10. 功能备注规范

> 硬性要求：每个新增或修改的模块、类、函数、方法、测试和入口都必须有具体、非空、与实现一致的功能备注。

### 10.1 模块备注

说明模块负责什么、所在业务能力、主要公开能力、不负责什么。

```python
"""订单管理能力。

负责创建、取消和查询订单，组织订单模型与库存适配器协作。
不负责支付流程、数据库连接细节和 CLI 参数解析。
"""
```

### 10.2 类备注

说明职责、Provider 角色、生命周期、边界和主要能力。

```python
class OrderManager:
    """订单业务编排器。

    职责：校验订单、协调库存适配器并维护订单状态。
    生命周期：由应用组装层创建，无长期外部资源。
    边界：不直接访问 HTTP，不负责 CLI 输出。
    """
```

### 10.3 函数与方法备注

说明目的、关键输入、输出、副作用和约束。

```python
def cancel_order(order_id: str, reason: str) -> Order:
    """取消订单并恢复可用库存。

    输入：已校验的订单 ID 和取消原因。
    输出：状态为 cancelled 的订单。
    副作用：调用库存适配器恢复库存。
    约束：已发货订单不能通过此函数取消。
    """
```

### 10.4 测试备注

说明验证场景、预期不变量和失败含义。

```python
def test_cancel_order_restores_inventory() -> None:
    """验证取消订单会恢复库存，并且不会改变其他订单状态。"""
```

### 10.5 备注质量禁区

- 不能只重复函数名；
- 不能写“处理数据”“实现逻辑”；
- 不能使用占位文本；
- 修改行为必须同步修改备注；
- LLM 摘要不能替代源码功能备注；
- 特殊方法必须说明生命周期或协议语义。

## 11. Python 编码规范

- Python `>=3.10`；
- 优先使用标准库；
- 新增第三方运行时依赖必须有明确理由；
- 使用明确的异常类型或错误结果；
- 捕获异常必须有处理动作，禁止空 `except`；
- 资源必须有释放路径；
- 日志不得输出密钥、令牌、密码或完整个人敏感信息；
- 一个函数只承担一个清晰职责；
- 纯计算与 IO 分离；
- 不提交无说明的 TODO、FIXME 或占位实现；
- 不为了减少代码行数牺牲可读性、类型安全或错误处理。

## 12. 测试与验证

### 12.1 测试要求

- 每个关键业务行为有成功、失败和边界测试；
- 缺陷修复先写可复现测试；
- 测试数据显式构造或通过 fixture 提供；
- 涉及时间、随机数、网络和文件系统的测试必须可控；
- 测试必须验证行为结果，不能只验证“没有抛异常”。

### 12.2 架构验证

在目标项目根目录执行：

```bash
python3 -m archmap build <project> --config <config> --out <output>
python3 -m archmap check <output>/architecture.json
```

验证时关注：

- `diagnostics` 是否为 0，或每条 warning 是否有明确原因；
- 模块数量、能力模块和空能力模块是否符合预期；
- 是否出现错误的 manager 自由函数；
- executionOnly callable 是否仍保留在源码和执行流中；
- 每个模块是否只有一个 owner；
- 公共 API 是否能追溯到明确的 Provider；
- 入口 flow 是否从正确函数开始；
- 动态分发是否有明确的候选和完整性标记；
- 生成的 HTML 是否能正常打开，项目页、flow 页和模块页是否可导航。

### 12.3 验证边界

- 不手工修改生成的 `architecture.json` 或 `architecture.html` 来“修复”结果；
- 分析结果不符合预期时，先检查源码结构、配置和文档；
- 如果确认是 ArchMap 引擎问题，应单独记录，不在业务项目中用伪结构绕过；
- 静态分析无法覆盖的运行时行为应明确说明，而不是假装完整。

## 13. AI 代码生成 Playbook

### 13.1 新建项目

```text
1. 识别业务能力和模块
2. 为每个模块确定 facade/manager、model、config、utility
3. 设计项目入口和 executionEntrypoints
4. 先写模型与契约
5. 写 manager 和 adapter
6. 写入口编排
7. 补功能备注和测试
8. 生成 archmap 配置
9. 执行 build/check 并审查模块、API 和 flow
```

### 13.2 修改现有项目

```text
1. 阅读 README、领域文档和现有模块配置
2. 判断改动属于哪个模块和 Provider Role
3. 检查是否改变公开 API / 数据契约 / 入口
4. 判断是否需要 executionOnly 或 internal 声明
5. 实现代码与测试
6. 更新 archmap 配置
7. 执行 build/check
8. 更新文档和功能备注
```

### 13.3 重构

重构的目标是让职责更清楚，而不是让图更多节点：

- 合并无意义的碎片模块；
- 拆分职责过多的 manager；
- 将内部 helper 从能力面移出；
- 将入口编排与业务实现分离；
- 将外部 IO 收敛到 adapter；
- 消除循环依赖和共享桶；
- 保持原有业务行为与测试通过。

### 13.4 配置生成

生成配置时必须逐项确认：

- include / exclude 覆盖正确；
- 每个文件只有一个模块 owner；
- 模块 include 不重叠；
- 模块 role 合法；
- entrypoints / executionEntrypoints 可解析；
- executionOnly callable 真实存在且确实参与执行流；
- 模块默认自由函数面符合实际；
- providerRoles 只用于必要覆盖；
- 不存在旧配置字段；
- build/check 成功。

## 14. 禁止事项

1. 建立 `shared` / `contracts` / `common` / `misc` 兜底模块。
2. 使用 `role: "entry"` 或 `providerRole: "entry"`。
3. 把入口状态当作模块类型或 Provider 类型。
4. 为隐藏内部 helper 而批量写 `providerRoles=utility`。
5. 把内部 helper 写入 `executionOnlyCallables`。
6. 把 executionOnly callable 当作模块公开能力。
7. 让 public 命名、控制流或项目内调用自动决定模块能力。
8. 让 config/model 提供普通方法 API。
9. 为了出图而制造空模块、无职责类或虚假关系。
10. 在展示层或配置层重新推导业务事实。
11. 在 UI 或 bundle 层手工修补错误分析结果。
12. 让入口函数承担深层业务规则和外部 IO 细节。
13. 使用隐藏全局状态或导入副作用连接模块。
14. 让通用业务代码依赖动态解析器的内部实现。
15. 提交没有功能备注的模块、类、函数、方法或测试。
16. 提交空泛 TODO、占位实现或无说明的临时绕行。
17. 引入不必要的外部运行时依赖。
18. 将架构图中的节点数量、连线数量作为代码质量的唯一指标。

## 15. 提交前检查清单

### 模块

- [ ] 模块按业务能力划分。
- [ ] 每个源码文件恰好属于一个模块。
- [ ] 模块 include 不重叠。
- [ ] 没有 shared/contracts/common/misc 兜底模块。
- [ ] 模块 role 只使用 `service/adapter/component/test/other`。

### Provider

- [ ] 每个类有明确 Provider Role。
- [ ] config/model 不泄漏行为 API。
- [ ] utility 默认 internal。
- [ ] manager/adapter/component/contract 的职责可解释。
- [ ] 自由函数已区分 capability/internal/execution。
- [ ] executionOnly callable 没有进入能力面。
- [ ] providerRoles 覆盖只用于必要场景。

### 入口与流程

- [ ] entrypoints 和 executionEntrypoints 指向正确函数/方法。
- [ ] 入口函数足够薄，编排与业务实现分离。
- [ ] 流程入口和流程内部编排单元正确标记为 executionOnly。
- [ ] 关键调用尽量静态可解析。
- [ ] 动态分发有 `dispatchHints` 和完整性标记。

### 代码质量

- [ ] 公共接口有类型、错误和副作用说明。
- [ ] 资源有释放路径。
- [ ] 外部输入在边界校验。
- [ ] 纯计算与 IO 分离。
- [ ] 没有隐藏全局状态或循环依赖。
- [ ] 模块、类、函数、方法、测试都有功能备注。

### 验证

- [ ] 单元测试和边界测试通过。
- [ ] `archmap build` 成功。
- [ ] `archmap check` 通过。
- [ ] diagnostics 为 0 或有明确解释。
- [ ] 模块卡、能力 API 和执行流符合预期。
- [ ] 生成产物未被手工修改。
- [ ] 文档、配置和代码同步。

## 16. Definition of Done

一个被分析项目的代码改动只有在同时满足以下条件时才算完成：

1. 模块边界按业务能力划分，文件归属唯一。
2. Provider Role、可见性和能力面语义清楚。
3. 公共能力、内部实现和仅执行流 callable 已正确区分。
4. 入口、编排、业务实现和基础设施分离。
5. 关键调用关系可静态分析，动态部分有显式说明。
6. 每个新增/修改的模块、类、函数、方法和测试都有高质量功能备注。
7. 关键行为、失败路径和边界条件有可重复测试。
8. `archmap build/check` 成功，诊断可解释。
9. 模块配置可以用少量声明表达，不依赖批量角色覆盖。
10. 架构分析结果能够帮助发现真实问题，而不是通过配置或展示层掩盖问题。
