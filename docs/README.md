# ArchMap 文档索引

> 最后更新：2026-11-17<br>
> 对应版本：ArchMap 1.1.0 / bundle schema 3.1

本索引用于区分**当前权威文档**与**历史归档文档**。新会话或后续维护应优先阅读当前权威文档；历史文档只用于追溯需求演进和旧版实现，不应作为当前契约。

## 1. 当前权威文档

| 文档 | 内容 |
|---|---|
| [`../README.md`](../README.md) | 产品定位、快速开始、配置、CLI、已知边界 |
| [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md) | 最新交接文档：当前状态、代码地图、数据契约、P2–P4 规划与风险 |
| [`archmap-v3-design.md`](archmap-v3-design.md) | v3.1 数据契约、三层投影、CallSite、布局覆盖与语言前端边界 |
| [`function-detail-p1.5-plan.md`](function-detail-p1.5-plan.md) | P1.5 决策与验收：移除 FunctionFlow，引入 FunctionDetail + Source View + Call Graph |
| [`archmap-class-layer-plan.md`](archmap-class-layer-plan.md) | 类语义层设计来源与 P0–P4 路线；其中 Phase 0/1 与 P1.5 已完成，P2–P4 尚未开始 |
| [`schema/archmap-v3-bundle.schema.json`](schema/archmap-v3-bundle.schema.json) | 当前 bundle JSON Schema |

## 2. 当前状态摘要

```text
P0    类语义数据模型                         已完成
P1    模块页类组件化与模块边界修复           已完成
P1.5  FunctionDetail + Source View + CallGraph 已完成
P2    类焦点页与类内方法图                   未开始
P3    继承、接口、多态与类层次               未开始
P4    类关系、影响分析与架构查询             未开始
```

当前默认产品形态：

```text
项目页
  └─ 模块页（类节点 + 模块级自由函数）
       └─ 方法详情页（源码 + 备注 + LLM 语义 + callers/callees）
```

当前**没有**类焦点页路由，也**没有**语句级 FunctionFlow。

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
2. 数据契约以 `archmap-v3-design.md` 和 `schema/archmap-v3-bundle.schema.json` 为准。
3. P1.5 之后的实现页统一称 **Method Detail**；不要再把 FunctionFlow 写回主产品路径。
4. 新增 P2–P4 能力时，先更新数据契约和交接文档，再更新 README 的使用说明。
5. 文档中的示例命令若引用自举配置，应同时核对 `examples/archmap_v3.archmap.json` 是否仍与源码模块一致。
