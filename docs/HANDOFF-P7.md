# ArchMap P7 交接文档

> 状态：P7.0-P7.5 已完成<br>
> 分支：`P7`<br>
> 版本：ArchMap 2.1.0 / bundle schema 6.0<br>
> 日期：2026-11-18

## 1. 修复摘要

P7 修复了 P6 入口模型中的层级混淆：

```text
Provider Role
Execution Flow Node
Project Page Item
```

最终模型：

- Provider Role 只保留七角色；
- `entry` 只作为 execution flow 节点类型存在；
- 每条执行流恰好一个标准 `entry` 节点；
- 项目页 flow card 与 module card 同层、同网格；
- 入口检测由项目级 `entrypoints` / `executionEntrypoints` 驱动；
- 模块不再承载 `entry` Provider Role。

## 2. 七 Provider Role

```text
config / model / manager / adapter / component / contract / utility
```

已删除：

```text
ProviderRole = entry
moduleComposition.entry
providerRoleCounts.entry
module role = entry
```

入口相关事实改为：

```text
functionDetails[].isFlowEntry
functionDetails[].isEntry
moduleGraphs[].entryFunctionIds
moduleGraphs[].flowEntryFunctionIds
executionFlows[].entrypointId
executionFlow.nodes[kind=entry]
```

## 3. Execution Flow 入口节点

`entry` 节点已恢复为正式 flow node：

```text
entry / exit / free_function / interface / branch / multi_branch
loop / break / continue / return / dispatch
```

约束：

- 与 loop / branch 同级；
- 使用标准执行卡片样式；
- 每条 flow 恰好一个 entry；
- entry 节点匹配 `entrypointId`；
- 所有节点从 entry 可达；
- 首句不可物化语句不导致断流；
- 空入口生成 entry→exit。

## 4. 项目页布局

新增：

```text
projectGraph.flowCards[]
```

flow card 与 module card 一起进入：

```text
projectGraph.layout.nodes
```

约束：

- 无顶部独立流程入口条；
- flow card 与 module card 同层、同网格；
- flow card 标注“主流程”；
- flow card 可拖拽、保存布局；
- module card 继续表示能力模块。

## 5. 动态分发

P6.1 的共享 resolver 保持不变：

```text
archmap/utility/call_resolution_utility.py
```

自举 `args.func` 验收：

```text
candidateCount = 9
candidateSetComplete = true
candidateSource = config
```

候选只在节点详情展示，不展开为控制分支。

## 6. 样例归一化

### student_system

```text
app              入口与顶层编排（role=service）
network          NetworkAdapter + ProtocolMessage + ProtocolCodec
database         Database + DatabaseConfig
menu             MenuSystem + StudentRecord + display utility
async-feedback   Spinner
test             验证脚本
```

- 一张 `main()` flow card；
- entry 函数有 `isFlowEntry=true`；
- 无 entry Provider Role；
- 无 contracts 模块。

### gomoku

```text
terminal       main.py / __main__.py / cli.py
terminal-ui    input_parser.py / renderer.py
application    game.py + GameConfig
domain         board.py + models.py
ai-adapter     ai.py
```

- 一张 `GameCli.run()` flow card；
- `GameCli` 为 component Provider；
- 模块 role 不为 entry。

### ArchMap 自举

```text
pipeline
python-frontend
graph-projection
validation
rendering
```

- 一张 `cli_entry.main()` flow card；
- pipeline 模块只展示流水线能力；
- Provider Role 计数只包含七角色。

## 7. 当前验收基线

```text
pytest:             109 passed, 1 skipped
browser smoke:      1 passed
schemaVersion:      6.0
package version:    2.1.0
self build/check:   OK
student build/check: OK
gomoku build/check: OK
diagnostics:        0 error / 0 warning / 0 info
```

ArchMap 自举：

```text
modules:              5
classes:              33
functions:            264
methods:              75
callSites:            3522
resolvedCalls:        622
typeRelations:        64
structuralRelations:  64
userSurfaces:         0
executionFlows:       1
executionNodes:       4
executionEdges:       3
flowCards:            1
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
executionNodes:       9
executionEdges:       10
flowCards:            1
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
executionNodes:       11
executionEdges:       10
flowCards:            1
```

## 8. 关键文件

```text
archmap/config/contract_config.py
archmap/config/project_config.py
archmap/frontends/python/execution_utility.py
archmap/utility/call_resolution_utility.py
archmap/utility/execution_flow_utility.py
archmap/utility/execution_layout_utility.py
archmap/utility/graph_utility.py
archmap/utility/validate_utility.py
archmap/render/assets/app.js
archmap/render/assets/app.css
docs/schema/archmap-v6-bundle.schema.json
examples/student_system.archmap.json
examples/gomoku.archmap.json
examples/archmap_v3.archmap.json
```

## 9. 常用验证命令

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

## 10. 变更门槛

1. 不恢复 Provider Role `entry`。
2. 不把 module role 设为 `entry`。
3. 不把 flow card 放回顶部独立区域。
4. 不把 flow card 混入 `projectGraph.modules`。
5. 不删除 execution flow 的标准 `entry` 节点。
6. 不把不可物化语句当作路径终止。
7. 不把 dispatch candidates 展开成控制分支。
8. 不恢复模块页调用边。
9. 数据契约变更必须先更新 schema、validator、测试和文档。

## 11. 后续方向

- User Surface 置信度校准与分组；
- ArkTS 前端；
- 增量扫描与缓存；
- 更精细的类型推断；
- impact 报告与可视化 overlay。
