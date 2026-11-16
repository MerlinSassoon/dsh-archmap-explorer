# ArchMap v3 数据与扩展设计

> 本文档冻结 `docs/HANDOFF.md` 中的新增概念，并作为实现和后续 ArkTS 扩展的契约。与 `archmap-2.0-design.md` 冲突时，以本文档和最新用户要求为准。

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
- 类方法归属 `class` 节点，不直接平铺为模块页函数节点；方法级关系保存在 `methodEdges`，供后续类焦点视图使用。
- 方法节点属于类组件的子级语义，不生成类级 FunctionFlow；只有具体方法拥有 FunctionFlow。
- 模块输入/输出边界只连接类节点或显式自由函数入口，并通过 `viaMethodIds` 保留方法级证据；抽象类/接口不接模块边界。
- 函数节点只展示函数名和人工备注，不展示步骤数、调用数等生成统计。
- 双击自由函数进入真实 FunctionFlow 页面；类方法当前从类详情面板进入。

### FunctionFlow

沿用 2.0 执行流语义：

- 每个函数恰好一个 ENTRY、一个 EXIT。
- 仅存在 `next_step` 和 `data_dep` 两种边。
- 函数内部调用是 `call` step，不展开为兄弟节点。
- 正交折线、Rank、结构树 x 布局、Lane、Merge 对齐和确定性几何。
- 布局坐标和 `d` 路径由 Python 预计算。

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

- 后端输出 ProjectGraph、ModuleGraph 和 FunctionFlow 的默认坐标与边路径。
- 前端不做 rank/x/y/Lane/自动布局。
- 拖拽写入 `localStorage` 覆盖层，键为 `archmap-v3-layout-v1`。
- 覆盖文件由前端导入/导出为 `layout-overrides.json`。
- 覆盖项按稳定 ID 保存，忽略过期或无效键。
- 覆盖不进入语义指纹。

### 函数页手动布局

- 函数执行流页的 ENTRY/EXIT、step、branch、loop、merge 节点均支持拖拽。
- 拖拽位移按当前画布缩放换算，拖拽结束后写入 `override.functions[functionId].nodes`。
- 浏览器复用边类型、端口规则和 Lane 规则，对边路径进行正交重算；颜色、线宽、虚实线和箭头样式保持不变。
- 函数级覆盖按稳定函数 ID 和节点 ID 保存，刷新、导入、导出后可恢复。
- “恢复自动布局”只删除当前函数的覆盖，不影响项目页和模块页。
- 手动布局是用户视图覆盖，不反写后端 `layout`，不参与语义指纹，也不要求继续满足 Merge 中心对齐或 Lane 校验。
- 函数页背景遵循系统 `prefers-color-scheme`；深色模式同步切换网格、图例、缩放控件和流程边 token。

## 7. 语言前端接口

`archmap/frontends/base.py` 定义 `LanguageFrontend`：

- 负责源码发现、解析、符号解析、模块投影和 canonical FunctionFlow 构建。
- `graph.py`、`layout.py`、`validate.py`、`render.py` 不依赖 Python AST。
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
  "schemaVersion": "3.0",
  "kind": "archmap.bundle",
  "project": {},
  "entrypoints": [],
  "projectGraph": {},
  "moduleGraphs": [],
  "functionFlows": [],
  "diagnostics": [],
  "stats": {}
}
```

JSON Schema：`docs/schema/archmap-v3-bundle.schema.json`。

单文件 HTML 内联 bundle、CSS 和 JS，无 CDN、外部字体、外部图片或网络请求。
