# ArchMap 旧文档归档

> 最近归档日期：2026-11-19<br>
> 当前版本：ArchMap 2.5.0 / bundle schema 6.4

本目录封存 ArchMap 各阶段的**过程文档、历史设计、旧交接、迁移记录、旧验收和旧原型**。
这些材料用于追溯需求演进、设计取舍和验证历史，不代表当前产品契约。

## 当前权威文档

- [项目 README](../../README.md)
- [数据与扩展设计](../archmap-v3-design.md)
- [架构与编码规范](../archmap-architecture-spec.md)
- [API 契约模型](../archmap-api-contract-model.md)
- [archmap-config-generation](../archmap-config-generation.md)
- [archmap-code-conventions](../archmap-code-conventions.md)
- [当前 bundle schema 6.4](../schema/archmap-v6.4-bundle.schema.json)
- [DSH 插件使用文档](../dsh-plugin.md)
- [DSH 插件 0.1.0 交接](../HANDOFF-DSH-PLUGIN-0.1.0.md)

## README 过程内容归档

| 文档 | 内容 |
|---|---|
| [`README-历史过程与验收数据.md`](README-历史过程与验收数据.md) | 原 README 中的 P0–P12 阶段状态、P5/P10/P11 过程说明、历史测试与验收数据、旧文档维护规则 |
| [`HANDOFF-DSH-PLUGIN.md`](HANDOFF-DSH-PLUGIN.md) | 历史快照：DSH 插件 dsh-archmap-explorer 实施前设计决策、包结构、工具与 Skill 契约、实施顺序和验收门槛；当前状态见 `docs/dsh-plugin.md` 与 `docs/HANDOFF-DSH-PLUGIN-0.1.0.md` |
| [`archmap-v3-design-阶段补充.md`](archmap-v3-design-阶段补充.md) | 原数据与扩展设计顶部的 P5–P12 阶段补充说明 |
| [`archmap-api-contract-阶段规划与实现记录.md`](archmap-api-contract-阶段规划与实现记录.md) | 原 API 契约模型中的阶段规划和 P2.2 实现记录 |
| [`archmap-architecture-spec-历史迁移说明.md`](archmap-architecture-spec-历史迁移说明.md) | 原架构规范中的 P2.3 识别策略与迁移原则 |

## 阶段计划与交接归档

### 11月9日批次

| 文档 | 内容 |
|---|---|
| [`11月9日/p5-main-execution-flow.md`](11月9日/p5-main-execution-flow.md) | P5 有界主流程执行流计划与历史边界 |
| [`11月9日/p10-interface-drilldown-plan.md`](11月9日/p10-interface-drilldown-plan.md) | P10 一级接口 scope 计划、控制臂语义、自动发现和验收 |
| [`11月9日/p11-dispatch-candidate-journeys-plan.md`](11月9日/p11-dispatch-candidate-journeys-plan.md) | P11 dispatch 候选旅程计划、候选 scope、预算和验收 |
| [`11月9日/HANDOFF-P5.5.md`](11月9日/HANDOFF-P5.5.md) | P5.5 阶段交接：主流程页与模块能力页分离 |
| [`11月9日/p5.1-execution-card-style.md`](11月9日/p5.1-execution-card-style.md) | P5.1 执行流项目节点卡片样式设计 |
| [`11月9日/p5.1-execution-flow-fan-in-plan.md`](11月9日/p5.1-execution-flow-fan-in-plan.md) | P5.1 汇入与边束分层设计 |
| [`11月9日/p2.4-main-module-flow.md`](11月9日/p2.4-main-module-flow.md) | P2.4 主模块/主流程历史契约；已由后续 schema 取代 |
| [`11月9日/p6-project-model-discussion.md`](11月9日/p6-project-model-discussion.md) | P6 项目模型重构讨论背景 |
| [`11月9日/p6-project-model-plan.md`](11月9日/p6-project-model-plan.md) | P6 实施计划与阶段验收 |
| [`11月9日/HANDOFF-P6.md`](11月9日/HANDOFF-P6.md) | P6 阶段交接：schema 5.0、项目级流程与能力模块 |
| [`11月9日/p7-entry-model-plan.md`](11月9日/p7-entry-model-plan.md) | P7 入口语义与项目页布局修复计划 |
| [`11月9日/HANDOFF-P7.md`](11月9日/HANDOFF-P7.md) | P7 阶段交接：七角色、标准 flow entry 与 flow card 布局 |
| [`11月9日/p8-execution-only-plan.md`](11月9日/p8-execution-only-plan.md) | P8 executionOnlyCallables 与空能力模块计划 |
| [`11月9日/HANDOFF-P8.md`](11月9日/HANDOFF-P8.md) | P8 阶段交接：schema 6.1 与能力面透明化 |
| [`11月9日/p9-free-function-surface-plan.md`](11月9日/p9-free-function-surface-plan.md) | P9 自由函数能力边界与模块默认面计划 |
| [`11月9日/HANDOFF-P9.md`](11月9日/HANDOFF-P9.md) | P9 阶段交接：schema 6.2 与验收基线 |
| [`11月9日/HANDOFF-P10.md`](11月9日/HANDOFF-P10.md) | P10 阶段交接：一级接口 scope、控制臂语义、自动发现与 schema 6.3 |
| [`11月9日/HANDOFF-P11.md`](11月9日/HANDOFF-P11.md) | P11 阶段交接：dispatch 候选旅程、双预算、schema 6.4 与浏览器回归 |

## 其他归档文档

| 文档 | 内容 |
|---|---|
| [`archmap-2.0-design.md`](archmap-2.0-design.md) | 已归档：2.0 函数内部执行流设计；FunctionFlow 已从默认产品路径移除 |
| [`archmap-class-layer-plan.md`](archmap-class-layer-plan.md) | 已归档：类语义层设计来源与历史路线；类焦点页不在当前计划 |
| [`function-detail-p1.5-plan.md`](function-detail-p1.5-plan.md) | 已归档：FunctionDetail / Source View / Call Graph 引入记录 |
| [`p2.3-migration-plan.md`](p2.3-migration-plan.md) | 已归档：旧路径到 canonical 目录的迁移过程与验收 |
| [`HANDOFF.md`](HANDOFF.md) | 已归档：旧版交接文档 |
| [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md) | 已归档：P2.2–P4 阶段交接快照 |
| [`HANDOFF-P2.4-CLEANUP.md`](HANDOFF-P2.4-CLEANUP.md) | 已归档：P2.4 cleanup 分支交接与 UI/布局修复记录 |
| [`HANDOFF-P3.md`](HANDOFF-P3.md) | 已归档：P3 继承、实现、继承 API 与多态阶段交接 |
| [`HANDOFF-P4.md`](HANDOFF-P4.md) | 已归档：P4 结构关系、User Surface、Impact/Trace 与 DSM 阶段交接 |
| [`BRANCHES.md`](BRANCHES.md) | 已归档：P2.4/P3/P4 分支返回与恢复指引 |
| [`v1-acceptance-report.md`](v1-acceptance-report.md) | 已归档：v1 验收记录，包含已移除的执行流页面与旧统计 |

## 归档 schema

| 资产 | 内容 |
|---|---|
| [`schema/archmap-v6.3-bundle.schema.json`](schema/archmap-v6.3-bundle.schema.json) | 历史 bundle schema 6.3 |
| [`schema/archmap-v6.2-bundle.schema.json`](schema/archmap-v6.2-bundle.schema.json) | 历史 bundle schema 6.2 |
| [`schema/archmap-v6.1-bundle.schema.json`](schema/archmap-v6.1-bundle.schema.json) | 历史 bundle schema 6.1 |
| [`schema/archmap-v6-bundle.schema.json`](schema/archmap-v6-bundle.schema.json) | 历史 bundle schema 6.0 |
| [`schema/archmap-v5-bundle.schema.json`](schema/archmap-v5-bundle.schema.json) | 历史 bundle schema 5.0 |
| [`schema/archmap-v4-bundle.schema.json`](schema/archmap-v4-bundle.schema.json) | 历史 bundle schema 4.1 |
| [`schema/archmap-v4.0-bundle.schema.json`](schema/archmap-v4.0-bundle.schema.json) | 历史 bundle schema 4.0 |
| [`schema/archmap-v3-bundle.schema.json`](schema/archmap-v3-bundle.schema.json) | 历史 bundle schema 3.8 |
| [`schema/workflow-2.0.schema.json`](schema/workflow-2.0.schema.json) | 更早的 FunctionFlow schema |
| [`schema/example-checkout.json`](schema/example-checkout.json) | 旧执行流样例 |
| [`schema/example-checkout.svg`](schema/example-checkout.svg) | 旧执行流示意图 |
| [`schema/example-checkout.png`](schema/example-checkout.png) | 旧执行流示意图 |

## 归档原型

| 资产 | 内容 |
|---|---|
| [`prototype/p5.1-execution-cards-preview.html`](prototype/p5.1-execution-cards-preview.html) | P5.1 执行流卡片样机 |
| [`prototype/p5.1-loop-node-preview.html`](prototype/p5.1-loop-node-preview.html) | P5.1 循环节点样机 |
| [`prototype/archmap-project-node-preview.html`](prototype/archmap-project-node-preview.html) | 旧项目节点样机 |
| [`prototype/archmap-project-node-preview-v2.html`](prototype/archmap-project-node-preview-v2.html) | 旧项目节点样机；当前交互以 `archmap/render/assets/` 为准 |

## 归档规则

1. 归档文档不再作为当前实现、数据契约或验收标准的依据。
2. 新阶段的过程记录先保留在当前工作区；阶段完成并形成新的权威契约后，再迁入本目录。
3. 当前产品状态只维护在根 README、当前权威文档和 `docs/schema/archmap-v6.4-bundle.schema.json` 中。
4. 旧文档中的相对链接可能仍指向历史路径；需要查证时以当前权威文档为准。
