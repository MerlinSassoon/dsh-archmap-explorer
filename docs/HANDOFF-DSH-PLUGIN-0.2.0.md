# HANDOFF：DSH 插件 dsh-archmap-explorer 0.2.0

> 状态：已发布，标签 `dsh-plugin-v0.2.0`；真实宿主模型 live smoke 主链路已通过<br>
> 发布提交：`d0df553`（main）<br>
> 插件版本：`0.2.0`<br>
> Python 核心：ArchMap `2.6.0` / bundle schema `6.4`<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> 上一发布标签：`dsh-plugin-v0.1.0`<br>
> 发布标签：`dsh-plugin-v0.2.0`<br>
> 当前使用文档：[dsh-plugin.md](dsh-plugin.md)

## 1. 本版定位

0.2.0 把插件从“build + annotate”扩展为 AI 可持续依赖的架构反馈工具，重点补齐：

```text
工具闭环
  - 结构化构建诊断
  - check/trace/impact/surfaces/dsm/method 查询
  - Skill fallback

分析可信度
  - cast / 属性链 / Protocol 单实现解析
  - polymorphic warning 分级
  - unresolved callers/trace 提示

使用体验
  - 注解 stale 增量
  - flowScopes 默认可见
  - 构建/注解耗时与产物统计
  - 模块 note 来源
```

bundle schema 仍为 `6.4`。

## 2. 主要交付

### 2.1 工具

- `archmap_build`
  - 结构化 `issues` / `issueSummary` / `nextActions`
  - `durationMs` / `bundleBytes` / `htmlBytes`
  - warning-only 项目继续生成 HTML
- `archmap_annotate`
  - `refreshMode=missing|stale|all`
  - sourceHash stale 增量刷新
  - `durationMs` / `batchDurationsMs`
  - 候选/状态/剩余/truncated 统计
- `archmap_query`
  - `check/trace/impact/surfaces/dsm/method`
  - 查询结果预算与 truncation
  - trace 返回低置信度 `unresolvedReferences`
- `archmap_guide`
  - 无原生 `skill` 工具时读取 bundled 权威 Markdown

### 2.2 分析

- 修复 type hierarchy 重置顺序导致的 `subclass_ids` 丢失。
- 支持 `cast(Type, value)`、属性链、构造/注解注入类型。
- Protocol/ABC 单实现返回候选；多实现保留候选集合。
- `POLYMORPHIC_CALL_CANDIDATES` 改为 warning。
- Provider Role 后缀推断：
  - Store/Repository/Client → adapter
  - Handler/Server/Cli → component
  - Controller/Service/Manager → manager
- `do_*` / `log_*` 默认 internal。
- 方法详情增加 unresolved callers。
- 模块 note 未配置时回退到 docstring，并输出 `noteSource`。

### 2.3 默认行为变化

- `flowScopes.enabled` 默认 `true`；显式 `false` 关闭。
- `autoDetect` 仍默认 `false`。
- 配置无效值/无匹配 override fail loud。
- 未知配置 key 目前为 warning，后续版本可收紧为 error。

## 3. 验证基线

```text
python3 -m pytest -q
163 passed, 1 skipped

ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py
1 passed

npm run prepare
prepare: ok

npm test
11 passed, 0 failed

python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self
5 modules / 308 functions / 4990 call sites

python3 -m archmap check .archmap/self/architecture.json --json
ok: true / issueCount: 0 / errorCount: 0 / warningCount: 0

npm pack --dry-run
76 files / 221.0 kB package
```

flowScopes 默认开启性能对比（学生管理系统）：

```text
durationMs  +4.3%
bundleBytes +9.2%
htmlBytes   +5.0%
```

均低于 20% 门禁。

## 4. 发布后验证

### 4.1 安装与配置验证

真实 Git URL 安装、`--dump-config`、`--dump-config-schema` 和包内 Python 核心版本检查均已完成：

```bash
dsh plugin --profile v020check add git+https://github.com/MerlinSassoon/dsh-archmap-explorer.git
dsh --profile v020check --dump-config
dsh --profile v020check --dump-config-schema
PYTHONPATH=<profile>/node_modules/dsh-archmap-explorer python3 -m archmap --version
```

结果：

- 首次安装被 pnpm `ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED` 拦截；按 pnpm 输出的精确 codeload key 写入 `onlyBuiltDependencies` 后重试成功。
- `prepare: ok`，安装版本 `dsh-archmap-explorer 0.2.0`。
- `--dump-config` 出现 `id: tool-archmap / name: dsh-archmap-explorer`。
- `--dump-config-schema` 包含 `tool-archmap`，`diagnostics: []`。
- 包内 Python 核心版本为 `archmap 2.6.0`。
- 临时 profile `v020check` 已清理。

### 4.2 真实宿主模型 live smoke

2026-11-19 已在 DSH 0.2.2-rc.1 + minimal preset + `deepseek-official / deepseek-flash` 会话中完成真实宿主模型 live smoke。详细记录见：

- [2026-11-19-dsh-archmap-explorer-live-smoke-验证记录.md](2026-11-19-dsh-archmap-explorer-live-smoke-验证记录.md)

主链路验证结果：

```text
archmap_guide  → code-conventions / config-generation / usage 均可读取
archmap_build  → 5 modules / 94 functions / 382 call sites / 3 flows
archmap_query  → check / surfaces / dsm / trace 可调用
archmap_annotate → 真实宿主模型两轮共 100 节点，0 rejected
architecture.html → 注解文本已进入渲染产物
```

最终构建诊断为：

```text
0 error / 0 warning / 1 info
```

注：`100` 个被注解节点是“项目 1 + 模块 5 + 函数 94”，不是 100 个函数。

### 4.3 live smoke 暴露的后续问题

本次验证只关闭“真实宿主模型主链路未验证”这一阻塞项，不代表所有产品边界已验证。实际暴露并需后续处理的事项：

- **CLI 行为回归**：示例项目 11 个 pytest 通过、build/check 0 warning，但 `client list/get/delete` 仍因 `argparse.Namespace` 字段不一致在运行期失败。说明结构检查不能替代 CLI 入口级验收。
- **`dispatchHints` 契约偏差**：过程会话按 warning 建议加入/修正 `dispatchHints` 后，build fingerprint 与 6 条 `POLYMORPHIC_CALL_CANDIDATES` warning 均未变化；最终通过显式实现契约消除 warning。需明确 `dispatchHints` 是 execution-flow 投影配置还是 callSite 解析配置。
- **trace 起点归一化**：`app.main:run_server` 无法作为起点，改用 `fn:app.main.run_server` 后成功。应增加唯一简写归一化或候选提示。
- **execution entrypoint 与 flow 叙事**：为消除 `EXECUTION_ONLY_NOT_IN_FLOW` 将 `main` 加入 `executionEntrypoints` 后，形成 `main()` / `run_server()` / `run_client()` 三条同层 flow，存在叙事重复。
- **注解成本与可信度**：两轮注解共约 110 秒、18 个 batch；评价会话指出注解体量约为 docstring 的 6.3 倍，存在复述和个别语义偏差。
- **能力面与角色质量**：评价会话统计 34 个 API 全部来自 naming 推断；测试替身进入能力面，契约与实现 API 重复；`StudentClientManager` 被低置信度推断为 `adapter`。
- **scope 预算与产物体积**：`run_client` scope 在默认 24 节点预算下截断；约 1,926 行源码对应约 1.6MB JSON / 1.4MB HTML。

本次 live smoke 未覆盖：模型非法 JSON 修复、取消/超时、workspace 越界、`refreshMode=stale`、`archmap_query impact/method`、大项目性能。这些仍由自动化测试或后续专项验收覆盖。

## 5. 发布完成记录

已完成的发布步骤：

1. 全量回归：
   - `python3 -m pytest -q`：163 passed, 1 skipped
   - `ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py`：1 passed
   - `npm run prepare`：ok
   - `npm test`：11 passed
   - 自构建 + `archmap check --json`：0 errors / 0 warnings
   - `npm pack --dry-run`：76 files / 221.0 kB
2. 临时 profile 真实 Git URL 安装验证：
   - 首次安装被 pnpm prepare allowlist 拦截；加入精确 codeload key 后成功
   - `--dump-config` 与 `--dump-config-schema` 通过
   - 包内 Python 核心 `archmap 2.6.0`
3. 已 fast-forward 合入 `main`。
4. 已新增并推送标签 `dsh-plugin-v0.2.0`，指向 `d0df553`。
5. 未移动 `dsh-plugin-v0.1.0`。
6. 临时 profile `v020check` 已清理。

发布后真实 DSH Web 宿主模型 live smoke 已完成；主链路通过，发现的后续问题记录在 live smoke 验证记录中。

## 6. 当前维护状态

- `main` 与 `origin/main` 已同步。
- 已发布标签：`dsh-plugin-v0.2.0`（指向 `d0df553`）。
- 历史发布标签：`dsh-plugin-v0.1.0`。
- 真实 DSH Web 宿主模型 live smoke 已完成，主链路通过。
- 仍需处理 live smoke 与评价会话发现的 CLI 验收、`dispatchHints` 契约、trace 起点归一化、能力面策展和注解可信度问题。
- 不移动已发布的 `dsh-plugin-v0.2.0`；如有修复，新增后续版本和标签。

## 7. 回滚

- 回退到 `dsh-plugin-v0.1.0`。
- 显式 `flowScopes.enabled=false` 可恢复 0.1.0 的默认 scope 行为。
- 注解 sidecar 结构未变化，旧版仍可读取。
- 新增工具为增量能力，不影响旧工具参数。
