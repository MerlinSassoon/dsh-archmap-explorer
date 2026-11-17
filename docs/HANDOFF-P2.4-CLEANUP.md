# ArchMap P2.4 清理分支交接文档

> 日期：2026-11-18<br>
> 版本：ArchMap 1.6.0 / bundle schema 3.6<br>
> 当前分支：`fix/p2.4-ui-migration-finalize`<br>
> P2.4 基线：`p2.4-main-flow` / `008d3c6`<br>
> 状态：P2.4 主流程与 P2.3 最终清理已完成；P3/P4 位于独立分支，尚未合入本分支。

---

## 0. 当前结论

当前分支已经从 P2.4 基线完成了三类收尾工作：

1. **P2.3 迁移彻底完成**
   - 16 个旧 import shim 已删除；
   - 测试、自举配置、CLI console script 已全部切换到新目录；
   - 当前代码中不存在旧模块路径兼容入口。

2. **主流程语义与可读性修复**
   - `with Spinner(...)` / `with Database(...)` 等上下文管理器用法会保留 canonical `context_manager` capability；
   - 主流程 Provider 节点带 `capabilityId`、`capabilityKind`、`protocols`、`usageKind`；
   - 修复同 rank 节点坐标重叠；
   - hover 聚焦不再把非关联 flow edge 降到几乎不可见；
   - 长 label、note、badge 不再溢出节点卡片。

3. **UI 清理**
   - 节点拖拽取消硬编码隐形边界；
   - 移除模块卡片“+”内联展开与 mini 图；
   - 方法详情页背景跟随系统浅色/深色模式。

当前主流程仍然遵循 P1.5/P2.4 边界：它是**函数级调用与模块组合 DAG**，不是语句级执行顺序图。

---

## 1. 分支拓扑

```text
p2.4-main-flow（008d3c6，P2.4 基线）
  ├─ p3-inheritance-polymorphism（40ab924，P3 已完成）
  │    └─ p4-impact-trace-surfaces（c64b928，P4 已完成）
  └─ fix/p2.4-ui-migration-finalize（当前清理分支）
       ├─ 32cc01d fix(p2.4): clean canvas UX and finalize P2.3 migration
       ├─ 12aeb44 feat(flow): preserve context-manager semantics and stabilize layout
       └─ 409d6c7 fix(flow): keep long labels and badges inside node cards
```

说明：

- P3/P4 分支能力**不包含在当前清理分支内**；
- 当前分支可独立构建、测试和验收；
- 后续应将当前分支的三个代码提交 cherry-pick 到 P3/P4，或先将 P2.4 清理分支合入 P3 后再整体向前合并；
- 合入前不要删除 P3/P4 中间分支。

---

## 2. 当前完成状态

```text
P0    类语义数据模型                              已完成
P1    模块页类组件化与模块边界修复                已完成
P1.5  FunctionDetail + Source View + Call Graph   已完成
P2.0  项目页/模块页能力契约重构                   已完成
P2.1  API 契约建模与展示                          已完成
P2.2  Provider Role 与模块组合                    已完成
P2.3  架构规范、自身代码迁移、旧 shim 清理         已完成
P2.4  主模块/功能模块/主流程 DAG                  已完成
P2.4  清理分支 UI / 布局 / 协议能力修复           已完成
P3    继承、接口、多态、继承 API                  独立分支已完成，未合入
P4    结构关系、User Surface、Impact/Trace/DSM    独立分支已完成，未合入
P5    尚未定义
```

当前清理分支不包含 P3/P4 的新增数据契约和查询命令。其权威能力边界仍以本分支的 bundle schema 3.6 为准。

---

## 3. P2.3 最终清理

已删除以下旧文件：

```text
archmap/analysis.py
archmap/callresolver.py
archmap/callsites.py
archmap/cli.py
archmap/config.py
archmap/contracts.py
archmap/details.py
archmap/discover.py
archmap/graph.py
archmap/pipeline.py
archmap/render.py
archmap/validate.py
archmap/frontends/base.py
archmap/frontends/registry.py
archmap/frontends/python/capabilities.py
archmap/frontends/python/roles.py
```

同步变更：

- `archmap/frontends/__init__.py` 不再暴露旧 `FRONTENDS` / `get_frontend` 兼容入口；
- `pyproject.toml` 的 console script 改为：
  ```toml
  archmap = "archmap.entry.cli_entry:main"
  ```
- 测试全部直接使用 `PipelineManager`、`ValidationManager`、`RenderManager`、`GraphManager` 或 canonical utility；
- `examples/archmap_v3.archmap.json` 删除旧 shim 排除项；
- 新增 `tests/test_p2_3_migration.py`，禁止旧路径和旧导入回流；
- 文档不再声称 import shim 仍然存在。

兼容性说明：

- CLI、bundle schema、HTML 产物契约不变；
- 旧 Python import 兼容路径不再支持，这是有意的最终迁移结果。

---

## 4. 主流程协议能力投影

### 4.1 CallSite 新增 usageKind

`CallSite` 新增可选字段：

```json
{
  "kind": "instantiate",
  "usageKind": "context_manager",
  "callText": "Spinner('等待连接中')"
}
```

取值：

```text
call
instantiate
context_manager
async_context_manager
```

识别规则：

- 只标记 AST 中真实的 `with` / `async with` 的最外层 context expression；
- 不能因为类拥有 `__enter__` / `__exit__` 就把所有实例化都标记为上下文管理器；
- 嵌套在 context expression 参数里的普通调用不继承 usageKind。

### 4.2 Provider 边界节点

上下文管理器用法继续使用 `kind=provider`，但节点补充 canonical capability 元数据：

```json
{
  "kind": "provider",
  "providerId": "cls:student_system.managers.spinner_manager.Spinner",
  "capabilityId": "api:cls:student_system.managers.spinner_manager.Spinner:context_manager",
  "capabilityKind": "context_manager",
  "protocols": ["context_manager"],
  "usageKind": "context_manager",
  "label": "with Spinner(message: str='加载中')",
  "flowBoundary": true,
  "expandable": false
}
```

当前策略：

- 每个类 Provider 默认仍只生成一个边界节点；
- 同一类同时存在普通实例化和 `with` 用法时，暂不拆成两个节点；
- 节点保留 protocol badge，具体调用文本写入 flow edge evidence 和 tooltip。

### 4.3 Flow Edge evidence

主流程边 evidence 增加：

```json
{
  "callSiteId": "call:...",
  "callText": "Spinner('等待连接中')",
  "usageKind": "context_manager"
}
```

UI tooltip 会显示：

```text
with Spinner('等待连接中') · high
```

---

## 5. 主流程布局与交互修复

### 5.1 非重叠布局

原布局在 rank 节点数超过 2 时使用：

```python
y = max(FLOW_PAD, start_y + index * FLOW_Y_GAP)
```

会把多个节点压到同一 y 坐标。修复后：

- 每个 rank 在全局最大 rank 高度内居中；
- 同 rank 节点使用固定、不重叠的纵向槽位；
- 使用前驱节点 y 中心进行稳定排序；
- 不再使用会把节点压到同一位置的 clamp。

当前常量：

```text
FLOW_NODE_H      140
FLOW_PROVIDER_H  140
FLOW_DISPATCH_H  140
FLOW_Y_GAP       190
```

### 5.2 Hover 聚焦

- 主流程 `.flow-edge` 不再因 hover/selection 添加 `is-dim`；
- 只高亮与当前节点关联的边；
- 功能模块能力页继续保持原有聚焦行为。

### 5.3 卡片内容约束

- 主流程节点改为纵向 flex 容器，并设置 `overflow: hidden`；
- label 最多 2 行，note 最多 2 行；
- badges 使用 `margin-top: auto` 固定在卡片内部底部；
- 不再用完整 `signature` 作为无备注节点的 note fallback；
- label / note 提供 `title` tooltip 查看完整内容。

---

## 6. 当前验收

```text
pytest:                 71 passed, 1 skipped
浏览器冒烟测试:          1 passed
self build:             6 modules / 172 functions / 2203 call sites
self diagnostics:       0
self check:             OK
student_system:         7 modules / 52 functions / 265 call sites
student diagnostics:    0
student check:          OK
JS syntax check:        OK
compileall:             OK
wheel build:            OK
wheel legacy shims:     无
```

已覆盖的回归点：

- P2.3 shim 不存在且代码不再导入旧路径；
- `with Spinner` / `with Database` usageKind 与 capability 元数据；
- 普通实例化不会被误标为 context manager；
- student_system 主流程节点不重叠、边路径不重复；
- hover Spinner 时全部 flow edge 仍然可见；
- ArchMap 自身长 label `RenderManager.render(...)` 的 label/note/badges 保持在卡片内；
- 方法详情页主题跟随系统；
- 节点拖拽无旧硬编码上限，Fit 可找回负坐标/远距离节点。

---

## 7. 关键代码地图

| 文件 | 职责 |
|---|---|
| `archmap/model/call_model.py` | CallSite `usageKind` |
| `archmap/utility/call_utility.py` | `with` / `async with` AST 识别 |
| `archmap/frontends/python/call_utility.py` | 写入 CallSite usageKind |
| `archmap/utility/detail_utility.py` | caller/callee usageKind |
| `archmap/utility/main_flow_utility.py` | 协议 Provider 元数据、非重叠布局、flow evidence |
| `archmap/render/assets/app.js` | flow badge/label、tooltip、hover 聚焦、卡片内容规则 |
| `archmap/render/assets/app.css` | 卡片 flex/overflow、长文本约束、方法页主题 |
| `archmap/utility/validate_utility.py` | usageKind、Provider capability 校验 |
| `docs/schema/archmap-v3-bundle.schema.json` | 新增可选字段定义 |
| `tests/test_browser_smoke.py` | 长 label、hover、布局和主题浏览器回归 |
| `tests/test_main_flow.py` | 协议能力、节点不重叠、边路径唯一 |
| `tests/test_call_sites.py` | with/普通实例化 usageKind |
| `tests/test_validation.py` | 新增校验规则 |

---

## 8. 已知边界与风险

- 主流程仍是函数级调用/模块组合 DAG，不表达 `if/while/try/with` 内部的逐语句执行顺序。
- 一个类 Provider 仍只生成一个边界节点；同一个类混合普通实例化和上下文管理器用法时，不拆分为多节点。
- 上下文管理器识别只覆盖 AST 中真实的 `with` / `async with` context expression。
- 通过变量持有的上下文管理器不会追溯其构造调用。
- 外部/动态 context manager 只能得到 unresolved 调用事实，不伪造 capability。
- 当前分支不包含 P3/P4 的继承、User Surface、Impact/Trace、DSM 能力。
- 本地保存的旧布局覆盖可能保留旧坐标；查看新默认主流程布局前可点击“重置布局”。
- 旧 Python import 路径已删除；依赖这些路径的外部脚本需要改为 canonical 模块。
- ArkTS 前端仍未实现。

---

## 9. 后续推进

### 9.1 分支整合

1. 将当前三个代码提交 cherry-pick 到 `p3-inheritance-polymorphism`；
2. 验证 P3 继承/多态与新的 flow usageKind、layout、card CSS 不冲突；
3. 再将 P3 合入 P4 分支，验证 P4 的 User Surface、Impact/Trace、DSM；
4. 最后整体合入 P2.4 基线或新主分支。

### 9.2 产品能力

- 若需要真正的执行顺序图，应单独立项，不能在本分支上直接恢复语句级 FunctionFlow。
- 若需要区分同一类的多种协议使用方式，可在后续设计多 usage 节点或 edge-level 展开。
- 继续保留“事实层 → 只读投影 → 渲染”的分层，不在 renderer 中重新解析源码。

---

## 10. 常用命令

```bash
# 全量测试
python3 -m pytest -q

# 浏览器冒烟测试
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py

# 自举构建与校验
python3 -m archmap build . \
  --config examples/archmap_v3.archmap.json \
  --out /tmp/archmap_self
python3 -m archmap check /tmp/archmap_self/architecture.json

# student_system 构建与校验
python3 -m archmap build Projects/student_system \
  --config examples/student_system.archmap.json \
  --out /tmp/student_system
python3 -m archmap check /tmp/student_system/architecture.json

# 查看单个方法
python3 -m archmap method Projects/student_system \
  --file student_system/managers/menu_manager.py \
  --function run
```

---

## 11. 交接阅读顺序

1. 本文
2. `README.md`
3. `docs/README.md`
4. `docs/p2.4-main-module-flow.md`
5. `docs/archmap-v3-design.md`
6. `docs/p2.3-migration-plan.md`
7. `archmap/utility/main_flow_utility.py`
8. `archmap/render/assets/app.js` / `app.css`
9. `tests/test_main_flow.py` / `tests/test_browser_smoke.py`
