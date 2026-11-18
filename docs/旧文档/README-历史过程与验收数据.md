# ArchMap README 历史过程与验收数据归档

> 归档日期：2026-11-19<br>
> 说明：本文承接原根 `README.md` 中的阶段状态、阶段功能说明、验收统计和文档维护过程。
> 这些内容用于追溯产品演进，不代表当前产品契约。当前使用说明以根 [README](../../README.md) 为准。

## 1. 阶段状态快照

原 README 的 P0–P12 阶段状态如下：

```text
P0    类语义数据模型                          已完成
P1    模块页类组件化与模块边界修复            已完成
P1.5  FunctionDetail + Source View + CallGraph 已完成
P2.0  项目页/模块页能力契约重构              已完成
P2.1  API 契约建模与展示                     已完成
P2.2  Provider Role 与模块组合                已完成
P2.3  架构规范、自身代码迁移、旧 shim 清理    已完成
P2.4  主模块/功能模块/主流程 DAG              已完成
P3    继承、接口、多态与继承 API              已完成
P4    结构关系、User Surface、Impact/Trace/DSM 已完成
P5    主流程执行流（首版）                 已完成
P5.1  执行流直接 fan-in 与项目节点卡片样式  已完成
P5.2  主流程执行入口归一化                  已完成
P5.3  终止节点与本地调用语义统一            已完成
P5.4  bundle schema 4.1 与执行卡注释回归     已完成
P5.5  主流程页与模块能力页分离               已完成
P6.0  项目模型重构计划与配置指南             已完成
P6.1  共享动态分发解析                       已完成
P6.2  schema 5.0、取消主模块与 mainFlows     已完成
P6.3  模块归属与 student/gomoku/self 规范化  已完成
P6.4  标准流程卡片与模块能力页收口         已完成
P6.5  回归、迁移、版本与文档收口           已完成
P7.0  入口语义与项目页布局修复计划         已完成
P7.1  Provider Role 七角色化               已完成
P7.2  标准 execution flow entry 节点恢复   已完成
P7.3  项目页 flow card 与模块卡片同层      已完成
P7.4  入口来源与样例模块配置归一化         已完成
P7.5  schema 6.0、回归与文档收口           已完成
P8    executionOnlyCallables、空能力模块收口 已完成
P9    保守自由函数推断、默认函数面收口     已完成
P10   一级接口 scope 下钻与 schema 6.3      已完成
P10.3 本地编排 callable 自动发现（保守）    已完成
P11   dispatch 候选旅程与 schema 6.4        已完成
P12   UI 美化、可调侧栏与模块依赖线移除      已完成
```

阶段完成后的产品边界快照：

```text
- 所有模块都是普通能力模块；schema 6.4 不再有主模块或 `moduleKind`。
- `executionOnlyCallables` 对模块能力面透明，但仍保留在源码、调用关系和执行流中。
- 模块级自由函数采用保守推断，`defaultFreeFunctionSurface` 支持 `auto` / `internal` / `capability`。
- 排除 executionOnly 和 internal Provider 后能力为空的模块，后端保留模块与 layout，前端不渲染模块卡。
- 主流程是项目级视图，不属于任何模块。
- 主流程只展开入口函数控制骨架；调用目标作为原子执行步骤，不穿透实现。
- 模块能力页只展示 Provider/Capability 与结构关系，不默认展示调用边。
- 项目页 flow card 与 module card 同层、同网格；空能力模块不渲染。
- 一级接口 scope 只展示直接外部能力接口与控制骨架，深度固定为 1。
- 功能接口节点是模块能力边界，永远不生成 scope；只有 `free_function` 编排 callable 可作为 scope root。
- Provider Role 为七角色；`entry` 不再是 Provider Role。
- 每条 execution flow 生成一个标准 `entry` 节点，与 loop / branch / dispatch 同级。
- 旧语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
- 旧 Python import 兼容 shim 已删除；源码只使用 canonical 目录。
```

## 2. P5 主流程执行流过程说明

以下内容原位于 README 的阶段功能章节。当前实现边界已经收敛，详细过程计划见
[`p5-main-execution-flow.md`](11月9日/p5-main-execution-flow.md)。

### P5 主流程执行流（首版已实现）

P5 把项目主流程从“函数级调用/模块组合 DAG”升级为**有界执行流图**：

- 只展示 selected entrypoint 函数内部的控制骨架；
- P10 允许对显式 scope root 生成一级接口视图，但不改变“调用目标原子化、不递归穿透”的主流程边界；
- 项目内 callable（自由函数与类方法统一为同一原子语义）和 canonical interface 都作为原子执行步骤，不展开；双击进入 Method Detail / 源码页面；
- 使用封闭节点集合：`entry` / `exit` / `free_function` / `interface` / `branch` / `multi_branch` / `loop` / `break` / `continue` / `return` / `dispatch`；`entry` 使用标准执行卡片样式；`free_function` 通过 `callableKind` 区分函数与方法；
- `return` 是终止节点，不生成出边；`exit` 只用于隐式落空等真正到达结束锚点的路径；
- `break` / `continue` 是循环内部终止标记，不生成出边；循环节点通过 `loop_complete` 作为唯一结构化离开边界；
- bundle schema 6.4 的执行边只允许 `next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`；
- 汇合不再生成 `merge` 节点，多条路径直接 fan-in 到同一个真实后继节点或 `exit`；
- 执行流实线只表示静态确定的直接控制/执行关系；虚线只表示推断、不完整或间接关系；
- 执行流卡片不渲染函数签名，正文展示人类备注；完整签名在 Method Detail / 节点详情中查看；
- 横向主脊布局，分支上下展开，循环节点通过 `循环体` 端口连接循环体，不再绘制回边 lane；
- 节点使用项目执行流卡片：彩色标题栏、深色主体、内嵌端口行、贝塞尔曲线；端口行无方框和独立背景，卡片外不再挂边标签胶囊；
- 节点位置可在浏览器中拖拽覆盖，关联曲线实时重算并持久化；
- 不生成逐语句节点、列表操作节点、`try/except` 异常控制、数据流边或图内下钻；
- 项目级执行视图保留 `executionFlows`、`flowCards` 和 `primaryExecutionFlowId`；`mainFlows` 已删除；
- 动态分发统一由共享 resolver 处理；新配置使用顶层 `dispatchHints`，旧 `mainFlow.dispatches` 仅作迁移兼容；
- P5 使用 schema 4.0/4.1；P6.2 升级到 5.0；P7.5 升级到 6.0。

P5 的防误解与防滑坡边界、student_system 目标快照、数据契约和验收标准见 [`p5-main-execution-flow.md`](11月9日/p5-main-execution-flow.md)。


## 3. P10 一级接口下钻过程说明

以下内容原位于 README 的阶段功能章节。详细过程计划见
[`p10-interface-drilldown-plan.md`](11月9日/p10-interface-drilldown-plan.md)。

### P10 一级接口下钻（已实现）

P10 在主流程之上增加一层受控的接口视图：

- 主流程节点保持原子化，`free_function` 编排节点可显示 `drilldown.interfaceSummary`；
- 配置 `flowScopes.roots` 指定需要展开的流程编排 callable；
- `executionOnlyCallables` 中的编排 callable 也可成为 scope root；
- 开启 `flowScopes.autoDetect` 后，会从主流程可见的 `free_function` 中保守发现同模块本地编排 callable；
- 自动候选必须有至少一个外部能力接口、至少一个控制结构、未触发 scope 预算且非直接递归；
- 显式 roots / executionOnly 优先于自动候选；
- scope root 必须是 `free_function`；`interface` 节点不展开内部实现；
- scope 路由为 `#/flow/<flowId>/scope/<nodeId>`，独立聚焦展示，不在主画布递归套图；
- scope 内展示目标函数控制骨架、直接外部能力接口、以及内部 helper 直接触达的接口提示；
- P10.2 普通赋值/非调用表达式不新增节点：branch 输出 `armSummaries`，跨控制边的普通语句写入 edge `statements`；
- 多分支不展示 case 内部赋值注释，只保留 case 条件与 `implicitNext=loop_iteration` 隐式循环提示；
- 画布选择高亮优先于 hover；单击空白 / 双击空白 / Esc 均可清除选择；
- scope 深度硬限制为 `1`，内部节点不可再次下钻；
- `maxScopesPerFlow`、`maxNodesPerScope`、`maxEdgesPerScope` 控制预算，截断会写入 scope diagnostics；
- 更深实现统一进入 Method Detail。

student_system 配置下钻 `server` / `client`，gomoku 配置下钻 `_play_one_game`。详见 [`p10-interface-drilldown-plan.md`](11月9日/p10-interface-drilldown-plan.md)。


## 4. P11 dispatch 候选旅程过程说明

以下内容原位于 README 的阶段功能章节。详细过程计划见
[`p11-dispatch-candidate-journeys-plan.md`](11月9日/p11-dispatch-candidate-journeys-plan.md)。

### P11 dispatch 候选旅程（已实现）

P11 在保持 dispatch 主流程原子边界的前提下，把动态分发候选升级为独立候选旅程：

- dispatch 节点仍是单一路由边界，不向主画布新增候选控制边；
- 配置 `dispatchCandidates.enabled=true` 后，完整 candidate set 会生成 `executionFlows[].dispatchGroups[]`；
- 每个候选以真实 `free_function` 为 root 生成一级 execution scope，深度固定为 1；
- 候选 scope 内不再递归生成 dispatch group，不形成调用树；
- dispatch 卡片显示来源、完整性、候选摘要与“候选旅程”入口；
- 候选旅程路由为 `#/flow/<flowId>/dispatch/<nodeId>/candidate/<candidateScopeId>`，支持候选切换和 Hash 刷新恢复；
- `completeOnly=true`（默认）只对声明完整的候选集合生成旅程，避免把不完整推断伪装成完整路由；
- `maxScopesPerDispatch` / `maxScopesPerFlow` / `maxNodesPerScope` / `maxEdgesPerScope` 控制候选 scope 预算，截断写入 group diagnostics 和 bundle stats。

ArchMap 自举的 `main()` CLI 路由器现在生成 1 个 dispatch group 与 9 个候选旅程，其中 `cmd_build` 候选 scope 展示真实构建流水线控制骨架；主流程本身仍保持 4 节点 / 3 边。详见 [`p11-dispatch-candidate-journeys-plan.md`](11月9日/p11-dispatch-candidate-journeys-plan.md)。

## 5. 历史测试与验收数据

以下数据是归档时的基线快照，不是固定承诺；重新构建后以实际产物为准。

```bash
# 全量测试（浏览器测试默认跳过）
python -m pytest -q

# 浏览器冒烟测试
ARCHMAP_RUN_BROWSER=1 python -m pytest -q tests/test_browser_smoke.py
```

当前基线：

```text
pytest:         142 passed, 1 skipped
browser smoke:  1 passed（显式开启）
```

测试覆盖：

- 三层 bundle 契约和交叉引用。
- 无主模块、普通能力模块、无 I/O 端口与纵向模块归属。
- P5 有界执行流：entrypoint 控制骨架、原子本地调用/接口、分支/多分支/循环/break/continue/return、终止 return 与按需 exit。
- 共享动态分发解析：配置、注释、argparse、registry、polymorphic candidates。
- 继承/实现结构边、C3 MRO、有效抽象性、继承 API、override 和多态 candidates。
- 类型关系 validator 不变量与 polymorphic dispatch 低置信度 composition。
- `instantiates/uses/aggregates/composes` 结构关系与角色元数据。
- User Surface 识别、entrypoint 传播和配置覆盖。
- Impact / Trace / DSM 查询、CLI JSON 输出与截断边界。
- 类节点、方法归属、抽象类边界。
- FunctionDetail、源码切片、sourceHash。
- CallSite 提取、callers/callees、函数级调用邻域；项目级模块依赖边已移除。
- API exposure、协议能力合成、Provider 分组和契约校验。
- Provider Role 判定、模块组合、config/model 类型卡片与 API 过滤。
- 宏布局几何、执行流正交布局、指纹稳定性、布局无关性和模块无调用边约束。
- 自包含 HTML、方法详情页和 LLM 注解嵌入。
- CLI build/check/method 闭环。
- schema 6.4、七 Provider Role、标准 flow entry 节点、flow card 与 module card 同层、student/gomoku/self 配置规范化。
- P8 `executionOnlyCallables` 对能力面透明、类方法排除、空能力模块后端保留/前端隐藏、旧几何覆盖失效。
- P9 保守自由函数推断、`defaultFreeFunctionSurface`、单函数 exposure 例外、自由函数表面计数与校验。
- P10 一级 flow scope、外部接口摘要、scope 预算/诊断、独立下钻路由与浏览器下钻回归。
- P10.1 interface 黑盒边界、scope root 仅限编排 callable、interface root 拒绝与 validator 不变量。
- P10.2 控制臂语句摘要、edge statement 标签、隐式循环继续语义、无 statement/basic-block 节点，以及画布空白点击/双击清除选择高亮的回归。
- P10.3 本地编排 callable 自动发现、显式/executionOnly 优先级、interface 排除、外部接口与控制结构门槛、自动来源标识。
- P11 dispatch 候选旅程：候选 group、候选 free_function scope、opt-in 配置、完整性/来源展示、双预算截断、Hash 路由恢复、schema 6.4 与浏览器回归。
- P12 UI：中文导航/指示、统一字号提升、详情栏拖拽调宽、紧凑模块状态条与顶部概览抽屉、模块画布卡片网格、人类注释摘要、移除“关系/单模块”按钮与模块依赖线后端生成。

浏览器交互已使用 Firefox Headless + geckodriver 验证：项目页主流程入口、独立主流程页、dispatch 候选旅程、模块能力页、方法详情页、类方法详情、Hash 刷新恢复、P3 继承 API、P4 surface/结构关系和无运行时错误。

### 当前验收数据

ArchMap 自举：

```text
modules:              5
classes:              35
functions:            284
methods:              81
callSites:            4583
resolvedCalls:        754
typeRelations:        68
structuralRelations:  68
userSurfaces:         0
executionFlows:       1
executionNodes:       4
executionEdges:       3
flowCards:            1
flowScopes:          0
flowScopeNodes:      0
flowScopeEdges:      0
dispatchGroups:      1
dispatchCandidateScopes: 9
dispatchScopeNodes:  81
dispatchScopeEdges:  84
dispatchScopeTruncated: 0
executionOnly:        1
freeFunctionSurface:  0 capability / 202 internal / 1 execution
capabilityModules:    5
emptyModules:         0
diagnostics:          0
self build/check:     OK
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
flowScopes:          2
flowScopeNodes:      20
flowScopeEdges:      19
dispatchGroups:      0
dispatchCandidateScopes: 0
dispatchScopeNodes:  0
dispatchScopeEdges:  0
dispatchScopeTruncated: 0
executionOnly:        3
freeFunctionSurface:  0 capability / 7 internal / 3 execution
capabilityModules:    4
emptyModules:         2
diagnostics:          0
build/check:          OK
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
flowScopes:          1
flowScopeNodes:      24
flowScopeEdges:      24
dispatchGroups:      0
dispatchCandidateScopes: 0
dispatchScopeNodes:  0
dispatchScopeEdges:  0
dispatchScopeTruncated: 0
executionOnly:        1
freeFunctionSurface:  0 capability / 10 internal / 0 execution
capabilityModules:    5
emptyModules:         0
diagnostics:          0
build/check:          OK
```

P3/P4 fixtures：

```text
inheritance_demo:     4 typeRelations / 2 polymorphicCalls / diagnostics 0
p4_demo:              9 structuralRelations / 2 userSurfaces / diagnostics 0
```

## 6. 历史文档维护规则

以下规则已从 README 移出，作为阶段收口过程记录保留：

### 文档维护规则

1. 当前产品状态只写入根 `README.md` 和 `docs/` 下的当前权威文档；历史材料只进入 `docs/旧文档/`，不反向修改为“当前设计”。
2. 当前数据契约以 [`archmap-v3-design.md`](../archmap-v3-design.md) 和 [`archmap-v6.4-bundle.schema.json`](../schema/archmap-v6.4-bundle.schema.json) 为准；过程计划与历史交接仅作追溯。
3. P1.5 之后的实现页统一称 **Method Detail**；不要恢复旧语句级 FunctionFlow。
4. 新增能力时先更新数据契约、当前权威文档和测试，再同步根 README 的使用说明。
5. 示例命令若引用自举配置，应核对 `examples/archmap_v3.archmap.json` 与源码模块一致。
6. 文档总入口统一为根 `README.md`。
7. 所有新增代码必须遵守 [`archmap-code-conventions.md`](../archmap-code-conventions.md)；模块、类、函数、方法和测试都必须有功能备注。


## 7. 归档说明

- 原 README 中面向使用者的定位、快速开始、页面、配置、CLI、能力边界和数据契约说明已改写保留在当前根 README。
- P5/P10/P11 过程计划、历史 schema 和旧原型均已迁入本目录。
- 当前权威文档只包括根 README、数据与扩展设计、架构与编码规范、API 契约模型、AI 编程 Skill、配置生成指南和 bundle schema 6.4。
