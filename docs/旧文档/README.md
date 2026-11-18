# ArchMap 旧文档归档

> 最近归档日期：2026-11-19<br>
> 当前版本：ArchMap 2.3.0 / bundle schema 6.2

本目录用于封存 ArchMap 各阶段的**过程文档、历史设计、旧交接、迁移记录、旧验收和旧原型**。
这些材料用于追溯需求演进、设计取舍和验证历史，不代表当前产品契约。

当前权威文档请从根文档入口开始：

- [项目 README](../../README.md)
- [当前数据契约](../archmap-v3-design.md)
- [P5 主流程执行流契约](../p5-main-execution-flow.md)
- [架构与编码规范](../archmap-architecture-spec.md)
- [API 契约模型](../archmap-api-contract-model.md)
- [规范化项目配置生成指南](../project-config-generation-guide.md)
- [被分析项目代码生成 Skill](../约定编程skill.md)
- [当前 bundle schema](../schema/archmap-v6.2-bundle.schema.json)

## 11月9日归档批次

本批次归档 P5.1–P9 阶段的过程计划、讨论记录和阶段交接文档：

| 文档 | 内容 |
|---|---|
| [`HANDOFF-P5.5.md`](11月9日/HANDOFF-P5.5.md) | P5.5 阶段交接：主流程页与模块能力页分离 |
| [`p5.1-execution-card-style.md`](11月9日/p5.1-execution-card-style.md) | P5.1 执行流项目节点卡片样式设计 |
| [`p5.1-execution-flow-fan-in-plan.md`](11月9日/p5.1-execution-flow-fan-in-plan.md) | P5.1 汇入与边束分层设计 |
| [`p2.4-main-module-flow.md`](11月9日/p2.4-main-module-flow.md) | P2.4 主模块/主流程历史契约；已由后续 schema 取代 |
| [`p6-project-model-discussion.md`](11月9日/p6-project-model-discussion.md) | P6 项目模型重构讨论背景 |
| [`p6-project-model-plan.md`](11月9日/p6-project-model-plan.md) | P6 实施计划与阶段验收 |
| [`HANDOFF-P6.md`](11月9日/HANDOFF-P6.md) | P6 阶段交接：schema 5.0、项目级流程与能力模块 |
| [`p7-entry-model-plan.md`](11月9日/p7-entry-model-plan.md) | P7 入口语义与项目页布局修复计划 |
| [`HANDOFF-P7.md`](11月9日/HANDOFF-P7.md) | P7 阶段交接：七角色、标准 flow entry 与 flow card 布局 |
| [`p8-execution-only-plan.md`](11月9日/p8-execution-only-plan.md) | P8 executionOnlyCallables 与空能力模块计划 |
| [`HANDOFF-P8.md`](11月9日/HANDOFF-P8.md) | P8 阶段交接：schema 6.1 与能力面透明化 |
| [`p9-free-function-surface-plan.md`](11月9日/p9-free-function-surface-plan.md) | P9 自由函数能力边界与模块默认面计划 |
| [`HANDOFF-P9.md`](11月9日/HANDOFF-P9.md) | P9 阶段交接：schema 6.2 与现行验收基线 |

## 其他归档文档

| 文档 | 内容 |
|---|---|
| [`archmap-2.0-design.md`](archmap-2.0-design.md) | 已归档：2.0 函数内部执行流设计；FunctionFlow 已在 P1.5 从默认产品路径移除 |
| [`archmap-class-layer-plan.md`](archmap-class-layer-plan.md) | 已归档：类语义层设计来源与历史路线；类焦点页不再计划 |
| [`function-detail-p1.5-plan.md`](function-detail-p1.5-plan.md) | 已归档：P1.5 移除 FunctionFlow、引入 FunctionDetail / Source View / Call Graph 的实现记录 |
| [`p2.3-migration-plan.md`](p2.3-migration-plan.md) | 已归档：P2.3 旧路径到 canonical 目录的迁移过程与验收记录 |
| [`HANDOFF.md`](HANDOFF.md) | 已归档：旧版交接文档 |
| [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md) | 已归档：P2.2–P4 阶段交接快照 |
| [`HANDOFF-P2.4-CLEANUP.md`](HANDOFF-P2.4-CLEANUP.md) | 已归档：P2.4 cleanup 分支交接、UI/布局/协议能力修复记录 |
| [`HANDOFF-P3.md`](HANDOFF-P3.md) | 已归档：P3 继承、实现、继承 API 与多态阶段交接 |
| [`HANDOFF-P4.md`](HANDOFF-P4.md) | 已归档：P4 结构关系、User Surface、Impact/Trace 与 DSM 阶段交接 |
| [`BRANCHES.md`](BRANCHES.md) | 已归档：P2.4/P3/P4 分支返回与恢复指引 |
| [`v1-acceptance-report.md`](v1-acceptance-report.md) | 已归档：v1 验收记录，包含已移除的执行流页面与旧统计 |

## 归档资产

| 资产 | 内容 |
|---|---|
| [`schema/workflow-2.0.schema.json`](schema/workflow-2.0.schema.json) | 已归档：旧 FunctionFlow schema |
| [`schema/example-checkout.json`](schema/example-checkout.json) | 已归档：旧执行流样例 |
| [`schema/example-checkout.svg`](schema/example-checkout.svg) | 已归档：旧执行流示意图 |
| [`schema/example-checkout.png`](schema/example-checkout.png) | 已归档：旧执行流示意图 |
| [`prototype/archmap-project-node-preview.html`](prototype/archmap-project-node-preview.html) | 已归档：旧前端样机 |
| [`prototype/archmap-project-node-preview-v2.html`](prototype/archmap-project-node-preview-v2.html) | 已归档：旧前端样机；当前交互以 `archmap/render/assets/` 为准 |

## 归档规则

1. 归档文档不再作为当前实现、数据契约或验收标准的依据。
2. 新阶段的过程记录先进入当前工作区；阶段完成并形成新的权威契约后，再迁入本目录。
3. 当前产品状态只维护在根 README 和 `docs/` 下的权威文档中。
4. 旧文档中的相对链接可能仍指向历史路径；需要查证时以当前权威文档为准。
