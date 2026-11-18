# P6 项目模型重构实施计划

> 状态：已批准，按阶段实施；P6.0/P6.1 已完成<br>
> 分支：`P6`<br>
> 起始基线：`P5.1` 分支 P5.5 完成状态<br>
> 日期：2026-11-18
>
> 本文是 P6 实施的当前计划入口。讨论背景见
> [`p6-project-model-discussion.md`](p6-project-model-discussion.md)，配置生成约束见
> [`project-config-generation-guide.md`](project-config-generation-guide.md)。

## 1. 目标

把 ArchMap 从“一个主模块 + 若干功能模块”的项目模型，调整为：

```text
项目级主流程
  + 普通能力模块
  + 单一 executionFlows 投影
  + 无主模块
  + 无模块页调用视图
```

核心目标：

- 取消 `mainModuleId`、`moduleKind` 和主模块唯一性不变量；
- 主流程是项目级视图，不属于任何模块；
- 所有模块统一为普通能力模块，保留 Provider Role；
- 模块按业务能力纵向组织，`config` / `model` / `utility` 围绕 manager 归属；
- 不建立 `contracts` / `shared` / `common` 兜底模块；
- 删除 `mainFlows` 双投影，保留 `executionFlows`；
- execution flow 不再使用语义 `entry` 节点，入口由 flow 元数据和标准入口卡片表达；
- 模块能力页不默认展示调用边；
- 保留 `callSites`、`functionDetails`、`typeRelations` 和 trace/impact/dsm 事实层。

## 2. 强制边界

- 每个源码文件、Provider 和模型有且仅有一个归属模块；
- 跨模块使用是依赖关系，不改变 owner，也不产生共享模块；
- `entry` 是 Provider Role，不是模块类型；
- `entrypoints` / `executionEntrypoints` 是项目级配置，不是模块配置；
- 调用总览 UI 不恢复；
- 执行流候选不展开为控制分支；
- 模块页不重新引入调用图；
- 任何破坏性契约变更必须先更新 schema、validator 和测试。

## 3. 阶段与提交

### P6.0：模型与契约定稿

产出：

- 本实施计划；
- 配置生成指南；
- 更新权威文档入口和 P5.5 交接状态。

提交要求：仅文档，不改运行时代码。

### P6.1：共享调用与动态分发解析（已完成）

产出：

- 建立模块无关的共享调用目标解析能力；
- 统一配置 dispatch hint、注释、argparse、static registry、polymorphic candidates；
- execution flow 消费共享解析结果；
- dispatch 详情展示候选与完整性；
- 保持执行流画布只有控制边；
- schema 暂不升级。

### P6.2：schema 5.0 与项目模型收缩

产出：

- 删除 `mainModuleId`、`moduleKind` 和主模块唯一性；
- 删除 `mainFlows` / `primaryFlowId`；
- execution flow 删除语义 `entry` 节点；
- 删除 `moduleGraphs[].edges` 的默认展示数据；
- 保留 `projectGraph.edges` 作为 DSM/关系查询事实，默认 UI 不绘制；
- schema 升级为 5.0；
- 旧配置兼容字段接受但忽略，并产生诊断。

### P6.3：模块归属与示例项目规范化

产出：

- `student_system` 删除 `main` / `contracts` 模块；
- `ProtocolMessage`、protocol codec 归入 network/protocol 模块并公开；
- `StudentRecord` 归入其展示/领域 owner 模块并公开；
- `DatabaseConfig` 归入 database；
- `gomoku` 取消主模块并拆分入口/终端/应用/领域能力；
- 自举配置完成同等模型校验；
- 配置生成指南与示例同步。

### P6.4：UI 与页面职责收口

产出：

- 项目页流程入口复用标准卡片；
- 多流程使用同构流程卡片；
- 主流程页独立且只展示执行流；
- 模块页只展示 Provider / Capability / 类型关系；
- 模块页不绘制调用边；
- 方法详情继续承担 callers/callees 与源码下钻。

### P6.5：回归、迁移与文档

产出：

- 全量测试、浏览器冒烟、自举 build/check；
- student_system 与 gomoku 新模型验收；
- schema 5.0 与旧 schema 文档；
- README、P5/P6 文档和配置指南同步；
- 最终交接说明。

## 4. 验收标准

- 项目页不再出现“主模块”；
- 所有模块均为普通能力模块；
- `projectGraph` 不再有 `mainModuleId`、`moduleKind`、`mainFlows`、`primaryFlowId`；
- execution flows 不包含 `entry` 节点；
- 模块页无调用连线；
- 自举 `args.func` dispatch 显示 9 个候选、complete、config；
- student_system 无 `contracts` 模块，跨模块类型有明确 owner 和公开接口；
- gomoku 无主模块，模块页无调用残留；
- 全量测试、浏览器冒烟、自举 build/check 通过；
- 所有旧 bundle 通过历史 schema 追溯，不要求当前 validator 接受。
