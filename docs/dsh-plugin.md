# DSH 插件：dsh-archmap-explorer

> npm 包：`dsh-archmap-explorer`（尚未发布到 npm，当前用 GitHub 或 Release tarball 安装）<br>
> 插件版本：`0.2.2`（标签 `dsh-plugin-v0.2.2`）<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> Python 核心：随 npm 包分发，要求 Python 3.10+<br>
> 许可证：MIT<br>
> 当前交接：[HANDOFF-DSH-PLUGIN-0.2.2.md](HANDOFF-DSH-PLUGIN-0.2.2.md) / [分发与收录](HANDOFF-2026-11-20-曝光与分发.md)

## 1. 定位

`dsh-archmap-explorer` 是 ArchMap Python 核心的 DSH 薄桥接层：

```text
DSH 插件（Node ESM）
  ├─ archmap_build       确定性构建 architecture.json / architecture.html
  ├─ archmap_annotate    通过 DSH 宿主模型生成源码语义注解
  ├─ archmap-config-generation   bundled Skill
  └─ archmap-code-conventions    bundled Skill
```

插件不实现 AST、调用解析、图投影、布局、校验或 HTML 渲染。插件也不直接持有 API Key，不直接请求模型 HTTP API。

Python 核心随 npm 包一起安装。用户不需要预先 `pip install archmap`。

## 2. 安装

### 2.1 从 GitHub 安装

```bash
dsh plugin --profile web add github:MerlinSassoon/dsh-archmap-explorer
```

也可以用 Release 里的预构建包（下载即装，不触发任何构建脚本）：

```bash
dsh plugin --profile web add \
  https://github.com/MerlinSassoon/dsh-archmap-explorer/releases/latest/download/dsh-archmap-explorer.tgz
```

安装后检查 profile 配置：

```bash
dsh --profile web --dump-config
```

应能看到：

```yaml
# == dsh-archmap-explorer
- id: tool-archmap
  name: dsh-archmap-explorer
```

### 2.2 0.2.2 起不再需要 pnpm 白名单

`prepare` 已改为 `prepack`：只在 `npm pack` / `npm publish` 时执行，安装阶段不运行任何
构建脚本。因此：

- `dsh plugin add github:...` 不会再遇到 `ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED`；
- 不需要修改 profile 的 `pnpm-workspace.yaml`；
- 包内没有构建产物，安装就是解包。

0.2.1 及更早版本仍会触发 pnpm 拦截，需要按 pnpm 提示加入 `onlyBuiltDependencies` 精确 key；
升级到 0.2.2 后该步骤消失。

### 2.3 本地开发安装

```bash
dsh plugin --profile web add link:/absolute/path/to/archmap_v3
```

修改插件代码后，link 安装会直接读取本地仓库。

## 3. 配置

插件配置全部可选。可在 profile 的 `cordis.patch.yml` 中覆盖：

```yaml
- id: tool-archmap
  name: dsh-archmap-explorer
  config:
    pythonPath: python3
    defaultOutputDir: .archmap
    toolTimeoutMs: 120000
    provider: ''
    model: ''
    llmMaxTokens: 8192
    annotationBatchSize: 6
    annotationMaxNodes: 50
    annotationMaxCharsPerNode: 6000
    includeSourceInAnnotations: true
```

| 配置 | 默认值 | 说明 |
|---|---|---|
| `pythonPath` | `$ARCHMAP_PYTHON` 或 `python3` | Python 3.10+ 可执行文件 |
| `defaultOutputDir` | `.archmap` | 构建默认输出目录，相对于被分析项目 |
| `toolTimeoutMs` | `120000` | Python 子进程和单个 DSH 工具调用的协作超时 |
| `provider` | 空 | 可选模型 provider；必须与 `model` 同时配置 |
| `model` | 空 | 可选模型 id；必须与 `provider` 同时配置 |
| `llmMaxTokens` | `8192` | 单次宿主模型调用输出上限 |
| `annotationBatchSize` | `6` | 每批发送给模型的节点数 |
| `annotationMaxNodes` | `50` | 单次注解最多处理的节点数 |
| `annotationMaxCharsPerNode` | `6000` | 单节点源码摘录字符上限 |
| `includeSourceInAnnotations` | `true` | 是否向模型提供源码摘录 |

## 4. 工具

### 4.1 `archmap_build`

根据 Python 项目生成：

```text
<outDir>/architecture.json
<outDir>/architecture.html
```

参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `projectPath` | 是 | 项目根目录，必须位于当前 DSH workspace 内 |
| `configPath` | 否 | `archmap.config.json` 路径 |
| `outDir` | 否 | 输出目录；默认 `<project>/.archmap` |

返回：

- 项目名与语义指纹
- 模块数、函数数、执行流数、call site 数
- error / warning / info 诊断统计
- `issues`（code/message/file/line/functionId/nodeId/sourceCode）与 `nextActions`
- `durationMs`、`bundleBytes`、`htmlBytes`
- `architecture.json` 与 `architecture.html` 绝对路径

构建内部校验失败时返回 `ok: false`、完整 diagnostics 明细和可执行修复建议，不伪造成功产物。只有结构错误会阻断构建；可解释的静态解析不完整（例如 polymorphic call 没有候选）以 warning 返回并继续生成 HTML。

### 4.2 `archmap_annotate`

使用当前 DSH 宿主模型生成源码语义注解，写入侧车文件并重新渲染 HTML。

参数：

| 参数 | 必填 | 说明 |
|---|---|---|
| `projectPath` | 二选一 | 先构建再注解 |
| `bundlePath` | 二选一 | 注解已有 `architecture.json` |
| `scope` | 否 | `project` / `modules` / `functions` / `all`，默认 `functions` |
| `nodeIds` | 否 | 精确节点 ID 列表 |
| `maxNodes` | 否 | 本次最大节点数 |
| `includeSource` | 否 | 是否包含源码摘录 |
| `force` | 否 | 是否覆盖已有/人工注解，默认 `false`；等价于 `refreshMode=all` |
| `refreshMode` | 否 | `missing` / `stale` / `all`，默认 `missing`；`stale` 只刷新 sourceHash 已过期节点 |

处理流程：

```text
projectPath 时先 build
→ python -m archmap annotations context
→ 按 refreshMode（missing/stale/all）先在 Python 侧过滤并截断
→ 按批调用 ctx.llm
→ 严格 JSON 解析，首次失败带错误信息修复一次
→ 写 annotation-proposal.json
→ python -m archmap annotations apply
→ 合并 llm-annotations.json
→ 重新渲染 architecture.html
```

安全与一致性约束：

- 模型只能返回 `summary` / `details` 等语义文本。
- `nodeId` 必须存在于 Python 提供的上下文中。
- `sourceHash` 一律由 Python 从 bundle 读取，不信任模型返回值。
- 模型不能改写源码或 `architecture.json`。
- 默认保留已有注解，`force=true` 才允许覆盖。
- 取消信号 `exec.signal` 透传到模型流和 Python 子进程。

返回：

- 实际 applied / skipped 数量
- 模型拒绝输出数量
- provider / model / promptVersion
- 批次数量、`durationMs` 和 `batchDurationsMs`
- 候选/选中/stale/missing/unchanged/remaining/truncated 统计
- `annotation-proposal.json` 之外的正式侧车路径与 HTML 路径

### 4.3 `archmap_query`

只读查询工具，不写 bundle、不改源码、不触发模型。

| 参数 | 必填 | 说明 |
|---|---|---|
| `operation` | 是 | `check/trace/impact/surfaces/dsm/method` |
| `bundlePath` | 视操作 | `check/trace/surfaces/dsm` 的 architecture.json |
| `beforePath` / `afterPath` | impact 必填 | 前后 bundle 路径 |
| `projectPath` / `configPath` | method 必填 | 方法详情构建来源 |
| `start` / `direction` / `maxDepth` / `maxNodes` | trace 可选 | 起点、方向与预算 |
| `module` / `level` / `includeInternal` | 可选 | surfaces 与 dsm 过滤 |

返回统一包含 `ok`、`text`、`operation`、`truncated`、`warnings`、`data`。trace 还会显式返回低置信度 `unresolvedReferences`，避免把解析失败误报为确定零调用。

### 4.4 `archmap_guide`

确定性 Skill fallback。它直接读取 npm 包内同一份权威 Markdown，不维护第二份正文。

| topic | 内容 |
|---|---|
| `code-conventions` | 模块边界、Provider Role、能力面、入口、备注和测试约定 |
| `config-generation` | `archmap.config.json` 生成与校验算法 |
| `usage` | 插件工具和工作流说明 |

当当前 DSH preset 不暴露原生 `skill` 工具时，模型应使用该工具，而不是自行搜索 `node_modules`。

## 5. 宿主模型路由

模型调用必须经过 DSH `ctx.llm`，路由顺序：

```text
1. 插件配置 provider + model
2. 当前 DSH 会话模型 exec.agent.model.current()
3. 第一个已注册且能列出模型的 provider
4. HOST_MODEL_UNAVAILABLE
```

实现使用：

- `ctx.llm.prepareCall()`
- `prepared.stream()`
- `BlockAssembler`

插件不读取、保存或转发 API Key。

## 6. Bundled Skill

| Skill | 必需 | 用途 |
|---|---|---|
| `archmap-config-generation` | 是 | 从源码事实生成/校验 `archmap.config.json` |
| `archmap-code-conventions` | 是 | 编写符合 ArchMap 模块、能力面和执行流约定的 Python 代码 |

- 名称使用 kebab-case。
- 正文直接读取包内权威 Markdown，不维护第二份副本。
- 使用 `BUNDLED_SKILL_RANK`。
- 两个 Skill 均允许模型和用户调用。
- `archmap-config-generation` 缺失或为空时，插件加载失败。

## 7. 产物与源码边界

插件调用 Python 后产生：

```text
architecture.json          # 稳定数据契约
architecture.html          # 自包含交互页面
llm-annotations.json       # 模型语义注解侧车
annotation-proposal.json   # 最近一次模型原始 proposal（中间文件）
layout-overrides.json      # 前端可选导出，不由插件写入
```

Python 核心和 bundled Python 文件位于 npm 包内。插件运行时通过 `PYTHONPATH` 指向包根目录，不依赖用户项目的虚拟环境安装 ArchMap。

## 8. 路径与安全约束

- 插件运行在 DSH workspace sandbox 之外，因此所有 `projectPath`、`configPath`、`outDir`、`bundlePath` 都通过 workspace 路径校验。
- 拒绝 `../` 越界和 workspace 外部绝对路径。
- 插件不扫描任意用户目录。
- 模型输出不得写入源码或 bundle。
- 注解文本最终由 HTML 渲染层转义显示。

## 9. 常见错误

| 错误 | 处理 |
|---|---|
| `HOST_MODEL_UNAVAILABLE` | 选择会话模型，或配置插件 `provider` + `model` |
| `HOST_MODEL_INVALID_JSON` | 插件会自动修复一次；仍失败时重试或减少批次节点数 |
| `HOST_MODEL_TRUNCATED` | 降低 `annotationBatchSize` 或提高 `llmMaxTokens` |
| `ARCHMAP_PATH_ESCAPE` | 使用当前 DSH workspace 内的路径 |
| `ARCHMAP_TIMEOUT` | 提高 `toolTimeoutMs` 或减少注解节点数 |
| `ARCHMAP_SKILL_MISSING` | 重新安装插件，确认包内两份 Skill Markdown 完整 |
| pnpm prepare 被拦截 | 按 pnpm 提示在 profile `pnpm-workspace.yaml` 加 `onlyBuiltDependencies` 精确 key 后重试 |
| Python 不可用 | 安装 Python 3.10+，或设置 `pythonPath` / `ARCHMAP_PYTHON` |

## 10. 验收命令

```bash
python3 -m pytest -q
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py

npm run prepack
npm test
npm pack --dry-run

dsh plugin --profile <test> add link:<repo>
dsh --profile <test> --dump-config
dsh --profile <test> --dump-config-schema
```

真实 Git URL 安装：

```bash
dsh plugin --profile <test> add git+https://github.com/MerlinSassoon/dsh-archmap-explorer.git
```

## 11. 发布后验证边界

0.2.0 的 Python 回归、Node 插件测试、npm pack、自构建、真实 Git URL 安装、`--dump-config-schema` 和真实 DSH 宿主模型 live smoke 主链路均已完成。

真实 live smoke 使用 DSH `0.2.2-rc.1`、minimal preset 和 `deepseek-official / deepseek-flash`，验证结果：

```text
archmap_guide：三份权威 Markdown 可读取
archmap_build：5 modules / 94 functions / 382 call sites / 3 flows
archmap_query：check / surfaces / dsm / trace 可调用
archmap_annotate：两轮共 100 节点，0 rejected
architecture.html：注解文本已渲染
最终诊断：0 error / 0 warning / 1 info
```

其中 100 个注解节点为“项目 1 + 模块 5 + 函数 94”，不是 100 个函数。

详细记录见 [`旧文档/11月20日/2026-11-19-dsh-archmap-explorer-live-smoke-验证记录.md`](旧文档/11月20日/2026-11-19-dsh-archmap-explorer-live-smoke-验证记录.md)。

live smoke 同时发现以下后续问题，不能把主链路通过等同于所有验收边界通过：

- CLI 入口级行为未被 pytest/build 捕获：示例项目 11 个测试通过，但 `client list/get/delete` 仍出现 `argparse.Namespace` 字段错误。
- 按 warning 建议加入/修正 `dispatchHints` 后，`POLYMORPHIC_CALL_CANDIDATES` warning 和 fingerprint 未变化；`dispatchHints` 的真实作用边界需要澄清。
- `archmap_query trace` 的起点需要 canonical `fn:` ID，简写未归一化。
- 注解成本、语义复述和可信度仍需专项评估。

本次未在真实会话中触发：模型非法 JSON 修复、取消/超时、workspace 越界、`refreshMode=stale`、`archmap_query impact/method` 和大项目性能。这些仍由自动化测试或后续专项验收覆盖。

## 12. 0.1.0 → 0.2.0 迁移说明

0.2.0 不修改 bundle schema，仍为 `6.4`；变化集中在 DSH 工具闭环、分析可信度、默认行为和诊断呈现。

### 12.1 新增能力

- 新增 `archmap_query`：`check/trace/impact/surfaces/dsm/method`。
- 新增 `archmap_guide`：原生 `skill` 工具不可用时的权威 Markdown fallback。
- `archmap_build` 返回结构化 `issues`、`issueSummary`、`nextActions`、`durationMs`、`bundleBytes`、`htmlBytes`。
- `archmap_annotate` 支持 `refreshMode=missing|stale|all`，并返回候选/状态/剩余/耗时统计。

### 12.2 行为变化

- `flowScopes.enabled` 默认从 `false` 改为 `true`；显式 `"enabled": false` 仍可关闭。
- `autoDetect` 仍默认 `false`。
- `POLYMORPHIC_CALL_CANDIDATES` 从 error 改为 warning；warning-only 项目继续生成 HTML。
- 配置无效值和无匹配 `apiExposure` / `providerRoles` target 现在 fail loud。
- `do_*` / `log_*` 默认按 internal 能力面处理。
- 常见角色后缀参与推断：Store/Repository/Client → adapter，Handler/Server/Cli → component。
- 方法详情增加 unresolved callers 提示；trace 返回 unresolved references。
- 模块 note 未配置时回退到模块 docstring 第一段，并返回 `noteSource`。

### 12.3 兼容性

- 现有配置文件仍可读取；显式 `flowScopes.enabled=false` 保持关闭。
- `archmap_build` / `archmap_annotate` 原有必需参数保持兼容。
- `llm-annotations.json` 结构保持兼容；sourceHash 过期机器注解可在 stale 模式下刷新。
- 已发布标签 `dsh-plugin-v0.1.0` 不移动。

## 13. 0.2.1 → 0.2.2 增量说明

0.2.2 是分发型版本：`prepare` 改为 `prepack`，安装阶段不再执行任何生命周期脚本，
因此 `dsh plugin add github:...` 不再需要 pnpm 的 `onlyBuiltDependencies` 授权。
Python 核心（2.6.1）、bundle schema（6.4）与四个工具的契约均未变化。
详见 [`HANDOFF-DSH-PLUGIN-0.2.2.md`](HANDOFF-DSH-PLUGIN-0.2.2.md)。

## 14. 0.2.0 → 0.2.1 增量说明

0.2.1 不改变 bundle schema，仍为 `6.4`，也不改变 Python 分析结果和 DSH 工具契约；变化集中在模块能力页渲染和信息架构。

- 模块页移除顶部“模块能力”概览浮层。
- 模块级信息统一到右侧详情栏。
- 用户交互面移至“模块组成”和“提供接口”之间，并支持 chips 自动换行。
- 类节点“结构关系”改名为“类型关系”，关系行改为两行布局，修复默认宽度下的重叠。
- 模块摘要保留“类型关系 N”计数，不展开模块级全量关系列表。
- “类型层级”和“类型关系”在继承/实现上的重叠当前明确接受，后续调整关系类型或信息密度时再评估。

详细交接见 [`HANDOFF-DSH-PLUGIN-0.2.1.md`](HANDOFF-DSH-PLUGIN-0.2.1.md)。
