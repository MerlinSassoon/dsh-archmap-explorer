# ArchMap v3.2

把 Python 项目转换为**模块优先、可逐层下钻、源码可读**的架构图：

```text
项目页（模块能力卡片 + 提供接口 + 项目输入/输出）
  └─ 模块页（模块输入/输出 + 提供接口 + 类节点 + 模块级自由函数）
       └─ 方法详情页（源码 + 人类备注 + LLM 语义 + callers/callees）
```

ArchMap 负责“结构和关系”，源码负责“实现细节”，LLM 负责“高层语义”。
默认产物是独立 CLI + 自包含单文件 HTML，不注册插件、不依赖 CDN、不需要第三方运行时依赖。

## 当前状态

```text
P0 / P1 / P1.5  已完成
P2.0 项目页/模块页能力契约重构  已完成
P2.1 API 契约建模与展示         已完成
P2.2 Provider Role 与模块组合   已批准，未开始
P2.3 ArchMap 自身分层重构       已批准，未开始
P3 继承/接口/多态/继承 API      未开始
P4 类关系/API impact/user surface 未开始
```

当前方法入口是 **Method Detail** 页面；语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
文档权威性与历史归档说明见 [docs/README.md](docs/README.md)。

## 快速开始

```bash
# 在当前环境中直接运行
python -m archmap build .

# 分析 student_system 样例
python3 -m archmap build Projects/student_system \
  --config examples/student_system.archmap.json \
  --out yield/student_system

# 分析 ArchMap 自身
python3 -m archmap build . \
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

- **项目页**：模块能力卡片，展示职责、角色、Provider/Capability、类/Provider/API 数量；默认不绘制模块依赖线，依赖证据仍保留在 bundle 中，可通过“关系”按钮查看。
- **模块页**：顶部展示模块提供接口；画布展示模块输入/输出、类节点、模块级自由函数节点；类方法归属类节点，不直接平铺。
- **类节点详情**：展示类类型、抽象/接口标记、构造签名和提供接口；内部方法只显示数量，不展开类内方法图。点击方法/函数接口进入方法详情页。
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
      "color": "#f59e0b",
      "role": "main"
    }
  ]
}
```

模块识别优先级：显式配置 → 包/命名空间 → 单模块兜底。文件仅作为源码证据，不直接作为页面模块。

## 模块能力契约

模块配置支持可选的 `role`：

```json
{
  "id": "database",
  "name": "数据访问",
  "role": "service"
}
```

当前角色：`main` / `service` / `adapter` / `test` / `other`。显式配置优先；未配置时，包含入口函数的模块视为 `main`，其余为 `service`。

每个 `moduleGraph` 会从已有事实派生 `providedApis` 和按 Provider 分组的 `apiProviders`：

- 公开类方法（含抽象契约方法）；
- 公开模块级自由函数；
- `context_manager` / `async_context_manager` / `callable` / `iterable` 协议能力；
- 构造函数、dunder 和下划线内部方法不进入普通方法 API；
- `__init__` 只作为构造签名，`__enter__` / `__exit__` 合成上下文管理器能力。

暴露级别由 `apiExposure` 表达，来源包括 `docstring` / `comment` / `decorator` / `config` / `entrypoint` / `protocol` / `naming`。支持在 `contract` 配置中扩展标签词表和显式覆盖。

详细契约模型见 [docs/archmap-api-contract-model.md](docs/archmap-api-contract-model.md)。

已批准的下一步模型：

```text
config    类型、字段、默认值、常量表、枚举
model     运行期数据模型 / DTO / 分析结果
manager   管理 model/config 实例，组织行为，对外 API
entry     主模块 / CLI / 用户入口
adapter   外部系统适配
component UI / 协议组件
contract  抽象类 / Protocol / 接口
utility   纯函数 / 助手
```

P2.2 将把 config/model 展示为类型卡片，只让 manager/entry/component/contract 的方法进入模块 API；主模块将使用独立的 user surface 表达用户交互面。

**延期项**：`__len__`、`__getitem__`、`__contains__`、切片、ArkTS index signature 等序列协议不在 P2.1 实现，避免启发式误报。

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

当前基线：`40 passed, 1 skipped`；显式开启浏览器测试后为 `1 passed`。

测试覆盖：

- 三层 bundle 契约和交叉引用。
- 类节点、方法归属、抽象类边界。
- FunctionDetail、源码切片、sourceHash。
- CallSite 提取、callers/callees、模块级聚合边。
- API exposure、协议能力合成、Provider 分组和契约校验。
- 宏布局几何、指纹稳定性和布局无关性。
- 自包含 HTML、方法详情页和 LLM 注解嵌入。
- CLI build/check/method 闭环。

浏览器交互已使用 Firefox Headless + geckodriver 验证：项目页、模块页、方法详情页、类方法详情、Hash 刷新恢复和无运行时错误。

## ArkTS 扩展

`archmap/frontends/` 提供语言适配层：

- `LanguageFrontend` 负责发现、解析、符号解析、CallSite 提取、FunctionDetail 和 API 契约能力构建。
- `graph.py`、`validate.py`、`render.py` 与语言无关。
- 语言注册使用显式 `FRONTENDS` 字典，不是插件系统。
- ArkTS 阶段新增 `frontends/arkts`，可使用可选解析器依赖；当前 Python 后端仍保持标准库零依赖。

当前文档入口：

- [docs/README.md](docs/README.md)：文档索引与当前/历史文档边界。
- [docs/archmap-v3-design.md](docs/archmap-v3-design.md)：v3.2 数据契约。
- [docs/archmap-api-contract-model.md](docs/archmap-api-contract-model.md)：Provider + Capability API 契约模型。
- [docs/function-detail-p1.5-plan.md](docs/function-detail-p1.5-plan.md)：P1.5 实现记录。
- [docs/HANDOFF-P2-P4.md](docs/HANDOFF-P2-P4.md)：P2.2–P4 最新交接文档。

## 已知边界

- 仅实现 Python 前端。
- 静态调用解析无法覆盖动态 `getattr`、`**kwargs` 分发、运行时注册表等。
- 方法详情默认内嵌源码切片，单函数源码有长度上限；超大函数会标记为 truncated。
- 宏布局的局部重叠和边界启发式仍需要持续校验。
- P2.1 只合成 context manager、async context manager、callable、iterable；序列协议延期。
- 类焦点页和类内方法图不在当前产品计划中。
- P2.2 Provider Role、P2.3 ArchMap 自身分层重构尚未开始。
- 用户交互面（user surface）尚未建模；主模块仍按普通模块展示 developer API。
- 方法详情页是 P1.5 的主入口；旧语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
- P3 继承/实现关系、继承 API、多态 candidates，以及 P4 的角色感知关系、API/type/surface impact、user surface 传播仍未实现。
- 模块层次/子模块（`parentId`）尚未建模，当前模块配置是扁平的。
- 旧 `docs/archmap-2.0-design.md` 和旧 `docs/HANDOFF.md` 中的 FunctionFlow 内容是历史设计，不是当前契约。
