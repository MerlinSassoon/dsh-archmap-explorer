# ArchMap 文档索引

> 最后更新：2026-11-18<br>
> 对应版本：ArchMap 1.6.0 / bundle schema 3.6

本索引用于区分**当前权威文档**与**历史归档文档**。新会话或后续维护应优先阅读当前权威文档；历史文档只用于追溯需求演进和旧版实现，不应作为当前契约。

## 1. 当前权威文档

| 文档 | 内容 |
|---|---|
| [`../README.md`](../README.md) | 产品定位、快速开始、配置、CLI、已知边界 |
| [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md) | 最新交接文档：当前状态、代码地图、数据契约、P3–P4 规划与风险 |
| [`archmap-architecture-spec.md`](archmap-architecture-spec.md) | P2.3/P2.4 架构与编码规范：四类物理文件、八角色语义、主模块/主流程边界、依赖方向与可见性 |
| [`p2.3-migration-plan.md`](p2.3-migration-plan.md) | P2.3 旧路径到新路径迁移记录、执行阶段与验收结果 |
| [`archmap-v3-design.md`](archmap-v3-design.md) | v3.6 数据契约、Provider Role/Visibility/Ownership、三层投影、CallSite、布局覆盖与语言前端边界 |
| [`archmap-api-contract-model.md`](archmap-api-contract-model.md) | Provider + Capability API 契约模型、Exposure、协议能力、延期项与 ArkTS 映射 |
| [`function-detail-p1.5-plan.md`](function-detail-p1.5-plan.md) | P1.5 决策与验收：移除 FunctionFlow，引入 FunctionDetail + Source View + Call Graph |
| [`p2.4-main-module-flow.md`](p2.4-main-module-flow.md) | P2.4：唯一主模块、功能模块、主流程 DAG、dispatch 候选与 composition 契约 |
| [`archmap-class-layer-plan.md`](archmap-class-layer-plan.md) | 类语义层设计来源与历史路线；类焦点页已不再计划，当前契约以 API 契约模型为准 |
| [`schema/archmap-v3-bundle.schema.json`](schema/archmap-v3-bundle.schema.json) | 当前 bundle JSON Schema |

## 2. 当前状态摘要

```text
P0    类语义数据模型                         已完成
P1    模块页类组件化与模块边界修复           已完成
P1.5  FunctionDetail + Source View + CallGraph 已完成
P2.0  项目页/模块页能力契约重构             已完成
P2.1  API 契约建模与展示                    已完成
P2.2  Provider Role 与模块组合               已完成
P2.3  架构规范落盘、自身代码迁移与语义归属   已完成（旧 shim 已删除）
P2.4  主模块/功能模块/主流程 DAG             已完成
P3    继承、接口、多态与继承 API             未开始
P4    类关系、API impact/user surface/DSM    未开始
```

当前默认产品形态：

```text
项目页（主模块 + 功能模块能力卡片）
  └─ 主模块页（entry → orchestrator/provider/interface 的主流程 DAG；可切换能力视图）
       └─ 功能模块页（Provider 组合 + 提供接口 + 类/自由函数）
            └─ 方法详情页（源码 + 备注 + LLM 语义 + callers/callees）
```

当前**没有**类焦点页路由，也**没有**语句级 FunctionFlow。类焦点页与类内方法图不在产品计划中。项目页默认不绘制模块依赖线；依赖证据保留在 `projectGraph.edges` 中。

P2.4 已完成模块语义纠偏与主流程边界冻结：每个项目恰好一个主模块，功能模块数量为 0..N；模块输入输出端口已删除；主流程只在主模块内部继续遍历，进入功能模块 canonical interface/provider 后停止，不穿透内部 utility。动态分发使用 dispatch 节点，候选边以虚线 low-confidence composition 表达。下一步进入 P3：继承、接口、多态与继承 API。

## 3. 历史归档文档

以下内容描述的是旧版执行流方案或旧版验收结果，保留用于追溯，不代表当前产品：

| 文档 | 状态 |
|---|---|
| [`archmap-2.0-design.md`](archmap-2.0-design.md) | 已归档：2.0 函数内部执行流设计；FunctionFlow 已在 P1.5 从默认产品路径移除 |
| [`HANDOFF.md`](HANDOFF.md) | 已归档：旧版交接；其工作区约束仍有参考价值，技术方案以本文索引中的当前文档为准 |
| [`v1-acceptance-report.md`](v1-acceptance-report.md) | 已归档：v1 验收记录，包含已移除的执行流页面与旧统计 |
| [`schema/workflow-2.0.schema.json`](schema/workflow-2.0.schema.json) | 已归档：旧 FunctionFlow schema |
| [`schema/example-checkout.json`](schema/example-checkout.json) | 已归档：旧执行流样例 |
| [`schema/example-checkout.svg`](schema/example-checkout.svg) / [`example-checkout.png`](schema/example-checkout.png) | 已归档：旧执行流示意图 |
| [`prototype/archmap-project-node-preview.html`](prototype/archmap-project-node-preview.html) | 已归档：旧前端样机 |
| [`prototype/archmap-project-node-preview-v2.html`](prototype/archmap-project-node-preview-v2.html) | 已归档：旧前端样机；当前交互以 `archmap/render/assets/` 为准 |

## 4. 文档维护规则

1. 当前产品状态只写入 `README.md`、`HANDOFF-P2-P4.md` 和本索引；旧文档只追加归档说明，不反向修改为“当前设计”。
2. 数据契约以 `archmap-v3-design.md`、`p2.4-main-module-flow.md` 和 `schema/archmap-v3-bundle.schema.json` 为准。
3. P1.5 之后的实现页统一称 **Method Detail**；不要再把 FunctionFlow 写回主产品路径。
4. 新增 P3–P4 能力时，先更新数据契约和交接文档，再更新 README 的使用说明。
5. 文档中的示例命令若引用自举配置，应同时核对 `examples/archmap_v3.archmap.json` 是否仍与源码模块一致。
