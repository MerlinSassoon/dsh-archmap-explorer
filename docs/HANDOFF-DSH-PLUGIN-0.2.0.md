# HANDOFF：DSH 插件 dsh-archmap-explorer 0.2.0

> 状态：发布候选，尚未创建 0.2.0 标签<br>
> 分支：`feat/plugin-p0-closed-loop`<br>
> 插件版本：`0.2.0`<br>
> Python 核心：ArchMap `2.6.0` / bundle schema `6.4`<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> 上一发布标签：`dsh-plugin-v0.1.0`<br>
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
75 files / 218.3 kB package
```

flowScopes 默认开启性能对比（学生管理系统）：

```text
durationMs  +4.3%
bundleBytes +9.2%
htmlBytes   +5.0%
```

均低于 20% 门禁。

## 4. 尚未完成的发布验证

真实 DSH 宿主模型 live smoke 仍需在已配置模型的会话中执行：

```text
projectPath = 一个 workspace 内的 Python 样例项目
scope = functions
maxNodes = 1
```

重点检查：

- `llm-annotations.json` 的 nodeId/sourceHash 正确。
- `architecture.html` 显示注解。
- 非法 JSON 只修复一次。
- 取消/超时能终止模型流与 Python 子进程。
- `archmap_query trace/impact` 在真实会话中可调用。
- `archmap_guide` 在 minimal preset 下可读取规范。

当前环境的模型调用链仍由 Node mock 覆盖。

## 5. 发布步骤

1. 在真实 DSH 会话完成 live smoke。
2. 全量回归：
   - `python3 -m pytest -q`
   - `ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py`
   - `npm run prepare`
   - `npm test`
   - 自构建 + `archmap check --json`
   - `npm pack --dry-run`
3. 临时 profile 安装验证：
   - link 安装
   - 真实 Git URL 安装
   - `--dump-config`
   - `--dump-config-schema`
4. 合入 `main`。
5. 新增标签 `dsh-plugin-v0.2.0`。
6. 不移动 `dsh-plugin-v0.1.0`。

## 6. 回滚

- 回退到 `dsh-plugin-v0.1.0`。
- 显式 `flowScopes.enabled=false` 可恢复 0.1.0 的默认 scope 行为。
- 注解 sidecar 结构未变化，旧版仍可读取。
- 新增工具为增量能力，不影响旧工具参数。
