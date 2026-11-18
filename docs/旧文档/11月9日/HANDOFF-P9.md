# ArchMap P9 交接文档

> 状态：P9 已完成，可交接<br>
> 分支：P7（P9 工作完成后提交）<br>
> 版本：ArchMap 2.3.0 / bundle schema 6.2<br>
> 日期：2026-11-19

## 1. 完成内容

P9 解决模块级自由函数的能力边界问题：

```text
保守自动推断
+ defaultFreeFunctionSurface
+ apiExposure 单函数例外
+ executionOnlyCallables 强覆盖
```

自由函数不再因为 public 命名、控制流或项目调用被默认推断为 `manager`。

## 2. 配置契约

```json
{
  "modules": [
    {
      "id": "terminal-ui",
      "role": "component",
      "defaultFreeFunctionSurface": "internal"
    }
  ]
}
```

允许值：

```text
auto / internal / capability
```

单函数例外：

```json
{
  "contract": {
    "apiExposure": {
      "gomoku.input_parser.parse_input": "public"
    }
  }
}
```

## 3. 判定优先级

```text
executionOnlyCallables
  > apiExposure=internal
  > 显式 Provider Role = utility
  > 显式 public API 标签 / config public exposure
  > 显式非 utility Provider Role
  > defaultFreeFunctionSurface=internal
  > defaultFreeFunctionSurface=capability
  > 跨模块调用证据
  > internal
```

## 4. 数据字段

FunctionDetail：

```json
{
  "functionSurface": "internal",
  "functionSurfaceSource": "module_default"
}
```

`functionSurface`：`capability | internal | execution`。

`functionSurfaceSource`：`config | exposure | module_default | call_graph | structure | metadata | file_unit`。

ModuleGraph：

```json
{
  "defaultFreeFunctionSurface": "internal",
  "capabilityFreeFunctionIds": [],
  "internalFreeFunctionIds": [],
  "executionFreeFunctionIds": [],
  "freeFunctionSurfaceCounts": {
    "capability": 0,
    "internal": 0,
    "execution": 0
  }
}
```

## 5. 行为不变量

- internal / execution 自由函数不进入 `providedApis` / `apiProviders` / 角色计数；
- capability 自由函数在基础 role=utility 时升级为 manager，`roleSource=surface`；
- 类方法不受模块默认自由函数面影响；
- `executionOnlyCallables` 仍支持类方法；
- 空能力模块后端保留、前端隐藏；
- 方法详情对 internal / execution 不显示 Provider Role，显示 surface / execution badge。

## 6. 样例结果

- `terminal-ui`：`defaultFreeFunctionSurface=internal`，7 个解析/渲染 helper 不进入能力面；
- `examples/gomoku_v2.archmap.json`：从 P8 的逐函数 `apiExposure=internal` 迁移为模块级默认 internal；
- `student_demo` / `roles_demo` / `class_demo`：显式 `defaultFreeFunctionSurface=capability`，原有自由函数 API 保持；
- student_system app：3 个 executionOnly callable 继续只在执行流展示；
- ArchMap 自举：`cli_entry.main` 继续 executionOnly，其余 utility 文件保持 internal。

## 7. 验收基线

```text
pytest:              120 passed, 1 skipped
browser smoke:       1 passed
schemaVersion:       6.2
package version:     2.3.0
self build/check:    OK
student build/check: OK
gomoku build/check:  OK
gomoku_v2 build/check: OK
diagnostics:         0 error / 0 warning / 0 info
```

ArchMap 自举：

```text
modules:                5
capabilityModules:      5
emptyCapabilityModules: 0
executionOnlyCallables: 1
freeFunctionSurfaces:   0 capability / 188 internal / 1 execution
executionFlows:         1
executionNodes:         4
executionEdges:         3
flowCards:              1
callSites:              3796
resolvedCalls:          661
```

student_system：

```text
modules:                6
capabilityModules:      4
emptyCapabilityModules: 2
executionOnlyCallables: 3
freeFunctionSurfaces:   0 capability / 7 internal / 3 execution
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
freeFunctionSurfaces:   0 capability / 10 internal / 0 execution
executionFlows:         1
executionNodes:         11
executionEdges:         10
flowCards:              1
callSites:              185
resolvedCalls:          83
```

## 8. 关键文件

```text
archmap/config/project_config.py
archmap/utility/config_utility.py
archmap/model/analysis_model.py
archmap/utility/role_utility.py
archmap/frontends/python/role_utility.py
archmap/utility/graph_utility.py
archmap/utility/validate_utility.py
archmap/utility/execution_flow_utility.py
archmap/render/assets/app.js
docs/archmap-config-generation.md
docs/schema/archmap-v6.2-bundle.schema.json
examples/gomoku.archmap.json
examples/gomoku_v2.archmap.json
tests/test_free_function_surfaces.py
tests/test_execution_only.py
```

## 9. 变更门槛

1. 不新增 Provider Role；七角色保持不变。
2. 不恢复“自由函数默认 manager”的推断。
3. 不让 `defaultFreeFunctionSurface` 影响类方法或 executionOnly callable。
4. 不把 `executionOnlyCallables` 当作 internal helper 的通用隐藏列表。
5. 不用批量 `providerRoles=utility` 替代模块默认自由函数面。
6. 不删除空能力模块的后端模块与 layout；只允许前端隐藏。
7. 不把 `functionSurface=internal/execution` 的自由函数加入 `providedApis`。
8. 数据契约变更必须同步 schema、validator、测试和文档。

## 10. 交接检查清单

- [x] `defaultFreeFunctionSurface` 配置解析与非法值 warning；
- [x] auto/internal/capability 三模式生效；
- [x] 保守自由函数推断，public 命名/控制流/项目调用不再默认 manager；
- [x] `apiExposure` 单函数例外优先；
- [x] `executionOnlyCallables` 强覆盖；
- [x] FunctionDetail surface / source 输出；
- [x] ModuleGraph capability/internal/execution IDs 和 counts；
- [x] schema 6.2；
- [x] validator 表面一致性、API 泄漏、空能力模块不变量；
- [x] 方法详情 surface / execution badge；
- [x] examples + fixtures 更新；
- [x] `archmap-config-generation.md` P9 收口；
- [x] 全量测试、浏览器冒烟、self/student/gomoku build/check。

## 11. 后续方向

- User Surface 置信度校准与分组；
- ArkTS 前端；
- 增量扫描与缓存；
- 更精细类型推断；
- impact 报告与可视化 overlay。
