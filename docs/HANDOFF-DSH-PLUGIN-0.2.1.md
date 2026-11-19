# HANDOFF：DSH 插件 dsh-archmap-explorer 0.2.1

> 状态：已发布，标签 `dsh-plugin-v0.2.1`<br>
> 插件版本：`0.2.1`<br>
> Python 核心：ArchMap `2.6.1` / bundle schema `6.4`<br>
> 目标 DSH：`0.2.2-rc.1`<br>
> 上一发布标签：`dsh-plugin-v0.2.0`<br>
> 当前使用文档：[dsh-plugin.md](dsh-plugin.md)

## 1. 本版定位

0.2.1 是模块能力页的信息架构收敛版本，不新增工具、不改变 bundle schema，也不改变 Python 静态分析结果。

核心变化：

```text
模块页
  - 移除顶部“模块能力”概览浮层
  - 模块级信息统一到右侧详情栏

右侧模块详情
  - 顺序调整为：模块组成 → 用户交互面 → 提供接口 → 模块注解
  - 用户交互面仅非空时显示，支持 chips 自动换行

类节点详情
  - “结构关系”改名为“类型关系”
  - 类型关系行改为两行布局，修复默认宽度下的字段重叠
```

## 2. 主要交付

### 2.1 模块页布局收敛

- 删除 `#moduleContracts` DOM。
- 删除 `renderModuleContracts()`、`setModuleContractsExpanded()` 和相关状态。
- 清理顶部浮层及抽屉的 CSS。
- 模块页 `fitView` 顶部留白从 122 调整为 64，重新释放画布空间。
- 项目页、模块页、flow 页、方法页不再包含顶部模块能力浮层。

### 2.2 用户交互面位置调整

模块右栏当前顺序：

```text
模块标题 / 备注
→ 模块摘要
→ 模块组成
→ 用户交互面
→ 提供接口
→ 模块注解
```

两个模块详情入口已同步：

- `#/module/<moduleId>`；
- 项目页选中模块节点后的右侧详情。

用户交互面来自 `moduleGraphs[].userSurfaces`，不是 `providedApis` 的一部分。当前只在非空时显示。

### 2.3 类节点类型关系展示

- 标题统一为“类型关系”。
- 每条关系采用两行布局：

```text
OrderManager aggregates → Config
来源：constructor_injection
```

- 类名支持安全换行，完整 canonical ID 保留在 tooltip。
- 默认 420px 详情栏下不再发生关系字段重叠。
- 模块摘要保留“类型关系 N”计数，但不展开模块级全量关系列表。

### 2.4 类型层级与类型关系重叠决策

当前明确接受：

```text
类型层级 = 继承/实现的基类、子类与未解析基类摘要
类型关系 = 当前节点全部带 source 的类型关系明细
```

两者在 `inherits` / `implements` 上存在有意的信息重叠，默认 UI 不去重。后续新增、删除关系类型或调整信息密度时，再评估是否把继承/实现从“类型关系”中分离。

该决策已写入 [archmap-v3-design.md](archmap-v3-design.md)。

## 3. 兼容性

- bundle schema 保持 `6.4`。
- `architecture.json` 字段不变。
- Python 静态分析、调用解析、Provider Role、能力面、执行流均不变。
- DSH 工具参数和返回契约不变。
- 仅有 HTML/CSS/JS 渲染层和 UI 信息架构变化。

## 4. 验证基线

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

python3 -m archmap --version
archmap 2.6.1

npm pack --dry-run
77 files / 223.2 kB package / dsh-archmap-explorer-0.2.1.tgz
```

浏览器冒烟额外覆盖：

- 顶部 `#moduleContracts` 不存在；
- 用户交互面位于“模块组成”和“提供接口”之间；
- 用户交互面容器 `flex-wrap: wrap`；
- 类详情显示“类型关系”；
- 类型关系行没有横向溢出；
- 模块页、flow 页、方法页无残留顶部浮层元素。

临时 profile 本地 link 安装验证：

```text
dsh plugin --profile v021check add link:<repo>
dsh --profile v021check --dump-config
dsh --profile v021check --dump-config-schema
PYTHONPATH=<profile>/node_modules/dsh-archmap-explorer python3 -m archmap --version
```

结果：

- `--dump-config` 出现 `id: tool-archmap / name: dsh-archmap-explorer`；
- `--dump-config-schema` 包含 `tool-archmap` 且 `diagnostics: []`；
- 包内 Python 核心版本为 `archmap 2.6.1`；
- 临时 profile `v021check` 已清理。

## 5. 发布步骤

1. 版本号：
   - `package.json`: `0.2.0` → `0.2.1`
   - `pyproject.toml`: `2.6.0` → `2.6.1`
   - `archmap/__init__.py`: `2.6.0` → `2.6.1`
2. 更新 `README.md`、`docs/dsh-plugin.md` 当前版本与交接链接。
3. 更新 `scripts/prepare.mjs` 的交接文档检查。
4. 更新 `package.json` 的 `files` 列表，包含本交接文档。
5. 全量测试、自构建、`npm pack --dry-run`。
6. 临时 profile 安装验证。
7. 合入 `main`，新增并推送标签 `dsh-plugin-v0.2.1`。
8. 不移动 `dsh-plugin-v0.2.0`。

## 6. 回滚

- 回退到 `dsh-plugin-v0.2.0`。
- bundle schema 未变，旧版仍可读取 0.2.1 产物。
- 回滚仅影响模块页信息架构和类详情关系展示，不影响分析事实或查询结果。
- 如 0.2.1 有回归，新增 `0.2.2` 修复标签，不移动已发布标签。

## 7. 后续待办

本版不处理以下 0.2.0 live smoke 暴露的后续项：

- CLI 入口级行为验收；
- `dispatchHints` 与 callSite polymorphic warning 的契约澄清；
- trace 起点唯一简写归一化；
- 能力面显式策展与测试替身排除；
- Provider Role 低置信度提示；
- 注解结构化与可证伪性；
- 大项目性能和产物体积基线。
