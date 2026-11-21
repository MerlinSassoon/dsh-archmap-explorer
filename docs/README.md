# ArchMap 文档地图

本仓库的文档分为三类：当前权威文档、历史归档，以及只在本地维护的操作记录。

## 当前权威文档

- [项目 README](../README.md) / [中文 README](../README.zh.md)
- [分发与收录状态](distribution-status.md)
- [数据与扩展设计](archmap-v3-design.md)
- [架构与编码规范](archmap-architecture-spec.md)
- [API 契约模型](archmap-api-contract-model.md)
- [配置生成规范](archmap-config-generation.md)
- [源码编写约定](archmap-code-conventions.md)
- [DSH 插件使用文档](dsh-plugin.md)
- [bundle schema 6.4](schema/archmap-v6.4-bundle.schema.json)

## 历史归档

[`旧文档/`](旧文档/README.md) 保存历史设计、旧交接、旧验收和过程复盘，仅用于追溯，
不代表当前实现或当前数据契约。当前行为以源码、测试、schema 和上面的权威文档为准。

## 本地维护者文档

账号、token、渠道操作、提交跟踪和内部排期等维护者资料只保存在本地
`.local-docs/`，该目录由 `.gitignore` 排除，不进入公共仓库或 npm 包。
公共仓库只保留可验证、可公开复现的分发事实。
