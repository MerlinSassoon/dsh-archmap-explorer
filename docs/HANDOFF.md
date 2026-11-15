# ArchMap v3 新会话交接文档

> 交接时间：2026-11-15 21:16 CST  
> 工作区根目录：`/home/sasson/桌面/Project/dsh_project/架构图_v3`  
> 当前状态：**v1 Python 后端、三层 bundle、真实函数执行流、单文件 HTML、CLI 与自动化/浏览器测试已完成。** ArkTS 前端仍为后续目标。
> 当前执行策略：普通开发工作不需要再向用户确认；按本文档与最新用户要求直接推进。  
> v1 验收记录：见 [`docs/v1-acceptance-report.md`](v1-acceptance-report.md)。

---

## 0. 一句话目标

把 ArchMap 做成一个**模块优先、函数为节点、可逐层下钻、可由 LLM 补充语义说明**的项目架构工具：

```text
项目页（模块节点 + 用户输入/输出）
  └─ 双击模块 → 模块页（模块输入/输出 + 函数节点）
       └─ 双击函数 → 函数执行流页（ENTRY → 步骤/分支/循环 → EXIT）
```

本轮只要求 Python 分析；后续至少支持鸿蒙 ArkTS。前端最终必须语言无关，ArkTS 通过新增语言前端接入，而不是重写布局和渲染。

---

## 1. 不可违反的工作区约束

新会话开工前先读完本节。

1. **以当前工作区 `架构图_v3` 为唯一项目根目录。**
2. **禁止阅读 `Projects` 目录内的原料代码。** 那是用于测试架构图生成能力的原始材料，不属于本项目源码。
3. **禁止阅读 `架构图_v2` 的代码。**
4. 外部 `架构图` 的 v0 版本代码和文档只可在必要时**有节制地参考**，且只限具体接口/文档细节；不得整仓库复制，不得把它当主依据。
5. 不注册 Cordis/DSH 插件，不实现插件清单，不实现 `lib/dsh-plugin.js`。v1 以独立 CLI + 单文件 HTML 为交付。
6. v1 后端只用 Python 标准库；不引入第三方运行时依赖。ArkTS 以后可以使用可选解析器依赖。
7. HTML 必须是自包含单文件：无 CDN、无外部字体、无外部图片、无网络请求。
8. 最新用户要求优先级高于 `docs/archmap-2.0-design.md` 的旧不变量。发现冲突时，先按本文档第 2 节处理，并在后续设计文档中同步修订。

---

## 2. 需求演进与文档冲突处理

`docs/archmap-2.0-design.md` 是内部函数执行流的基础设计，但其中若干表述已被用户最新需求覆盖。

| 旧文档表述 | 当前要求 |
|---|---|
| “一个函数 = 一张画布”，不存在把多个函数平铺在同一页的视图 | 改为**三层视图**：项目页模块节点 → 模块页函数节点 → 函数执行流页。函数内部仍一张画布。 |
| 图中不存在平级函数之间的 `calls` 边 | **宏观层**允许函数/模块之间的调用或数据流边；**函数内部**仍将调用表达为 call step，不能把被调函数展开成兄弟节点。 |
| 模块只用于侧栏分组 | 模块是项目页的一等节点，有名称、备注、输入、输出，可展开、可拖动、可双击进入独立页面。 |
| 所有连线必须是正交折线 | 项目页/模块页的宏观连线可使用平滑曲线；函数内部执行流仍用正交折线、圆角、Lane、Merge 对齐。 |
| 按文件分析 | 界面主分类按**逻辑模块**，文件只作为源码证据出现在详情中。 |
| 节点卡片展示步骤数、调用数等 | 卡片只展示**节点名 + 人工备注摘要**；不再展示程序生成的执行步骤统计。 |
| 右侧详情自动生成简单信息 | 右侧详情保留占位，最终由语言大模型阅读源码后给出语义说明。 |
| 单文件内弹窗下钻 | 页面必须平级切换，使用 URL/Hash 路由和浏览器历史；不得再使用弹窗式执行流。 |

**优先级建议：**

1. 最新用户明确要求。
2. `docs/prototype/archmap-project-node-preview-v2.html` 中已验证的交互与视觉约定。
3. `docs/archmap-2.0-design.md` 中函数内部执行流语义、布局和校验规则。
4. 外部 v0 的可选参考。

---

## 3. 当前已交付文件

```text
docs/
├── HANDOFF.md                                  ← 本文件
├── archmap-2.0-design.md                       ← 原始 2.0 函数执行流设计
├── schema/
│   ├── workflow-2.0.schema.json                ← 原 2.0 JSON Schema
│   ├── example-checkout.json                   ← 原单函数执行流样例
│   ├── example-checkout.svg
│   └── example-checkout.png
└── prototype/
    ├── archmap-project-node-preview.html       ← v1 前端样机，仅历史参考
    └── archmap-project-node-preview-v2.html    ← 当前最新前端样机
```

### 当前应以哪个文件为准

- **视觉和交互以 `archmap-project-node-preview-v2.html` 为准。**
- v1 只保留作历史对照，不要在新工作中继续扩展 v1。
- 函数内部的 `ENTRY/EXIT`、step、branch、loop、merge、正交路由参考原设计文档和 `example-checkout.svg`。

---

## 4. v2 前端样机说明

主文件：

```text
docs/prototype/archmap-project-node-preview-v2.html
```

规模：

- 约 88.5 KB。
- 约 1469 行。
- 原生 HTML + CSS + JavaScript，无外部依赖。

### 4.1 路由

```text
#/project
#/module/<moduleId>
#/module/<moduleId>/function/<functionId>
```

行为：

- 页面级切换，不使用弹窗。
- 面包屑、返回按钮、浏览器前进/后退均可用。
- URL 刷新后恢复当前页面。

### 4.2 项目页

- 模块为独立节点。
- 每个模块显示：模块名、备注摘要、`IN` 输入、`OUT` 输出。
- 模块可拖动。
- 模块可点击 `+ / −` 行内展开，展开后显示子函数节点。
- 双击模块标题区域或点击 `↗` 进入模块页面。
- 项目边界节点：`用户输入`、`用户输出`。
- 顶部“单模块”按钮展示单模块项目闭环：`用户输入 → 模块 → 用户输出`。

### 4.3 模块页

- 显示模块输入节点、模块输出节点和子函数节点。
- 函数节点、输入/输出节点均可拖动。
- 双击函数节点进入函数执行流页。
- 函数节点只显示函数名和备注，不显示步骤数、调用数等。
- 页面详情默认显示模块备注和 LLM 占位。

### 4.4 函数执行流页

- 独立页面，浅色蓝图风格，与项目/模块页平级。
- 包含 ENTRY、EXIT、step、branch、loop、merge、return、回边等。
- 当前是 **checkout 的样式模板**；点击任何函数都会显示同一模板，并在代码中注明“样式示意”。
- 节点内部执行流后续应由 Python 后端按真实语义生成，不再使用固定模板。

### 4.5 右键/详情面板

- 项目页/模块页节点被单击后，右侧显示：
  - 节点名称
  - 人工备注
  - 源码路径（函数节点）
  - 输入/输出（模块节点）
  - **LLM 语义说明占位区**
- 严格不显示步骤数、调用数、入边/出边列表等简单生成统计。

### 4.6 拖拽与布局保存

- 拖拽已实现：模块节点、项目边界节点、展开模块内的子函数、模块页函数节点、模块页输入/输出节点。
- 拖拽结束后自动写入 `localStorage`。
- 顶部“保存布局”按钮可手动保存并提示。
- 顶部重置按钮清除布局并恢复默认坐标。
- 布局保存键：`archmap-v2-layout-v1`。
- 保存内容：
  - 项目页模块位置和展开状态
  - 项目用户输入/输出位置
  - 单模块模式
  - 模块页输入/输出位置
  - 模块页函数位置
  - 展开卡片内的子函数位置

### 4.7 当前 mock 数据

- 4 个模块：订单与结算、支付与账务、库存与商品、通知与任务。
- 项目输入：用户下单请求。
- 项目输出：订单结果。
- 每模块 3–4 个函数。
- 项目边和模块内边均为静态 mock。
- 当前边语义混合：
  - 项目页图例写“模块数据流”
  - 模块页图例写“函数调用”
  - 后端接入前必须冻结真实边语义。

### 4.8 关键代码位置

| 内容 | 行号约值 |
|---|---|
| `STORAGE_KEY` | 391 |
| `DEFAULT_MODULES` mock 模块/函数/边 | 402 |
| `saveLayout` / `loadLayout` | 633 / 660 |
| 项目页渲染 | 783 |
| 模块页渲染 | 985 |
| 函数页入口 | 1083 |
| 函数执行流 SVG 模板 | 1291 |
| 路由与全局事件 | 1400+ |
| 启动入口 | 1465 |

行号会随改动变化，使用前先 `grep -n` 定位。

---

## 5. 已验证内容与已知问题

### 已通过

- JavaScript 语法检查。
- JSDOM 加载与基础交互测试：
  - 项目页 4 个模块、2 个边界节点、4 个展开子函数、10 条边。
  - 模块页 4 个函数节点、2 个模块输入/输出边界。
  - 双击函数后进入浅色执行流页。
  - 单模块模式得到 1 个模块、2 条输入/输出边。
  - 无运行时错误。
- Firefox Headless + geckodriver 实际截图检查：
  - 项目页
  - 模块页
  - 函数执行流页
  - 单模块模式
- 修复过一个实际视觉 bug：页面入场动画的 `transform` 曾覆盖 fit/zoom 变换，导致画布按 100% 显示并被右侧面板裁切；现在入场动画只改变透明度。

### 已知限制

1. 前端数据全部是静态 mock，不连接后端。
2. 没有真实 Python AST 分析、函数调用解析、模块识别。
3. 没有从源码提取“函数名下方备注”的逻辑。
4. 右侧 LLM 区只是骨架占位，没有模型调用、没有注解持久化。
5. 所有函数执行流页都使用 checkout 模板，尚未按函数生成真实流程图。
6. 模块页/项目页的边语义尚未冻结。
7. 输入/输出目前每个模块固定一个；真实项目是否需要多个端口待定。
8. 不支持嵌套模块；当前只有“项目 → 模块 → 函数”两层宏观结构。
9. 布局只保存在浏览器 localStorage，没有导入/导出 JSON 文件。
10. 布局坐标是用户拖拽结果，后端还需要定义“默认布局”与“用户覆盖布局”的合并规则。
11. 执行流页的步骤节点不参与拖拽；当前只有宏观项目/模块节点支持拖拽。
12. 没有 ArkTS 前端。
13. 没有插件桥接，这是有意为之。

---

## 6. 建议的正式后端架构

### 6.1 总体原则

- 语言前端只负责把源码变成规范 IR。
- 校验、指纹、布局、路由、HTML 渲染都与语言无关。
- Python 用标准库 `ast`；ArkTS 后续用独立可选前端。
- 函数内部布局沿用 2.0 设计；项目/模块宏观层是新增的上一层投影。
- 不使用插件系统；语言注册用显式代码字典即可。

### 6.2 三层图投影

建议在数据模型上明确拆成三个投影，不要强行塞进一个 `functions[]` 数组。

#### A. `ProjectGraph`

```json
{
  "kind": "archmap.project-graph",
  "project": {
    "name": "dsh-shop",
    "language": "python",
    "inputs": ["用户下单请求"],
    "outputs": ["订单结果"]
  },
  "boundaryNodes": [
    {"id": "user-input", "kind": "input", "label": "用户输入"},
    {"id": "user-output", "kind": "output", "label": "用户输出"}
  ],
  "modules": [
    {
      "id": "orders",
      "name": "订单与结算",
      "note": "...",
      "inputs": ["用户下单请求"],
      "outputs": ["订单结果"],
      "functions": ["orders/checkout", "orders/validate_order"]
    }
  ],
  "edges": [
    {"from": "user-input", "to": "orders", "type": "data|call|control"},
    {"from": "orders", "to": "user-output", "type": "data|call|control"}
  ]
}
```

#### B. `ModuleGraph`

```json
{
  "kind": "archmap.module-graph",
  "moduleId": "orders",
  "inputs": [{"id": "__input__", "label": "用户下单请求"}],
  "outputs": [{"id": "__output__", "label": "订单结果"}],
  "nodes": [
    {
      "uid": "orders/checkout",
      "name": "checkout",
      "note": "订单结算主入口，串联校验、优惠、支付与通知。",
      "file": "app/orders/checkout.py",
      "line": 42,
      "functionFlowId": "fn:app.orders.checkout.checkout"
    }
  ],
  "edges": [
    {"from": "__input__", "to": "checkout", "type": "call|data"},
    {"from": "checkout", "to": "validate_order", "type": "call|data"}
  ]
}
```

#### C. `FunctionFlow`

沿用 `docs/schema/workflow-2.0.schema.json` 的结构：

- 每个函数恰好一个 ENTRY、一个 EXIT。
- step / branch / loop / merge。
- 仅 `next_step` 和 `data_dep` 内部边。
- Python 预计算布局与 `d`。
- 双击 call step 的旧交互可保留为未来增强，但当前优先完成“项目 → 模块 → 函数页”三层导航。

### 6.3 语言前端接口

建议新增：

```python
class LanguageFrontend(Protocol):
    language: str
    file_suffixes: tuple[str, ...]

    def discover(root, config) -> list[SourceFile]: ...
    def analyze(files, config) -> AnalysisBundle: ...
    def find_entrypoints(analysis, config) -> list[Entrypoint]: ...
```

`AnalysisBundle` 至少包含：

- 模块树与模块输入/输出。
- 项目边界。
- 函数符号、文件证据、备注。
- 调用目标、候选、外部/未解析状态。
- 每个函数的 `FunctionFlow`。
- 语言侧诊断。

v1 只实现 `frontends/python`。ArkTS 阶段新增 `frontends/arkts`，共享校验、布局和渲染。

### 6.4 备注提取

用户在需求中明确：节点备注不是程序生成的，而是**函数名下方的备注**，增删备注只修改函数名下方的备注。

实现前需要冻结 Python 与 ArkTS 的提取规则，建议：

- Python：函数定义后的第一个 docstring，或紧邻函数定义下方的注释块；只取第一段摘要。
- ArkTS：函数/方法声明下方的 JSDoc/行注释；只取第一段摘要。
- 不把 LLM 生成文本写回源码备注字段，LLM 文本放在独立注解侧车文件。
- 备注应参与语义指纹，LLM 注解不参与代码语义指纹。

### 6.5 LLM 详情侧车

建议单独保存：

```json
{
  "version": 1,
  "model": "...",
  "generatedAt": "...",
  "nodes": {
    "orders/checkout": {
      "summary": "由 LLM 阅读源码后生成的职责说明",
      "details": "输入、输出、约束、异常路径等",
      "sourceHash": "sha256:..."
    }
  }
}
```

右侧详情面板先读侧车；没有时显示当前占位骨架。LLM 输出不得覆盖人工备注。

---

## 7. 下一会话推荐开工顺序

### 阶段 0：冻结契约

1. 新增 `docs/archmap-v3-design.md`（或修订 2.0 文档），明确三层图投影。
2. 修改/新增 JSON Schema：
   - `ProjectGraph`
   - `ModuleGraph`
   - 继续复用 `FunctionFlow` schema
3. 冻结宏观边语义：调用、数据流、控制流是否分别建模。
4. 冻结模块识别规则：显式配置优先，其次包/命名空间，不以文件路径作为界面分类。
5. 冻结备注提取规则和 LLM 注解侧车格式。

### 阶段 1：Python 后端

1. 建立 `archmap/` Python 包。
2. 文件发现、模块识别、项目配置。
3. AST 索引：模块、类、函数、导入、备注。
4. 调用解析：局部函数、模块函数、`self.method`、类型注解方法、导入、外部、候选、递归。
5. 构建 `ProjectGraph`、`ModuleGraph`。
6. 构建每个函数的 `FunctionFlow`。
7. 函数内 def-use 数据依赖。
8. 语义校验、诊断、指纹。

### 阶段 2：布局

1. 宏观布局：
   - 模块节点位置
   - 用户输入/输出边界
   - 模块页函数节点位置
   - 输入/输出端口
2. 微观布局：
   - 沿用 2.0 的 rank、phantom edge、结构树 x 布局、Lane、正交路由。
3. 默认布局与用户拖拽布局分离：
   - 后端只产出默认几何
   - 前端 localStorage 保存用户覆盖
   - CLI 可导出/导入 `layout-overrides.json`
4. 增加布局校验和基准测试。

### 阶段 3：渲染与交互

1. 把 v2 HTML 结构迁移为 Python 模板。
2. 内联真实 `ProjectGraph` / `ModuleGraph` / `FunctionFlow` JSON。
3. 保持：
   - Hash 页面路由
   - 拖拽
   - 布局保存
   - 模块展开
   - 用户输入/输出
   - 右侧 LLM 占位
4. 前端仍不做 rank / x / y / Lane / 自动布局。
5. 函数内部执行流使用后端坐标和正交 `d`。

### 阶段 4：CLI 与交付

建议命令：

```bash
python -m archmap build . --out .archmap
python -m archmap build . --json
python -m archmap check .archmap/architecture.json
python -m archmap flow app/checkout.py --function checkout --json
python -m archmap serve .archmap
python -m archmap diff before.json after.json
```

产物：

```text
.archmap/
├── architecture.json
├── architecture.html
├── layout-overrides.json   # 可选
└── llm-annotations.json    # 可选
```

不实现插件注册。

### 阶段 5：ArkTS 预留

本轮不实现 ArkTS，但必须保证：

- `language` 字段可扩展。
- 前端接口不依赖 Python AST 类型。
- 项目/模块/函数 IR 不出现 Python 专有字段。
- 新增 ArkTS 扫描器不需要改布局和渲染。
- ArkTS 解析器可作为可选依赖，不污染 Python v1 零依赖运行。

---

## 8. 验收清单

### 当前 v2 前端

- [x] 单文件、无外部网络资源。
- [x] 模块节点可拖动。
- [x] 模块可展开显示子函数。
- [x] 双击模块进入独立模块页，不是弹窗。
- [x] 路由、面包屑、浏览器后退可用。
- [x] 模块页函数可拖动。
- [x] 布局可保存、可重置。
- [x] 项目有用户输入/输出边界。
- [x] 模块有输入/输出。
- [x] 单模块项目模式可运行。
- [x] 卡片显示函数名和备注，不显示步骤统计。
- [x] 右侧显示 LLM 语义占位。
- [x] 函数执行流页平级存在。

### 正式 v1 还需要

- [ ] Python AST 真实分析。
- [ ] 按模块而不是文件分组。
- [ ] 真实调用/数据边。
- [ ] 真实函数内部执行流，而不是 checkout 模板。
- [ ] 从函数下方备注自动提取卡片摘要。
- [ ] LLM 注解侧车读取与展示。
- [ ] 布局覆盖文件导入/导出。
- [ ] 语义指纹与确定性布局。
- [ ] 结构/布局 Schema 校验。
- [ ] pytest / ruff / mypy / 浏览器交互测试。
- [ ] 100 函数项目 build < 2s；1000 节点函数 layout < 100ms。
- [ ] 不出现插件代码。

### ArkTS 后续

- [ ] `frontends/arkts` 可解析 ArkTS。
- [ ] 能识别 `@Entry` / `@Component` 等页面入口。
- [ ] 模块/函数/调用/备注进入与 Python 相同的 IR。
- [ ] 布局和渲染层零改动或最小改动。
- [ ] 有可选依赖边界和清晰安装说明。

---

## 9. 新会话建议阅读顺序

1. 本文件 `docs/HANDOFF.md`。
2. `docs/prototype/archmap-project-node-preview-v2.html`（当前前端事实标准）。
3. `docs/archmap-2.0-design.md` 第 2–5 节（函数内部 schema、数据流、布局、路由）。
4. `docs/schema/workflow-2.0.schema.json` 与 `example-checkout.json`。
5. 需要确认历史差异时才看 `docs/prototype/archmap-project-node-preview.html`。
6. 不要阅读 `Projects`，不要阅读 `架构图_v2`。

---

## 10. 尚未冻结、开工前应优先决策的问题

1. **宏观边语义**：项目页模块之间是调用流、数据流、控制流，还是混合？当前 v2 图例同时出现“模块数据流”和“函数调用”。
2. **模块输入/输出是否多端口**：当前每模块一个 IN/OUT，是否需要数组。
3. **是否支持嵌套模块**：项目 → 子模块 → 函数，还是本轮只做项目 → 模块 → 函数。
4. **备注语法**：Python docstring、紧邻函数下方的注释，还是自定义标记；ArkTS 对应规则是什么。
5. **LLM 注解格式和生成时机**：CLI 单独命令、构建后异步生成，还是前端触发。
6. **布局覆盖文件格式**：是否要提供 `layout-overrides.json` 导出/导入，还是仅 localStorage。
7. **函数内部 call step 下钻**：模块页已经提供函数页；内部 call step 是否还需要二次下钻，当前 v2 未实现。
8. **函数执行流页是否留在 v1**：当前 v2 已实现页面骨架，但真实数据需要后端；如果时间紧，可把它延后为 v1.1，但不要退回弹窗方案。

---

## 11. 给新会话的直接开工建议

如果下一会话直接开始编码，建议第一件事不是改 v2 HTML，而是：

```text
1. 读 HANDOFF.md
2. 冻结 ProjectGraph / ModuleGraph / FunctionFlow 三个数据契约
3. 建立 Python 包与 Python frontend 最小闭环
4. 用一个自编 fixture 生成：
   用户输入 → 单模块 → 用户输出
   模块输入 → 2 个函数 → 模块输出
   其中一个函数带真实 ENTRY/EXIT 执行流
5. 再把真实 JSON 注入 v2 前端模板
```

第一个可运行里程碑应是：

> 输入一个自编 Python 小项目，输出一个 `architecture.html`：项目页可看到模块与用户输入/输出；双击模块看到函数节点；双击函数看到真实内部执行流；拖动布局可保存。

不要先做 ArkTS，不要先做插件，不要先做完整 LLM 调用，也不要把 mock 数据继续堆大。
