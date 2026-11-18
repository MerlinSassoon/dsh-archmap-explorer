# P10 接口级主流程下钻计划

> 状态：已完成<br>
> 当前 schema：6.3<br>
> 版本：ArchMap 2.4.0

## 1. 背景与目标

当前 P5 执行流只展开入口函数控制骨架，调用目标统一原子化。该边界保证了主流程可读性，但也隐藏了流程节点实际触达的外部模块接口。

P10 增加**一级 callable scope 下钻**：

- 主流程节点保持原子化，不递归展开；
- 节点上展示其一级 scope 的外部接口摘要；
- 点击可进入独立的 scope 聚焦视图；
- scope 内展示目标函数控制骨架、直接外部接口和紧凑内部 helper；
- 深度硬限制为 1；更深实现进入 Method Detail。

P10 不把主流程退化为完整调用图。

## 2. 产品层级

### L0 主流程层

保持当前执行流语义。新增节点级 `drilldown` 元数据和外部接口摘要，不新增主流程节点。

### L1 接口下钻层

一个 scope 对应一个 callable。scope 视图包含：

- `entry` / `exit`；
- 目标函数自身控制骨架；
- 直接调用的公开外部接口；
- 紧凑内部 helper 或由 helper 触达的接口提示；
- 预算截断和诊断信息。

scope 内节点均为 terminal，不提供二级下钻。

### L2 方法详情层

完整源码、callers/callees、类型关系与 User Surface 继续由现有 Method Detail 承载。

## 3. Scope 根节点边界

允许成为 scope root：

1. 配置 `flowScopes.roots` 显式指定的流程编排 callable；
2. `executionOnlyCallables` 中的流程编排 callable。

硬约束：

- execution 节点 kind 必须是 `free_function`；
- `interface` 节点是功能模块暴露的能力边界，永远不可作为 scope root；
- `entry`、`dispatch` 和控制节点不可作为 scope root；
- 显式 roots 命中 interface 时只产生 warning，不生成 scope。

不允许生成 scope：

- 同模块 private helper，除非显式配置；
- constructor / dunder；
- utility Provider；
- unresolved call；
- 动态 dispatch；
- 低置信度多态候选；
- 递归/循环节点；
- scope 内部节点。

## 4. Scope 内容规则

完整展示：

- 目标函数 entry / exit 与控制节点；
- 直接调用的外部公开能力接口；
- 直接出现的 User Surface primitive。

紧凑展示：

- 同模块 private helper 不递归展开；
- helper 的外部接口触达作为 `interfaceSummary` 或节点提示保留。

不展示：

- 深层 helper 完整控制流；
- dispatch 候选实现；
- try/except、数据流、逐语句节点；
- 完整调用树。

## 5. 配置

建议配置形态：

```json
"flowScopes": {
  "enabled": true,
  "roots": [
    "student_system.app.main:server",
    "student_system.app.main:client",
    "gomoku.cli:GameCli._play_one_game"
  ],
  "maxScopesPerFlow": 6,
  "maxNodesPerScope": 24,
  "maxEdgesPerScope": 32
}
```

非法值回退默认并产生 warning。P10.1 起不再自动把跨模块 capability/interface 节点转成 scope；P10.3 起 `autoDetect=true` 会从主流程可见的 `free_function` 中保守发现同模块本地编排 callable。显式 roots 和 executionOnly 优先，接口节点永远不参与自动发现。

## 6. 数据契约

schema 升级到 6.3。

主流程节点新增：

```json
"drilldown": {
  "status": "available | blocked | none",
  "scopeId": "scope:...",
  "reason": "configured_root | execution_only",
  "interfaceSummary": []
}
```

ExecutionFlow 新增：

```json
"scopes": [
  {
    "id": "scope:...",
    "parentNodeId": "node:...",
    "rootFunctionId": "fn:...",
    "moduleId": "app",
    "depth": 1,
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
]
```

约束：

- scope 复用现有 execution node / edge 契约，不新增 kind；
- scope 深度恒为 1；
- 父流程边只连接父节点，不连接 scope 内部节点；
- scope 节点 ID 全 bundle 唯一；
- semantic fingerprint 纳入 scope，忽略 layout；
- 预算截断必须显式标记，不静默丢失。

## 7. UI 与交互

- 主流程节点显示外部接口摘要，最多展示少量 chip；
- 可下钻节点显示 `L1` 或下钻入口；
- 路由：`#/flow/<flowId>/scope/<nodeId>`；
- scope 页面显示面包屑并支持返回主流程；
- 父节点返回后保持高亮；
- scope 使用现有执行流卡片和布局算法；
- scope 内节点可打开 Method Detail，但不可再次下钻。

采用独立 scope 聚焦视图，不在主画布内递归套图，避免父布局重排和组合爆炸。

## 8. 后端流程

1. 解析并校验 `flowScopes` 配置；
2. 从 execution flow 节点筛选 scope roots；
3. 为每个 root 复用执行骨架构建逻辑生成一级 scope；
4. 分类外部接口、内部 helper、dispatch 与 unresolved；
5. 提取 `interfaceSummary`；
6. 应用节点/边预算并生成诊断；
7. 写入父节点 `drilldown` 和 `executionFlow.scopes`。

建议诊断码：

```text
FLOW_SCOPE_ROOT_UNRESOLVED
FLOW_SCOPE_ROOT_BLOCKED
FLOW_SCOPE_NO_EXTERNAL_INTERFACE
FLOW_SCOPE_NODE_BUDGET_EXCEEDED
FLOW_SCOPE_EDGE_BUDGET_EXCEEDED
FLOW_SCOPE_CYCLE_BLOCKED
FLOW_SCOPE_DEPTH_BLOCKED
```

## 9. 校验与测试

- schema 6.3 契约测试；
- scope parent / root / node / edge 交叉引用校验；
- 深度、预算、ID 唯一性校验；
- scope 内不得嵌套 scope；
- 动态 dispatch 不展开候选实现；
- unresolved root 不伪造 scope；
- student_system：server 显示数据库接口，client 显示 `MenuSystem.run()`，不展开菜单内部；
- gomoku：`_play_one_game` 显示对局/输入/渲染接口，不展开领域实现；
- 浏览器 smoke 覆盖下钻、返回、刷新恢复和运行时错误；
- 全量测试、自举 build/check。

## 10. 阶段与验收

### P10.0 契约与方案冻结

- 计划文档；
- 配置、schema、节点/边语义冻结。

### P10.1 后端 scope 构建

- scope 模型；
- root 筛选；
- scope 骨架；
- 接口摘要；
- 预算和诊断；
- 单元测试。

### P10.2 校验与布局

- validator；
- layout；
- fingerprint；
- schema 6.3。

### P10.3 前端下钻

- 主节点摘要；
- scope 路由与视图；
- 面包屑和返回；
- 浏览器 smoke。

### P10.4 样例与文档收口

- student/gomoku 配置；
- README 与权威文档；
- 全量验收。

## 11. 明确不做

- 递归 scope 或主画布套图；
- 完整调用树；
- 类焦点页；
- try/except、数据流、逐语句 CFG；
- dispatch 候选实现展开；
- ArkTS 前端；
- 增量扫描与缓存；
- 序列协议推断。

## 12. 实施结果

P10 已按本计划完成：

- schema 升级为 `6.3`，新增 `executionFlows[].scopes[]`、节点 `drilldown` 与 `interfaceHints`；
- `flowScopes` 配置支持 `enabled` / `roots` / 三项预算；
- 主流程中的 `free_function` 编排节点可显示外部接口摘要，并通过 L1 入口打开独立 scope 视图；
- `interface` 节点强制黑盒：不生成 `drilldown`，不渲染 L1 入口；
- scope 路由为 `#/flow/<flowId>/scope/<nodeId>`，支持面包屑返回与布局独立持久化；
- scope 深度硬限制为 1，validator 拒绝嵌套 scope、错误 parent link 和非法预算结构；
- 内部 helper 保持原子节点，其直接触达的外部接口通过 `interfaceHints` 展示；
- student_system 生成 2 个 scope（server / client），gomoku 生成 `_play_one_game` scope；
- 全量测试、浏览器下钻冒烟、self/student/gomoku build/check 均通过。

## 13. P10.1 语义收紧

P10.1 修正了 P10 初版中 `autoDetect` 把跨模块 capability 节点转成 scope 的问题：

- scope root 必须是 `free_function` 编排 callable；
- `interface` 节点是功能模块暴露的能力边界，不允许生成 scope；
- student_system 的 `NetworkAdapter.init_connection()` 不再显示 L1；
- student_system 的 scope 数量从 3 降为 2，仅保留 `server` / `client`；
- scope 内仍展示 `Database.actions()`、`MenuSystem.run()` 等 interface 子节点；
- validator 新增 `EXEC_INTERFACE_SCOPE_FORBIDDEN`、`EXEC_SCOPE_PARENT_KIND` 与 `EXEC_SCOPE_ROOT_MISMATCH`；
- 显式 roots 命中 interface 时报告 `FLOW_SCOPE_INTERFACE_ROOT_FORBIDDEN`，不生成 scope；
- 前端对 interface 节点做防御性隐藏，即使旧 bundle 带错误 `drilldown` 也不显示 L1 按钮。

## 14. P10.2 控制臂语义摘要

P10.2 在不增加 statement / state_update / basic_block 节点的前提下补足普通语句语义：

- branch 节点新增 `armSummaries`，记录 true/false 臂内不可见普通语句、源码行和下一控制动作；
- 普通语句如果位于控制节点与后续可见节点之间，通过 edge `statements` / `statementLines` 表达；
- 多分支不生成 case 内部语句摘要；case 只保留条件标签，避免重复条件和误导性截断；
- 循环体末尾 endpoint 标记 `implicitNext=loop_iteration`，UI 显示“隐式进入下一轮循环”；
- 选中高亮优先于 hover；单击空白、双击空白或 Esc 清除选择；
- 主流程和 scope 均复用同一摘要机制；
- 不新增执行节点 kind，不改变既有控制流算法和分支 fan-in 规则；
- 新增 schema 可选字段：`armSummaries` / `implicitNext` / edge `statements` / `statementLines`；
- 浏览器回归覆盖 edge 语句标签、控制臂摘要和节点裁剪检查。

## 15. P10.2 交互收口

- 多分支 case 内部注释已回退；不再生成或渲染 `caseSummaries` / `defaultSummary`；
- `implicitNext=loop_iteration` 保留，用于解释循环体末尾分支的隐式继续；
- `focusPage` 改为 selected 优先于 hovered，避免鼠标经过其他节点时选中焦点丢失；
- 单击画布空白清除选择；
- 双击画布空白清除选择并保留适应画布；
- 画布平移通过移动阈值与空白点击区分，拖拽不会误清除选择；
- Esc 继续作为键盘清除选择入口；
- 项目页保留默认不按关系邻域 dim 的既有语义，关系模式下和其他图页面一样支持 focus / 清除。

## 16. 空能力模块布局收口

空能力模块继续保留在 `projectGraph.modules` 和 `projectGraph.layout.nodes` 中，但默认布局改为：

1. 先排列 `flowCards`；
2. 再排列 `capabilitySurface.hasProviders=true` 的模块；
3. 最后排列空能力模块；
4. 网格列数按可见卡片数量计算，而不是全部模块数量。

因此前端过滤空模块后，可见卡片仍占据连续的前部网格，不会在默认项目页留下空洞。`layout.visibleCount` / `layout.columns` 输出当前布局使用的可见数量和列数。用户已有本地拖拽覆盖仍按其自定义坐标显示；重置布局后恢复正常紧凑默认。

## 17. P10.3 本地编排 callable 自动发现

P10.3 实现了保守的 `flowScopes.autoDetect`：

- 只检查当前 executionFlow 中已经出现的 `free_function` 节点；
- 只接受与当前 flow 同模块的 target callable；
- 排除 flow entry、interface、已显式 root、已 executionOnly、synthetic、直接递归；
- 用现有 scope 构建器试构建，要求：
  - 至少触达一个跨模块外部能力接口；
  - 至少包含一个 branch / multi_branch / loop；
  - 未触发 scope 截断；
  - scope 节点预算内；
- 显式 roots / executionOnly 先构建，自动候选只使用剩余 `maxScopesPerFlow` 预算；
- 自动候选 reason 为 `auto_orchestrator`，节点 `drilldown.autoDetected=true`；
- 默认不自动打开 scope，只预生成可点击 L1；
- UI 在节点详情和 L1 按钮上标识“自动发现”；
- README、配置指南、schema、validator、fingerprint 和浏览器回归同步更新。
