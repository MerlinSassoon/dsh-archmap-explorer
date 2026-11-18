# ArchMap P10 交接文档

> 状态：P10 / P10.1 / P10.2 / P10.3 已完成，可交接<br>
> 分支：`p10-interface-drilldown`（尚未合并 master）<br>
> 版本：ArchMap 2.4.0 / bundle schema 6.3<br>
> 日期：2026-11-20

## 1. 阶段目标

P10 在 P5 有界主流程之上增加**一级接口 scope 下钻**：

```text
主流程 free_function 编排节点
  → L1 scope 聚焦视图
  → 直接外部能力接口 + 控制骨架 + helper 接口提示
  → Method Detail / 源码
```

核心原则：

- 主流程调用节点默认保持原子化；
- scope 深度硬限制为 1，不递归；
- 功能接口节点是模块能力边界，永远作为黑盒，不生成 scope；
- 普通语句不新增执行节点，只通过控制臂/边摘要表达；
- 自动发现只做保守候选，不自动把主画布铺满。

## 2. 完成内容

### P10：一级 scope 基础

- 新增 `flowScopes` 配置；
- 新增 `projectGraph.executionFlows[].scopes[]`；
- 主流程节点输出 `drilldown` 摘要；
- 新增独立 scope 路由：
  `#/flow/<flowId>/scope/<nodeId>`；
- scope 内支持执行节点、布局、拖拽、详情与源码跳转；
- 初版自动候选曾错误包含跨模块 interface，后续在 P10.1 修正。

### P10.1：interface 黑盒边界

- scope root 只允许 `free_function` 编排 callable；
- `interface` 节点不得生成 scope；
- 显式 roots 命中 interface 时只产生 warning；
- validator 新增：
  - `EXEC_INTERFACE_SCOPE_FORBIDDEN`
  - `EXEC_SCOPE_PARENT_KIND`
  - `EXEC_SCOPE_ROOT_MISMATCH`
  - `FLOW_SCOPE_INTERFACE_ROOT_FORBIDDEN`
- 前端对 interface 做防御性隐藏，即使旧 bundle 带错误 drilldown 也不渲染 L1。

### P10.2：控制臂语义摘要

- 普通赋值/非调用表达式不生成 `statement` 节点；
- branch 节点输出 `armSummaries`；
- 控制节点到后续可见节点之间的普通语句写入 edge：
  - `statements`
  - `statementLines`
- 多分支只保留 case 条件与 `implicitNext=loop_iteration`，不展示 case 内部赋值注释；
- 画布交互修正：
  - selected 优先于 hovered；
  - 单击空白 / 双击空白 / Esc 清除选择；
  - 画布平移使用移动阈值，不误清除选择；
  - 项目页保留默认不按关系邻域 dim 的既有语义。

### P10.3：本地编排 callable 自动发现

- `flowScopes.autoDetect=true` 已真正生效；
- 只检查当前 executionFlow 中可见的 `free_function`；
- 自动候选必须：
  - 与当前 flow 同模块；
  - 非 flow entry / interface / synthetic；
  - 非显式 root / executionOnly / 直接递归；
  - 试构建 scope 后至少触达一个跨模块外部能力接口；
  - 至少包含一个 `branch` / `multi_branch` / `loop`；
  - 未触发 scope 截断且节点预算内；
- 自动候选 reason 为 `auto_orchestrator`；
- 节点 `drilldown.autoDetected=true`；
- UI 在 L1 按钮和详情面板标识“自动发现”；
- 默认不自动打开 scope。

### 项目页空模块布局

- 空能力模块仍保留在 `projectGraph.modules` 与 `projectGraph.layout.nodes`；
- 默认布局顺序改为：
  1. flow cards；
  2. 可见 capability modules；
  3. 空能力模块；
- 网格列数按可见卡片数量计算；
- `layout.visibleCount` / `layout.columns` 输出布局元数据；
- `GEOMETRY_VERSION` 升级到 3，旧默认布局覆盖失效。

## 3. 配置契约

```json
"flowScopes": {
  "enabled": true,
  "roots": [
    "student_system.app.main:server",
    "student_system.app.main:client"
  ],
  "autoDetect": true,
  "maxScopesPerFlow": 6,
  "maxNodesPerScope": 24,
  "maxEdgesPerScope": 32
}
```

优先级：

```text
显式 flowScopes.roots
  > executionOnlyCallables
  > autoDetect 自动候选
```

规则：

- `roots` 支持 `module:qualname` 与 canonical function id；
- interface 永远不参与 scope；
- 自动发现默认 `false`；
- 显式 roots / executionOnly 先占用 scope 预算；
- 自动候选只使用剩余 `maxScopesPerFlow` 名额。

## 4. 数据契约

### ExecutionFlow

```text
executionFlows[].scopes[]
```

scope 关键字段：

```json
{
  "kind": "archmap.execution-scope",
  "id": "scope:...",
  "parentNodeId": "exec:...",
  "rootFunctionId": "fn:...",
  "moduleId": "app",
  "depth": 1,
  "reason": "configured_root | execution_only | auto_orchestrator",
  "autoDetected": false,
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

### 主流程节点

```json
{
  "drilldown": {
    "status": "available",
    "scopeId": "scope:...",
    "reason": "configured_root | execution_only | auto_orchestrator",
    "autoDetected": false,
    "interfaceSummary": []
  }
}
```

控制臂语义字段：

```text
armSummaries
interfaceHints
implicitNext
```

边语义字段：

```text
statements
statementLines
```

### 项目布局

```text
projectGraph.layout.visibleCount
projectGraph.layout.columns
```

## 5. UI 路由与行为

```text
#/project
#/flow/<flowId>
#/flow/<flowId>/scope/<nodeId>
#/module/<moduleId>
#/module/<moduleId>/function/<functionId>
```

行为：

- L1 节点显示接口数量；
- 自动候选 L1 按钮带“自动”和虚线样式；
- 节点详情显示 L1 来源；
- scope 详情显示 L1 来源与外部接口摘要；
- scope 内节点不可再次下钻；
- 单击节点选中并 dim 其他节点；
- 单击空白 / 双击空白 / Esc 清除选择；
- 平移与空白点击通过移动阈值区分。

## 6. 关键文件

```text
archmap/config/project_config.py
archmap/utility/config_utility.py
archmap/utility/execution_flow_utility.py
archmap/utility/execution_layout_utility.py
archmap/utility/graph_utility.py
archmap/utility/validate_utility.py
archmap/frontends/python/execution_utility.py
archmap/render/assets/app.js
archmap/render/assets/app.css
docs/p10-interface-drilldown-plan.md
docs/project-config-generation-guide.md
docs/schema/archmap-v6.3-bundle.schema.json
tests/test_flow_scopes.py
tests/test_browser_smoke.py
```

## 7. 验收基线

```text
pytest:              132 passed, 1 skipped
browser smoke:       1 passed
schemaVersion:       6.3
package version:     2.4.0
self build/check:    OK
student build/check: OK
gomoku build/check:  OK
diagnostics:         0 error / 0 warning / 0 info
```

ArchMap 自举：

```text
modules:                5
classes:                34
functions:              280
methods:                81
callSites:              4273
resolvedCalls:          723
typeRelations:          66
structuralRelations:    66
executionFlows:         1
executionNodes:         4
executionEdges:         3
flowCards:              1
flowScopes:             0
executionOnlyCallables: 1
freeFunctionSurfaces:   0 capability / 198 internal / 1 execution
capabilityModules:      5
emptyCapabilityModules: 0
```

student_system：

```text
modules:                6
capabilityModules:      4
emptyCapabilityModules: 2
executionOnlyCallables: 3
executionFlows:         1
executionNodes:         9
executionEdges:         10
flowCards:              1
flowScopes:             2
flowScopeNodes:         20
flowScopeEdges:         19
callSites:              265
resolvedCalls:          50
```

gomoku：

```text
modules:                5
capabilityModules:      5
emptyCapabilityModules: 0
executionOnlyCallables: 1
executionFlows:         1
executionNodes:         11
executionEdges:         10
flowCards:              1
flowScopes:             1
flowScopeNodes:         24
flowScopeEdges:         24
callSites:              185
resolvedCalls:          83
```

自动发现验收补充：

- gomoku `flowScopes.roots=[]` + `autoDetect=true` 时只发现 `_play_one_game()`；
- `_write()` / `_read_line()` 等叶子 helper 不生成 scope；
- interface 节点不生成 scope；
- student executionOnly server/client 优先于自动发现。

## 8. 变更门槛

1. 不恢复 interface 作为 scope root。
2. 不增加递归 scope 或图内多层套图。
3. 不新增 statement / state_update / basic_block 节点 kind，除非单独立项并更新契约。
4. 普通语句继续作为控制臂/边摘要，不逐语句节点化。
5. 自动发现必须保持保守；显式 roots / executionOnly 永远优先。
6. 不把 `autoDetect` 实现成自动铺开主画布；只预生成可点击 L1。
7. scope 预算截断必须显式标记，不静默丢节点。
8. 空能力模块后端保留，项目页布局追加到可见卡片之后。
9. 数据契约变更必须同步 schema、validator、fingerprint、测试、README 和配置指南。
10. 不把 `caseSummaries` / `defaultSummary` 重新引入多分支 UI。

## 9. 已知边界与后续方向

当前边界：

- P10 scope 只展开一级；
- 静态解析不到的接口不会伪造；
- 动态 dispatch 不展开候选实现；
- 自动发现只覆盖当前主流程可见、同模块 `free_function`；
- 普通语句不进入节点图；
- 类焦点页和类内方法图不在产品计划中。

后续方向：

- 真实项目解析质量与诊断体系；
- User Surface 置信度校准与分组；
- Impact 报告与可视化 overlay；
- 增量扫描与缓存；
- 模块层次 / 子模块；
- ArkTS 前端；
- 序列协议与 async_iterable。

## 10. 交接检查清单

- [x] `flowScopes` 配置与 schema 6.3；
- [x] interface 黑盒边界；
- [x] 显式 roots / executionOnly scope；
- [x] 一级 scope 数据、布局、路由与详情；
- [x] 控制臂/边语句摘要；
- [x] 自动发现本地编排 callable；
- [x] 自动候选优先级与预算；
- [x] validator / fingerprint / stats；
- [x] 空能力模块布局紧凑化；
- [x] 选择高亮与空白清除交互；
- [x] README、P10 计划、配置指南、设计文档同步；
- [x] 全量测试、浏览器冒烟、self/student/gomoku build/check。

## 11. 本阶段提交

```text
717ca4a feat(p10): add one-level flow interface drilldown
2ca1f62 fix(p10.1): keep capability interfaces as black-box boundaries
ca81344 feat(p10.2): summarize control-arm statements without node growth
d41d328 fix(p10.2): revert multi-branch case notes and clear canvas focus
ec44f8a fix(project-layout): compact visible cards before empty modules
0675c4c feat(p10.3): auto-discover local orchestration callables
```
