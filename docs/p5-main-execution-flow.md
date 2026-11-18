# P5 主流程执行流（Main Execution Flow）

> 状态：已立项，尚未实现<br>
> 目标版本：ArchMap 1.9.0 / bundle schema 4.0（计划）<br>
> 日期：2026-11-18<br>
> 适用范围：P5 主流程执行流的设计、实现、测试、验收与后续变更控制。

## 0. 一句话定义

P5 从项目入口函数出发，以**入口函数内部的控制流**为主干，将主模块自由函数和功能模块公开接口视为**不可展开的执行步骤**，生成一张**静态、控制流优先、可直接跳转源码**的主执行流图。

它不是运行时轨迹，也不是完整函数 CFG，更不是旧语句级 FunctionFlow 的恢复。

## 1. 背景与结论

P2.4 当前的主流程是函数级调用/模块组合 DAG。它能回答“调用了谁”，但不能充分回答“先做什么、在哪个条件处分叉、哪里循环、从哪里退出”。

P5 需要把主流程的主叙事重新拉回执行顺序，同时必须避免两个极端：

1. 继续停留在调用/依赖图，主流程无法解释项目实际执行过程；
2. 直接恢复完整语句级 FunctionFlow，图规模失控，重新变成函数内部 CFG 浏览器。

因此 P5 的结论是：

> **只画入口函数的执行骨架；主模块自由函数和功能模块接口都原子化；流程控制显式表达；细节通过源码页面查看。**

## 2. 防止误解：P5 不是什么

| 容易被误解为 | P5 的实际边界 |
|---|---|
| 运行时执行轨迹 | 静态控制流投影；分支和循环表示所有可能路径，不代表一次真实运行 |
| 完整函数 CFG | 只提取 entrypoint 函数的控制骨架，不生成函数内部任意图 |
| 旧 FunctionFlow 恢复 | 不恢复语句级 FunctionFlow；不生成逐语句节点 |
| 新的调用图 | 调用目标是节点属性；执行边只表达顺序和控制关系 |
| 可以无限下钻的图浏览器 | 所有自由函数和接口节点均不可展开；双击进入源码/Method Detail |
| Provider 组合图 | 主执行流不生成类 Provider 卡片 |
| 逐语句数据流图 | P5 不生成数据流边，也不生成列表操作节点 |
| 异常控制图 | P5 不建模 `try/except/finally` 分支 |
| 仅 UI 改造 | P5 同时涉及数据契约、Python 前端、布局、校验、UI 和测试 |
| 已实现能力 | 本文档只完成立项和边界定义；代码尚未开始 |

## 3. 防止滑坡：P5 的硬边界

以下规则是 P5 的产品边界，不是临时延期项。任何一条要改变，都必须先更新本文档、schema 和测试，再进入实现。

### 3.1 节点必须属于封闭集合

主执行流只允许以下节点：

```text
entry
exit
free_function
interface
branch
multi_branch
loop
break
continue
return
dispatch
merge
```

禁止新增：

- `action` / `statement` / `step` 等逐语句节点；
- `provider` / `class` 等类卡片节点；
- `list_append` / `list_sort` / `list_clear` 等列表方法节点；
- `try` / `except` / `finally` 等异常控制节点；
- 纯数据节点或数据端口节点。

新增节点类型必须作为新的产品决策单独立项，不能以“先临时加一个节点”的方式进入实现。

### 3.2 自由函数和接口都不展开

- 主模块自由函数是原子执行步骤；
- 功能模块公开接口是原子执行步骤；
- 两者双击打开 Method Detail / 源码页面；
- 不在图内展示其 callees；
- 不生成子流程、子画布或可展开容器。

“自由函数节点显示 `loop` / `branch` 徽章”可以作为摘要展示，但不能演变为展开入口。

### 3.3 只提取入口函数

P5 v1 只提取 selected entrypoint 函数本身的执行骨架。

- 不递归提取被调自由函数；
- 不穿透功能模块接口；
- 不提取功能模块内部 utility；
- 不把函数调用图重新塞回执行流。

### 3.4 不实现列表操作细度

千星奇域的列表节点只借鉴“语义明确、端口清楚、执行顺序显式”的设计思路。

P5 不实现：

- 拼接列表；
- 清除列表；
- 列表插入/移除/设值/排序；
- 列表迭代的独立节点类型。

列表遍历统一使用通用 `loop` 节点表达。

### 3.5 不实现异常控制

P5 不生成 `try` / `except` / `finally` 控制节点和异常边。

为保持透明，入口函数中出现 `try/except/finally` 时：

- `try` body 按普通顺序处理；
- 不绘制 exception handler / finally 分支；
- 产生 `EXCEPTION_CONTROL_SIMPLIFIED` 诊断；
- 完整细节保留在源码/Method Detail。

`raise` 不生成独立控制节点，也不伪造异常边；其源码证据保留在 Method Detail。

### 3.6 外部调用默认不进入节点

`input()`、`print()`、`socket`、第三方库等外部调用默认不生成执行节点。

它们可以：

- 折叠进相邻控制节点的条件文本；
- 作为 User Surface 或源码证据保留；
- 在 Method Detail 中查看。

P5 不把外部 IO 细节重新变成主流程节点。

### 3.7 细节查看的唯一去向是源码页面

当用户需要理解某个自由函数或接口内部逻辑时，入口是 Method Detail / 源码页面，而不是图内继续下钻。

这条规则用于防止 P5 重新长成完整 CFG 浏览器。

## 4. 产品视图定位

P5 实现后，主模块页提供两个视图：

| 视图 | 主用途 | 数据来源 |
|---|---|---|
| 执行流（默认） | 理解入口执行顺序、分支、循环和出口 | `projectGraph.executionFlows` |
| 调用总览（辅助） | 理解主流程中的调用/模块组合关系 | 现有 `projectGraph.mainFlows` |

两者不是替代关系：

- `executionFlows` 是执行叙事；
- `mainFlows` 是调用与组合叙事；
- Method Detail 是源码事实。

在 P5 实现完成前，当前默认主流程仍然是 P2.4 的调用/组合视图，README 不得写成执行流已上线。

## 5. 节点契约

### 5.1 节点类型

| 节点 | 含义 | 输出端口 |
|---|---|---|
| `entry` | 入口函数 | `out` |
| `exit` | 主流程结束 | 无 |
| `free_function` | 主模块自由函数调用步骤 | `in / out` |
| `interface` | 功能模块公开能力调用步骤 | `in / out` |
| `branch` | 双分支 | `true / false` |
| `multi_branch` | 多分支 | `case... / default` |
| `loop` | 循环 | `body / complete` |
| `break` | 跳出当前循环 | 控制边 |
| `continue` | 进入下一轮 | 控制边 |
| `return` | 函数返回 | 指向 `exit` |
| `dispatch` | 动态调用或候选集合 | `out` |
| `merge` | 分支汇合，自动生成 | `in / out` |

### 5.2 关键节点语义

#### `free_function`

- 目标必须是主模块自由函数；
- 必须携带 `functionId`、`callSiteId`、文件、行号、签名和备注；
- 不展示内部执行流；
- 双击进入 Method Detail / 源码页面。

#### `interface`

- 目标必须是功能模块公开 capability；
- 支持公开方法、模块级公开函数、context manager、callable、iterable；
- 必须携带 `capabilityId`、`targetFunctionId`、模块、文件和行号；
- 不展示内部执行流；
- 双击进入 Method Detail / 源码页面。

#### `branch`

- 用于简单 `if / else`；
- 恰好一条 `true` 边和一条 `false` 边；
- else 缺失时 false 边指向汇合点。

#### `multi_branch`

- 用于 `if / elif / else` 链和 `match / case`；
- 每个 case 一个输出端口；
- 默认路径使用 `default` 端口；
- 条件文本来自 AST，长文本可截断并以完整文本作为 tooltip/详情。

#### `loop`

- 统一表示 `for`、`while`、`async for`；
- 携带 `loopKind`、条件/迭代表达式、循环变量、`mayExit`；
- 恰好一条 `body` 边和一条 `complete` 边；
- `continue` 指回 loop；
- `break` 指向该 loop 的 `complete` 路径。

#### `dispatch`

- 用于动态调用或多态候选；
- 保存候选数量、候选来源、完整性和未解析原因；
- 不把候选强制展开为执行分支；
- 后续执行流通过 `next` 继续。

#### `merge`

- 由构建器自动生成；
- 至少一条入边、恰好一条出边；
- 用于分支汇合和布局对齐，不代表业务步骤。

## 6. 边契约

执行边只表达顺序与控制关系：

```text
next
true / false
case / default
loop_body / loop_complete
back / break / continue
return
dispatch
```

边不表达“调用谁”。调用目标属于节点属性：

```text
targetFunctionId
capabilityId
moduleId
```

禁止在 P5 执行流中继续使用 `call` / `call_path` / `composition` 作为执行边类型。

## 7. 生成规则

### 7.1 入口提取

只遍历 selected entrypoint 的 AST：

- 顺序语句中只保留项目调用和控制结构；
- `if / elif / else` → branch/multi_branch；
- `match / case` → multi_branch；
- `for / while / async for` → loop；
- `break / continue` → 控制节点，解析到最内层循环；
- `return` → return 节点并连接 exit；
- 分支汇合、循环结束自动生成 merge/exit 相关节点。

### 7.2 调用节点提取

入口函数中的一次可执行调用，最多生成一个执行节点：

1. 目标是主模块自由函数 → `free_function`；
2. 目标是功能模块公开 capability → `interface`；
3. 动态或多态且无法唯一确定 → `dispatch`；
4. 外部库、stdlib、内部 utility → 不生成节点；
5. 类构造本身不生成节点；如果构造结果直接用于 context manager 能力，则使用对应 `interface` 表达；
6. 条件表达式中的调用折叠进控制节点标签，不单独生成节点；
7. 同一调用点在不同执行路径出现时按 `callSiteId` 分别实例化，不按函数 ID 合并。

### 7.3 源码证据

每个执行节点至少保存：

```text
file
line
endLine
sourceHash（可取得时）
```

函数/接口节点还必须保存 `callSiteId`，确保重复调用不会丢失执行上下文。

## 8. student_system 目标快照

P5 实现后，student_system 的主执行流应类似：

```text
ENTRY main()
  ↓
LOOP while True
  ├─ body
  │   ↓
  │  INTERFACE NetworkAdapter.init_connection()
  │   ↓
  │  MULTI_BRANCH model
  │   ├─ case SERVER → FREE_FUNCTION server()
  │   ├─ case CLIENT → FREE_FUNCTION client()
  │   └─ default     → merge
  │   ↓
  │  MERGE
  │   ↓
  │  BRANCH status.upper() == "Q"
  │   ├─ true  → BREAK
  │   └─ false → back to LOOP
  └─ complete → EXIT
```

明确要求：

- `server()`、`client()` 是 `free_function` 节点，不展开；
- `NetworkAdapter.init_connection()` 是 `interface` 节点，不展开；
- 执行流中不得出现 `Spinner`、`Database.actions()`、`MenuSystem.run()`；
- 执行流中不得出现 Provider 类卡片；
- 双击 `server()` / `client()` / 接口节点进入源码页面；
- 调用总览仍保留原有 student_system 主流程内容。

## 9. 数据契约计划

P5 计划升级到 bundle schema 4.0。

新增：

```text
projectGraph.executionFlows[]
projectGraph.primaryExecutionFlowId
```

保留：

```text
projectGraph.mainFlows[]
projectGraph.primaryFlowId
```

### 9.1 executionFlow

```json
{
  "kind": "archmap.execution-flow",
  "id": "exec-flow:1:...",
  "moduleId": "main",
  "entrypointId": "fn:student_system.main.main",
  "name": "main()",
  "nodes": [],
  "edges": [],
  "layout": {},
  "nodeCount": 0,
  "edgeCount": 0,
  "truncated": false,
  "diagnostics": []
}
```

### 9.2 executionNode

```json
{
  "id": "exec:...:call:...",
  "kind": "interface",
  "label": "NetworkAdapter.init_connection()",
  "moduleId": "network",
  "callSiteId": "call:...",
  "targetFunctionId": "fn:...",
  "capabilityId": "api:...",
  "file": "student_system/managers/network_manager.py",
  "line": 21,
  "endLine": 49,
  "ports": ["in", "out"],
  "note": "初始化连接：让用户选择角色并建立初始化套接字接口",
  "expandable": false
}
```

控制节点额外字段：

```text
condition
cases[]
loopKind
iterable
loopVariable
mayExit
terminalKind
```

### 9.3 executionEdge

```json
{
  "id": "exec-edge:...",
  "from": "exec:...",
  "to": "exec:...",
  "kind": "true",
  "label": "SERVER",
  "confidence": "high",
  "evidence": []
}
```

### 9.4 统计

新增：

```text
executionFlows
executionNodes
executionEdges
```

`mainFlows` 相关统计保持原有语义。

## 10. 布局与 UI

### 10.1 布局

- Python 端生成确定性布局，浏览器不重新推导控制流；
- branch 左右展开；
- multi_branch 多列展开；
- loop body 向下、complete 向右/下；
- back / continue 使用左侧 lane；
- break / loop_complete 使用右侧 lane；
- merge 与 branch 中心对齐；
- 边使用正交折线，禁止穿越节点；
- 嵌套结构必须有碰撞检测。

### 10.2 UI

- 主模块页默认显示执行流，调用总览作为辅助切换；
- 节点显示名称、模块、备注和必要徽章；
- 分支显示“是/否”；
- 多分支显示 case / default；
- 循环显示“循环体/循环完成”；
- break / continue / return 明确可见；
- 函数和接口节点双击打开 Method Detail；
- 不提供图内展开按钮或下钻手势；
- 提供图例、适应画布、缩放、平移和空状态；
- 所有节点颜色不能只作为唯一语义来源，必须同时有文字标签。

## 11. 校验不变量

`archmap check` 必须新增执行流校验：

- 恰好一个 `entry`；
- 至少一个 `exit`；
- 所有节点可达；
- 非终止路径最终可达 `exit`；
- `branch` 恰好一条 `true` 和一条 `false`；
- `multi_branch` 至少一个 case，default 最多一个；
- `loop` 恰好一条 `body` 和一条 `complete`；
- `back` 目标必须是所属 loop；
- `break` / `continue` 必须解析到当前最内层 loop；
- `return` 必须指向 `exit`；
- `merge` 至少一条入边、恰好一条出边；
- `free_function` / `interface` 必须有 target 和 callSiteId；
- 节点类型必须属于封闭集合；
- 不允许 `expandable=true`；
- 不允许 Provider、action、statement、list 或 try/except 节点混入；
- 不允许执行边使用 `call` / `call_path` / `composition`。

## 12. 实施计划

### M0：契约与样例

- 冻结节点/边枚举；
- 编写 schema 4.0 草案；
- 建立 student_system 目标快照；
- 建立 `p5_execution_demo` fixture；
- 冻结 validator 不变量。

### M1：入口执行骨架

- entrypoint AST 遍历；
- 顺序调用节点；
- branch / multi_branch；
- return / exit；
- 源码证据。

### M2：循环与边界

- loop；
- break / continue；
- back / complete；
- 嵌套分支与循环；
- dispatch；
- 简化诊断。

### M3：执行流组装

- call-site 级节点 ID；
- free_function / interface 目标解析；
- 模块/Provider 元数据补充；
- executionFlow 输出；
- 统计与校验。

### M4：布局与 UI

- 结构化布局；
- 端口与正交路由；
- 执行流渲染；
- 执行流/调用总览切换；
- 双击源码跳转；
- 浏览器冒烟。

### M5：验收与文档

- 全量回归；
- 自举 build/check；
- student_system 快照测试；
- README、schema、设计文档更新；
- 性能数据和已知边界记录。

## 13. 验收标准

- schema 4.0 通过校验；
- 现有 `mainFlows` 与调用总览保持兼容；
- student_system 执行流满足第 8 节快照；
- 节点和边满足第 11 节不变量；
- 自由函数/接口双击可进入源码；
- 执行流中不出现 Provider、列表操作、try/except 或外部 IO 节点；
- 现有 88 个测试继续通过；
- 自举 build/check 通过；
- 浏览器冒烟无运行时错误。

## 14. 已知限制与风险

| 限制/风险 | 处理方式 |
|---|---|
| 静态执行流不是运行时轨迹 | UI 明确标注，并保留源码入口 |
| 不建模 try/except | 产生诊断，不假装异常路径完整 |
| 隐藏外部 IO | 在 Method Detail 和 User Surface 中保留证据 |
| 只提取入口函数 | 通过双击源码查看被调函数内部实现 |
| 布局复杂 | 结构化布局 + 正交性校验 + 浏览器冒烟 |
| 两个视图可能漂移 | `executionFlows` 与 `mainFlows` 分开构建、分开校验 |
| 未来需求诱导下钻 | 以第 3 节硬边界为变更门槛 |

## 15. 变更控制

P5 后续任何实现变更必须遵守：

1. 先更新本文档；
2. 再更新 schema 与 validator 规则；
3. 再补 fixture 和测试；
4. 最后实现和更新 README；
5. 不允许先加“临时节点”或“临时下钻”再补文档。

如果需求确实需要完整函数 CFG、异常图、列表操作节点或图内下钻，应另行立项，不得在 P5 范围内逐步扩展。
