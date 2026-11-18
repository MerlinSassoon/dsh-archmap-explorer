# HANDOFF：DSH 插件 dsh-archmap-explorer

> 状态：设计已确认，尚未开始插件实现<br>
> 交接日期：2026-11-19<br>
> 目标 DSH 版本：`0.2.2-rc.1`<br>
> npm 包名：`dsh-archmap-explorer`<br>
> 插件版本：`0.1.0`（与 ArchMap Python 核心版本独立）<br>
> 许可证：MIT<br>
> 安装方式：仓库地址安装

## 1. 产品目标

在保留现有 Python CLI + 自包含 HTML 交付方式的同时，把 ArchMap 扩展为 DSH bundle 插件：

```text
DSH 插件（Node ESM，薄桥接层）
  ├─ archmap_build       生成 architecture.json / architecture.html
  ├─ archmap_annotate    用 DSH 宿主模型生成 LLM 语义注解
  ├─ archmap-config-generation  必须随包安装的配置技能
  └─ archmap-code-conventions   源码编程约定技能
```

插件只负责 DSH 适配、宿主模型调用和 Python 子进程桥接。AST、调用解析、图投影、校验、布局、HTML 渲染和注解合法性仍由 Python 核心负责。

安装目标：

```bash
dsh plugin --profile web add git+https://github.com/MerlinSassoon/dsh-archmap-explorer.git
```

## 2. 已确认决策

```text
npm 包名：dsh-archmap-explorer
初始版本：0.1.0
许可证：MIT
分发方式：仓库根 package.json + DSH bundle patch
Python 分发：ArchMap Python 核心随 npm 包一起分发，不要求用户先 pip install
DSH 宿主模型：ctx.llm
模型路由：配置 provider/model → 当前会话模型 → 第一个可用模型
第一批工具：archmap_build、archmap_annotate
第一批 SKILL：archmap-config-generation、archmap-code-conventions
```

`archmap-config-generation` 是必须安装项，缺失时插件初始化或 prepare 必须失败。两份 SKILL 直接读取仓库当前权威 Markdown，不在插件内维护第二份正文，避免文档漂移。

## 3. 包结构

计划在仓库根目录增加：

```text
package.json
cordis.patch.yml
LICENSE
lib/
├─ index.js
├─ host-llm.js
├─ python-bridge.js
└─ annotations.js
scripts/
└─ prepare.mjs
```

`package.json` 关键字段：

```json
{
  "name": "dsh-archmap-explorer",
  "version": "0.1.0",
  "type": "module",
  "main": "lib/index.js",
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  },
  "engines": {
    "node": ">=22",
    "dsh": "^0.2.2-rc.1"
  },
  "peerDependencies": {
    "@deepseek-ai/cordis": "^4.1.0",
    "@deepseek-ai/dsh-skill": "^0.2.2-rc.1",
    "@deepseek-ai/dsh-tools": "^0.2.2-rc.1",
    "@deepseek-ai/dsh-llm": "^0.2.2-rc.1",
    "@deepseek-ai/schemastery": "^3.19.0"
  }
}
```

`files` 必须包含：

```text
lib
scripts
archmap
docs/archmap-config-generation.md
docs/archmap-code-conventions.md
docs/archmap-v3-design.md
docs/archmap-architecture-spec.md
docs/archmap-api-contract-model.md
docs/schema/archmap-v6.4-bundle.schema.json
pyproject.toml
cordis.patch.yml
README.md
LICENSE
```

不得把 `yield/`、`.archmap/`、`Projects/`、测试缓存或浏览器测试产物打入 npm 包。

`cordis.patch.yml`：

```yaml
- insert:
    - id: tool-archmap
      name: dsh-archmap-explorer
```

## 4. Python 侧待实现能力

新增两个注解命令：

```bash
python -m archmap annotations context <bundle> --scope functions --max-nodes 50 --json
python -m archmap annotations apply <bundle> --proposal <json> --provider <id> --model <id> --json
```

### `annotations context`

从 schema 6.4 bundle 的 `functionDetails`、`moduleGraphs` 和 `projectGraph` 生成有界上下文：

- 支持 `project` / `modules` / `functions` / `all`；
- 支持 nodeIds、最大节点数、单节点源码字符上限；
- 输出 nodeId、签名、人工备注、源码摘录、准确 sourceHash、已有注解摘要；
- 输出 annotation system prompt 和 promptVersion；
- 不调用 LLM。

### `annotations apply`

- 严格校验 proposal；
- 只接受上下文中存在的 nodeId；
- sourceHash 必须由 Python 从 bundle 读入，不能信任模型返回；
- 默认保留已有注解，`force` 才允许覆盖；
- 合并写入 `llm-annotations.json`；
- 重新渲染 `architecture.html`；
- 返回 applied / skipped / 原因统计。

## 5. DSH 工具

### `archmap_build`

- 参数：projectPath、configPath、outDir；
- 调用 Python `archmap build`；
- 返回模块数、函数数、执行流数、诊断统计、JSON/HTML 路径；
- 构建内部校验失败时返回明确错误。

### `archmap_annotate`

- 参数：projectPath 或 bundlePath、scope、nodeIds、maxNodes、includeSource、force；
- 必要时先 build；
- 调用 annotations context；
- 按批次通过 `ctx.llm.prepareCall()` + `prepared.stream()` 调用宿主模型；
- 使用 `BlockAssembler` 聚合文本；
- 严格解析 `{"nodes":[...]}`；
- 首次解析失败可带错误信息修复一次；
- 调用 annotations apply 写 sidecar 并重渲染 HTML。

第一版不增加 `archmap_check`、`archmap_query`、`archmap_method`、`archmap_impact`、`archmap_trace` 等工具。现有 CLI 仍可直接使用，避免 DSH 工具 schema 膨胀。

## 6. 宿主模型约束

- 不直接持有或读取 API Key；
- 不直接请求 DeepSeek/OpenAI HTTP API；
- 必须通过 DSH `ctx.llm`；
- 路由顺序：

```text
1. 插件配置 provider + model
2. 当前 DSH 会话模型 exec.agent.model.current()
3. 第一个已注册且可列出模型的 provider
4. HOST_MODEL_UNAVAILABLE
```

- 必须透传 `exec.signal`；
- 必须支持取消、超时和批次上限；
- 模型输出不得改写源码或 bundle；
- sourceHash 必须使用 bundle 中的原值。

## 7. SKILL 安装与命名

DSH skill 名称必须为 kebab-case：

| Skill | 来源文档 | 要求 |
|---|---|---|
| `archmap-config-generation` | `docs/archmap-config-generation.md` | 必须安装，模型/用户均可调用 |
| `archmap-code-conventions` | `docs/archmap-code-conventions.md` | 随包安装，模型/用户均可调用 |

实现方式：

- 插件 `inject = ['tools', 'skills', 'llm']`；
- 使用 `ctx.skills.registerProvider()` 注册 bundled provider；
- 正文直接读取包内当前权威 Markdown；
- 使用 `BUNDLED_SKILL_RANK`；
- `prepare` 校验两份文件存在且非空；
- 配置技能缺失必须导致插件加载失败。

## 8. `prepare` 脚本

只做确定性自检：

1. package.json 合法；
2. `dsh.bundle.patch` 指向存在文件；
3. `lib/*.js` 语法检查；
4. `archmap/__main__.py`、`pyproject.toml` 存在；
5. 两份 SKILL Markdown 存在且非空；
6. 可选检查 Python 版本。

不得联网、跑完整 pytest、生成用户项目文件或启动浏览器。

pnpm 11 可能拦截 prepare，需要用户在 DSH 插件页允许构建脚本后重试。安装文档必须写明此流程。

## 9. 文档更新要求

- 根 README 增加 DSH 插件安装与使用说明，但不得把未实现能力写成已交付。
- 新增 `docs/dsh-plugin.md`，说明插件架构、配置、工具、SKILL、模型路由、错误与兼容性。
- 更新当前权威文档和所有指向两份 SKILL 的链接。
- MIT LICENSE 使用标准文本，版权行待确认。
- 归档文档只在需要保证链接可解析时更新路径。

## 10. 实施顺序

```text
1. Python annotations context/apply
2. Python 单元测试
3. package.json / cordis.patch.yml / LICENSE
4. Node Python bridge / prepare
5. archmap_build
6. archmap_annotate + ctx.llm
7. 注册两个 bundled SKILL
8. README / docs/dsh-plugin.md
9. npm pack + 临时 DSH profile 安装
10. 真实 Git URL 安装
11. 0.1.0 发布收口
```

## 11. 验收门槛

```text
python -m pytest -q
ARCHMAP_RUN_BROWSER=1 python -m pytest -q tests/test_browser_smoke.py
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
python3 -m archmap check .archmap/self/architecture.json
npm run prepare
npm pack --dry-run
```

额外验收：

- 临时 profile 通过 `dsh plugin add link:<path>` 安装；
- `dsh --profile <test> --dump-config` 能看到 bundle 与 plugin row；
- `ctx.skills.list()` 能看到两个 SKILL；
- `ctx.skills.get('archmap-config-generation')` 返回完整配置指南；
- 宿主模型可对样例项目生成注解；
- HTML 占位块变为已加载；
- Git URL 安装验证通过；
- 0.1.0 打标签 `dsh-plugin-v0.1.0`。

## 12. 历史参考与风险

- `v1.5` 分支存在早期 DSH 插件原型（`plugin/lib/dsh-plugin.js`、`host-llm.js`、`assets/archmap.md`）。
- 该原型可参考 `ctx.llm.prepareCall()`、`BlockAssembler`、严格 JSON 解析和 skill provider 模式。
- 不可直接复用其 `functionFlows`、旧 CLI 命令和旧 schema 逻辑。
- 必须验证当前 DSH `exec.agent.model.current()` 是否可用，并保留 provider/model 配置回退。
- 当前 Node 为 22.23.2，DSH 自身包声明 Node >=24.9；插件声明 `node >=22`，以实际宿主运行验证为准。
- 插件宿主代码在 workspace sandbox 之外运行，所有项目路径必须限制在 DSH workspace 内。
