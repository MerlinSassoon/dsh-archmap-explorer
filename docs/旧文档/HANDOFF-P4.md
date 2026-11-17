# ArchMap P4 交接文档：结构关系、User Surface、Impact/Trace 与 DSM

> 日期：2026-11-18<br>
> 版本：ArchMap 1.8.0 / bundle schema 3.8<br>
> 开发分支：`p4-impact-trace-surfaces`<br>
> 基线分支：`p3-inheritance-polymorphism`（提交 `40ab924`，未合并到 P2.4）<br>
> 状态：P4 核心能力已完成；P5 未定义。

---

## 0. 分支信息与返回方式

按要求，P4 未等待 P3 合入，直接从 P3 分支切出：

```text
p2.4-main-flow
  └─ p3-inheritance-polymorphism（40ab924）
       └─ p4-impact-trace-surfaces（当前）
```

```bash
# 回到 P3
git switch p3-inheritance-polymorphism

# 回到 P4
git switch p4-impact-trace-surfaces

# 回到 P2.4 基线
git switch p2.4-main-flow
```

分支总表见 [`BRANCHES.md`](BRANCHES.md)。

---

## 1. P4 完成范围

P4 把 ArchMap 从“结构/调用浏览器”推进到“可查询的架构事实层”。

已完成：

- 结构关系：
  - `instantiates`
  - `uses`
  - `aggregates`
  - `composes`
- 关系来源与角色元数据：
  - `source`
  - `fromProviderId` / `toProviderId`
  - `fromProviderRole` / `toProviderRole`
  - `fromVisibility` / `toVisibility`
  - `evidenceFunctionIds`
- User Surface 投影：
  - CLI 输入/输出
  - 文件 IO
  - 网络监听/连接
  - 键盘事件
  - 配置显式覆盖入口
- User Surface 从 entrypoint 可达性传播，保留 evidence 与 confidence。
- 只读查询层：
  - `impact`：两个 bundle 之间的反向影响传播
  - `trace`：静态调用与多态候选的入/出向 trace
  - `surfaces`：用户交互面查询
  - `dsm`：module/provider 依赖结构矩阵
- CLI 新命令与 JSON 输出。
- UI：
  - 项目页/模块契约条展示 user surfaces；
  - 类详情展示结构关系；
  - 方法详情展示 surface 标签；
  - 主流程节点展示 surface 标签；
  - 保留“无类焦点页、无语句级 FunctionFlow”的产品边界。
- Bundle schema 从 3.7 升级到 3.8。
- validator 增加结构关系、surface、surface 投影一致性约束。

---

## 2. 数据契约增量

### 2.1 扩展 typeRelation

`projectGraph.typeRelations` / `moduleGraphs[].typeRelations` 现在支持：

```text
inherits
implements
instantiates
uses
aggregates
composes
```

示例：

```json
{
  "id": "type:cls:app.manager.OrderManager:composes:cls:app.cache.Cache",
  "kind": "composes",
  "fromClassId": "cls:app.manager.OrderManager",
  "toClassId": "cls:app.cache.Cache",
  "fromProviderId": "cls:app.manager.OrderManager",
  "toProviderId": "cls:app.cache.Cache",
  "moduleId": "service",
  "targetModuleId": "domain",
  "confidence": "high",
  "source": "constructor_assignment",
  "fromProviderRole": "manager",
  "toProviderRole": "manager",
  "fromVisibility": "public",
  "toVisibility": "public",
  "evidenceFunctionIds": [
    "fn:app.manager.OrderManager.__init__"
  ],
  "evidence": {
    "file": "app/manager.py",
    "line": 13
  }
}
```

关系语义：

| kind | 含义 | 证据 |
|---|---|---|
| `inherits` | 具体类继承 | 基类表达式 |
| `implements` | 实现抽象类/Protocol | 基类表达式 |
| `instantiates` | 创建实例 | AST 构造调用 |
| `uses` | 类型注解/字段引用 | 参数、返回、字段注解 |
| `aggregates` | 持有外部注入对象 | 构造参数注入、字段注解 |
| `composes` | 创建并拥有对象 | `__init__` 中实例化并赋给 `self.attr` |

### 2.2 User Surface

```json
{
  "id": "surface:cli_input:fn:app.main.run_cli",
  "kind": "cli_input",
  "display": "CLI 输入 · run_cli()",
  "audiences": ["end_user"],
  "moduleId": "main",
  "providerId": "fn:app.main.run_cli",
  "providerRole": "utility",
  "evidenceFunctionIds": ["fn:app.main.run_cli"],
  "propagatedFunctionIds": ["fn:app.main.run_cli"],
  "entrypointIds": ["fn:app.main.main"],
  "confidence": "high",
  "source": "io_primitive"
}
```

当前 surface kind：

```text
cli_input / cli_output / file_io
network_endpoint / network_client
keyboard_event
http_endpoint / tui_menu / ui_component（预留）
```

配置覆盖：

```json
{
  "userSurface": {
    "overrides": [
      {
        "function": "app.menu:MenuSystem.run",
        "kind": "tui_menu",
        "audiences": ["end_user"],
        "confidence": "high",
        "display": "TUI 主菜单"
      }
    ]
  }
}
```

### 2.3 FunctionDetail

新增：

```json
{
  "userSurfaceKinds": ["cli_input", "cli_output"]
}
```

### 2.4 Stats

```json
{
  "typeRelations": 9,
  "structuralRelations": 9,
  "polymorphicCalls": 0,
  "userSurfaces": 2
}
```

---

## 3. 查询层

查询结果**不写入 architecture.json**，避免组合爆炸；由 CLI 按需生成。

### Impact

```bash
python3 -m archmap impact before.json after.json [--json]
```

- 比较 functions / APIs / typeRelations / userSurfaces；
- 从变化种子反向传播；
- 路径包含 caller、reverse structural relation、owner；
- 有 `maxDepth` / `maxNodes` 和 `truncated`。

### Trace

```bash
python3 -m archmap trace architecture.json \
  --from fn:app.main.main \
  --direction outbound \
  --max-depth 8
```

- 默认穿透 internal utility；
- 支持 `--exclude-internal`；
- 多态调用保留 `polymorphic_candidate` 边；
- 输出 bounded paths 和截断标记。

### Surfaces

```bash
python3 -m archmap surfaces architecture.json --module main --json
```

### DSM

```bash
python3 -m archmap dsm architecture.json --level module --json
python3 -m archmap dsm architecture.json --level provider --include-internal --json
```

---

## 4. 代码地图增量

| 文件 | P4 职责 |
|---|---|
| `archmap/frontends/python/relation_utility.py` | `instantiates/uses/aggregates/composes` 提取与来源合并 |
| `archmap/frontends/python/surface_utility.py` | IO/事件 primitive 识别、entrypoint 传播、surface 覆盖 |
| `archmap/frontends/python/call_utility.py` | `self.attr.method()` 类型解析，支撑 P4 trace/impact |
| `archmap/utility/query_utility.py` | impact / trace / DSM 只读查询 |
| `archmap/utility/cli_utility.py` | `impact/trace/surfaces/dsm` CLI |
| `archmap/utility/graph_utility.py` | structuralRelations、userSurfaces、stats、function surface 投影 |
| `archmap/utility/validate_utility.py` | P4 relation / surface 不变量 |
| `archmap/render/assets/app.js/css` | surface chips、结构关系、方法 surface 标签 |
| `tests/test_p4_queries.py` | P4 关系、surface、query、DSM、schema 回归 |
| `tests/fixtures/p4_demo/` | manager/model/repository/cache + CLI surface fixture |

---

## 5. 验收数据

```text
pytest:                    78 passed, 1 skipped
browser smoke:             1 passed（ARCHMAP_RUN_BROWSER=1）
schemaVersion:             3.8
ArchMap 1.8.0
```

### self build

```text
modules:              6
classes:              26
functions:            229
methods:              48
call sites:           3180
resolvedCalls:        516
macroEdges:           225
typeRelations:        45
structuralRelations:  45
userSurfaces:         0
diagnostics:          0
build/check:          OK
```

### student_system

```text
modules:              7
classes:              7
functions:            52
methods:              40
call sites:           265
resolvedCalls:        50
macroEdges:           19
typeRelations:        4
structuralRelations:  4
userSurfaces:         14
diagnostics:          0
build/check:          OK
```

### p4_demo

```text
modules:              3
classes:              6
functions:            6
methods:              4
call sites:           12
typeRelations:        9
structuralRelations:  9
userSurfaces:         2
diagnostics:          0
build/check:          OK
```

### inheritance_demo 回归

```text
typeRelations:        4
polymorphicCalls:     2
diagnostics:          0
build/check:          OK
```

---

## 6. 已知边界

- User Surface 识别是启发式，不等同于产品 UX 分析；primitive 识别覆盖常见 Python 标准库/框架形态。
- `uses/aggregates` 仍然可能因复杂泛型、`typing.Annotated`、字符串注解别名产生噪声，已通过 confidence 和角色元数据控制。
- Trace/Impact 是静态分析 + 多态候选；动态注册、`getattr`、运行时依赖注入仍可能缺失。
- Impact 默认按节点上限截断，必须检查 `truncated`。
- DSM 的 provider 级聚合以 class/function Provider 为粒度，不展开类内方法。
- 仍不新增类焦点页；类只作为 Provider 展示类型层次和结构关系。
- 主流程边界和 P3 多态 composition 规则保持不变。

---

## 7. 后续建议

P4 之后可进入：

1. User Surface 置信度校准与 UI 交互面分组；
2. impact 结果的 HTML 报告与可视化 overlay；
3. ArkTS 前端 surface 映射；
4. 增量扫描与缓存；
5. 组合/聚合关系的进一步类型推断。

任何后续阶段都应继续以 bundle 事实层为唯一输入，不在渲染或查询层重新解析源码。
