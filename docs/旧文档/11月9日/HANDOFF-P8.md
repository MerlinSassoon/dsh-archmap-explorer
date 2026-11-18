# ArchMap P8 交接文档

> 状态：P8 已完成<br>
> 版本：ArchMap 2.2.0 / bundle schema 6.1<br>
> 日期：2026-11-19

## 1. 完成内容

P8 增加模块级 `executionOnlyCallables`，解决主模块降级后 `main/client/server` 等流程编排 callable 被推断为 `manager` 并进入模块能力面的问题。

```text
显式声明 executionOnlyCallables
→ 对 capability 面透明
→ 保留源码 / callSites / 执行流事实
→ 空能力模块后端保留、前端隐藏
```

## 2. 核心契约

模块配置：

```json
{
  "executionOnlyCallables": [
    "student_system.app.main:main",
    "student_system.app.main:client",
    "student_system.app.main:server"
  ]
}
```

模块输出：

```json
{
  "executionOnlyFunctionIds": ["fn:..."],
  "capabilitySurface": {
    "hasProviders": false,
    "providerCount": 0,
    "apiCount": 0
  }
}
```

函数详情：

```json
{
  "isExecutionOnly": true,
  "functionSurface": "execution",
  "executionRole": "entry"
}
```

项目图：

```json
{
  "capabilityModuleIds": ["network", "database", "menu"]
}
```

## 3. 行为不变量

- 七 Provider Role 不变；
- executionOnly callable 不进入 `providedApis` / `apiProviders` / composition / role counts；
- executionOnly 类方法不进入类 API，但类 Provider 保留；
- executionOnly callable 仍保留 functionDetails、callSites、callers/callees、源码和执行流节点；
- 空能力模块保留在 projectGraph.modules、moduleGraphs 和 layout；
- 前端不渲染空能力模块卡；
- 直接访问空能力模块路由回到项目页并提示；
- 项目页模块计数使用 `capabilityModuleIds` / `capabilitySurface`；
- 方法详情显示 `execution:entry` / `execution:orchestrator`，不显示 Manager Role。

## 4. 配置校验

错误：

- `EXECUTION_ONLY_CALLABLE_UNRESOLVED`
- `EXECUTION_ONLY_MODULE_MISMATCH`
- `EXECUTION_ONLY_DUPLICATE`
- validator 的 `EXECUTION_ONLY_API_LEAK` / `EXECUTION_ONLY_NODE_LEAK` / `EXECUTION_ONLY_SURFACE` 等

警告：

- `EXECUTION_ONLY_PROVIDER_ROLE_CONFLICT`
- `EXECUTION_ONLY_CROSS_MODULE_CALLER`
- `EXECUTION_ONLY_NOT_IN_FLOW`

## 5. 样例状态

student_system：

```text
app executionOnly: main/client/server
app capabilitySurface: hasProviders=false
app backend module: retained
app frontend card: hidden
main flow: 9 nodes / 10 edges
```

ArchMap 自举：

```text
pipeline executionOnly: cli_entry.main
pipeline capabilitySurface: hasProviders=true（保留 PipelineManager 等 Provider）
```

gomoku 配置：

```text
terminal executionOnly: gomoku.cli:main, gomoku.cli:GameCli.run
GameCli 类 Provider 保留
```

## 6. 关键文件

```text
archmap/config/project_config.py
archmap/utility/config_utility.py
archmap/model/analysis_model.py
archmap/frontends/python/analysis_utility.py
archmap/frontends/python/contract_utility.py
archmap/utility/graph_utility.py
archmap/utility/execution_flow_utility.py
archmap/utility/validate_utility.py
archmap/render/assets/app.js
docs/archmap-config-generation.md
docs/schema/archmap-v6.1-bundle.schema.json
examples/student_system.archmap.json
examples/gomoku.archmap.json
examples/archmap_v3.archmap.json
tests/test_execution_only.py
```

## 7. 当前验收基线

```text
pytest:             114 passed, 1 skipped
browser smoke:      1 passed（显式开启）
schemaVersion:      6.1
package version:    2.2.0
self build/check:   OK
student build/check: OK
gomoku build/check: OK
diagnostics:        0 error / 0 warning / 0 info
```

ArchMap 自举：

```text
modules:                5
capabilityModules:      5
emptyCapabilityModules: 0
executionOnlyCallables: 1
executionFlows:         1
executionNodes:         4
executionEdges:         3
flowCards:              1
callSites:              3680
resolvedCalls:          644
```

student_system：

```text
modules:                6
capabilityModules:      5
emptyCapabilityModules: 1
executionOnlyCallables: 3
executionFlows:         1
executionNodes:         9
executionEdges:         10
flowCards:              1
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
callSites:              185
resolvedCalls:          83
```

## 8. 验收命令

```bash
python3 -m pytest -q
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out /tmp/archmap-self
python3 -m archmap check /tmp/archmap-self/architecture.json
python3 -m archmap build Projects/student_system \
  --config examples/student_system.archmap.json --out /tmp/student-system
python3 -m archmap check /tmp/student-system/architecture.json
```

## 9. 后续方向

- User Surface 置信度校准与分组；
- ArkTS 前端；
- 增量扫描与缓存；
- 更精细类型推断；
- impact 报告与可视化 overlay。
