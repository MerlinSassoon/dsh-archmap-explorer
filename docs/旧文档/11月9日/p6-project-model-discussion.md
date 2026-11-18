# P6 项目模型重构讨论稿：项目级主流程与纵向能力模块

> 状态：已完成讨论，P6 实施计划已批准；本文保留讨论背景<br>
> 日期：2026-11-18<br>
> 关联问题：主模块概念、模块页调用视图残留、技术层模块、执行流入口节点
>
> 本文记录当前讨论形成的目标方向与待决事项。它不是已冻结的数据契约；实施前必须先更新正式设计文档、schema、validator 和迁移说明。

## 1. 触发问题

当前模型要求每个项目恰好有一个“主模块”，主流程也默认依附于该模块。实际样例暴露出两个问题：

### 1.1 student_system 的主模块撑不起来

`student_system` 的 `main` 模块页面只有入口与编排函数：

```text
5 个节点 / 4 条调用边 / 3 个入口 API
main / __main__ / client / server
```

该模块没有独立的 manager、config 或 model。它本质上是“程序入口文件集合”，不是业务能力模块。

### 1.2 gomoku 的主模块变成文件堆放区

`gomoku` 的 `main` 模块页面包含：

```text
14 个节点 / 10 条调用边
GameCli、_InputHandled、ParsedCommand、BoardRenderer
7 个 utility 函数
```

CLI、输入解析、渲染和协议模型被放入同一个“主模块”，导致模块能力页同时承担入口编排、终端适配、类型定义和调用图展示。

### 1.3 共享契约模块是按技术层切出的杂项桶

`student_system` 的 `contracts` 模块聚合了：

```text
DatabaseConfig
ProtocolMessage
StudentRecord
encode_message / decode_message
```

这些内容分别服务于不同 manager 和业务能力，不应因为“都是配置、模型或工具”就放入同一个技术层模块。

## 2. 核心目标

```text
Project
├─ 主流程卡片（项目级入口，不隶属于某个模块）
└─ 普通能力模块
    ├─ manager / entry / adapter / component
    ├─ 该模块自己的 config / model
    └─ 该模块自己的 utility
```

目标不是“主模块可选”，而是取消“主模块”这一独立模型概念：

- 所有模块都是普通能力模块；
- 主流程是项目级视图，不归属于任何模块；
- 项目页提供标准卡片式主流程入口；
- 模块页只展示模块能力与 Provider 结构；
- 调用关系保留在事实层和按需查询中，不作为模块能力页的默认结构。

## 3. 模块模型

### 3.1 模块统一

建议删除或废弃以下概念：

- `mainModuleId`；
- `moduleKind = main | functional`；
- “恰好一个主模块”的唯一性不变量；
- 主模块专属路由或默认选中逻辑。

模块继续保留职责角色：

```text
service / adapter / component / entry / test / other
```

入口文件可以归入一个普通模块，例如：

```text
app / terminal orchestration    role = entry
```

但它不再被称为主模块，也不默认承载主流程页面。

### 3.2 模块按业务能力纵向组织

模块应以 manager 或明确能力 facade 为中心：

```text
database
├─ Database             manager / adapter
├─ DatabaseConfig       config
├─ StudentRecord        model
└─ 数据库相关 utility

network
├─ NetworkAdapter       adapter
├─ ProtocolMessage      model
└─ encode_message / decode_message
```

原则：

- `config`、`model`、`utility` 是 Provider Role，不是模块类型；
- 每个源码文件、Provider 和模型必须有且仅有一个归属模块；
- 跨模块使用不会改变归属，也不自动产生“共享模块”；
- 不能建立 `contracts`、`shared`、`common`、`misc` 这类无业务边界的兜底模块；
- 确实具有独立职责的组件可以成为能力模块，例如异步反馈模块。

### 3.3 跨模块能力使用与所有权

模块对外暴露能力是正常边界，不是“共享模型”。

例如异步等待模块：

```text
async-feedback
└─ Spinner
   └─ context_manager capability: with Spinner(...)
```

`Spinner` 的 owner 是异步反馈模块。network、menu 等模块使用 `with Spinner(...)` 是依赖该模块的公开能力，不需要把 `Spinner` 再归入“共享模型”，也不需要为其建立共享契约模块。

“唯一 owner”应理解为：

- 每个文件必须属于且只属于一个模块；
- 每个 Provider 必须有一个明确归属模块；
- `config` / `model` / `contract` 类型的定义必须有一个明确归属模块；
- 一个能力被多个模块消费，不构成多 owner，也不构成共享模块。

该原则解决的是归属歧义和重复建模问题，不是限制跨模块能力复用。

## 4. 页面与流程模型

### 4.1 项目页

项目页包含：

- 一个或多个项目级主流程卡片；
- 全部普通能力模块卡片。

主流程卡片复用标准卡片样式，不采用异形布局、特殊 banner 或独立入口视觉语言。

### 4.2 主流程页

主流程页只展示项目级执行流：

- 以 `entrypoints` / `executionEntrypoints` 为分析入口；
- 不归属任何模块；
- 节点可以携带来源模块信息，但模块不是流程的所有者；
- 支持多个 flow 选择；
- 流程页不展示模块能力契约或调用总览。

### 4.3 模块能力页

模块能力页只回答“模块提供什么”：

- Provider / Capability；
- manager / config / model / contract / utility 摘要；
- 类型关系与继承关系；
- 不默认绘制调用边；
- 不嵌入主流程。

调用关系继续保存在：

- `callSites`；
- `functionDetails[].callers / callees`；
- Method Detail；
- trace / impact / DSM 等按需查询。

### 4.4 执行流 entry 节点

需要区分三个概念：

1. `entrypoints` / `executionEntrypoints`：项目级分析配置；
2. `entry` Provider Role：入口函数或入口类的职责标签；
3. execution flow 中的 `entry` 节点：执行流内的语义节点。

讨论倾向：

- 保留 `entrypoints` 配置；
- 保留 `entry` Provider Role；
- 取消 execution flow 中的 `entry` 语义节点；
- 入口信息由 flow 元数据和标准入口卡片表达；
- 第一个真实执行节点成为图的根；
- 空入口函数显示空状态，不伪造 entry / exit 节点。

如果暂不删除 `entry` 节点，至少应复用标准卡片样式，不再使用异形入口。

## 5. 调用视图清理

当前 `moduleGraphs[].edges` 是基于 CallSite 的调用聚合。它不应作为模块能力页的默认结构。

建议分两层处理：

1. UI 层：模块能力页不默认绘制调用线；
2. 数据层：评估是否从默认 bundle 移除 `moduleGraphs[].edges`，或显式标记为事实数据而非展示结构。

应保留：

- `callSites`；
- `functionDetails`；
- `typeRelations`；
- trace / impact / DSM 所需的边和索引。

`mainFlows` 与 `executionFlows` 的双投影最终应收缩为单一执行流投影。删除 `mainFlows` 前，必须先抽取其中仍有价值的共享动态分发解析能力。

## 6. 数据契约影响

该方向属于重大模型变更，建议作为 schema 5.0 候选，而不是 4.x 小版本：

- 移除或废弃 `projectGraph.mainModuleId`；
- 移除 `moduleKind`；
- 移除主模块唯一性校验；
- 评估移除 `projectGraph.mainFlows` / `primaryFlowId`；
- 重新定义 execution flow 节点集合与根节点规则；
- 模块页默认不展示调用边；
- 示例配置去掉 `mainModule` 与 `kind: main`；
- 旧配置在过渡期允许兼容字段，但产生 deprecation 诊断；
- 旧 bundle 使用历史 schema 追溯。

## 7. 建议的迁移顺序

```text
讨论定稿并更新正式设计文档
  → 抽取共享调用 / 动态分发解析
  → 实现项目级 flow 与标准流程入口卡片
  → 删除 mainFlows 与主模块模型
  → 收缩模块图调用边展示
  → 按业务能力重写示例配置
  → 更新 schema、validator、测试和 README
```

在共享动态分发解析完成前，不应直接删除 `mainFlows`，否则会丢失配置 hint、argparse、static registry 和 polymorphic 候选解析能力。

## 8. 待决事项

- execution flow 的 `entry` 节点是删除，还是仅统一为标准卡片；
- `moduleGraphs[].edges` 是从 bundle 删除，还是保留为数据事实但默认不展示；
- 多个入口 flow 在项目页使用单卡片聚合，还是一入口一卡片；
- 跨模块模型 owner 的最终判定规则；
- schema 5.0 的兼容窗口与旧配置迁移策略。

## 9. 变更门槛

- 该讨论稿不改变当前运行时行为；
- 任何实现必须先更新正式设计文档、schema 和 validator；
- 不允许先删除主模块 / `mainFlows` 再补契约；
- 不允许把模块页重新做成调用视图；
- 不允许以“共享”为名恢复无业务边界的技术层模块。
