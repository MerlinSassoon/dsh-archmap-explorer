# ArchMap P5.5 交接文档

> 状态：P5.5 已完成；下一步为“共享调用/动态分发解析”与“主流程调用图数据契约收缩”<br>
> 分支：`P5.1`<br>
> 功能基线：`d4e47f0 chore: align example configs with current source layout`<br>
> 版本：ArchMap 1.9.0 / bundle schema 4.1<br>
> 日期：2026-11-18

## 1. 交接摘要

P5.5 已完成主流程页与模块能力页的拆分：

```text
#/project             项目页：主流程入口 + 全部模块能力卡片
#/flow[/<id>]         主流程页：只展示 executionFlows
#/module/<id>         模块能力页：主模块与功能模块统一
#/module/<id>/function/<functionId>  方法详情
```

核心结论：

- 主流程是项目级执行叙事，不再挂在主模块页下。
- 主模块和功能模块统一使用模块能力页。
- 调用总览与能力视图不再作为主流程页的并列 tab。
- `mainFlows` 数据仍保留，但不再进入默认 UI。
- 动态分发解析尚未合并到执行流，是下一阶段第一优先事项。

## 2. 当前基线

### 2.1 测试与构建

```text
python3 -m pytest -q
101 passed, 1 skipped

ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py
1 passed

ArchMap 自举 build/check
OK

student_system build/check
OK

五子棋 build/check
OK
```

### 2.2 自举验收数据

```text
schemaVersion:          4.1
modules:                6
classes:                31
functions:              272
methods:                71
callSites:              3850
resolvedCalls:          653
executionFlows:         1
executionNodes:         4
executionEdges:         3
typeRelations:          57
structuralRelations:    57
diagnostics:            0 errors / 0 warnings / 0 info
```

### 2.3 当前提交链

```text
d4e47f0 chore: align example configs with current source layout
d412d31 feat: separate main flow page from module capability views
3b9341a feat: upgrade bundle contract to 4.1 and restore execution notes
f43ec0d feat: unify execution flow entrypoints and terminal semantics
6596876 feat: implement P5.1 embedded execution cards and direct fan-in
```

## 3. 已完成能力

### 3.1 页面与路由

- 项目页新增独立主流程入口卡片；
- 主流程页 `#/flow` 与多 flow 选择器；
- `#/module/<id>` 统一为模块能力页；
- 主模块不再默认进入执行流；
- 无效 flow ID 回退 primary flow 并修正 URL；
- 浏览器 back/forward 与刷新恢复正常。

### 3.2 执行流

- 只展开 selected entrypoint 的控制骨架；
- `executionEntrypoints` 可独立于分析入口，支持类方法；
- `free_function` 统一表示主模块本地 callable：
  - `callableKind=function|method`
  - `ownerClassId` / `ownerClassName`
- `return`、`break`、`continue` 为 terminal node，无出边；
- `loop_complete` 为循环唯一结构化离开出口；
- `exit` 按真实隐式落空路径按需生成；
- 执行卡片显示 label + human note + badges，不显示 signature；
- 实线表示确定控制关系，虚线只表示推断/不完整/间接关系。

### 3.3 数据契约

当前 schema：`docs/schema/archmap-v4-bundle.schema.json`，版本 4.1。

执行边只允许：

```text
next
true / false
case / default
loop_body / loop_complete
```

历史 4.0 契约保留在：

```text
docs/schema/archmap-v4.0-bundle.schema.json
```

### 3.4 示例配置

- `examples/archmap_v3.archmap.json`
  - 已覆盖全部 `archmap/**/*.py`；
  - P5 执行流、布局、查询工具归入 `graph-projection`；
  - CLI dispatch 候选补齐为 9 个。
- `examples/student_system.archmap.json`
  - 已覆盖全部样例 Python 文件。
- `examples/gomoku.archmap.json`
  - 使用 `executionEntrypoints: ["gomoku.cli:GameCli.run"]`；
  - 测试目录显式排除。

## 4. 当前关键文件

```text
archmap/render/assets/app.js
  #/flow 与 #/module 路由、项目页主流程入口、执行流渲染、模块能力页

archmap/render/assets/index.html
  projectFlowEntry / flowPicker 容器

archmap/render/assets/app.css
  主流程入口卡片、flow picker、执行流与模块能力页样式

archmap/frontends/python/execution_utility.py
  entrypoint AST 控制骨架提取；terminal/loop 语义

archmap/utility/execution_flow_utility.py
  执行流组装、main-module local callable/interface/dispatch 目标解析

archmap/utility/main_flow_utility.py
  现有较完整的调用投影与 dispatch 候选解析实现

archmap/utility/graph_utility.py
  bundle 投影、executionFlows/mainFlows 装配、schemaVersion

archmap/utility/validate_utility.py
  schema 4.1 与执行流不变量校验

docs/schema/archmap-v4-bundle.schema.json
  当前 bundle schema 4.1
```

## 5. 尚未执行的第一步：共享调用/动态分发解析

### 5.1 问题

当前有两套动态分发处理：

```text
main_flow_utility.py
  - 支持 config dispatch hints
  - 支持源码注释
  - 支持 argparse set_defaults
  - 支持静态 registry
  - 支持 polymorphic candidates
  - 输出 candidateSetComplete / candidateSource / unresolvedReason

execution_flow_utility.py
  - 主要只使用 CallSite.candidates
  - 不消费 config.dispatchHints
  - 不扫描 argparse / 静态 registry
```

结果：

```text
自举项目 args.func
mainFlows 数据：9 candidates / complete / config
executionFlow UI：0 candidates / partial call
```

这会让执行流中的动态分发节点变成信息黑洞。

### 5.2 目标

建立一份共享的调用目标与分发动解析结果，供执行流消费；调用总览 UI 不恢复。

建议解析结果至少包含：

```json
{
  "kind": "local_callable | interface | dispatch | external | unresolved",
  "targetFunctionId": "...",
  "capabilityId": "...",
  "moduleId": "...",
  "callableKind": "function | method",
  "ownerClassId": "...",
  "candidateCount": 9,
  "candidates": ["..."],
  "candidateSetComplete": true,
  "candidateSource": "config | argparse_registry | static_registry | polymorphic | unknown",
  "unresolvedReason": null,
  "callSiteId": "...",
  "file": "...",
  "line": 0
}
```

### 5.3 实施任务

1. 从 `main_flow_utility.py` 抽取可共享逻辑：
   - `_resolve_function_ref`
   - `_is_dynamic_dispatch_site`
   - `_static_dispatch_candidates`
   - `_resolve_hint_candidates`
   - 配置 hint / 注释 / argparse / static registry / polymorphic 候选合并
2. 将这些能力接入 `execution_flow_utility.py` 的 target resolver。
3. 将 `analysis.config.dispatch_hints` 传入 `build_execution_flows()`。
4. 执行流 `dispatch` 节点补全：
   - `candidates`
   - `candidateCount`
   - `candidateSetComplete`
   - `candidateSource`
   - `unresolvedReason`
   - 可读 note
5. dispatch 节点详情面板展示候选列表；候选可跳转 Method Detail。
6. 不在执行流画布中绘制 candidate 边；保持 dispatch 原子边界。
7. 补充测试：
   - 自举 `args.func`：9 candidates、complete、config；
   - unresolved dispatch：明确原因；
   - 候选点击进入 Method Detail；
   - 执行流画布不出现 composition 候选边。
8. 更新 README、P5 文档和 dynamic dispatch 说明。
9. 保留 `mainFlows` 数据与调用总览相关后端测试，暂不删除。

### 5.4 验收标准

- 执行流与 mainFlow 使用同一份 dispatch 候选解析结果；
- 自举执行流 dispatch 显示 9 个候选、complete、config；
- 候选可在详情面板中查看和跳转；
- 执行流画布仍只有控制边；
- 全量测试、浏览器冒烟、自举 build/check 通过；
- schema 本轮不升级。

### 5.5 暂不做

- 不把候选展开成执行流分支；
- 不恢复调用总览 UI；
- 不删除 `mainFlows`；
- 不重构任务范围外的 impact/trace/dsm。

## 6. 尚未执行的第二步：收缩主流程调用图数据契约

### 6.1 前置条件

必须先完成第一步的共享解析，并确认：

- 执行流已覆盖主流程所需的 dispatch 候选；
- Method Detail 可承担调用关系下钻；
- `mainFlows` 不再被默认 UI 使用；
- 外部查询只依赖 `callSites`、`functionDetails`、`projectGraph.edges`、`typeRelations`。

### 6.2 目标

收缩数据契约，去掉主流程页不需要的重复调用图投影。

候选方向：

```text
remove: projectGraph.mainFlows
remove: projectGraph.primaryFlowId
keep:   projectGraph.executionFlows
keep:   projectGraph.primaryExecutionFlowId
keep:   callSites
keep:   functionDetails[].callers/callees
keep:   projectGraph.edges
keep:   projectGraph.typeRelations
```

同时决定配置命名：

```text
mainFlow.dispatches
  → dispatchHints
或
  → callResolution.dispatches
```

如需兼容旧配置，可保留别名并产生 deprecation 信息。

### 6.3 实施任务

1. 确定 `mainFlows` 的最终去留：
   - 完全删除；或
   - 标记 optional/legacy，仅内部保留一个版本。
2. schema 升级（预计 4.2）：
   - 删除或降级 required `mainFlows` / `primaryFlowId`；
   - 更新 bundle 顶层与 projectGraph 契约。
3. 决定 `mainFlow.dispatches` 的新配置归属并更新 config loader/docs。
4. 删除或内联 `main_flow_utility.py` 中不再需要的投影构建代码。
5. 更新 `graph_utility.py`、validation、stats、semantic fingerprint。
6. 更新所有依赖 mainFlows 的测试：
   - `tests/test_main_flow.py` 迁移为共享 dispatch resolver 测试；
   - 保留 trace/impact/dsm 查询测试。
7. 更新 README、架构图、数据契约文档和示例配置。
8. 旧 4.1 bundle 用历史 schema 保留追溯。

### 6.4 验收标准

- 默认 bundle 不再有重复的 `mainFlows` 投影，或明确标记 legacy；
- 执行流、方法详情、trace/impact/dsm 无功能回退；
- `archmap check` 校验当前 schema；
- 旧 schema 文件仍可追溯；
- 全量测试与浏览器冒烟通过；
- 文档不再把调用总览描述为默认 UI。

### 6.5 风险

- 外部脚本可能读取 `mainFlows`；
- 默认移除会破坏 schema 兼容；
- 配置命名迁移可能遗漏示例或文档；
- 如果第一步未完成就删除 mainFlows，会丢失动态分发候选能力。

## 7. 已知限制与风险

| 项目 | 当前状态 |
|---|---|
| 执行流动态分发详情 | 弱；下一步第一优先 |
| `mainFlows` 与 `executionFlows` 双投影 | 数据层仍并存，UI 只使用执行流 |
| `mainFlow.dispatches` 命名 | 仍是旧命名，待第二步决定 |
| 条件表达式中的调用 | 仍折叠进控制节点标签，不单独物化 |
| 执行流卡片签名 | 已移除；签名保留在 Method Detail |
| 主模块能力页 | 已恢复为独立 `#/module/main` 能力视图 |
| 调用总览 UI | 已移除 |
| ArkTS 前端 | 尚未实现 |
| 执行流图内下钻 | 明确不支持 |

## 8. 常用验证命令

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

## 9. 变更门槛

继续开发时必须保持：

1. 主流程页只展示执行流，不重新引入调用总览或模块契约。
2. 模块能力页只展示 Provider/API/类型关系，不嵌入执行流。
3. `return` / `break` / `continue` 不得重新获得出边。
4. 执行边不得恢复 `break` / `continue` / `return` / `back` / `dispatch` kind。
5. 执行流卡片不得重新渲染 signature。
6. 动态分发候选不得直接展开成执行流控制分支。
7. 第一步完成前不得删除 `mainFlows` 数据。
8. 任何数据契约变更必须先更新设计文档、schema、validator 和迁移说明。

## 10. 交接检查清单

- [x] P5.5 页面拆分已完成
- [x] 主流程页只展示执行流
- [x] 模块能力页独立
- [x] 调用总览 UI 移除
- [x] `mainFlows` 数据保留
- [x] schema 4.1 与 terminal/edge 契约稳定
- [x] 执行卡 human note 回归
- [x] 示例配置与源码结构对齐
- [ ] 下一步第一步：共享调用/动态分发解析
- [ ] 下一步第二步：收缩主流程调用图数据契约
