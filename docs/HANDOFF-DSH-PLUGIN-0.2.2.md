# HANDOFF：DSH 插件 dsh-archmap-explorer 0.2.2

> 状态：待发布，标签 `dsh-plugin-v0.2.2`<br>
> 插件版本：`0.2.2`<br>
> Python 核心：ArchMap `2.6.1` / bundle schema `6.4`（本版未改）<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> 上一发布标签：`dsh-plugin-v0.2.1`<br>
> 当前使用文档：[dsh-plugin.md](dsh-plugin.md)

## 1. 本版定位

0.2.2 是**分发型版本**，不新增工具、不改变 Python 分析结果、不改变 bundle schema。

起因：npm 账号注册被风控阻断，短期无法通过 npm 分发。GitHub 直装又被 pnpm 10 的
`ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED` 拦住，必须让用户手工改 `pnpm-workspace.yaml`。
这个手工步骤是安装路径上最大的流失点，与本版要解决的问题直接冲突。

因此本版做一件事：**让安装不再需要任何构建脚本审批**。

## 2. 核心变更

```text
package.json
  - "prepare": "node ./scripts/prepare.mjs"
  + "prepack": "node ./scripts/prepare.mjs"

版本
  - 插件：0.2.1 → 0.2.2
  - Python 核心：2.6.1（不变）
  - bundle schema：6.4（不变）
```

原因：

- `prepare` 会在 git 依赖安装时执行，pnpm 10 默认拒绝，于是安装失败并要求用户加白名单。
- `prepack` 只在 `npm pack` / `npm publish` 时执行，正好是「打包前自检」的本意。
- 包内没有构建产物（Python 源码与前端资产都是源码直出），git 安装不需要生成任何东西。

自检脚本本身没有改动：仍然只做文件存在性、JS 语法和 Python 版本检查，不联网、不跑
pytest、不启动浏览器。

## 3. 安装方式（本版起的推荐顺序）

```bash
# 1) GitHub 直装（无需 pnpm 白名单）
dsh plugin add github:MerlinSassoon/dsh-archmap-explorer

# 2) 预构建 tarball（Release 附件，安装最快）
dsh plugin add https://github.com/MerlinSassoon/dsh-archmap-explorer/releases/latest/download/dsh-archmap-explorer.tgz

# 3) npm（账号可用后恢复）
dsh plugin add dsh-archmap-explorer
```

tarball 文件名刻意不带版本号：`latest/download/` 只在请求时解析 `latest`，文件名按字面取，
带版本会随下一次发版静默 404。

## 4. 验证基线

```text
python3 -m pytest -q                163 passed, 1 skipped
npm test                            11 passed, 0 failed
npm run prepack                     prepare: ok
npm pack                            产出 dsh-archmap-explorer-0.2.2.tgz
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
python3 -m archmap check .archmap/self/architecture.json
```

安装验证（必须在**全新 profile** 上做，且不预先写 `onlyBuiltDependencies`）：

```bash
dsh plugin --profile v022gh add github:MerlinSassoon/dsh-archmap-explorer
dsh --profile v022gh --dump-config | grep -A1 tool-archmap
dsh --profile v022gh --dump-config-schema
PYTHONPATH=<profile>/node_modules/dsh-archmap-explorer python3 -m archmap --version
```

判据：不出现 `ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED`，不需要改任何 profile 配置，
`--dump-config-schema` 的 `diagnostics` 为空。

## 5. 发布步骤

1. 版本号：`package.json` `0.2.1` → `0.2.2`（Python 核心不动）。
2. 更新 `README.md`、`README.zh.md`、`docs/dsh-plugin.md` 的版本与安装命令。
3. `npm run prepack`、`npm test`、`pytest`、自构建与 `check` 全绿。
4. 合入 `main`，新增并推送标签 `dsh-plugin-v0.2.2`（不移动 0.2.1）。
5. `npm pack` 生成 tgz，作为 GitHub Release `dsh-plugin-v0.2.2` 的附件上传，文件名去掉版本号。
6. 用 tarball URL 再验证一次全新 profile 安装。

## 6. 回滚

- 回退到 `dsh-plugin-v0.2.1`，但 0.2.1 的 git 安装需要 pnpm 白名单，属于已知摩擦。
- Python 核心与 schema 未变，0.2.2 产物与 0.2.1 完全互通。

## 7. 与 npm 的关系

npm 仍是长期最优分发方式（Discover 索引按 npm 已发布版本收录、可显示下载量）。
本版不依赖 npm，但不阻止后续发布：

- npm 账号可用后，`npm publish` 同一个 0.2.2 即可，无需改代码；
- 届时把 `github:` 安装命令降级为备选，主推 `dsh plugin add dsh-archmap-explorer`。

## 8. 待办

- 英文 UI：方法详情页的界面文案仍为中文（见[曝光规划 §8](旧文档/11月20日/2026-11-20-dsh-archmap-explorer-曝光规划.md) 决策项）。
- `main()` 一类函数的 `unresolved` 被调数量偏高，属 P1-1 属性链解析，曝光前评估是否需要先修。
