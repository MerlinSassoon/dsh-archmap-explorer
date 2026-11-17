# ArchMap P2–P4 交接文档

> 日期：2026-11-16；最后核对：2026-11-17<br>
> 适用版本：ArchMap 1.1.0 / bundle schema 3.1<br>
> 当前阶段：P0、P1、P1.5 已完成；P2、P3、P4 尚未开始。
>
> 本文用于新会话接手项目，包含项目现状、代码地图、数据契约、后续规划、设计来源和风险。文档归档边界见 [`docs/README.md`](README.md)；旧 FunctionFlow 文档不再代表当前契约。

---

## 1. 新会话阅读顺序

建议按以下顺序阅读：

1. 本文 `docs/HANDOFF-P2-P4.md`
2. `docs/README.md` — 当前/历史文档边界
3. `README.md`
4. `docs/function-detail-p1.5-plan.md`
5. `docs/archmap-class-layer-plan.md`
6. `docs/archmap-v3-design.md`
7. `archmap/graph.py` — 三层投影、类节点、模块边界、methodEdges
8. `archmap/callsites.py` — 静态调用事实
9. `archmap/details.py` — FunctionDetail / 源码 / callers / callees
10. `archmap/render/assets/app.js` — 方法详情页与模块页
11. `tests/test_class_layer.py`、`tests/test_call_sites.py`、`tests/test_build.py`

历史文档 `docs/archmap-2.0-design.md`、`docs/HANDOFF.md` 中关于 FunctionFlow 的章节是历史设计，不是当前默认契约。当前产品已明确移除语句级执行流。

---

## 2. 项目一句话

ArchMap 把 Python 项目转换为**模块优先、类为组件、方法为行为、源码为事实来源**的可交互架构浏览器。

产品分工：

```text
架构图 = 结构和关系
源码   = 实现细节
LLM    = 高层语义
```

默认产物：

```text
.archmap/<project>/
├── architecture.json   # ProjectGraph + ModuleGraph + FunctionDetail + CallSite
├── architecture.html   # 自包含单文件 HTML
├── llm-annotations.json（可选）
└── layout-overrides.json（前端导出）
```

---

## 3. 当前项目状态

### 3.1 已完成

- P0：类语义数据模型
- P1：模块页类组件化、模块边界修复
- P1.5：FunctionFlow 移除、FunctionDetail + Source View + Call Graph

### 3.2 当前已实现能力

- Python AST 源码发现、模块归属、类/函数/方法索引；
- 类元数据：
  - `classKind`
  - `isAbstract`
  - `bases`
  - `decorators`
  - `methodKind`
  - `visibility`
- 模块页：
  - 模块输入/输出；
  - 类节点；
  - 模块级自由函数；
  - 类方法不再平铺。
- 类详情面板：
  - 类类型、抽象标记、方法列表；
  - 方法按钮进入 Method Detail。
- 方法详情页：
  - 人类备注、LLM 语义；
  - 签名、返回、异常；
  - 源码切片、行号、调用行高亮；
  - Callers / Callees；
  - 点击调用邻域继续下钻。
- 独立 CallSite 静态调用提取；
- 模块/项目级调用边聚合；
- 自包含 HTML；
- 语义指纹；
- 浏览器冒烟测试。

### 3.3 当前未实现

- 类焦点页；
- 类内方法图；
- 继承/实现的结构化边；
- 多态调用 candidates；
- 组合/聚合关系；
- 类级 impact / trace；
- 类关系矩阵；
- 类层次视图；
- 完整语法高亮（当前源码是纯文本 + 行号 + 调用行高亮）。

### 3.4 当前验收数据

最近一次自举：

```text
project:       archmap_v3
modules:       6（其中 2 个为空模块，见下方说明）
classes:       15
functions:     96
methods:       24
call sites:    987
resolvedCalls: 162
macroEdges:    88
HTML:          ~1.2 MB
JSON:          ~1.6 MB
```

> 注意：`examples/archmap_v3.archmap.json` 仍引用已删除的 `archmap/flow.py` 和 `archmap/layout.py`，因此自举结果中的 `flow-build`、`layout-routing` 是空模块。该配置和对应测试断言需要清理；当前统计不能理解为有 6 个有效源码模块。

`student_system`：

```text
modules:       5
classes:       3
functions:     45
methods:       36
call sites:    266
resolvedCalls: 43
```

类语义验收：

- `MenuSystem`：1 个类节点 + 1 个自由函数节点；
- `MenuSystem` 模块边界：1 进 / 1 出；
- `Spinner`：1 个类节点；
- `Spinner` 模块边界：1 进 / 1 出；
- 抽象类 `Worker`：不接模块边界，`entryMethodIds=[]`。

测试：

```text
pytest: 26 passed, 1 skipped（默认跳过浏览器测试）
ARCHMAP_RUN_BROWSER=1 pytest tests/test_browser_smoke.py: 1 passed
archmap check: OK
```

---

## 4. 当前架构与流水线

```text
config
  → discover_sources
  → analyze_project (AST / classes / functions / imports)
  → collect_call_sites (independent ast.Call extraction)
  → build_function_details (source / callers / callees / sourceHash)
  → build_bundle (ProjectGraph / ModuleGraph / aggregated edges)
  → validate_bundle
  → render_html
```

### 4.1 语言前端

`archmap/frontends/base.py`：

```python
class LanguageFrontend(Protocol):
    def analyze(project_root, config_path=None) -> Any: ...
    def build_call_sites(analysis) -> list[Any]: ...
    def build_function_details(analysis, call_sites) -> list[dict]: ...
```

Python 前端：

```text
archmap/frontends/python/__init__.py
  → analysis.analyze_project
  → callsites.collect_call_sites
  → details.build_function_details
```

ArkTS 未来应实现相同接口，不应修改 HTML 渲染核心。

### 4.2 关键代码地图

| 文件 | 职责 |
|---|---|
| `archmap/config.py` | 配置加载 |
| `archmap/discover.py` | 源码发现、模块归属 |
| `archmap/analysis.py` | AST 索引、类/函数/方法元数据 |
| `archmap/callresolver.py` | 调用目标解析 |
| `archmap/callsites.py` | 独立 CallSite 提取 |
| `archmap/details.py` | FunctionDetail、源码切片、callers/callees |
| `archmap/graph.py` | ProjectGraph、ModuleGraph、类节点、聚合边、指纹 |
| `archmap/validate.py` | bundle 交叉引用与数据校验 |
| `archmap/render.py` | 单文件 HTML 模板注入 |
| `archmap/cli.py` | build / check / method / serve / diff |
| `archmap/render/assets/app.js` | 三层页面、类详情、方法详情 |
| `archmap/render/assets/app.css` | 页面样式 |
| `archmap/frontends/` | 语言前端抽象 |

已删除：

- `archmap/flow.py`
- `archmap/layout.py`

不要重新引入语句级 FunctionFlow 作为主视图。

---

## 5. 当前数据契约

Bundle 顶层：

```json
{
  "schemaVersion": "3.1",
  "kind": "archmap.bundle",
  "project": {},
  "entrypoints": [],
  "projectGraph": {},
  "moduleGraphs": [],
  "functionDetails": [],
  "callSites": [],
  "diagnostics": [],
  "stats": {}
}
```

### 5.1 Class 节点

`moduleGraphs[].nodes` 中 `kind: "class"`：

```json
{
  "id": "cls:menu_system.MenuSystem",
  "kind": "class",
  "name": "MenuSystem",
  "qualifiedName": "menu_system.MenuSystem",
  "classKind": "service",
  "isAbstract": false,
  "bases": [],
  "decorators": [],
  "methodCount": 18,
  "publicMethodIds": [],
  "entryMethodIds": [],
  "exitMethodIds": [],
  "methods": []
}
```

方法摘要包含：

- `id`
- `name`
- `qualifiedName`
- `ownerClassId`
- `methodKind`
- `visibility`
- `isAbstract`
- `signature`
- `note`
- `file` / `line` / `endLine`
- `functionDetailId`

### 5.2 FunctionDetail

```json
{
  "id": "fn:menu_system.MenuSystem.run",
  "ownerClassId": "cls:menu_system.MenuSystem",
  "methodKind": "public_api",
  "visibility": "public",
  "signature": "def run(self)",
  "returns": "",
  "raises": [],
  "note": "",
  "source": {
    "text": "...",
    "startLine": 334,
    "endLine": 360,
    "truncated": false,
    "language": "python"
  },
  "sourceHash": "sha256:...",
  "callers": [],
  "callees": [],
  "callerCount": 0,
  "calleeCount": 3
}
```

### 5.3 CallSite

```json
{
  "id": "call:fn:...:line:column:ordinal",
  "fromFunctionId": "fn:...",
  "toFunctionId": "fn:...",
  "file": "menu_system.py",
  "line": 340,
  "column": 9,
  "calleeText": "self.print_menu",
  "callText": "self.print_menu()",
  "kind": "call",
  "resolved": true,
  "external": false,
  "recursive": false,
  "confidence": "high",
  "candidates": [],
  "argumentCount": 0
}
```

### 5.4 边

- `moduleGraphs[].edges`：类/自由函数组件级聚合边；
- `moduleGraphs[].methodEdges`：方法级调用边；
- `projectGraph.edges`：模块级聚合边；
- 当前 `primaryType`：`call` / `data` / `control`。

P3/P4 需要增加结构关系类型：`inherits`、`implements`、`composes`、`aggregates` 等。不要把它们伪装成 `call`。

---

## 6. 项目约束

新会话必须继续遵守：

1. 工作区根目录是当前项目根目录。
2. 不注册插件，不实现插件清单，不实现 `lib/dsh-plugin.js`。
3. Python 运行时只用标准库。
4. HTML 必须自包含：无 CDN、外部字体、外部图片、网络请求。
5. 不恢复语句级 FunctionFlow 作为主视图。
6. 类不是执行流节点；类本身没有 ENTRY/EXIT。
7. 抽象类/接口不接模块输入输出。
8. 源码是方法实现的最终事实来源；LLM 注解是侧车，不写回源码。
9. 布局覆盖只影响项目页/模块页（类页命名空间在 P2 增加），不影响语义指纹。

---

## 7. P2：类焦点页与类内方法图

### 7.1 目标

把当前“类详情面板 + 方法列表”升级为独立类视图：

```text
项目页
  └─ 模块页
       └─ 类焦点页
            └─ 方法详情页
```

类焦点页展示：

- 类信息：`classKind`、`isAbstract`、bases、方法数；
- 公开 API 方法；
- 生命周期方法；
- 内部方法；
- 方法间调用/数据关系；
- 点击方法进入 Method Detail；
- 类内方法图默认只展示类内边，跨类边作为“外部依赖”列表或二级入口。

### 7.2 设计来源

- Sourcetrail：类节点可展开成员，聚焦当前符号的邻域；
- CodeViz AI：类节点 + 方法 membership 边 + ELK 层级布局；
- cgviz：统一节点/边、focus mode、视图过滤；
- codeglass：`Symbol.parent`、`TypeHierarchyResult` 的类/方法组织结构。

### 7.3 建议路由

```text
#/project
#/module/:moduleId
#/module/:moduleId/class/:classId
#/module/:moduleId/class/:classId/function/:methodId
#/module/:moduleId/function/:functionId
```

旧函数路由继续兼容到 Method Detail。

### 7.4 数据方案

优先从现有数据派生，不新增第二套事实源：

- 方法节点来自 `classNode.methods`；
- 方法级边来自 `moduleGraphs[].methodEdges`；
- 方法详情来自 `functionDetails`；
- 类内布局由 Python 生成，建议新增 `classViews[]` 或 `classGraphs[]` 投影，但必须标记为 ModuleGraph 的投影。

建议 `classView` 结构：

```json
{
  "classId": "cls:menu_system.MenuSystem",
  "moduleId": "menu",
  "nodes": [],
  "edges": [],
  "layout": {}
}
```

### 7.5 实施任务

1. 生成类焦点投影（classView）。
2. 复用或抽取 `graph.py` 的宏观布局算法为类内方法布局。
3. 增加类焦点 Hash 路由。
4. 模块页类节点双击/按钮进入类焦点页。
5. 类页方法节点双击进入 Method Detail。
6. 类页右侧详情显示类备注、继承、公开 API。
7. 布局覆盖增加 `classes` 命名空间。
8. 浏览器测试覆盖类页和方法跳转。

### 7.6 验收标准

- `MenuSystem` 类页出现 18 个方法节点；
- `Spinner` 类页出现 4 个方法节点；
- 方法间 `methodEdges` 正确显示；
- 点击方法进入 Method Detail；
- 类页不出现语句级执行流；
- 旧函数路由不回归。

### 7.7 风险

- 18 个方法的类页需要可读的布局；
- 跨类调用在类页中如何表达需要明确：内部边 vs 外部依赖列表；
- 类页布局覆盖不能污染模块页坐标。

---

## 8. P3：继承、接口、多态与类层次

### 8.1 目标

在 P2 类页基础上增加“类型/契约”语义：

- `inherits`：类 → 基类；
- `implements`：类 → 接口/Protocol；
- 抽象方法契约；
- 多态调用 candidates；
- 类型层次视图；
- 继承/实现关系与调用/依赖关系分视图展示。

### 8.2 设计来源

- CortexPlexus：`get_class_hierarchy` 方向性继承/实现遍历，`get_implementations`，避免兄弟节点污染；
- codeglass：`TypeHierarchyResult` 含 `bases`、`subclasses`、`is_abstract`；
- Emerge：inheritance graph 与 dependency graph 分开；
- Sourcetrail / Understand：UML/类型层级视图与调用图分开；
- Python 语义：`abc.ABC`、`ABCMeta`、`typing.Protocol`、`@abstractmethod`。

### 8.3 数据模型

Class 节点增加或完善：

```json
{
  "bases": ["ABC"],
  "baseClassIds": [],
  "subclassIds": [],
  "implementsIds": [],
  "abstractMethodIds": []
}
```

结构边：

```json
{
  "from": "cls:...",
  "to": "cls:...",
  "kind": "inherits",
  "confidence": "high",
  "evidence": {"file": "...", "line": 12}
}
```

多态调用：

```json
{
  "resolved": false,
  "polymorphic": true,
  "candidates": ["fn:repo.StudentRepository.load", "fn:repo.TeacherRepository.load"],
  "confidence": "medium"
}
```

### 8.4 实施任务

1. 解析类引用和导入，把 `bases` 字符串解析为 `baseClassIds`。
2. 增加全局类索引和 base/subclass 双向关系。
3. 增加 `inherits` / `implements` 结构边。
4. 类型层次视图或类页关系区块。
5. 多态调用解析：
   - `self.abstract_method()`；
   - `cls.method()`；
   - 已知类型注解的变量；
   - 没有唯一实现时返回 candidates。
6. 抽象方法不生成执行流；具体模板方法仍可生成 FunctionDetail。
7. 继承来的方法调用解析（当前 `EchoWorker.run -> self.label()` 仍是 unresolved）。

### 8.5 验收标准

- `class_demo` 中 `EchoWorker` 继承 `Worker`，产生 `inherits` 边；
- `Worker` 抽象方法列表正确；
- 抽象类不接模块边界；
- 调用抽象方法时产生 candidates，而不是伪造唯一目标；
- 类层次视图不出现兄弟节点污染；
- 不影响 ModuleGraph 和 Method Detail。

### 8.6 风险

- Python 动态类型导致多态解析天然不确定；
- 继承/接口关系不能硬塞进现有 `call/data/control` 三种边；
- 导入路径解析仍是限制，当前 `from service import ...` 和 `app.service` 的差异会造成 unresolved。

---

## 9. P4：类关系、影响分析与架构查询

### 9.1 目标

从“类结构浏览器”升级为“可查询的架构知识图”：

- `composes`：强所有权；
- `aggregates`：弱引用/可选引用；
- `uses`：类型引用/字段访问；
- `instantiates`：构造调用；
- 类级 impact analysis；
- 调用路径 trace；
- 类关系矩阵/DSM 视图；
- 项目级依赖视图切换。

### 9.2 设计来源

- CodeScope 资料中提到的 `COMPOSES` / `AGGREGATES` / `INHERITS` 方向值得借鉴；但公开 PyPI `codescope` 实际主要是 Adonis/Scope 调用图，本次未确认其完整关系 API，因此应把组合/聚合视为我们自己的 UML 扩展，而不是已验证实现事实。
- UML 类图：组合、聚合、继承、依赖。
- Structure101 / Lattix：DSM/依赖矩阵，避免“边界到所有节点”的启发式污染。
- cgviz：impact analysis、trace path、view modes。
- CortexPlexus：`get_dependencies`、`get_impact_analysis`、DI/实体关系。
- Emerge：dependency graph、inheritance graph、complete graph 分视图。

### 9.3 数据模型

结构关系：

```json
{
  "kind": "composes",
  "from": "cls:OrderService",
  "to": "cls:OrderRepository",
  "confidence": "medium",
  "evidence": {"file": "services.py", "line": 42}
}
```

候选提取依据：

- `__init__` 中的 `self.repo = Repo(...)` → `composes`；
- 类型注解 `repo: Repo` + 非 Optional → `composes`；
- `repo: Repo | None` / `Optional[Repo]` → `aggregates`；
- 参数/局部变量类型 → `uses`；
- `Repo()` → `instantiates`。

### 9.4 查询能力

建议提供按需查询而不是全量展开：

- `class_dependencies(classId)`；
- `class_impact(classId, depth)`；
- `trace_calls(fromId, toId, depth)`；
- `type_hierarchy(classId, direction)`；
- `implementations(interfaceId)`。

这些可以只作为 bundle 数据和 CLI/前端视图，不需要引入图数据库。

### 9.5 可视化方向

- 类页关系区块：继承/实现/组合/聚合；
- 模块页视图切换：调用关系 / 类型关系 / 全部关系；
- 项目级 DSM 或依赖矩阵；
- 边点击显示证据列表；
- impact 视图高亮反向依赖闭包。

### 9.6 验收标准

- `OrderService -> OrderRepository` 类型注解产生 `composes` 或 `aggregates`；
- 可选类型产生 `aggregates`；
- 构造调用产生 `instantiates`；
- `impact` 从任一方法/类返回反向依赖闭包与深度；
- 结构关系与调用关系可分开筛选；
- 不伪造无源码证据的边。

### 9.7 风险

- 动态类型和运行时装配合降低静态关系可信度；
- 组合/聚合与普通依赖边界模糊，需要置信度和证据；
- 数据/边规模增长会放大 HTML 体积；
- 不能为了追求“全图”破坏已确立的按需下钻体验。

---

## 10. 设计来源与置信度

| 来源 | 可借鉴内容 | 置信度/备注 |
|---|---|---|
| Sourcetrail | 类节点可展开成员、聚焦邻域、边 bundle、源码浏览 | 高；已归档，但文档和源码可查 |
| CodeViz AI | 类节点 + 方法 membership、ELK 层级布局、collapse | 高；实际检查过 parser/layout |
| cgviz | 统一 node/edge kind、focus、view modes、impact/trace | 高；实际检查过 README 和 DB 模型 |
| codeglass (PyPI) | `Symbol.parent`、`TypeHierarchyResult`、`is_abstract` | 高；实际下载检查过包源码 |
| CortexPlexus | `get_class_hierarchy`、`get_implementations`、impact | 中高；README 明确列出工具 |
| Emerge | dependency / inheritance / complete graph 分离 | 高；README 明确列出 |
| Understand | 多图分离、Butterfly、CFG/类图/UML | 中；商业工具，未做源码验证 |
| Structure101 / Lattix | DSM 思想、显式依赖矩阵 | 中；商业工具，方向性参考 |
| CodeScope `COMPOSES/AGGREGATES/INHERITS` | 组合/聚合/继承分类 | 低；公开 PyPI `codescope` 未确认该完整 API |

原则：**不要因为某个名称听起来合理就直接实现；先验证它是否真实、是否适合当前架构。**

---

## 11. 当前已知问题

1. 静态调用解析仍不完整：
   - 动态 `getattr`；
   - `**kwargs` 分发；
   - 运行时注册表；
   - 继承来的方法调用；
   - 跨包导入路径差异。
2. 抽象/接口检测是基础 AST 规则，不是完整 Python 类型系统。
3. `ClassInfo.bases` 仍是原始字符串，没有解析为类 ID。
4. 方法详情源码目前纯文本展示，没有完整语法高亮。
5. 单函数源码有 24000 字符上限，超长会 truncated。
6. 方法详情页没有“调用路径搜索”，目前只有 callers/callees 列表。
7. 类焦点页尚未实现，类方法目前从类详情面板进入。
8. 旧 schema 3.0 bundle 不再通过 `archmap check`。
9. 旧 FunctionFlow 注解的 `sourceHash` 会过期，需要重新生成。
10. 旧函数级布局覆盖 `override.functions` 不再生效。
11. `config.py` 中部分旧 `maxSteps` / `maxDataDeps` 配置已失去主要用途，后续可清理。
12. 浏览器测试默认跳过，只有当 `ARCHMAP_RUN_BROWSER=1` 时执行。
13. `examples/archmap_v3.archmap.json` 仍包含已删除的 `flow.py` / `layout.py` 模块配置，导致自举出现 `flow-build`、`layout-routing` 两个空模块；测试 `test_archmap_v3_self_config_builds_cross_module_edges` 也仍断言 6 个模块，需要同步清理。
14. 旧 `docs/archmap-2.0-design.md`、`docs/HANDOFF.md`、`docs/v1-acceptance-report.md` 已加归档说明；维护时不要把其中的 FunctionFlow 设计重新写回当前契约。

---

## 12. 常用命令

```bash
# 全量测试
python3 -m pytest -q

# 浏览器测试
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py

# 构建（注意：自举配置当前仍有两个空模块，待清理）
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out .archmap/self

# 校验
python3 -m archmap check .archmap/self/architecture.json

# 查看单个方法
python3 -m archmap method . --file archmap/graph.py --function build_bundle

# 本地预览
python3 -m archmap serve .archmap/self
```

---

## 13. 新会话建议开工顺序

1. 先跑全量测试和浏览器测试，确认当前基线。
2. 清理 `examples/archmap_v3.archmap.json` 的两个空模块配置，并同步修正自举测试断言。
3. 阅读 `graph.py` 中类节点/`methodEdges` 生成逻辑。
4. 阅读 `app.js` 中 `renderModuleClassNode`、`renderSelectionDetail`、`renderMethodPage`。
5. 先实现 P2 的 classView 数据投影，不要先动 UI。
6. 用 `class_demo` 和 `student_system` 验证类页数据和布局。
7. P2 验收后，再做 P3 的类型层次和 candidates。
8. P4 最后做组合/聚合、impact/trace 和 DSM。

不要同时开始 P2、P3、P4。
不要重新引入 FunctionFlow。
不要为了类页一次性重写现有 Macro Layout；先复用和投影。
