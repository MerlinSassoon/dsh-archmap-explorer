# P8 执行流专属 callable 与空能力模块计划

> 状态：已完成<br>
> 版本：ArchMap 2.2.0 / bundle schema 6.1<br>
> 日期：2026-11-19

## 1. 背景

P6/P7 已把入口、执行流和能力模块拆开，但入口模块中的 `main/client/server` 这类流程编排函数仍会被角色推断为 `manager`，进入 `providedApis`、Provider 卡片和能力计数。

这不是模块边界问题，而是能力呈现面缺少显式声明：

```text
callable 属于模块源码边界
≠
callable 必须作为模块能力 Provider 展示
```

## 2. 目标

- 模块配置支持 `executionOnlyCallables`；
- 支持模块级自由函数和类方法；
- executionOnly callable 对能力面透明；
- 保留 functionDetails、callSites、callers/callees、执行流节点和方法详情下钻；
- 能力为空的模块后端保留模块与 layout，前端不渲染模块卡；
- 不新增 Provider Role，保持七角色；
- 不以模块级删除代替 callable 级声明。

## 3. 配置契约

```json
{
  "modules": [
    {
      "id": "app",
      "name": "应用入口与编排",
      "include": ["src/app/**"],
      "role": "service",
      "executionOnlyCallables": [
        "src.app.main:main",
        "src.app.main:run_client",
        "src.app.main:run_server",
        "src.app.cli:GameCli.run"
      ]
    }
  ]
}
```

引用格式为 `module.path:qualname`。显式声明优先于自动角色推断。

## 4. 透明化不变量

executionOnly callable：

- 不进入 `providedApis`；
- 不进入 `apiProviders`；
- 不进入 `moduleComposition`；
- 不进入 `providerRoleCounts` / `publicProviderRoleCounts`；
- 不生成模块能力节点或能力卡；
- 不显示 Provider Role；方法详情显示 `execution:entry` 或 `execution:orchestrator`；
- 其完全独占产生的 User Surface 不进入模块能力页。

仍然保留：

- `functionDetails`；
- `callSites`；
- callers / callees；
- 源码切片；
- executionFlow 节点；
- trace / impact 查询。

类方法被声明为 executionOnly 时，owner class 仍保留为 Provider，仅该方法从类能力 API 中移除。

## 5. 空能力模块规则

模块排除 executionOnly callable 和 internal Provider 后没有可见 Provider 时：

- `capabilitySurface.hasProviders=false`；
- 后端保留 `projectGraph.modules[]`、`moduleGraphs[]`、文件归属和 `layout.nodes[moduleId]`；
- 前端不渲染模块卡；
- 项目页模块计数、单模块模式、搜索和 fitView 只使用可见模块；
- 直接访问该模块能力路由时返回项目页并提示“该模块仅承载执行流，无能力视图”；
- `projectGraph.capabilityModuleIds` 列出前端应渲染的模块集合。

## 6. 校验

错误：

- executionOnly callable 引用无法解析；
- callable 不属于声明模块；
- 同一 callable 被多个模块声明；
- executionOnly callable 出现在 `providedApis` 或模块能力节点；
- executionOnly detail 缺少 `functionSurface=execution` 或非法 `executionRole`。

警告：

- executionOnly callable 同时配置了 `providerRoles`；
- executionOnly callable 被其他模块调用；
- executionOnly callable 不在任何 execution flow 中可达。

## 7. 实施阶段

### P8.0 契约锁

- 配置字段、引用语法、类方法支持；
- 空能力模块后端/前端行为；
- 直接路由策略。

### P8.1 后端投影

- 配置解析与 callable 解析；
- capability 过滤；
- moduleGraph / projectGraph 派生字段；
- validator 与诊断。

### P8.2 前端

- 隐藏空能力模块卡；
- 可见模块计数；
- 直接路由回退；
- 方法详情 execution 徽标；
- 不渲染 executionOnly Provider 卡。

### P8.3 样例与文档

- student_system、gomoku、self 配置；
- `archmap-config-generation.md`；
- README、数据契约、schema、验收与交接。

## 8. 验收

```text
student app: 3 个 executionOnly callable
student app: capabilitySurface.hasProviders=false
student app: 前端不显示模块卡
student main flow: 节点和边不减少
self cli_entry.main: 从能力面移除
self pipeline: 因 PipelineManager 保留能力卡
schemaVersion: 6.1
diagnostics: 0 error
```

## 9. 非目标

- 不自动识别所有流程函数；
- 不删除模块；
- 不新增 Provider Role；
- 不恢复主模块；
- 不改变 execution flow 控制骨架；
- 不做前端可见卡片自动重排。
