# HANDOFF：DSH 插件 dsh-archmap-explorer 0.1.0

> 状态：已交付，已打标签 `dsh-plugin-v0.1.0`<br>
> 交接日期：2026-11-19<br>
> npm 包：`dsh-archmap-explorer@0.1.0`<br>
> Python 核心：ArchMap `2.5.0` / bundle schema `6.4`<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> 许可证：MIT<br>
> 当前权威使用文档：[dsh-plugin.md](dsh-plugin.md)

## 1. 交接摘要

`dsh-archmap-explorer@0.1.0` 已完成从 Python 注解命令到 DSH 工具和 bundled Skill 的完整实现。

当前边界：

```text
Node/DSH 插件负责：
  - DSH 工具 schema 与工具注册
  - workspace 路径限制
  - Python 子进程桥接
  - 宿主模型路由与调用
  - bundled Skill 注册
  - 注解 proposal 的模型输出净化

Python 核心负责：
  - AST 与源码分析
  - 调用解析、图投影、布局与校验
  - annotations context/apply
  - sidecar 合并、sourceHash 权威校验
  - architecture.html 重渲染
```

插件版本与 Python 核心版本相互独立。本次没有修改 bundle schema，也没有改变现有 Python CLI 或 HTML 数据契约。

## 2. 已交付内容

### 2.1 Python 注解命令

```bash
python -m archmap annotations context <bundle> --scope functions --max-nodes 50 --json
python -m archmap annotations apply <bundle> --proposal <json> --provider <id> --model <id> --json
```

实现文件：

- `archmap/annotations.py`
- `archmap/utility/annotation_utility.py`
- `archmap/utility/cli_utility.py`

能力：

- `project` / `modules` / `functions` / `all` 四种 scope
- 显式 `node_ids`
- 最大节点数、单节点源码字符上限
- 输出签名、人工备注、源码摘录、权威 `sourceHash`、已有注解摘要
- proposal 严格校验
- 未知 nodeId、空摘要、过期哈希跳过
- 默认保留已有注解，`force` 才允许覆盖
- 合并写入 `llm-annotations.json`
- 重新渲染 `architecture.html`

### 2.2 npm 包与 DSH bundle

实现文件：

- `package.json`
- `cordis.patch.yml`
- `LICENSE`
- `.npmignore`

关键字段：

```text
name: dsh-archmap-explorer
version: 0.1.0
type: module
dsh.bundle.patch: ./cordis.patch.yml
```

`cordis.patch.yml` 注册 bundle row：

```yaml
- insert:
    - id: tool-archmap
      name: dsh-archmap-explorer
```

### 2.3 Python 子进程桥

实现文件：`lib/python-bridge.js`

能力：

- 通过 `ctx.workingDirectory.ensure()` 获取当前 DSH workspace
- 拒绝 workspace 外部路径和 `../` 越界
- 通过 `PYTHONPATH` 使用 npm 包内 bundled Python 核心
- 透传 `exec.signal`
- 超时与 SIGTERM
- 有界 stdout/stderr 捕获
- 统一错误摘要

### 2.4 `archmap_build`

实现位置：`lib/index.js`

参数：

```text
projectPath
configPath
outDir
```

返回：

- `ok`
- 项目名、语义 fingerprint
- 模块数、函数数、执行流数、call site 数
- error / warning / info 诊断统计
- `architecture.json` / `architecture.html` 绝对路径

### 2.5 `archmap_annotate`

实现位置：`lib/index.js`、`lib/host-llm.js`、`lib/annotations.js`

参数：

```text
projectPath | bundlePath
scope
nodeIds
maxNodes
includeSource
force
```

流程：

```text
projectPath 时先 build
→ python annotations context
→ 按批调用 ctx.llm
→ 严格解析 JSON；首次失败带错误信息修复一次
→ 净化模型节点：nodeId 必须属于当前上下文
→ sourceHash 从 Python context 复制，忽略模型返回值
→ 写 annotation-proposal.json
→ python annotations apply
→ 合并 llm-annotations.json
→ 重渲染 architecture.html
```

模型路由：

```text
1. 插件配置 provider + model
2. 当前会话模型 exec.agent.model.current()
3. 第一个可列出模型的已注册 provider
4. HOST_MODEL_UNAVAILABLE
```

模型调用只经过 DSH `ctx.llm`，使用 `prepareCall()` + `prepared.stream()` + `BlockAssembler`。插件不读取或保存 API Key。

### 2.6 bundled Skill

实现位置：`lib/index.js`

| Skill | 要求 |
|---|---|
| `archmap-config-generation` | 必须存在；缺失或为空导致插件加载失败 |
| `archmap-code-conventions` | 随包安装 |

两份 Skill：

- 名称 kebab-case
- `source: bundled`
- `rank: BUNDLED_SKILL_RANK`
- 模型和用户均可调用
- 正文直接读取包内权威 Markdown

## 3. 当前 Git 与发布状态

实现与收口提交：

```text
615ba93 feat(dsh): deliver dsh-archmap-explorer 0.1.0
d4c63da docs(dsh): document 0.1.0 install and pnpm allowlist
```

发布标签：

```text
dsh-plugin-v0.1.0
```

标签已推送到远端，指向 `d4c63da`。本交接文档后续再提交时，如需同步发布标签内容，需要重新评估是否移动或新增标签。

> 注意：本次交接文档更新只要求本地提交，不要求推送远端。

## 4. 验证基线

最近一次完整验证结果：

```text
python3 -m pytest -q
150 passed, 1 skipped

ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py
1 passed

npm run prepare
prepare: ok

npm test
7 passed, 0 failed

npm pack --dry-run
74 files
package size: 203.8 kB
unpacked size: 920.3 kB
forbidden artifacts: none

python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
5 modules / 297 functions / 4828 call sites
archmap check: OK
```

Node 测试覆盖：

- 插件注册 `archmap_build` 与 `archmap_annotate`
- 两项 Skill 的 list/get
- bundled Python 核心真实构建
- 宿主模型 mock 注解生成
- 模型错误 `sourceHash` 不进入侧车
- 首次非法 JSON 后带 repair 信息修复一次
- workspace 越界拒绝
- 模型路由三级回退
- fenced JSON 解析

### 4.1 真实 Git URL 安装

已使用临时 profile 验证：

```bash
dsh plugin --profile gitcheck add \
  git+https://github.com/MerlinSassoon/dsh-archmap-explorer.git
```

首次安装被 pnpm 的 `ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED` 拦截。按 pnpm 输出中的完整 key 在 profile 的 `pnpm-workspace.yaml` 加入：

```yaml
onlyBuiltDependencies:
  - "dsh-archmap-explorer@git+ssh://git@github.com/MerlinSassoon/dsh-archmap-explorer.git#<resolved-commit>"
```

重试后：

- `prepare: ok`
- bundle 自动加入 profile
- `dsh --dump-config` 能看到 `tool-archmap`
- `dsh --dump-config-schema` 能导入插件和 Config schema
- 包内 bundled Python 核心可运行 `archmap 2.5.0`
- 包内 docs / Skill / lib 文件完整

### 4.2 尚未完成的真实验证

真实 DSH 宿主模型注解未在当前终端完成。headless profile 返回：

```text
MISSING_CREDENTIAL: llm-deepseek: no API key for provider route "deepseek-official"
```

这是运行环境凭证限制，不是插件接口错误。已验证的部分：

- `ctx.llm.prepareCall()` / `prepared.stream()` / `BlockAssembler` 调用形状由 mock 覆盖
- 模型 JSON 修复、节点净化、sourceHash 保护和 Python apply 链路由 Node 测试覆盖
- 真实 DSH Web 会话中配置模型后，应执行一次完整 live smoke：

```text
让模型调用 archmap_annotate
projectPath = tests/fixtures/student_demo
scope = functions
maxNodes = 1
检查 llm-annotations.json 与 architecture.html
```

这是 0.1.0 之后最优先的发布后验证项。

## 5. 关键文件地图

```text
package.json                         npm 包与 DSH bundle 元数据
cordis.patch.yml                     DSH profile 挂载 patch
lib/index.js                         tools + bundled Skills
lib/python-bridge.js                 workspace/Python 子进程桥
lib/host-llm.js                      ctx.llm 路由与模型流
lib/annotations.js                   模型 proposal 净化
scripts/prepare.mjs                  确定性包自检
archmap/annotations.py               公共注解 API facade
archmap/utility/annotation_utility.py
                                     context/apply 核心实现
tests/test_annotations.py            Python 注解测试
tests/node/archmap-plugin.test.mjs   DSH 插件 Node 测试
docs/dsh-plugin.md                   当前使用与维护文档
```

## 6. 维护约束

后续修改必须保持以下不变量：

1. 模型不得改写源码或 `architecture.json`。
2. `sourceHash` 只能由 Python 从 bundle 读取，不能信任模型。
3. 模型 proposal 只接受上下文内 nodeId。
4. 默认保留已有/人工注解，`force` 才能覆盖。
5. 所有工具路径必须限制在 DSH workspace 内。
6. 插件不得持有或读取 API Key。
7. 两份 Skill 必须随包安装；配置 Skill 缺失必须 fail loud。
8. 新增或修改 `lib/*.js` 后必须同步更新 Node 测试和 `prepare` 自检。
9. 修改 bundle 契约时必须同步 schema、Python 测试、渲染测试和当前权威文档。
10. 过程性文档不得反向改写为当前契约。

## 7. 已知风险与后续建议

- **真实宿主模型 smoke 未执行**：需要可访问模型的 DSH 会话中完成一次 live run。
- **孤立 profile 的 peer 警告**：DSH profile 使用 `autoInstallPeers: false`，pnpm 会报告 peer 未安装；DSH 运行时通过安装锚点解析，`dump-config-schema` 已验证可加载。
- **pnpm allowlist key 含 resolved commit**：插件升级后可能需要更新 `onlyBuiltDependencies` key。
- **Node 版本声明**：插件声明 `node >=22`，实际 DSH 0.2.2-rc.1 自身声明 Node >=24.9；以真实宿主运行结果为准。
- **模型批大小**：大项目建议从 `annotationBatchSize=6` 或更小开始，观察 `HOST_MODEL_TRUNCATED` / `HOST_MODEL_INVALID_JSON`。
- **本地测试依赖**：Node 测试需要能解析 `@deepseek-ai/dsh-tools` 等 peer；CI 或干净环境需先安装兼容 DSH 依赖，或通过临时 DSH profile 执行。

## 8. 推荐下一步

1. 在已配置模型的 DSH Web 会话中执行一次真实 `archmap_annotate` smoke。
2. 对真实项目运行 `archmap_build`，检查大型 bundle 的渲染和查询性能。
3. 评估是否把 `archmap_annotate` 的 provider/model 选择暴露到 profile UI。
4. 评估是否需要为注解任务增加重试/成本统计/更细的取消粒度。
5. 若修改发布内容，新增后续标签，例如 `dsh-plugin-v0.1.1`，不要静默移动已发布标签。
