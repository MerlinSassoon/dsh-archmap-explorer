# P9 自由函数能力边界与模块默认面计划

> 状态：已完成<br>
> 版本：ArchMap 2.3.0 / bundle schema 6.2<br>
> 日期：2026-11-19

## 1. 背景

P8 解决了执行流 callable 的能力面透明问题，但模块级自由函数仍可能因为 public 命名、控制流或项目调用被默认推断为 `manager`。典型现象是 terminal-ui 模块的解析/渲染 helper 全部进入 `providedApis`，形成错误的 MANAGER 卡片。

P9 的目标是把自由函数能力边界从“推断决定”升级为：

```text
保守自动推断
+ 模块级默认自由函数面
+ 单函数显式 exposure 例外
+ executionOnly 强覆盖
```

## 2. 配置契约

模块配置新增：

```json
{
  "id": "terminal-ui",
  "role": "component",
  "defaultFreeFunctionSurface": "internal"
}
```

允许值：

```text
auto        保守推断
internal    模块级自由函数默认 internal
capability  模块级自由函数默认 capability
```

单函数例外继续使用 `contract.apiExposure`：

```json
{
  "contract": {
    "apiExposure": {
      "gomoku.input_parser.parse_input": "public",
      "gomoku.input_parser.column_letters": "internal"
    }
  }
}
```

`executionOnlyCallables` 保持最高优先级。

## 3. 判定顺序

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

## 4. 数据投影

FunctionDetail 对自由函数输出：

```json
{
  "functionSurface": "internal",
  "functionSurfaceSource": "module_default"
}
```

ModuleGraph 输出：

```json
{
  "defaultFreeFunctionSurface": "internal",
  "capabilityFreeFunctionIds": [],
  "internalFreeFunctionIds": ["fn:gomoku.input_parser.parse_input"],
  "executionFreeFunctionIds": [],
  "freeFunctionSurfaceCounts": {
    "capability": 0,
    "internal": 7,
    "execution": 0
  }
}
```

## 5. 不变量

- `functionSurface=internal` 的自由函数不进入 `providedApis` / `apiProviders` / Provider 角色计数；
- `functionSurface=execution` 的 callable 继续只作为执行流事实；
- `functionSurface=capability` 的自由函数如果基础角色为 utility，会升级为 manager，并使用 `roleSource=surface`；
- 类方法不受 `defaultFreeFunctionSurface` 影响；
- 空能力模块继续后端保留、前端隐藏；
- 自动推断不再因控制流、项目调用或 public 命名把自由函数升级为 manager。

## 6. 实施阶段

### P9.0 契约与基准

- 确定 `defaultFreeFunctionSurface` 字段；
- 明确 auto/internal/capability 语义；
- 明确 `apiExposure` 与 `executionOnlyCallables` 优先级。

### P9.1 自由函数表面推断

- 保守化 `_infer_function_role`；
- 收集跨模块调用证据；
- 解析 effective free-function surface；
- FunctionDetail / ModuleGraph 输出。

### P9.2 配置、schema 与校验

- schema 6.2；
- validator 检查 surface 一致性；
- API 泄漏与空能力模块不变量。

### P9.3 前端与样例

- 方法详情显示 surface badge；
- internal / execution 不显示 Provider Role；
- terminal-ui / student / self 样例更新。

### P9.4 文档与验收

- project-config-generation-guide；
- README、数据契约、API 契约、架构规范；
- 全量测试、浏览器冒烟、三样例 build/check。

## 7. 验收

```text
student_demo: defaultFreeFunctionSurface=capability，原有自由函数 API 保持
terminal-ui: defaultFreeFunctionSurface=internal，7 个 helper 不进入能力面
auto 模块: 无显式 public 证据的自由函数默认 internal
显式 public exposure: 覆盖 internal 默认面
executionOnlyCallables: 覆盖 capability 默认面
schemaVersion: 6.2
diagnostics: 0 error / 0 warning / 0 info
```
