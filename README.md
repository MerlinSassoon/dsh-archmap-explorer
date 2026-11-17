# ArchMap v3.1

把 Python 项目转换为**模块优先、可逐层下钻、源码可读**的架构图：

```text
项目页（模块 + 用户输入/输出）
  └─ 模块页（模块输入/输出 + 类节点 + 模块级自由函数）
       └─ 方法详情页（源码 + 人类备注 + LLM 语义 + callers/callees）
```

ArchMap 负责“结构和关系”，源码负责“实现细节”，LLM 负责“高层语义”。
默认产物是独立 CLI + 自包含单文件 HTML，不注册插件、不依赖 CDN、不需要第三方运行时依赖。

## 当前状态

```text
P0 / P1 / P1.5  已完成
P2 类焦点页与类内方法图  未开始
P3 继承/接口/多态/类层次  未开始
P4 类关系/impact/trace  未开始
```

当前方法入口是 **Method Detail** 页面；语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
文档权威性与历史归档说明见 [docs/README.md](docs/README.md)。

## 快速开始

```bash
# 在当前环境中直接运行
python -m archmap build .

# 分析 student_system 样例
python -m archmap build /path/to/student_system \
  --config examples/student_system.archmap.json \
  --out .archmap/student_system

# 分析 ArchMap 自身
python -m archmap build . \
  --config examples/archmap_v3.archmap.json \
  --out .archmap/self

# 校验产物
python -m archmap check .archmap/student_system/architecture.json

# 查看单个函数/方法详情
python -m archmap method . --file menu_system.py --function run

# 本地预览
python -m archmap serve .archmap/student_system
```

产物：

```text
.archmap/student_system/
├── architecture.json       # projectGraph + moduleGraphs + functionDetails + callSites
├── architecture.html       # 自包含交互页面
├── llm-annotations.json    # 可选输入
└── layout-overrides.json   # 前端可导出
```

## 三层视图

- **项目页**：模块节点、项目输入/输出边界、模块间真实调用/数据关系。
- **模块页**：模块输入/输出、类节点、模块级自由函数节点；类方法归属类节点，不直接平铺。
- **类节点详情**：展示类类型、抽象/接口标记、方法列表和源码证据；点击方法进入方法详情页。独立类焦点页仍是后续项。
- **方法详情页**：左侧/右侧展示人类备注、LLM 语义、签名、返回/异常、源码切片、callers/callees；点击调用者可继续下钻。
- 所有页面使用 Hash 路由和平级切换，不使用弹窗。
- 项目页与模块页节点支持拖拽；布局默认坐标由 Python 生成，浏览器只保存项目页/模块页的用户覆盖。
- 不再生成或渲染函数内部语句级执行流图；函数实现以源码为最终事实来源。

## 配置

```json
{
  "projectName": "my-project",
  "language": "python",
  "include": ["src/**/*.py"],
  "exclude": ["**/__pycache__/**"],
  "project": {
    "inputs": ["用户请求"],
    "outputs": ["处理结果"]
  },
  "entrypoints": ["app.main:main"],
  "modules": [
    {
      "id": "orders",
      "name": "订单与结算",
      "include": ["src/orders/**"],
      "note": "订单主流程",
      "inputs": ["用户下单请求"],
      "outputs": ["订单结果"],
      "color": "#f59e0b"
    }
  ]
}
```

模块识别优先级：显式配置 → 包/命名空间 → 单模块兜底。文件仅作为源码证据，不直接作为页面模块。

## 人工备注与 LLM 注解

- Python 函数备注优先取 docstring 第一段，其次取函数体首部紧邻注释块。
- 备注和源码参与 `sourceHash`；LLM 文本不写回源码，放在独立侧车文件：

```json
{
  "version": 1,
  "nodes": {
    "fn:app.main.main": {
      "summary": "程序主入口",
      "details": "加载数据并编排后续步骤。",
      "sourceHash": "sha256:..."
    }
  }
}
```

构建时自动读取输出目录或项目 `.archmap/llm-annotations.json`，也可使用 `--annotations`。`sourceHash` 不匹配时页面会标记注解已过期。

## 调用关系与宏观边

函数/方法级调用统一由独立 CallSite 提取，不再依赖语句级执行流：

- `callSites`：每次调用的文件、行、列、调用文本、解析状态、外部/未解析标记。
- `functionDetails[].callers` / `callees`：函数级入/出调用邻域。
- `moduleGraphs[].methodEdges`：类内和模块内的方法级调用关系。
- `moduleGraphs[].edges`：类/函数组件级聚合边。
- `projectGraph.edges`：模块级聚合边。

宏观边包含：

- `primaryType`：`call` / `data` / `control`。
- `relations`：同一对节点可同时具有调用和数据证据。
- `role`：普通内部关系、项目/模块输入输出边界。
- `evidence`：具体函数、文件和行号。
- `confidence`：解析置信度。

没有静态证据的关系不会生成边。

## CLI

```bash
python -m archmap build <project> [--out DIR] [--config FILE] [--split] [--json] [--annotations FILE]
python -m archmap check <architecture.json>
python -m archmap method <project> [--file FILE] [--function NAME] [--json]
python -m archmap serve <directory> [--port 8765]
python -m archmap diff <before.json> <after.json>
```

## 测试

```bash
# 全量测试（浏览器测试默认跳过）
python -m pytest -q

# 浏览器冒烟测试
ARCHMAP_RUN_BROWSER=1 python -m pytest -q tests/test_browser_smoke.py
```

当前基线：`26 passed, 1 skipped`；显式开启浏览器测试后为 `1 passed`。

测试覆盖：

- 三层 bundle 契约和交叉引用。
- 类节点、方法归属、抽象类边界。
- FunctionDetail、源码切片、sourceHash。
- CallSite 提取、callers/callees、模块级聚合边。
- 宏布局几何、指纹稳定性和布局无关性。
- 自包含 HTML、方法详情页和 LLM 注解嵌入。
- CLI build/check/method 闭环。

浏览器交互已使用 Firefox Headless + geckodriver 验证：项目页、模块页、方法详情页、类方法详情、Hash 刷新恢复和无运行时错误。

## ArkTS 扩展

`archmap/frontends/` 提供语言适配层：

- `LanguageFrontend` 负责发现、解析、符号解析、CallSite 提取和 FunctionDetail 构建。
- `graph.py`、`validate.py`、`render.py` 与语言无关。
- 语言注册使用显式 `FRONTENDS` 字典，不是插件系统。
- ArkTS 阶段新增 `frontends/arkts`，可使用可选解析器依赖；当前 Python 后端仍保持标准库零依赖。

当前文档入口：

- [docs/README.md](docs/README.md)：文档索引与当前/历史文档边界。
- [docs/archmap-v3-design.md](docs/archmap-v3-design.md)：v3.1 数据契约。
- [docs/function-detail-p1.5-plan.md](docs/function-detail-p1.5-plan.md)：P1.5 实现记录。
- [docs/HANDOFF-P2-P4.md](docs/HANDOFF-P2-P4.md)：P2–P4 最新交接文档。

## 已知边界

- 仅实现 Python 前端。
- 静态调用解析无法覆盖动态 `getattr`、`**kwargs` 分发、运行时注册表等。
- 方法详情默认内嵌源码切片，单函数源码有长度上限；超大函数会标记为 truncated。
- 宏布局的局部重叠和边界启发式仍需要持续校验。
- 方法详情页是 P1.5 的主入口；旧语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
- 类焦点页、继承/实现/组合/聚合关系图、多态 candidates 和类级 impact/trace 仍在 P2–P4。
- 旧 `docs/archmap-2.0-design.md` 和旧 `docs/HANDOFF.md` 中的 FunctionFlow 内容是历史设计，不是当前契约。
