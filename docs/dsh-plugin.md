# DSH 插件：dsh-archmap-explorer

> npm 包：`dsh-archmap-explorer`<br>
> 插件版本：`0.1.0`<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> Python 核心：随 npm 包分发，要求 Python 3.10+<br>
> 许可证：MIT

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

### 2.1 从 GitHub 仓库安装

```bash
dsh plugin --profile web add git+https://github.com/MerlinSassoon/dsh-archmap-explorer.git
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

### 2.2 pnpm 拦截 prepare

pnpm 可能拦截 npm 包的 `prepare` 脚本。该脚本只做确定性自检，不联网、不跑完整测试、不生成用户项目文件、不启动浏览器。

如果安装输出提示 `dsh-archmap-explorer` 的构建脚本被拦截，按 pnpm 给出的精确提示处理：在目标 profile 的 `pnpm-workspace.yaml` 中加入对应的 `allowBuilds` 条目，然后重新执行安装。

profile 目录通常为：

```text
$DSH_HOME/profiles/<profile>/
```

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
- `architecture.json` 与 `architecture.html` 绝对路径

构建内部校验失败时返回 `ok: false` 和明确错误信息，不伪造成功产物。

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
| `force` | 否 | 是否覆盖已有/人工注解，默认 `false` |

处理流程：

```text
projectPath 时先 build
→ python -m archmap annotations context
→ 过滤已有注解（非 force）
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
- 批次数量
- `annotation-proposal.json` 之外的正式侧车路径与 HTML 路径

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
| pnpm prepare 被拦截 | 按 pnpm 提示在 profile `pnpm-workspace.yaml` 加 `allowBuilds` 后重试 |
| Python 不可用 | 安装 Python 3.10+，或设置 `pythonPath` / `ARCHMAP_PYTHON` |

## 10. 验收命令

```bash
python3 -m pytest -q
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py

npm run prepare
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
