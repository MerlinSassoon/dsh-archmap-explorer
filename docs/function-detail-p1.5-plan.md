# P1.5：FunctionDetail + Source View + Call Graph

> 状态：已实现（P1.5）<br>
> 日期：2026-11-16；最后核对：2026-11-17<br>
> 目标：移除语句级 FunctionFlow 主产品路径，把方法详情、源码阅读和调用关系升级为架构浏览器核心。
>
> 后续状态：P2.0 项目页/模块页能力契约、P2.1 API 契约建模已完成；P2.2 Provider Role 与 P2.3 ArchMap 自身分层重构已批准但未开始；类焦点页不再计划；P3/P4 尚未开始。当前交接与实施顺序见 [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md)。

## 1. 决策

ArchMap 的产品分工冻结为：

```text
架构图 = 结构和关系
源码   = 实现细节
LLM    = 高层语义
```

因此：

- 默认 bundle 不再包含 `functionFlows`；
- 默认 HTML 不再渲染 ENTRY/EXIT、语句节点、CFG 布局或流程拖拽；
- 方法详情页取代函数执行流页；
- 函数/方法之间的调用关系由独立 CallSite 提取，不再依赖执行流节点；
- 项目页、模块页和类节点继续保留。

## 2. 新数据契约

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

### FunctionDetail

```json
{
  "id": "fn:menu_system.MenuSystem.run",
  "name": "run",
  "qualifiedName": "menu_system.MenuSystem.run",
  "module": "menu_system",
  "moduleId": "menu",
  "ownerClassId": "cls:menu_system.MenuSystem",
  "methodKind": "public_api",
  "visibility": "public",
  "isAbstract": false,
  "isAsync": false,
  "file": "menu_system.py",
  "line": 334,
  "endLine": 360,
  "signature": "def run(self)",
  "returns": "",
  "raises": [],
  "note": "",
  "source": {
    "text": "def run(self): ...",
    "startLine": 334,
    "endLine": 360,
    "truncated": false,
    "language": "python"
  },
  "sourceHash": "sha256:...",
  "callers": [],
  "callees": [],
  "callerCount": 0,
  "calleeCount": 18
}
```

### CallSite

```json
{
  "id": "call:fn:menu_system.MenuSystem.run:340:9:1",
  "fromFunctionId": "fn:menu_system.MenuSystem.run",
  "fromModuleId": "menu",
  "toFunctionId": "fn:menu_system.MenuSystem.print_menu",
  "toModuleId": "menu",
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

## 3. 调用图独立化

新增 `archmap/callsites.py`：

- 遍历函数体内的全部 AST `ast.Call`；
- 不进入嵌套函数/类定义体；
- 复用 `CallResolver`；
- 识别 call、instantiate、external、unresolved 和 recursive；
- 记录文件、行、列、调用文本和参数数量。

新增 `archmap/details.py`：

- 从函数源码生成 `source` 切片；
- 计算稳定 `sourceHash`（函数 id、签名、备注、源码）；
- 从 CallSite 聚合 `callers` / `callees`；
- 提取签名、返回类型、显式 raises 和源码位置。

## 4. 流水线变化

旧：

```text
analysis → FunctionFlow → CFG layout → bundle
```

新：

```text
analysis → CallSite → FunctionDetail → Project/Module graph → bundle
```

已删除：

- `archmap/flow.py`
- `archmap/layout.py`
- 前端执行流 canvas、拖拽、正交重路由与布局覆盖
- `archmap flow` CLI 命令
- FunctionFlow schema 的默认产物地位

## 5. 方法详情页

默认展示：

- 方法名称、签名、owner class、文件/行号；
- 人类备注；
- LLM 语义注解；
- 返回类型和显式异常；
- 源码切片，带行号；
- 源码调用点高亮；
- Callers / Callees 列表；点击跳转到目标方法详情。

Hash 路由保持旧兼容：

```text
#/module/:moduleId/function/:functionId
```

但页面内容由 Method Detail 渲染，不再渲染 FunctionFlow。

## 6. 验收结果

- 默认 bundle 无 `functionFlows`；
- `student_demo`：5 个 FunctionDetail、6 个 CallSite；
- `class_demo`：6 个 FunctionDetail、3 个 CallSite；
- `MenuSystem`：18 个方法、1 个自由函数，模块边界 1 进 1 出；
- `Spinner`：4 个方法，模块边界 1 进 1 出；
- 方法详情页浏览器测试通过；
- `archmap check` 通过；
- 全量测试通过，浏览器冒烟测试通过。

## 7. 后续

- P2.1：API 契约建模（已完成，替代原类焦点页计划）。
- P3：继承/实现边、抽象方法契约、多态 candidates 与类层次。
- P4：组合/聚合、instantiates、类级 impact/trace 与 DSM。

P2–P4 均尚未开始；详细方案见 [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md)。

## 8. 兼容性

- `schemaVersion` 从 `3.0` 升级到 `3.1`，后续 P2.1 升级到 `3.2`；旧 bundle 不再通过 `archmap check`。
- 旧 `#/module/:id/function/:fid` 路由保留，但渲染 Method Detail。
- 旧函数级布局覆盖 `override.functions` 不再生效；项目页/模块页覆盖继续可用。
- 旧 LLM 注解的 `sourceHash` 基于 FunctionFlow；新版本会将其标记为过期，建议重新生成。
- CLI 的 `archmap flow` 已由 `archmap method` 替代。
