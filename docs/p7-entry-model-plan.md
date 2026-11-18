# P7 入口语义与项目页布局修复计划

> 状态：已批准，按阶段实施；P7.0-P7.4 已完成<br>
> 起始基线：`P6` 分支 5b3c245<br>
> 日期：2026-11-18

## 1. 目标

彻底分离三层语义：

```text
Provider Role
Execution Flow Node
Project Page Item
```

最终模型：

- Provider Role 只保留七角色：config / model / manager / adapter / component / contract / utility；
- execution flow 恢复 `entry` 节点，与 loop/branch 同级；
- 项目页 flow card 与 module card 同级、同布局；
- 入口检测由项目级 `entrypoints` / `executionEntrypoints` 驱动，不依赖 Provider Role；
- 模块不承载入口角色、入口 API 或流程导航；
- 首句不可物化语句不导致执行流断开。

## 2. 阶段

### P7.0：契约与规划

- 记录 P7 计划；
- 更新文档入口；
- 明确三层语义和验收标准。

### P7.1：Provider Role 七角色化（已完成）

- 删除 Provider Role `entry`；
- 删除模块 role `entry`；
- 删除 entrypoint 强制角色注入；
- 删除 entry 自动 API 暴露；
- 新增 `isFlowEntry` / `flowIds` 流程引用事实；
- 兼容旧配置中的 entry role override 并产生 deprecation warning；
- 更新 validator 和测试。

### P7.2：执行流入口节点恢复（已完成）

- execution node kind 恢复 `entry`；
- 入口节点使用标准卡片样式；
- builder 从入口节点开始；
- 不可物化语句 pass-through；
- 空流程生成 entry→exit；
- validator 恢复唯一 entry 节点和可达性约束。

### P7.3：项目页 flow card 同层布局（已完成）

- 新增 `projectGraph.flowCards`；
- flow cards 与 module cards 一起进入项目布局；
- 删除顶部独立流程入口区域；
- flow card 使用标准卡片样式并标注“主流程”；
- 支持多 flow card、拖拽和布局覆盖持久化。

### P7.4：模块与样例配置归一化（已完成）

- student_system / gomoku / self 配置移除 entry role；
- 模块卡片不展示入口 API；
- 保留所有源码文件的唯一模块归属；
- 验证入口检测、dispatch 候选和 P3/P4 查询无回退。

### P7.5：最终验收与文档

- 全量测试、浏览器冒烟；
- self/student/gomoku build/check；
- schema 6.0 与版本更新；
- README、架构规范、API 契约、P7 交接文档收口。

## 3. 验收标准

- Provider Role 枚举无 `entry`；
- 模块 role 枚举无 `entry`；
- 每条 execution flow 恰好一个标准 `entry` 节点；
- 入口为实例化语句时，后续调用仍进入执行流；
- 空函数 flow 至少包含 entry→exit；
- 项目页无顶部独立流程入口条；
- flow card 与 module card 同层同网格；
- 模块不展示 entry API；
- student_system 只有一张 `main()` flow card；
- gomoku 只有一张 `GameCli.run()` flow card；
- self 只有一张 `cli_entry.main()` flow card；
- 自举 dispatch 仍为 9 candidates / complete / config；
- 全量测试与浏览器冒烟通过；
- schema 6.0 校验通过。

## 4. 非目标

- 不恢复主模块；
- 不恢复 mainFlows；
- 不恢复模块页调用边；
- 不改变动态分发候选语义；
- 不把 dispatch candidates 展开为控制分支；
- 不新增类焦点页；
- 不实现 ArkTS。
