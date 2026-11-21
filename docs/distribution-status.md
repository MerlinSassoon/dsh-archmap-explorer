# 分发与收录状态

> 更新时间：2026-11-21<br>
> 当前版本：ArchMap 2.6.1 / DSH 插件 0.2.2 / bundle schema 6.4

本文只记录可公开验证的分发事实。账号操作、token、投放策略和内部排期不进入公共仓库。

## 已验证

| 项目 | 状态 |
|---|---|
| 在线演示 | <https://merlinsassoon.github.io/dsh-archmap-explorer/> 可访问；d1/d2/d3 页面可加载 |
| awesome-dsh-plugin 收录 | PR [#17251](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/pull/17251) 已由维护者合并；[目录详情页](https://awesome-dsh-plugin.com/p/MerlinSassoon/dsh-archmap-explorer/) 可访问 |
| GitHub 安装 | `dsh plugin --profile <name> add github:MerlinSassoon/dsh-archmap-explorer`，全新 profile 实测约 21s |
| 预构建 tarball 安装 | Release 附件 `dsh-archmap-explorer.tgz`，全新 profile 实测约 23.4s |
| 安装后加载 | `dsh --profile <name> --dump-config` 出现 `id: tool-archmap` / `name: dsh-archmap-explorer` |
| 自动测试 | Python 163 passed / 1 skipped；DSH 插件 11 passed |

合并事实：

```text
PR:        #17251
merged_at: 2026-11-20T17:17:27Z
merged_by: fkysly
entry:     data/plugins/MerlinSassoon__dsh-archmap-explorer.yml
```

## 安装

```bash
# 从 GitHub 安装
dsh plugin --profile web add github:MerlinSassoon/dsh-archmap-explorer

# 或从 Release 预构建包安装
dsh plugin --profile web add \
  https://github.com/MerlinSassoon/dsh-archmap-explorer/releases/latest/download/dsh-archmap-explorer.tgz

# 验证插件已进入 profile
dsh --profile web --dump-config
```

## 尚未完成

- **npm 尚未发布。** npm 发布后，可以改为 `dsh plugin add dsh-archmap-explorer`。
- **DSH Discover / `plugin_market` 索引尚未包含本插件。** 目录的市场索引当前只收录 npm 上有明确版本的条目；本插件已进入目录全量 `plugins.json`，但尚未进入市场索引 `index.json`。在 npm 发布并完成目录探测前，不要表述为“可在 Discover 搜到”。

## 公开渠道

- awesome-dsh-plugin：[PR #17251](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/pull/17251) · [目录详情页](https://awesome-dsh-plugin.com/p/MerlinSassoon/dsh-archmap-explorer/)
- dshbase：issue [#353](https://github.com/ylwl1997/dshbase/issues/353)
- DeepSeek Harness Discussions：[#13900](https://github.com/deepseek-ai/deepseek-harness/discussions/13900)
- 本仓库公告帖：[discussions/1](https://github.com/MerlinSassoon/dsh-archmap-explorer/discussions/1)

## 相关文档

- [文档地图](README.md)
- [DSH 插件使用文档](dsh-plugin.md)
- [DSH 插件 0.2.2 交接](HANDOFF-DSH-PLUGIN-0.2.2.md)
