# P5 主流程执行流（Main Execution Flow）

> 状态：P5 首版已实现；P5.1 已移除 merge 并改为内嵌端口卡片；P5.2 已支持显式 executionEntrypoints；P5.3 已统一终止节点、边型和本地调用语义；P5.4 已升级 bundle schema 4.1 并回归执行卡注释<br>
> 版本：ArchMap 1.9.0 / bundle schema 4.1<br>
> 日期：2026-11-18<br>
> 适用范围：P5 主流程执行流的设计、实现、测试、验收与后续变更控制。

## 0. 一句话定义

P5 从项目入口函数出发，以**入口函数内部的控制流**为主干，将主模块本地调用（自由函数或类方法）和功能模块公开接口视为**不可展开的执行步骤**，生成一张**静态、控制流优先、可直接跳转源码**的主执行流图。

它不是运行时轨迹，也不是完整函数 CFG，更不是旧语句级 FunctionFlow 的恢复。

## 1. 背景与结论

P2.4 当前的主流程是函数级调用/模块组合 DAG。它能回答“调用了谁”，但不能充分回答“先做什么、在哪个条件处分叉、哪里循环、从哪里退出”。

P5 需要把主流程的主叙事重新拉回执行顺序，同时必须避免两个极端：

1. 继续停留在调用/依赖图，主流程无法解释项目实际执行过程；
2. 直接恢复完整语句级 FunctionFlow，图规模失控，重新变成函数内部 CFG 浏览器。

因此 P5 的结论是：

> **只画入口函数的执行骨架；主模块本地调用和功能模块接口都原子化；流程控制显式表达；细节通过源码页面查看。**

## 2. 防止误解：P5 不是什么

| 容易被误解为 | P5 的实际边界 |
|---|---|
| 运行时执行轨迹 | 静态控制流投影；分支和循环表示所有可能路径，不代表一次真实运行 |
| 完整函数 CFG | 只提取 entrypoint 函数的控制骨架，不生成函数内部任意图 |
| 旧 FunctionFlow 恢复 | 不恢复语句级 FunctionFlow；不生成逐语句节点 |
| 新的调用图 | 调用目标是节点属性；执行边只表达顺序和控制关系 |
| 可以无限下钻的图浏览器 | 所有本地调用和接口节点均不可展开；双击进入源码/Method Detail |
| Provider 组合图 | 主执行流不生成类 Provider 卡片 |
| 逐语句数据流图 | P5 不生成数据流边，也不生成列表操作节点 |
| 异常控制图 | P5 不建模 `try/except/finally` 分支 |
| 仅 UI 改造 | P5 同时涉及数据契约、Python 前端、布局、校验、UI 和测试 |
| 已实现能力 | P5 首版已实现并在 README 中记录验收数据；本文档继续保持同一产品边界 |

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
```

禁止新增：

- `action` / `statement` / `step` 等逐语句节点；
- `provider` / `class` 等类卡片节点；
- `list_append` / `list_sort` / `list_clear` 等列表方法节点；
- `try` / `except` / `finally` 等异常控制节点；
- 纯数据节点或数据端口节点。

新增节点类型必须作为新的产品决策单独立项，不能以“先临时加一个节点”的方式进入实现。

### 3.2 本地调用和接口都不展开

- 主模块自由函数与类方法是同一类原子执行步骤；任意私有/公开方法都按本地 callable 处理，不按可见性制造两套执行语义；
- 功能模块公开接口是原子执行步骤；
- 两者双击打开 Method Detail / 源码页面；
- 不在图内展示其 callees；
- 不生成子流程、子画布或可展开容器。

“本地调用节点显示 `loop` / `branch` 徽章”可以作为摘要展示，但不能演变为展开入口。

### 3.3 只提取入口函数

P5 v1 只提取 selected entrypoint 函数本身的执行骨架。

- selected entrypoint 默认来自配置 `entrypoints`；
- 可选配置 `executionEntrypoints` 单独指定主执行流起点，支持类方法；
- `executionEntrypoints` 省略或全部无法解析时回退到 `entrypoints`；
- 不递归提取被调本地 callable；
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

当用户需要理解某个本地 callable 或接口内部逻辑时，入口是 Method Detail / 源码页面，而不是图内继续下钻。

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

P5 实现后，主模块默认进入执行流视图，调用/组合视图保留为“调用总览”。

## 5. 节点契约

### 5.1 节点类型

| 节点 | 含义 | 输出端口 |
|---|---|---|
| `entry` | 入口函数 | `out` |
| `exit` | 按需生成的主流程结束锚点；仅用于隐式落空等真实到达路径 | `in` |
| `free_function` | 主模块本地调用步骤；`callableKind` 区分自由函数与方法 | `in / out` |
| `interface` | 功能模块公开能力调用步骤 | `in / out` |
| `branch` | 双分支 | `in / true / false` |
| `multi_branch` | 多分支 | `in / case... / default` |
| `loop` | 循环 | `in / loop_body / loop_complete`（离开循环） |
| `break` | 跳出当前循环 | `in` |
| `continue` | 进入下一轮 | `in` |
| `return` | 函数返回，终止节点 | `in`，无出边 |
| `dispatch` | 动态调用或候选集合 | `in / out` |

### 5.2 关键节点语义

#### `free_function`

- 表示主模块本地可调用步骤，统一覆盖自由函数与类方法；
- `callableKind` 为 `function` 或 `method`，类方法额外携带 `ownerClassId` / `ownerClassName`；
- 私有/公开不改变执行步骤语义；可见性只影响 API/契约视图；
- 必须携带 `targetFunctionId`、`callSiteId`、文件、行号、签名和备注；
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
- 最多一条 `true` 边和一条 `false` 边；
- continuing arm 直接连接下一个真实语句；没有后继时连接 `exit`；
- 如果 false arm 位于循环体末尾，隐式进入下一轮迭代，因此可以不产生可见出边。

#### `multi_branch`

- 用于 `if / elif / else` 链和 `match / case`；
- 每个 case 一个输出端口；
- 默认路径使用 `default` 端口；
- 条件文本来自 AST，长文本可截断并以完整文本作为 tooltip/详情。

#### `loop`

- 统一表示 `for`、`while`、`async for`；
- 携带 `loopKind`、条件/迭代表达式、循环变量、`mayExit`、`hasBreak`；
- 卡片端口为 `进入循环 / 循环体 / 离开循环`；
- 最多一条 `loop_body` 边和一条 `loop_complete` 边；
- `loop_complete` 是该循环唯一的结构化离开出口；正常完成或 break 离开都从这里继续；
- `while True` 且既无 break 也不可正常完成时不生成 `loop_complete`；
- break / continue 是循环体内部终止标记，不生成出边；
- 不绘制 back 回边；循环体完成后隐式回到循环节点；
- `loop_complete` 路径直接连接循环后的真实节点；没有后继且路径真实到达时进入 `exit`。

#### `dispatch`

- 用于动态调用或多态候选；
- 保存候选数量、候选来源、完整性和未解析原因；
- 不把候选强制展开为执行分支；
- 后续执行流通过 `next` 继续。

#### 汇入（不是节点）

- 多分支/循环路径的重汇合由多个入边直接指向同一个真实后继节点表达；
- 不生成 `merge` 节点；
- 每条入边保留自己的 kind、label、confidence 和 evidence；
- 没有后继时所有继续执行的路径直接指向 `exit`；
- 循环体内部的隐式迭代不生成 back lane，也不为了补齐端口而制造合成节点。

## 6. 边契约

执行边只表达顺序与控制关系：

```text
next
true / false
case / default
loop_body / loop_complete
```

执行边只表达连接关系，不表达终止动作：`break` / `continue` / `return` 是节点类型，不是执行边类型。循环体通过 `loop_body` 从循环节点进入，循环何时回到条件由循环节点本身表达，不绘制回边 lane。

`return` 是终止节点，不生成到 `exit` 的边。`exit` 不是每个 flow 的必备节点；只有隐式落空、raise 简化路径等真实到达结束锚点的路径才生成它。

边型语义统一为：

- 实线：静态确定的直接控制/执行关系；
- 虚线：推断、不完整或间接关系；
- 无出边：终止节点或未展开去向。

因此 `default` 等确定控制关系使用实线；`break` / `continue` 不再生成出边，控制差异由节点类型、颜色、端口和标签表达。

边不表达“调用谁”。调用目标属于节点属性：

```text
targetFunctionId
capabilityId
moduleId
```

禁止在 P5 执行流中继续使用 `call` / `call_path` / `composition` 作为执行边类型。

## 7. 生成规则

### 7.1 入口提取

只遍历 selected entrypoint 的 AST。主执行流入口按以下顺序确定：

1. 配置 `executionEntrypoints` 中可解析的函数或类方法；
2. 若未配置或全部无法解析，回退到分析入口 `entrypoints`；
3. 无法解析的执行入口产生 `EXECUTION_ENTRYPOINT_UNRESOLVED` 诊断，并保留显式回退诊断 `EXECUTION_ENTRYPOINT_FALLBACK`；
4. `entrypoints` 仍用于入口角色、User Surface 传播、调用关系和主流程事实，不因执行入口覆盖而丢失。

遍历规则：

- 顺序语句中只保留项目调用和控制结构；
- `if / elif / else` → branch/multi_branch；
- `match / case` → multi_branch；
- `for / while / async for` → loop；
- `break / continue` → 控制节点，解析到最内层循环；
- `return` → return 终止节点，不生成出边；
- 分支汇合、循环结束直接连接下一个真实节点；只有真实到达隐式结束时才连接 exit；
- 不生成 merge 节点。

### 7.2 调用节点提取

入口函数中的一次可执行调用，最多生成一个执行节点：

1. 目标是主模块本地 callable（自由函数或类方法）→ `free_function`，`callableKind` 区分 `function` / `method`；
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

student_system 的主执行流目标快照如下，并已成为验收基线：

```text
ENTRY main()
  → LOOP while True
      → INTERFACE NetworkAdapter.init_connection()
          → MULTI_BRANCH model
              ├─ case → FREE_FUNCTION server()
              ├─ case → FREE_FUNCTION client()
              └─ default → BRANCH status.upper() == "Q"
                            ├─ 是 → BREAK
                            └─ 否 → 循环体结束（隐式迭代）
  └─ loop_complete ───────────────→ EXIT

BREAK 是循环体内终止标记，无出边。
```

该图采用横向主脊：顺序节点从左向右，branch / multi_branch 的路径在上下 lane 展开，循环节点不绘制回边。`while True` 通过 break 离开时统一从 loop 的 `loop_complete` 端口进入 `exit`；不存在 break 直连、`LOOP_COMPLETE` 或 `merge` 合成节点。

明确要求：

- `server()`、`client()` 是 `free_function` 节点，不展开；
- `NetworkAdapter.init_connection()` 是 `interface` 节点，不展开；
- 执行流中不得出现 `Spinner`、`Database.actions()`、`MenuSystem.run()`；
- 执行流中不得出现 Provider 类卡片；
- 双击 `server()` / `client()` / 接口节点进入源码页面；
- 调用总览仍保留原有 student_system 主流程内容。

## 9. 数据契约

P5 当前 bundle schema 为 4.1。JSON Schema 位于 [`docs/schema/archmap-v4-bundle.schema.json`](schema/archmap-v4-bundle.schema.json)，4.0 历史契约位于 [`docs/schema/archmap-v4.0-bundle.schema.json`](schema/archmap-v4.0-bundle.schema.json)。

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
  "entrypointReason": "configured",
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

4.1 中 `executionEdge.kind` 仅允许：`next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`。

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

- Python 端生成确定性横向布局，浏览器不重新推导控制流；
- 主流程从左向右推进；
- branch 的上/下路径垂直展开；
- multi_branch 各 case 垂直展开；
- loop 通过 `循环体` 端口连接 body，不绘制 back lane；
- loop complete 长距离边使用曲线 lane 绕开节点；
- 多入边直接进入同一个目标节点，不生成汇合节点；
- 边使用贝塞尔曲线，禁止穿过卡片内容；
- 布局节点提供真实端口锚点；
- 嵌套结构必须有碰撞检测，卡片内容自适应高度。

### 10.2 UI

- 主模块页默认显示执行流，调用总览作为辅助切换；
- 节点使用项目执行流卡片风格：彩色标题栏、深色主体、内嵌端口行；
- 端口行无方框、无独立背景色，流程文字和端口标签位于卡片内部；
- 不再生成卡片外的边标签胶囊；
- 分支显示“是/否”；
- 多分支显示 case / default；
- 循环显示“进入循环/循环体/循环完成”；
- break / continue / return 明确可见；
- 函数和接口节点双击打开 Method Detail；
- 节点支持拖拽移动，关联曲线实时重算；
- 拖拽覆盖写入浏览器布局并持久化，可通过“重置布局”恢复；
- 不提供图内展开按钮或下钻手势；
- 提供图例、适应画布、缩放、平移和空状态；
- 所有节点颜色不能只作为唯一语义来源，必须同时有文字标签。

## 11. 校验不变量

`archmap check` 必须新增执行流校验：

- 恰好一个 `entry`；
- 最多一个 `exit`；仅当存在隐式落空等真实路径时才需要；
- 所有节点可达；
- 非终止路径若存在，最终可达 `exit`；
- `branch` 最多一条 `true` 和一条 `false`，不得重复；
- `multi_branch` 至少一个 case，default 最多一个；
- `loop` 最多一条 `body` 和一条 `complete`；`loop_complete` 必须从 `loop` 节点发出；
- `break` / `continue` 必须解析到当前最内层 loop，且不得有出边；
- `return` 是 terminal sink，不得有出边；
- `exit` 不得有出边；
- 不允许出现 `merge` 节点；汇合由同一目标节点的多条入边表达；
- `free_function` / `interface` 必须有 target 和 callSiteId；
- `free_function.callableKind` 只能是 `function` 或 `method`；
- 节点类型必须属于封闭集合；
- 不允许 `expandable=true`；
- 不允许 Provider、action、statement、list 或 try/except 节点混入；
- 不允许执行边使用 `call` / `call_path` / `composition`；
- 执行边 kind 只允许 `next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`。

### 9.1 schema 4.0 → 4.1 迁移

4.0 的执行边契约同时包含连接关系和终止动作，导致 `break → exit`、`return → exit` 等重复语义。4.1 收紧为：

- 删除执行边 kind：`back`、`break`、`continue`、`return`、`dispatch`；
- `break` / `continue` / `return` 只作为节点 kind，不产生出边；
- `loop_complete` 是 loop 的唯一结构化离开出口，break 离开也归并到该端口；
- `exit` 只在真实隐式落空路径需要时生成；
- 执行流卡片不渲染 signature，只展示 label、note 和状态 badges；签名保留在 FunctionDetail / Method Detail。

旧 4.0 bundle 继续由历史 schema 描述，不自动迁移；需要重新 build 才能生成 4.1 产物。

## 12. 实施阶段

P5 首版实现落在以下模块：

```text
archmap/model/execution_model.py
archmap/frontends/python/execution_utility.py
archmap/utility/execution_flow_utility.py
archmap/utility/execution_layout_utility.py
archmap/utility/graph_utility.py
archmap/utility/validate_utility.py
archmap/render/assets/app.js
archmap/render/assets/app.css
docs/schema/archmap-v4-bundle.schema.json
tests/test_execution_flow.py
```

### M0：契约与样例

- 冻结节点/边枚举；
- 编写 schema 4.0 草案；P5.4 收紧执行边并升级到 4.1；
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
- loop body / complete；
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

- 横向结构化布局；
- 端口锚点与贝塞尔曲线；
- 节点拖拽与布局覆盖持久化；
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

- schema 4.1 通过校验；
- 现有 `mainFlows` 与调用总览保持兼容；
- student_system 执行流满足第 8 节快照；
- 节点和边满足第 11 节不变量；
- 本地调用/接口双击可进入源码；
- 执行流中不出现 Provider、列表操作、try/except 或外部 IO 节点；
- 全量测试与浏览器冒烟通过；
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
