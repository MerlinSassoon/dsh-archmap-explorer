# 11月20日批次归档

> 归档日期：2026-11-20<br>
> 归档时版本：ArchMap 2.6.1 / DSH 插件 0.2.2 / bundle schema 6.4

本批次归档的是 DSH 插件从「能用」到「能被发现」这一阶段的过程文档：一次真实使用复盘、
一份由它派生的改进计划、一份 live smoke 验证记录，以及一份曝光与分发规划。

这些文档记录的是当时的判断与验收数据，**不代表当前实现或当前契约**。当前状态见
[项目 README](../../../README.md)、[文档地图](../../README.md)、[分发与收录状态](../../distribution-status.md)、
[插件使用文档](../../dsh-plugin.md) 和 [0.2.2 交接](../../HANDOFF-DSH-PLUGIN-0.2.2.md)。

| 文档 | 内容 | 归档原因 |
|---|---|---|
| [`2026-11-19-dsh-archmap-explorer-真实使用复盘.md`](2026-11-19-dsh-archmap-explorer-真实使用复盘.md) | 一次真实开发会话的工具调用统计与 P0/P1 问题清单（diagnostics 不回流、查询不可用、注解不可增量、静默错误） | 问题清单已转化为 P0-1…P1-5 工作包并实施，阶段结束 |
| [`2026-11-19-dsh-archmap-explorer-改进计划.md`](2026-11-19-dsh-archmap-explorer-改进计划.md) | 由复盘派生的 P0–P2 工作包、里程碑、测试矩阵与 Definition of Done | 主要工作包已落地，剩余项转入常规迭代 |
| [`2026-11-19-dsh-archmap-explorer-live-smoke-验证记录.md`](2026-11-19-dsh-archmap-explorer-live-smoke-验证记录.md) | 真实 DSH 宿主上的 live smoke 执行记录与边界 | 验证已完成，结论已并入 0.2.0/0.2.1 交接 |

## 维护者资料边界

曝光规划、分发手账、账号操作、token 处理和收录操作清单属于维护者运营资料，已移入本地
`.local-docs/`，由 `.gitignore` 排除，不进入公共仓库或 npm 包。

## 与当前文档的关系

- 产品改进优先级以复盘 + 改进计划为**历史依据**；当前实现以源码、测试和 `docs/schema/` 为准。
- 分发与收录的公开事实以 [分发与收录状态](../../distribution-status.md) 和
  [0.2.2 交接](../../HANDOFF-DSH-PLUGIN-0.2.2.md) 为准。
- 旧文档内的相对链接保持归档时的形态；跨目录引用已在归档时改为指向本目录。
