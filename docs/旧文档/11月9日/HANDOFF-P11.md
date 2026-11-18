# ArchMap P11 交接文档

> 状态：P11 已完成，可交接<br>
> 分支：`p11-dispatch-candidate-journeys`（尚未合并 master）<br>
> 版本：ArchMap 2.5.0 / bundle schema 6.4<br>
> 日期：2026-11-19<br>
> 阶段提交：`8226bf4 feat(p11): add dispatch candidate journeys`

## 1. 阶段目标

P11 解决 P6.1 遗留的**dispatch 语义阻塞**问题：

```text
P6.1 已解析 dispatch candidates
  → 但主流程只有一个 dispatch 原子节点
  → 候选只藏在详情面板
  → 路由器入口的主流程图几乎没有信息量
```

P11 保留 dispatch 的主流程原子边界，同时增加：

```text
dispatch 节点
  → dispatchGroup
  → 每个候选 free_function 的独立一级 scope
  → 候选旅程页面 / 候选 Tab
  → Method Detail / 源码
```

核心原则：

- dispatch 本身不是 callable scope root；
- 候选 `free_function` 才是真实 scope root；
- 主流程 `edges` 不新增 `dispatch -> candidate` 控制边；
- 候选 scope 深度固定为 1；
- 候选 scope 内不递归生成 dispatch group；
- 候选集合不完整时不伪装成完整路由；
- 候选 scope 数量、节点和边都有显式预算。

## 2. 完成内容

### 2.1 配置

新增顶层配置 `dispatchCandidates`：

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

规则：

- 默认 `enabled=false`，避免所有项目无条件生成候选 scope；
- `completeOnly=true` 默认只接受 `candidateSetComplete=true` 的 dispatch；
- 非法预算回退默认值并产生 `DISPATCH_CANDIDATE_LIMIT_INVALID` warning；
- ArchMap 自举配置已显式开启，并生成 `args.func` 的 9 个候选旅程。

### 2.2 后端 dispatch group

`executionFlows[]` 新增：

```text
dispatchGroups[]
```

每个 group 包含：

```json
{
  "kind": "archmap.dispatch-group",
  "id": "dispatch-group:...",
  "parentNodeId": "exec:...:dispatch:...",
  "expression": "args.func",
  "candidateSource": "config",
  "candidateSetComplete": true,
  "candidateCount": 9,
  "candidateIds": [],
  "scopeIds": [],
  "omittedCandidateIds": [],
  "scopes": [],
  "truncated": false,
  "diagnostics": []
}
```

覆盖关系：

```text
candidateIds = 已生成的 scope roots ∪ omittedCandidateIds
```

预算截断不会静默丢失候选，而是写入 `omittedCandidateIds` 和 group diagnostics。

dispatch 节点新增：

```json
{
  "drilldown": {
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
}
```

当候选集合不完整、无可用候选或预算耗尽时，`status=blocked`，不伪造 scope。

### 2.3 候选 scope

候选 scope 复用 P10 的 `archmap.execution-scope` 主体结构，并增加：

```json
{
  "origin": "dispatch_candidate",
  "reason": "dispatch_candidate",
  "candidateSource": "config",
  "depth": 1
}
```

约束：

- `parentNodeId` 指向 dispatch 节点；
- `rootFunctionId` 指向真实候选 `free_function`；
- 不得包含嵌套 `scopes` 或 `dispatchGroups`；
- 复用现有 execution node / edge 契约；
- 复用现有 layout、helper interface hints 与 `interfaceSummary`；
- scope 节点 ID 全 bundle 唯一。

### 2.4 校验与统计

validator 新增：

- schemaVersion 必须为 `6.4`；
- dispatch group 必须指向真实 dispatch 节点；
- parent node `drilldown.dispatchGroupId` 必须反向匹配；
- `scopeIds` 必须与 `scopes[].id` 一致；
- `scopes[].rootFunctionId` 必须是 `candidateIds` 子集；
- `candidateIds` 必须覆盖生成候选和 omitted 候选；
- candidate scope `origin=dispatch_candidate`；
- candidate scope `depth=1`；
- 不允许嵌套 scope / dispatch group；
- 非 dispatch 节点不能携带 dispatch drilldown；
- dispatch 节点不能携带接口 `scopeId`。

bundle `stats` 新增：

```text
dispatchGroups
dispatchCandidateScopes
dispatchScopeNodes
dispatchScopeEdges
dispatchScopeTruncated
```

semantic fingerprint 已纳入 dispatch group 与候选 scope 语义，但继续忽略布局坐标。

### 2.5 前端交互

主流程 dispatch 卡片：

- 移除无条件的 `low confidence`；
- 显示 candidateSource，例如“配置声明”；
- 显示候选完整性，例如“9/9 完整”；
- 显示候选预览，例如：
  `cmd_build / cmd_check / cmd_diff / +6`；
- 提供“候选旅程”入口。

新增路由：

```text
#/flow/<flowId>/dispatch/<nodeId>
#/flow/<flowId>/dispatch/<nodeId>/candidate/<candidateScopeId>
```

候选旅程页面：

- 顶部候选 Tab 切换；
- 显示 expression、来源、完整性、候选数、scope 节点数与外部接口；
- 支持 Hash 刷新恢复当前候选；
- 支持返回主流程；
- 候选 scope 内节点可打开 Method Detail；
- 候选 scope 内部不再显示新的候选旅程下钻按钮；
- 独立保存候选 scope 的拖拽布局覆盖。

详情面板：

- dispatch 候选列表中的可用候选以 `journey` 标识；
- 点击候选打开对应候选旅程；
- 未生成 scope 的候选仍可打开 Method Detail；
- 显示候选来源、完整性、预算截断说明和阻塞原因。

## 3. UI 路由

```text
#/project
#/flow/<flowId>
#/flow/<flowId>/scope/<nodeId>
#/flow/<flowId>/dispatch/<nodeId>
#/flow/<flowId>/dispatch/<nodeId>/candidate/<candidateScopeId>
#/module/<moduleId>
#/module/<moduleId>/function/<functionId>
```

## 4. 关键文件

```text
archmap/config/project_config.py
archmap/config/__init__.py
archmap/utility/config_utility.py
archmap/utility/execution_flow_utility.py
archmap/utility/graph_utility.py
archmap/utility/validate_utility.py
archmap/render/assets/app.js
examples/archmap_v3.archmap.json
docs/p11-dispatch-candidate-journeys-plan.md
docs/schema/archmap-v6.4-bundle.schema.json
tests/test_dispatch_candidate_scopes.py
tests/test_browser_smoke.py
```

## 5. 验收基线

```text
pytest:              140 passed, 1 skipped
browser smoke:       1 passed（显式开启）
schemaVersion:       6.4
package version:     2.5.0
self build/check:    OK
student build/check: OK
gomoku build/check:  OK
```

ArchMap 自举：

```text
modules:                  5
classes:                  35
functions:                283
methods:                  81
callSites:                4564
resolvedCalls:            757
typeRelations:            68
structuralRelations:      68
executionFlows:           1
executionNodes:           4
executionEdges:           3
flowCards:                1
flowScopes:               0
dispatchGroups:           1
dispatchCandidateScopes:  9
dispatchScopeNodes:       81
dispatchScopeEdges:       84
dispatchScopeTruncated:   0
executionOnlyCallables:   1
freeFunctionSurfaces:     0 capability / 201 internal / 1 execution
diagnostics:              0 error / 0 warning / 0 info
```

主流程验收：

- `main()` 主流程仍为 4 节点 / 3 边；
- `args.func` dispatch 生成 1 个 dispatch group；
- 9 个候选均生成独立 scope；
- `cmd_build` 候选 scope 包含非空真实控制骨架；
- 主流程 `edges` 中不存在候选控制边；
- 候选 scope 内不存在嵌套 dispatch group。

student_system：

```text
modules:                  6
capabilityModules:        4
emptyCapabilityModules:   2
executionFlows:           1
executionNodes:           9
executionEdges:           10
flowScopes:               2
dispatchGroups:           0
callSites:                265
resolvedCalls:            50
```

gomoku：

```text
modules:                  5
capabilityModules:        5
emptyCapabilityModules:   0
executionFlows:           1
executionNodes:           11
executionEdges:           10
flowScopes:               1
dispatchGroups:           0
callSites:                185
resolvedCalls:            83
```

## 6. 浏览器验收

已使用 Firefox Headless + geckodriver 验证：

- 主流程 dispatch 卡片显示候选摘要；
- “候选旅程”按钮进入 dispatch 路由；
- 9 个候选 Tab 正确渲染；
- 候选切换后画布节点正确变化；
- Hash 刷新后候选选择保持；
- 页面无运行时错误；
- P10 interface scope、方法详情、模块页、P3/P4 页面无回归。

## 7. 变更门槛

1. dispatch 本身不得被定义为 P10 意义上的 callable scope root；
2. 候选 scope root 必须是真实 `free_function`；
3. 主流程 `flow.edges` 不得新增 `dispatch -> candidate` 控制边；
4. 候选 scope 不得递归生成 dispatch group 或嵌套 scope；
5. `completeOnly=true` 时不得为不完整 candidate set 生成候选旅程；
6. 候选 scope 预算截断必须显式写入 `omittedCandidateIds` 和 diagnostics；
7. `flow.scopes` 与 `flow.dispatchGroups[].scopes` 的 parent 约束必须分别校验；
8. schema、validator、fingerprint、stats、UI 路由、测试和文档必须同步变更；
9. 不把 P11 候选旅程扩展成完整调用树或真实运行时路径分析。

## 8. 已知边界

- 候选来源依赖 P6.1 共享 resolver，静态解析不到的 dispatch 仍然无候选；
- `completeOnly=true` 时，不完整候选集合只显示 blocked 状态，不生成旅程；
- 候选 scope 只展开一层，不穿透候选内部的再分发；
- 候选 scope 的接口摘要仍是静态能力投影，不代表运行时实际调用；
- 默认关闭；只有显式开启 `dispatchCandidates.enabled` 的项目才生成 group；
- 候选旅程不在项目页拆成独立 flow card，仍是主流程内的下钻视图；
- 当前未实现候选旅程的按需懒构建，bundle 会预生成候选 scope；
- 模块层次、增量扫描、ArkTS 前端仍不在 P11 范围。

## 9. 后续建议

P11 完成后，建议下一阶段优先：

1. 真实项目解析质量与 unresolved call 诊断；
2. dispatch candidate 来源置信度与候选过滤策略；
3. 候选 scope 增量/懒构建，降低大型项目 bundle 体积；
4. User Surface 校准；
5. 增量扫描与缓存；
6. ArkTS 前端。

## 10. 交接检查清单

- [x] `dispatchCandidates` 配置模型与解析；
- [x] execution flow `dispatchGroups[]`；
- [x] dispatch 节点 dispatch drilldown；
- [x] 候选 free_function 一级 scope；
- [x] candidateIds / scopeIds / omittedCandidateIds 覆盖关系；
- [x] 双预算与截断诊断；
- [x] schema 6.4；
- [x] validator 交叉引用、origin/depth、嵌套禁令；
- [x] stats 与 fingerprint；
- [x] 主画布候选摘要与来源/完整性展示；
- [x] 候选旅程路由、候选 Tab、刷新恢复；
- [x] 浏览器 dispatch 旅程冒烟；
- [x] ArchMap 自举开启并生成 9 个候选 scope；
- [x] student_system / gomoku P10 scope 回归；
- [x] README、设计文档、P5 契约、配置指南、编码 Skill、P11 计划同步；
- [x] 工作区 clean。

## 11. 本阶段提交

```text
8226bf4 feat(p11): add dispatch candidate journeys
```
