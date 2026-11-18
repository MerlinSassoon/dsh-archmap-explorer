# ArchMap 规范化项目配置生成指南

> 状态：P6 配置生成与评审指南；目标模型已批准，随 P6 分阶段落地<br>
> 日期：2026-11-18<br>
> 适用范围：为 Python 项目生成或维护 `archmap` 配置的人员、脚本与 LLM
>
> 本指南用于避免把“主流程”“主模块”“入口”“Provider Role”“模块”混为一谈。迁移完成前，当前运行时仍可能兼容旧字段；具体字段以当前 schema 和 validator 为准。

## 1. 先区分五个概念

生成配置前必须区分：

| 概念 | 回答的问题 | 不应混淆为 |
|---|---|---|
| `include` / `exclude` | 分析哪些源码文件 | 模块划分 |
| 模块 | 哪些 Provider 属于同一个业务能力 | 页面或调用图 |
| Provider Role | 这个类/函数承担什么职责 | 模块类型 |
| `entrypoints` | 项目静态分析的入口根 | 主模块 |
| `executionEntrypoints` | 主流程叙事从哪个函数/方法开始 | 模块配置 |
| dispatch hints | 动态调用候选如何解析 | 模块 API |

主流程是项目级视图，不是模块；`entry` 是 Provider Role，不是模块类型。

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
└─ StudentRecord

network
├─ NetworkAdapter
├─ ProtocolMessage
└─ protocol utility
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

### 2.4 不创建“共享模块”兜底

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

## 4. 入口与流程配置

### 4.1 `entrypoints` 与分析根

`entrypoints` 用于：

- 入口角色识别；
- User Surface 传播；
- 调用关系与主流程事实。

格式示例：

```json
"entrypoints": ["package.module:main"]
```

类方法入口也可以显式配置为：

```json
"executionEntrypoints": ["package.module:Class.run"]
```

### 4.2 `executionEntrypoints` 与执行流

- 入口函数的分析根和流程叙事起点可以不同；
- 薄启动包装函数适合作为 `entrypoints`；
- 真正的用户旅程方法可以作为 `executionEntrypoints`；
- 不要让 `executionEntrypoints` 承担模块划分职责；
- 不存在主模块时，流程仍可通过项目级 `entrypoints` / `executionEntrypoints` 定位。

### 4.3 动态分发配置

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

### 4.3 不为入口伪造模块

- 入口函数可以属于普通模块，Role 可设为 `entry`；
- 不要求创建名为 `main` 的特殊模块；
- 不把主流程页挂到某个模块页面；
- 过渡期若运行时仍兼容主模块字段，应将其视为兼容占位，不据此把无关文件塞入该模块。

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

### 5.2 常见角色理解

- `manager`：组织行为、维护状态、提供业务 API；
- `adapter`：外部系统适配；
- `component`：UI / 协议组件；
- `entry`：入口函数或入口类；
- `config`：静态配置、常量、枚举；
- `model`：运行期数据模型、DTO、结果；
- `contract`：抽象类、Protocol、接口；
- `utility`：无状态内部辅助逻辑。

`entry` 不应被理解为“主模块”；`config` / `model` 不应被理解为“技术层模块”。

## 6. 常见错误配置

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 设置一个 `main` 模块并塞入所有入口文件 | 主模块变成文件堆放区 | 入口文件归入普通能力模块，流程放项目层 |
| 建 `contracts` / `shared` 模块 | 模块边界失效，能力归属不清 | 模型/配置归入其服务的业务模块 |
| 按 `config/`、`model/`、`utility/` 建模块 | 模块页只有零散类型，没有 facade | 按业务能力纵向组织 |
| 每个文件一个模块 | 模块图碎裂，无法表达能力 | 以 manager / 业务能力聚合 |
| 所有代码一个模块 | 模块页失去意义 | 识别 facade 与能力边界 |
| 模块 include 重叠 | 文件归属歧义 | 保证每文件恰好一个模块 |
| 创建空模块占位 | 项目页出现无意义卡片 | 删除空模块或补足真实职责 |
| 把测试脚本混入业务模块 | 生产 API 与测试事实混杂 | 独立 test 模块或排除 |
| 把所有函数都设置 role override | 角色模型失真 | 优先依赖结构与注释 |
| 把调用边当作模块边界 | 模块页重新变成调用图 | 调用关系留在 CallSite / Method Detail |
| 将 `executionEntrypoints` 当作模块入口 | 配置语义混乱 | 明确它是项目级流程起点 |

## 7. 生成前检查

生成配置前至少确认：

- 项目根目录和源码目录正确；
- `include` 覆盖目标源码；
- `exclude` 排除缓存、构建、虚拟环境和无关测试；
- 模块 include 是否有重叠；
- 是否存在未归属文件；
- 是否出现 `contracts` / `shared` / `misc` 等兜底模块；
- 每个模块是否有可解释的 manager / facade；
- config/model 是否围绕对应 manager；
- entrypoints 是否可解析；
- executionEntrypoints 是否指向真正的流程起点；
- role override 是否只用于必要场景。

## 8. 生成后验证

建议依次执行：

```bash
python3 -m archmap build <project> --config <config> --out <output>
python3 -m archmap check <output>/architecture.json
```

人工检查：

- diagnostics 为 0，或每条 warning 都有明确原因；
- 项目页没有无意义模块卡片；
- 主流程卡片与模块卡片职责分离；
- 模块页不依赖调用连线才能理解；
- 每个 API 都能追溯到 Provider；
- 每个 config/model 都有明确模块归属；
- 没有跨模块重复定义的同一模型；
- 没有把内部 utility 暴露成模块 API；
- 没有为了生成成功而设置兜底模块。

## 9. 规范化样例

### 9.1 student_system

```text
app              入口与顶层编排（role=entry）
network          NetworkAdapter + ProtocolMessage + ProtocolCodec
database         Database + DatabaseConfig
menu             MenuSystem + StudentRecord + display utility
async-feedback   Spinner
test             表格验证脚本
```

关键点：

- 不建立 `contracts` 共享模块；
- `ProtocolMessage` 是 network 模块的 public model；
- `ProtocolCodec` 是 network 模块的 public manager capability；
- `StudentRecord` 是 menu 模块的 public model；
- `DatabaseConfig` 跟随 database manager。

### 9.2 gomoku

```text
entry          main.py / __main__.py / cli.py
terminal-ui    input_parser.py / renderer.py
application    game.py + GameConfig
domain         board.py + models.py
ai-adapter     ai.py
```

`GameConfig` 跟随 application manager，不再单独建立技术层 `game-config` 模块。

## 10. 过渡期注意事项

P6.2 已落地 schema 5.0。当前运行时：

- 读取旧 `mainModule` / `kind` 字段时只产生 deprecation warning，不再参与模块模型；
- 新配置生成器不应再输出 `mainModule`、`kind: main` 或 `kind: functional`；
- `mainFlows` / `primaryFlowId` 已从 bundle 删除；
- 模块页不渲染调用边；
- execution flow 不再生成语义 `entry` 节点。

最终目标是：

```text
项目级主流程
  + 普通能力模块
  + 单一执行流投影
  + 无主模块
```
