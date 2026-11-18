# ArchMap v3 设计阶段补充归档

> 归档日期：2026-11-19<br>
> 本文承接原 `docs/archmap-v3-design.md` 顶部的 P5–P12 阶段补充说明，仅用于追溯。当前数据契约以根 README、数据与扩展设计和 schema 6.4 为准。

> 本文档记录 v3.8 基础数据契约及 P5.1-P12 增量修订，并作为实现和后续 ArkTS 扩展的依据。当前 bundle schema 为 6.4；历史文档已归档到 [`docs/旧文档/`](README.md)。发生冲突时，以本文档、[根 README](../../README.md) 和当前 bundle schema 为准。
>
> **P5 补充（2026-11-18）**：P5 主流程执行流首版已实现，新增 `projectGraph.executionFlows` / `primaryExecutionFlowId`，bundle schema 4.1；P5.2 增加可选 `executionEntrypoints`，用于将主执行流起点与分析入口解耦；执行流边界见 [`p5-main-execution-flow.md`](11月9日/p5-main-execution-flow.md)。<br>
>
> **P5.1 补充（2026-11-18）**：移除执行流 `merge` 合成节点，改为多边直接 fan-in；卡片改为内嵌端口行样式。详见 [`p5.1-execution-card-style.md`](11月9日/p5.1-execution-card-style.md) 与 [`p5.1-execution-flow-fan-in-plan.md`](11月9日/p5.1-execution-flow-fan-in-plan.md)。<br>
>
> **P5.3 补充（2026-11-18）**：`return` 成为无出边的终止节点，`exit` 按真实隐式结束路径按需生成；执行边实线只表示确定直接关系、虚线只表示推断/不完整/间接关系；`free_function` 统一表示主模块本地 callable，通过 `callableKind` 区分函数与方法。<br>
>
> **P5.4 补充（2026-11-18）**：bundle schema 升级到 4.1。执行边只保留连接关系 `next` / `true` / `false` / `case` / `default` / `loop_body` / `loop_complete`；`break` / `continue` / `return` 仅作为节点终止类型且无出边；`loop_complete` 是循环唯一结构化离开出口。执行卡片改用 human note，不再渲染 signature。<br>
>
> **P5.5 补充（2026-11-18）**：主流程页独立为 `#/flow` 项目级视图，只展示 `executionFlows`；主模块与功能模块统一进入 `#/module/<id>` 能力页。`mainFlows` 数据保留，但不再作为默认 UI 调用总览展示。<br>
>
> **当前状态（2026-11-19）**：P0-P12 已完成，当前 bundle schema 为 6.4。类焦点页与类内方法图不在产品计划中；后续扩展以真实项目解析质量、User Surface 校准、增量扫描和 ArkTS surface 为主。
>
> **P6 计划（2026-11-18）**：项目模型重构已批准，目标为取消主模块、项目级主流程、单一 executionFlows 投影和纵向能力模块。实施契约、阶段与验收以 [`p6-project-model-plan.md`](11月9日/p6-project-model-plan.md) 为准。<br>
> **P6.2 已实施（2026-11-18）**：bundle schema 升级为 5.0；移除 `mainModuleId`、`moduleKind`、`mainFlows`、`primaryFlowId`；所有模块统一为普通能力模块；execution flow 移除语义 `entry` 节点；`moduleGraphs[].edges` 调用视图数据移除。本文以下 P5/P2.4 段落中涉及主模块与 mainFlows 的内容为历史契约说明；P11 当前契约以 schema 6.4 为准。
>
> **P7 已实施（2026-11-18）**：bundle schema 升级为 6.0；Provider Role 删除 `entry`，模块 role 删除 `entry`；execution flow 恢复标准 `entry` 节点；项目页新增 `flowCards` 并与 module card 同布局；入口语义完全由项目级 entrypoints / execution flow 承担。
>
> **P8 已实施（2026-11-19）**：bundle schema 升级为 6.1；模块配置新增 `executionOnlyCallables`，用于把流程入口和流程内部编排 callable 从能力面透明化；这些 callable 仍保留在 functionDetails、callSites 和执行流中。模块新增 `capabilitySurface`；能力为空时后端保留模块与 layout，前端不渲染模块卡。Provider Role 仍为七角色。
>
> **P9 已实施（2026-11-19）**：bundle schema 升级为 6.2；模块配置新增 `defaultFreeFunctionSurface`，自由函数采用保守推断，未经显式公开 API 或跨模块调用证据不再默认成为 `manager`。自由函数 FunctionDetail 输出 `functionSurface` / `functionSurfaceSource`，ModuleGraph 输出 capability/internal/execution 自由函数 ID 和计数。
>
> **P10 已实施（2026-11-20）**：bundle schema 升级为 6.3；新增一级 `executionScopes` 投影。主流程调用节点仍原子化，但可携带 `drilldown.interfaceSummary`；scope 以独立 `#/flow/<flowId>/scope/<nodeId>` 视图展示目标函数控制骨架、直接外部能力接口和内部 helper 接口提示。scope 深度硬限制为 1，受 `maxScopesPerFlow` / `maxNodesPerScope` / `maxEdgesPerScope` 预算约束，不递归展开。详见 [`p10-interface-drilldown-plan.md`](11月9日/p10-interface-drilldown-plan.md)。
> **P11 已实施（2026-11-19）**：bundle schema 升级为 6.4；新增 `executionFlows[].dispatchGroups[]` 与 dispatch 节点 `drilldown.kind=dispatch`。dispatch 仍是主流程原子路由边界，完整候选以独立 `origin=dispatch_candidate` 的一级 scope 展示；候选 scope 不递归生成 dispatch group，不在主画布新增候选控制边。支持 `dispatchCandidates` 配置、双预算、候选来源/完整性展示和 `#/flow/<flowId>/dispatch/<nodeId>/candidate/<candidateScopeId>` 路由。详见 [`p11-dispatch-candidate-journeys-plan.md`](11月9日/p11-dispatch-candidate-journeys-plan.md)。
>
> **P12 已实施（2026-11-19）**：前端导航与指示中文化，通用 UI 字号提升；右侧详情栏支持拖拽调宽并独立持久化；模块能力页顶部改为紧凑状态条，类型关系与用户交互面通过顶部抽屉展开，提供接口只在右侧详情栏展示；模块画布改为矩形卡片网格；API 与 dispatch 候选签名下方展示人类注释；移除“关系”和“单模块”入口。后端不再生成项目级模块依赖边，`projectGraph.edges` 固定为空数组以兼容 schema。

