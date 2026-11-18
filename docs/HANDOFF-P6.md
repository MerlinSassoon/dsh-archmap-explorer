# ArchMap P6 交接文档

> 状态：P6.0-P6.5 已完成；P7 已修复其中 entry 节点移除问题。本文保留 P6 历史状态。<br>
> 分支：`P6`<br>
> 版本：ArchMap 2.0.0 / bundle schema 5.0<br>
> 日期：2026-11-18

## 1. 交接摘要

P6 完成了项目模型重构：

```text
项目级主流程
  + 普通能力模块
  + 单一 executionFlows 投影
  + 无主模块
  + 无模块页调用视图
```

核心结论：

- 不存在主模块、`mainModuleId`、`moduleKind`；
- 主流程是项目级视图，不属于任何模块；
- 所有模块都是普通能力模块，role 仅表达职责；
- 项目页使用标准卡片展示一个或多个执行流；
- execution flow 不再生成语义 `entry` 节点；
- 模块能力页只展示 Provider / Capability / 类型关系；
- `moduleGraphs[].edges` 已移除；
- `mainFlows` / `primaryFlowId` 已删除；
- 模块按业务能力纵向组织，`config/model/utility` 围绕 manager 归属；
- 禁止 `contracts` / `shared` / `common` / `misc` 技术层兜底模块。

## 2. 当前数据契约

当前 schema：`docs/schema/archmap-v5-bundle.schema.json`，版本 `5.0`。

已移除：

```text
projectGraph.mainModuleId
projectGraph.moduleKind
projectGraph.mainFlows
projectGraph.primaryFlowId
moduleGraphs[].moduleKind
moduleGraphs[].edges
executionFlow node kind=entry
```

保留：

```text
projectGraph.executionFlows
projectGraph.primaryExecutionFlowId
projectGraph.modules
projectGraph.edges          # 模块级关系事实，默认 UI 不绘制
projectGraph.typeRelations
moduleGraphs[].providedApis
moduleGraphs[].apiProviders
moduleGraphs[].nodes
moduleGraphs[].methodEdges
functionDetails
callSites
```

执行流节点集合：

```text
exit / free_function / interface / branch / multi_branch
loop / break / continue / return / dispatch
```

执行流边集合：

```text
next / true / false / case / default / loop_body / loop_complete
```

## 3. 动态分发

P6.1 引入共享 resolver：

```text
archmap/utility/call_resolution_utility.py
```

候选来源：

- 顶层 `dispatchHints`；
- 兼容旧字段 `mainFlow.dispatches`；
- 行内 `# archmap:dispatch ...`；
- argparse `set_defaults(func=...)`；
- 静态 registry；
- polymorphic candidates。

execution flow dispatch 节点输出：

```text
candidates
candidateCount
candidateSetComplete
candidateSource
unresolvedReason
```

候选只在节点详情面板展示并支持跳转 Method Detail，不展开为执行画布分支。

## 4. 模块规范化

### 4.1 student_system

```text
app              入口与顶层编排
network          NetworkAdapter + ProtocolMessage + ProtocolCodec
database         Database + DatabaseConfig
menu             MenuSystem + StudentRecord + display utility
async-feedback   Spinner
test             表格验证脚本
```

关键归属：

- `ProtocolMessage`、`ProtocolCodec` 归 network；
- `DatabaseConfig` 归 database；
- `StudentRecord` 归 menu；
- `Spinner` 归 async-feedback；
- 不保留 `contracts` 模块。

### 4.2 gomoku

```text
entry          main.py / __main__.py / cli.py
terminal-ui    input_parser.py / renderer.py
application    game.py + GameConfig
domain         board.py + models.py
ai-adapter     ai.py
```

`GameConfig` 跟随 application manager，不再单独建立技术层配置模块。

### 4.3 ArchMap 自举

```text
pipeline-entry
python-frontend
graph-projection
validation
rendering
```

原 `core-contracts` 技术层模块已删除。

## 5. 当前验收基线

```text
pytest:          101 passed, 1 skipped
browser smoke:   1 passed（ARCHMAP_RUN_BROWSER=1）
self build/check: OK
student build/check: OK
gomoku build/check: OK
diagnostics:     0 error / 0 warning / 0 info
```

ArchMap 自举：

```text
modules:              5
classes:              33
functions:            264
methods:              75
callSites:            3424
resolvedCalls:        610
typeRelations:        64
structuralRelations:  64
userSurfaces:         0
executionFlows:       1
executionNodes:       3
executionEdges:       2
```

student_system：

```text
modules:              6
classes:              8
functions:            52
methods:              42
callSites:            265
resolvedCalls:        50
typeRelations:        5
structuralRelations:  5
userSurfaces:         14
executionFlows:       1
executionNodes:       8
executionEdges:       9
```

gomoku：

```text
modules:              5
classes:              14
functions:            64
methods:              54
callSites:            185
resolvedCalls:        83
typeRelations:        54
structuralRelations:  54
userSurfaces:         4
executionFlows:       1
executionNodes:       10
executionEdges:       9
```

## 6. 常用验证命令

```bash
python3 -m pytest -q

ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py

python3 -m archmap build . \
  --config examples/archmap_v3.archmap.json \
  --out /tmp/archmap-self

python3 -m archmap check /tmp/archmap-self/architecture.json

python3 -m archmap build Projects/student_system \
  --config examples/student_system.archmap.json \
  --out /tmp/student-system

python3 -m archmap check /tmp/student-system/architecture.json

python3 -m archmap build /path/to/五子棋 \
  --config examples/gomoku.archmap.json \
  --out /tmp/gomoku

python3 -m archmap check /tmp/gomoku/architecture.json
```

## 7. 常用页面路由

```text
#/project
#/flow[/<flowId>]
#/module/<moduleId>
#/module/<moduleId>/function/<functionId>
```

## 8. 变更门槛

1. 不恢复主模块、`moduleKind`、`mainFlows`。
2. 不恢复模块能力页默认调用线。
3. 不恢复 execution flow `entry` 节点。
4. 不把动态分发候选展开为执行流分支。
5. 不建立 `contracts` / `shared` / `common` / `misc` 兜底模块。
6. 不允许一个源码文件被多个模块声明。
7. 数据契约变更必须先更新 schema、validator、测试和文档。
8. 项目页流程入口必须继续使用标准卡片样式。

## 9. 后续方向

P6 完成后可进入：

- User Surface 置信度校准与分组展示；
- ArkTS 前端接入；
- 增量扫描与缓存；
- 更精细的类型推断和跨模块模型 owner 校验；
- impact 报告与可视化 overlay。

任何后续方向都应继续以 bundle 事实层为唯一输入，不在渲染或查询层重新解析源码。
