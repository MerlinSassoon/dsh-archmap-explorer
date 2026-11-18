# P11 Dispatch 候选旅程计划

> 状态：已完成<br>
> 版本：ArchMap 2.5.0 / bundle schema 6.4<br>
> 制定日期：2026-11-19<br>
> 关联问题：P6.1 已解析 dispatch 候选，但执行流画布仍把 dispatch 当作信息黑洞

## 1. 背景

P5 主流程只展开入口函数自身的控制骨架，调用目标统一原子化。P6.1 在此基础上建立了共享 `DispatchResolver`，让 execution flow 的 `dispatch` 节点可以携带：

```text
candidates
candidateCount
candidateSetComplete
candidateSource
unresolvedReason
```

但 P6.1 的验收同时明确：

- 候选只在节点详情面板展示；
- 候选不展开为执行流控制边；
- dispatch 节点仍是原子边界。

这解决了“候选数据是否存在”的问题，但没有解决“候选如何参与主流程叙事”的问题。

对于 ArchMap 自身，`main()` 是 CLI 路由器：

```text
main()
  -> build_parser()
  -> dispatch args.func
  -> return
```

真正的用户旅程位于 `cmd_build`、`cmd_check`、`cmd_method` 等 9 个候选函数中。  
因此当前主流程虽然数据正确，但默认视图几乎没有业务信息量。

## 2. 问题定义

本轮不是继续提高 dispatch 解析率，而是解决三个叠加问题：

1. **入口语义问题**：路由器入口的控制骨架天然很薄；
2. **视图语义问题**：dispatch 候选被藏在详情面板，无法形成可读旅程；
3. **置信度表达问题**：`candidateSource=config` 且 `candidateSetComplete=true` 时，前端仍统一展示 `low confidence`，语义不准确。

## 3. 目标

把 dispatch 节点升级为**候选旅程导航容器**：

- 主流程画布仍保持 dispatch 原子节点；
- dispatch 卡片直接展示候选来源、完整性和候选摘要；
- 点击 dispatch 进入独立候选旅程视图；
- 候选旅程以真实候选 `free_function` 为 scope root；
- 每个候选 scope 只展开一层控制骨架；
- 候选 scope 不生成控制边回到主流程；
- 候选 scope 内不得继续生成候选旅程，避免递归爆炸。

## 4. 非目标

明确不做：

- 不把 dispatch 本身定义成 P10 意义上的 `flowScopes` callable root；
- 不在主流程画布新增 `dispatch -> candidate` 控制边；
- 不把候选实现合并进主画布；
- 不生成完整调用树；
- 不递归展开候选 scope 内部的 dispatch；
- 不把项目页拆成每个候选一张 flow card；
- 不改变 `flowScopes` 现有 root 约束；
- 不恢复旧调用总览；
- 不引入运行时分析、LLM 推断或 ArkTS 前端。

## 5. 产品模型

### L0 主流程层

保持现有 execution flow：

```text
main()
  -> build_parser()
  -> dispatch args.func
  -> return
```

新增的是 dispatch 节点的可读摘要和导航入口，不改变节点集合和主流程控制边。

### L1 候选旅程层

dispatch 节点拥有一个 `dispatchGroup`。一个 group 包含：

- dispatch 表达式；
- 候选来源与完整性；
- 已解析候选函数 ID；
- 每个候选对应的一级 execution scope；
- 预算截断和诊断信息。

UI 在 dispatch 页面用候选 Tab / 卡片选择器切换候选：

```text
args.func
配置声明 · 9/9 完整

[cmd_build] [cmd_check] [cmd_method] ... [cmd_trace]
```

选中候选后展示该候选的一级控制骨架：

```text
cmd_build()
  -> PipelineManager().build_architecture()
  -> validate
  -> write JSON / HTML
```

### L2 方法详情层

候选 scope 内节点仍可打开 Method Detail 查看源码、callers/callees 和类型关系。  
更深实现继续由现有 Method Detail 承载。

## 6. 核心不变量

1. `dispatch` 不是 callable scope root；
2. 候选 scope 的 `rootFunctionId` 必须是项目内真实 `free_function`；
3. `flow.scopes` 继续只承载 P10 callable scope；
4. 候选 scope 只存放在 `flow.dispatchGroups[].scopes`；
5. 主流程 `flow.edges` 不得新增候选关系边；
6. 一个 dispatch 节点的候选 scope 数量受独立预算限制；
7. 一个候选 scope 的 depth 恒为 1；
8. 候选 scope 内不得包含 `dispatchGroups` 或嵌套 scope；
9. 候选集合不完整时不得伪装成完整路由；
10. 预算截断必须显式记录 `truncated` 和 diagnostics。

## 7. 配置方案

新增顶层配置 `dispatchCandidates`，默认关闭，避免所有项目无条件生成候选 scope：

```json
{
  "dispatchCandidates": {
    "enabled": true,
    "completeOnly": true,
    "maxScopesPerDispatch": 16,
    "maxScopesPerFlow": 32,
    "maxNodesPerScope": 24,
    "maxEdgesPerScope": 32
  }
}
```

字段语义：

| 字段 | 默认值 | 说明 |
|---|---:|---|
| `enabled` | `false` | 是否生成 dispatch 候选旅程 |
| `completeOnly` | `true` | 仅对 `candidateSetComplete=true` 的 dispatch 生成 group |
| `maxScopesPerDispatch` | `16` | 单个 dispatch 最多生成多少候选 scope |
| `maxScopesPerFlow` | `32` | 单条 flow 所有 dispatch group 合计候选 scope 上限 |
| `maxNodesPerScope` | `24` | 单个候选 scope 节点预算 |
| `maxEdgesPerScope` | `32` | 单个候选 scope 边预算 |

非法值回退默认值并产生 `DISPATCH_CANDIDATE_LIMIT_INVALID` warning。

ArchMap 自举配置建议显式开启：

```json
"dispatchCandidates": {
  "enabled": true,
  "completeOnly": true
}
```

## 8. 数据契约

目标 bundle schema：`6.4`。

### 8.1 ExecutionFlow 新增字段

```json
{
  "dispatchGroups": []
}
```

### 8.2 dispatch 节点 `drilldown`

dispatch 节点新增 dispatch 专用 drilldown：

```json
{
  "kind": "dispatch",
  "status": "available",
  "reason": "dispatch_candidates",
  "dispatchGroupId": "dispatch-group:...",
  "candidateSource": "config",
  "candidateSetComplete": true,
  "candidateCount": 9,
  "candidateScopeCount": 9,
  "interfaceSummary": []
}
```

约束：

- 只有 kind=`dispatch` 的节点允许携带 `drilldown.kind=dispatch`；
- `interface`、`free_function` 节点不能携带 dispatch drilldown；
- `free_function` 的 P10 drilldown 继续使用现有 `scopeId` 语义；
- 旧消费者可忽略新增字段，但 schema 6.4 校验必须接受两种 drilldown。

### 8.3 DispatchGroup

```json
{
  "kind": "archmap.dispatch-group",
  "id": "dispatch-group:...",
  "parentNodeId": "exec:...:dispatch:...",
  "expression": "args.func",
  "candidateSource": "config",
  "candidateSetComplete": true,
  "candidateIds": ["fn:..."],
  "scopeIds": ["scope:..."],
  "scopes": [],
  "truncated": false,
  "diagnostics": []
}
```

### 8.4 候选 ExecutionScope

候选 scope 复用现有 `archmap.execution-scope` 主体结构，并新增来源字段：

```json
{
  "kind": "archmap.execution-scope",
  "id": "scope:dispatch:...",
  "parentNodeId": "exec:...:dispatch:...",
  "rootFunctionId": "fn:...cmd_build",
  "origin": "dispatch_candidate",
  "reason": "dispatch_candidate",
  "candidateSource": "config",
  "moduleId": "pipeline",
  "depth": 1,
  "entrypointId": "fn:...cmd_build",
  "name": "cmd_build() 候选流程",
  "nodes": [],
  "edges": [],
  "layout": {},
  "nodeCount": 0,
  "edgeCount": 0,
  "truncated": false,
  "omittedNodeCount": 0,
  "diagnostics": [],
  "interfaceSummary": []
}
```

候选 scope 内节点继续使用现有 execution node / edge 契约，不新增节点或边类型。

### 8.5 统计字段

bundle `stats` 新增：

```json
{
  "dispatchGroups": 1,
  "dispatchCandidateScopes": 9,
  "dispatchScopeNodes": 0,
  "dispatchScopeEdges": 0,
  "dispatchScopeTruncated": 0
}
```

semantic fingerprint 纳入 dispatch group、候选 scope 语义、候选来源和截断标记，但继续忽略布局坐标。

## 9. 后端构建流程

1. 加载并校验 `dispatchCandidates` 配置；
2. 在现有 execution flow 构建完成后遍历 `dispatch` 节点；
3. 读取共享 resolver 产出的 `candidates`、`candidateSource`、`candidateSetComplete`；
4. 按以下条件筛选候选：
   - candidate ID 可解析到项目内 `FunctionInfo`；
   - 非 synthetic；
   - 不是当前 flow entrypoint 的直接自调用；
   - `completeOnly=true` 时要求 `candidateSetComplete=true`；
5. 对每个候选复用 `build_entry_execution_skeleton()` 生成一级骨架；
6. 复用 `_trim_scope()`、helper interface hint 和 interface summary 逻辑；
7. 为候选 scope 生成独立 layout；
8. 应用 `maxScopesPerDispatch` / `maxScopesPerFlow` 预算；
9. 写入 dispatch 节点 `drilldown` 和 `flow.dispatchGroups`；
10. 汇总 stats 和 diagnostics。

任何候选生成失败都不得删除主流程 dispatch 节点，只记录诊断。

## 10. 诊断码

建议新增：

```text
DISPATCH_CANDIDATE_LIMIT_INVALID
DISPATCH_CANDIDATE_GROUP_DISABLED
DISPATCH_CANDIDATE_SET_INCOMPLETE
DISPATCH_CANDIDATE_ROOT_UNRESOLVED
DISPATCH_CANDIDATE_RECURSION_BLOCKED
DISPATCH_CANDIDATE_DISPATCH_BUDGET
DISPATCH_CANDIDATE_FLOW_BUDGET
DISPATCH_CANDIDATE_NODE_BUDGET
DISPATCH_CANDIDATE_EDGE_BUDGET
DISPATCH_CANDIDATE_SCOPE_TRUNCATED
```

warning 和 info 必须可在 bundle diagnostics 或 group diagnostics 中追溯。

## 11. 校验规则

validator 新增：

- schemaVersion 必须为 `6.4`；
- `dispatchGroups` 必须是数组；
- group parent 节点必须存在且 kind=`dispatch`；
- group parent `drilldown.dispatchGroupId` 必须反向指向 group；
- group 的 `candidateIds` 记录全部可解析候选；`scopeIds` 与 `scopes[].id` 一致；
- 预算截断的候选写入 `omittedCandidateIds`，且 `candidateIds = scope roots ∪ omittedCandidateIds`；
- 候选 scope `parentNodeId` 必须等于 group parent；
- 候选 scope root 必须存在于 functionDetails；
- 候选 scope depth 恒为 1；
- 候选 scope 不得嵌套 `scopes` 或 `dispatchGroups`；
- scope / group ID 全 bundle 唯一；
- 候选 scope 节点与边必须通过现有 execution 节点/边不变量；
- `flow.scopes` 与 `dispatchGroups[].scopes` 的 parent 约束分别校验，互不混用；
- 非 dispatch 节点携带 dispatch drilldown 必须报错；
- dispatch 节点携带 callable `scopeId` 必须报错。

## 12. 前端交互

### 12.1 主流程 dispatch 卡片

- 移除无条件的 `low confidence`；
- 展示来源与完整性：
  - `配置声明 · 9/9 完整`
  - `argparse 推断 · 部分`
  - `未解析`
- 展示前 3 个候选名称和 `+N`；
- 提供明确的“候选旅程”入口；
- 双击仍可打开 dispatch 表达式所在源码 / 方法详情。

### 12.2 候选旅程路由

```text
#/flow/<flowId>/dispatch/<nodeId>
#/flow/<flowId>/dispatch/<nodeId>/<candidateScopeId>
```

无 candidateScopeId 时默认选中第一个候选。  
刷新页面后根据 hash 恢复候选选择。

### 12.3 候选旅程页面

- 顶部展示 dispatch 表达式、来源、完整性；
- 横向候选 Tab / 卡片列表；
- 选中候选展示一级 execution canvas；
- 面包屑：

```text
项目 / main() / args.func / cmd_build()
```

- 支持返回主流程和打开 Method Detail；
- 候选 scope 内不渲染 L1 下钻按钮；
- 保留独立拖拽覆盖与适应画布能力。

### 12.4 dispatch 详情面板

- 候选主操作改为“打开候选旅程”；
- 源码 / Method Detail 作为次级操作；
- 显示 group 截断、候选来源和失败原因；
- 对不支持候选旅程的 dispatch 显示解释文案。

## 13. 测试计划

### 后端

- 配置默认关闭时不生成 `dispatchGroups`；
- 开启后仅为 dispatch 节点生成 group；
- 自举 `args.func` 生成 9 个候选 scope；
- 主流程节点数与边数不变；
- 候选 scope 根是真实 free_function；
- candidate scope 内不出现嵌套 group/scope；
- `completeOnly` 对 partial candidate set 生效；
- 单 dispatch / 单 flow 预算截断；
- candidate 源函数解析失败时保留 dispatch 且产生诊断；
- stats 和 fingerprint 稳定；
- validator 正反例。

### 前端 / 浏览器

- dispatch 卡片显示来源、完整性和候选摘要；
- 点击进入候选旅程；
- 候选 Tab 切换正确；
- hash 刷新恢复所选候选；
- 返回主流程并保留 dispatch 选中；
- 无运行时错误。

### 样例

- ArchMap 自举：1 个 dispatch group / 9 个候选 scope；
- `cmd_build` 候选旅程包含非空控制骨架；
- student_system 与 gomoku 现有 P10 scope 回归不变；
- self / student_system / gomoku build/check 全部通过。

## 14. 实施阶段

### P11.0 方案与契约冻结

- 完成本计划文档；
- 冻结 dispatch group / candidate scope 语义；
- 明确配置与路由。

### P11.1 配置与后端投影

- ProjectConfig / config loader；
- dispatch group 构建；
- 候选 scope 复用与预算；
- stats / diagnostics / fingerprint。

### P11.2 Schema 6.4 与校验

- 新 schema 文件；
- validation 规则；
- fixture 与单元测试。

### P11.3 前端交互

- dispatch 卡片摘要；
- 候选旅程路由；
- 候选 Tab 与 canvas；
- 详情面板操作；
- 浏览器 smoke。

### P11.4 自举与文档收口

- ArchMap 自举配置开启；
- README / design / config guide 更新；
- 全量回归与验收数据刷新。

## 15. 验收标准

```text
schemaVersion:                  6.4
self dispatchGroups:            1
self dispatchCandidateScopes:  9
self main flow nodes:           4（保持不变）
self main flow edges:           3（保持不变）
self dispatch scope:            cmd_build 等至少一个候选含非空控制骨架
candidate control edges:        0
nested dispatch groups:         0
validator errors:               0
pytest:                         全绿
browser smoke:                  通过
self/student/gomoku build/check:通过
```

## 16. 风险与对策

| 风险 | 对策 |
|---|---|
| 候选 scope 数量爆炸 | 双预算：单 dispatch + 单 flow；显式截断 |
| 候选集合不完整造成误导 | 默认 `completeOnly=true`，partial 明确标记 |
| 主流程被候选边污染 | 候选只存在于 dispatch group，不进入 `flow.edges` |
| 与 P10 callable scope 混淆 | 分离 `flow.scopes` 与 `flow.dispatchGroups` |
| 前端路由和状态复杂化 | 明确 hash 路由与刷新恢复验收 |
| 复用执行骨架产生维护分叉 | 抽取现有 scope 构建为共享内部函数 |
| bundle 体积增长 | 节点/边/候选三层预算和 stats 监控 |


## 17. 实施结果

P11 已按本计划完成：

- `ProjectConfig` 新增 `dispatchCandidates`，支持 `enabled` / `completeOnly` / 四个预算字段；
- execution flow 新增 `dispatchGroups[]`，dispatch 节点新增 `drilldown.kind=dispatch`；
- 每个完整候选生成独立 `archmap.execution-scope`，`origin=dispatch_candidate`，复用一级控制骨架、helper 接口提示、预算和 layout；
- 主流程节点和边不因候选旅程增加，候选实现不画回主画布；
- 候选 scope 内不递归生成 dispatch group；
- 前端支持 `#/flow/<flowId>/dispatch/<nodeId>/candidate/<candidateScopeId>`，候选 Tab、来源/完整性展示和 Hash 刷新恢复；
- 移除 dispatch 卡片无条件的 `low confidence`，改为显示 candidateSource、完整性和候选摘要；
- bundle schema 升级为 6.4，validator 新增 dispatch group / candidate scope 交叉引用、origin、depth、覆盖关系与嵌套禁令；
- ArchMap 自举 `args.func` 生成 1 个 group / 9 个候选旅程，主流程仍为 4 节点 / 3 边；
- 全量测试、浏览器 dispatch 旅程冒烟、self/student/gomoku build/check 通过。
