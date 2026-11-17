# ArchMap v3 数据与扩展设计

> 本文档冻结 v3.1 数据契约，并作为实现和后续 ArkTS 扩展的依据。与 `archmap-2.0-design.md`、旧 `docs/HANDOFF.md` 冲突时，以本文档、[`README.md`](../README.md) 和 [`HANDOFF-P2-P4.md`](HANDOFF-P2-P4.md) 为准。
>
> **当前状态（2026-11-17）**：P0/P1/P1.5 已完成；P2 类焦点页、P3 继承/接口/多态、P4 类关系/impact/trace 尚未开始。本文中的 ClassFocusView 和结构关系是后续契约，不代表当前已经生成。

## 1. 三层投影

### ProjectGraph

项目页只展示逻辑模块和项目边界：

- 模块是项目页一等节点，包含名称、人工备注、输入、输出和函数 ID。
- 项目边界节点表示用户输入和用户输出。
- 模块之间可以存在聚合调用/数据关系；宏观边使用平滑曲线。
- 默认几何由 Python 计算，前端只负责渲染与用户拖拽覆盖。

### ModuleGraph

模块页展示模块输入/输出、类节点和模块级自由函数节点：

- 类节点是模块内的一等组件，带 `classKind`、`isAbstract`、方法摘要、公开 API 和入口方法信息。
- 类方法归属 `class` 节点，不直接平铺为模块页函数节点；方法级关系保存在 `methodEdges` 和全局 `callSites` 中。
- 方法节点属于类组件的子级语义；类本身不拥有执行流。
- 模块输入/输出边界只连接类节点或显式自由函数入口，并通过 `viaMethodIds` 保留方法级证据；抽象类/接口不接模块边界。
- 函数节点只展示函数名和人工备注，不展示步骤数、调用数等生成统计。
- 双击自由函数或点击类方法进入 Method Detail 页面。
- 类焦点页、类内方法布局和类路由尚未实现；当前类方法从模块页的类详情面板进入 Method Detail。

### FunctionDetail / CallSite

P1.5 起，默认产品不再生成语句级 FunctionFlow：

- 每个函数/方法生成 `FunctionDetail`，包含源码切片、签名、备注、返回/异常、callers/callees 和 `sourceHash`。
- 每次静态调用生成 `CallSite`，记录文件、行、列、调用文本、解析状态和置信度。
- `methodEdges` 和模块/项目边由 CallSite 聚合，不再从执行流节点反推调用。
- 方法详情页以源码、人类备注、LLM 语义和调用邻域为主视图。
- 旧 FunctionFlow 仅保留在历史设计文档中，不再是默认 bundle 或 UI 的一部分。

## 2. 宏观边契约

宏观边不是模糊的“混合箭头”，而是可验证的关系聚合：

```json
{
  "id": "e:project:1",
  "from": "entry-network",
  "to": "database",
  "primaryType": "call",
  "relations": ["call", "data"],
  "role": "internal",
  "confidence": "high",
  "evidence": [
    {
      "fromFunctionId": "fn:main.server",
      "toFunctionId": "fn:database.Database.actions",
      "file": "main.py",
      "line": 15
    }
  ]
}
```

- `call`：由已解析的跨函数调用聚合。
- `data`：调用步骤携带参数/返回值等数据证据时附加。
- `control`：主要用于项目/模块输入输出边界，不用于伪造跨模块控制流。
- `primaryType` 只决定默认视觉样式，`relations` 保留全部证据。
- 没有证据的关系不生成边。

## 3. 模块识别

优先级：

1. 配置中的 `modules[].include`。
2. Python 包/命名空间。
3. 单模块兜底。

禁止把每个文件机械地当成一个界面模块。源码文件只作为函数节点详情中的证据。

## 4. 人工备注

- Python 函数优先取 docstring 第一段。
- 其次取函数体首部或定义上方的连续注释块。
- 备注参与语义指纹。
- LLM 注解放在侧车文件，不参与代码语义指纹，不覆盖人工备注。

## 5. LLM 注解侧车

```json
{
  "version": 1,
  "model": "...",
  "generatedAt": "...",
  "nodes": {
    "fn:app.main.main": {
      "summary": "...",
      "details": "...",
      "sourceHash": "sha256:..."
    }
  }
}
```

v1 只读取并在详情面板展示，不调用 LLM。`sourceHash` 不匹配时显示过期提示。

## 6. 默认布局与用户覆盖

- 后端输出 ProjectGraph、ModuleGraph 的默认坐标与边路径。
- 前端不做宏观 rank/x/y/自动布局。
- 项目页、模块页类/函数节点和展开模块内部节点拖拽写入 `localStorage` 覆盖层，键为 `archmap-v3-layout-v1`。
- 覆盖文件由前端导入/导出为 `layout-overrides.json`。
- 覆盖项按稳定 ID 保存，忽略过期或无效键。
- 覆盖不进入语义指纹。
- P1.5 后不再存在函数级执行流布局覆盖；方法详情页以源码和调用关系为主。
- 类焦点页布局覆盖命名空间属于 P2 规划，当前尚未启用。
- 方法详情页和源码面板遵循系统 `prefers-color-scheme`。

## 7. 语言前端接口

`archmap/frontends/base.py` 定义 `LanguageFrontend`：

- 负责源码发现、解析、符号解析、模块投影、CallSite 提取和 FunctionDetail 构建。
- `graph.py`、`validate.py`、`render.py` 不依赖 Python AST。
- 注册使用显式 `FRONTENDS` 字典，不是插件系统。
- Python 前端使用标准库 `ast`，v1 运行时零第三方依赖。

### ArkTS 接入要求

后续 `frontends/arkts` 需要：

- 将文件、类、函数、调用和注释转换为与 Python 相同的 canonical IR。
- 识别 `@Entry` / `@Component` 等页面入口。
- 使用可选解析器依赖，不污染 Python v1 的零依赖边界。
- 不要求修改布局、校验、渲染或路由核心。

## 8. 产物

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

JSON Schema：`docs/schema/archmap-v3-bundle.schema.json`。

单文件 HTML 内联 bundle、CSS 和 JS，无 CDN、外部字体、外部图片或网络请求。
