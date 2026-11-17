# ArchMap v3.6

把 Python 项目转换为**模块优先、可逐层下钻、源码可读**的架构图：

```text
项目页（主模块 + 功能模块能力卡片）
  └─ 主模块页（入口 → 编排函数 → 功能模块接口的主流程 DAG）
       └─ 功能模块页（提供接口 + 类节点 + 模块级自由函数）
            └─ 方法详情页（源码 + 人类备注 + LLM 语义 + callers/callees）
```

ArchMap 负责“结构和关系”，源码负责“实现细节”，LLM 负责“高层语义”。
默认产物是独立 CLI + 自包含单文件 HTML，不注册插件、不依赖 CDN、不需要第三方运行时依赖。

## 当前状态

```text
P0 / P1 / P1.5  已完成
P2.0 项目页/模块页能力契约重构  已完成
P2.1 API 契约建模与展示         已完成
P2.2 Provider Role 与模块组合   已完成
P2.3 ArchMap 自身分层重构       已完成（含旧 import shim 清理）
P2.4 主模块/功能模块/主流程     已完成
P2.4 清理分支 UI/布局/协议能力  已完成
P3 继承/接口/多态/继承 API      独立分支已完成，未合入当前分支
P4 类关系/API impact/user surface 独立分支已完成，未合入当前分支
P5 尚未定义
```

当前开发分支：`fix/p2.4-ui-migration-finalize`，基于 `p2.4-main-flow` 的 `008d3c6`。
P3 位于 `p3-inheritance-polymorphism`，P4 位于 `p4-impact-trace-surfaces`；当前清理分支不包含 P3/P4 新增能力，后续需要分支整合。

当前方法入口是 **Method Detail** 页面；语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。
P2.4 起，每个项目恰好有一个主模块；主模块展示函数级主流程，功能模块只暴露 Provider/Capability，不再拥有输入输出端口。
当前主流程还支持 context-manager capability 投影（例如 `with Spinner(...)`），但仍是函数级调用/模块组合图，不是语句级执行顺序图。
文档权威性与历史归档说明见 [docs/README.md](docs/README.md)，当前交接见 [docs/HANDOFF-P2.4-CLEANUP.md](docs/HANDOFF-P2.4-CLEANUP.md)。

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
python -m archmap check yield/student_system/architecture.json

# 查看单个函数/方法详情
python -m archmap method Projects/student_system \
  --file student_system/managers/menu_manager.py \
  --function run

# 本地预览
python -m archmap serve yield/student_system
```

产物：

```text
yield/student_system/
├── architecture.json       # projectGraph + moduleGraphs + functionDetails + callSites
├── architecture.html       # 自包含交互页面
├── llm-annotations.json    # 可选输入
└── layout-overrides.json   # 前端可导出
```

## 三层视图

- **项目页**：模块能力卡片，展示职责、模块角色、Provider Role 数量、Provider/Capability、类/Provider/API 数量；默认不绘制模块依赖线，依赖证据仍保留在 bundle 中，可通过“关系”按钮查看。
- **项目页交互**：模块卡片不再提供“+”内联展开；双击卡片或点击右上角 ↗ 进入独立模块页面。
- **主模块页**：默认展示 entry → orchestrator/provider/interface 的主流程 DAG；可切换到能力视图查看类与自由函数。上下文管理器等协议用法会在 Provider 边界节点上携带 `capabilityKind`、`protocols` 与 `usageKind`，例如显示 `with Spinner(...)`，但主流程仍是调用/模块组合图，不是语句级执行顺序图。
- **功能模块页**：顶部展示模块提供接口与 Provider Role 组合；画布展示类节点、模块级自由函数节点；不再有模块输入/输出端口。config/model Provider 以类型卡片展示字段摘要。
- **类节点详情**：展示类类型、抽象/接口标记、构造签名和提供接口；内部方法只显示数量，不展开类内方法图。点击方法/函数接口进入方法详情页。
- **方法详情页**：左侧/右侧展示人类备注、LLM 语义、签名、返回/异常、源码切片、callers/callees；点击调用者可继续下钻；页面背景跟随系统浅色/深色模式。
- 所有页面使用 Hash 路由和平级切换，不使用弹窗。
- 项目页与模块页节点支持无固定边界拖拽；布局默认坐标由 Python 生成，浏览器只保存项目页/模块页的用户覆盖；可用“适应画布”或“重置布局”找回节点。
- 不再生成或渲染函数内部语句级执行流图；函数实现以源码为最终事实来源。

## 配置

```json
{
  "projectName": "my-project",
  "language": "python",
  "include": ["src/**/*.py"],
  "exclude": ["**/__pycache__/**"],
  "mainModule": "orders",
  "entrypoints": ["app.main:main"],
  "modules": [
    {
      "id": "orders",
      "name": "订单与结算",
      "kind": "main",
      "include": ["src/orders/**"],
      "note": "订单主流程组合根",
      "color": "#f59e0b",
      "role": "main"
    },
    {
      "id": "payments",
      "name": "支付能力",
      "kind": "functional",
      "include": ["src/payments/**"],
      "note": "支付 Provider 与公开接口",
      "color": "#60a5fa",
      "role": "service"
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

**延期项**：`__len__`、`__getitem__`、`__contains__`、切片、ArkTS index signature 等序列协议不在 P2.1 实现，避免启发式误报。

## Provider Role 与模块组合

P2.2 在 Capability 之上增加 Provider 级职责：

```text
config    类型定义、字段、默认值、常量表、枚举
model     运行期数据模型 / DTO / 分析结果
manager   管理 model/config 实例，组织行为，对外 API
entry     主模块 / CLI / 用户入口
adapter   外部系统适配
component UI / 协议组件
contract  抽象类 / Protocol / 接口
utility   纯函数 / 助手
```

角色判定优先级：

```text
contract.providerRoles 显式覆盖
  > 注释 / 装饰器 / JSDoc 标注
  > 结构规则
  > 命名弱提示
```

每个 Provider 节点、`apiProviders` 条目和 API capability 都携带：

```json
{
  "providerRole": "manager",
  "roleSource": "structure",
  "roleConfidence": "high"
}
```

模块图额外输出：

```json
{
  "moduleComposition": {
    "config": ["cls:app.config.AppConfig"],
    "model": ["cls:app.model.Order"],
    "manager": ["cls:app.manager.OrderManager"],
    "entry": ["fn:app.main.main"],
    "adapter": [],
    "component": [],
    "contract": [],
    "utility": ["fn:app.util.helper"]
  },
  "providerRoleCounts": {
    "config": 1,
    "model": 1,
    "manager": 1,
    "entry": 1,
    "adapter": 0,
    "component": 0,
    "contract": 0,
    "utility": 1
  }
}
```

展示规则：

- `manager` / `entry` / `component` / `contract`：展示方法/协议能力；
- `config` / `model`：展示类型卡片、字段摘要和默认值，不把 `as_dict()` 等序列化方法当作模块 API；
- `adapter`：展示适配器入口能力；
- `utility`：展示函数签名。

显式角色覆盖示例：

```json
{
  "contract": {
    "providerRoles": {
      "app.model.Order": "model",
      "app.config.AppConfig": "config"
    }
  }
}
```

## 代码架构规范

P2.3 起，ArchMap 自身源码遵循“物理代码单元 + 逻辑 Provider Role”两层规范。

物理代码单元：

```text
<domain>/<domain>_config.py     静态定义、默认值、常量、枚举
<domain>/<domain>_model.py      数据结构、DTO、结果、契约接口
<domain>/<domain>_manager.py    状态、生命周期、行为编排、入口代理
<domain>/<domain>_utility.py    无状态内部辅助逻辑
```

逻辑角色仍然是：

```text
config / model / manager / entry / adapter / component / contract / utility
```

关键规则：

- `contract` 默认物理归入 model 文件，逻辑角色保持独立；
- `entry`、`adapter`、`component` 默认物理归入 manager 文件，逻辑角色由入口/外部 IO/协议生命周期派生；
- `utility` 是无状态内部实现，默认 `providerVisibility = "internal"`，不进入项目页/模块页；
- utility 仍保留在 `functionDetails`、`callSites` 和 impact/trace 事实层中；
- 项目页角色计数只使用 `publicProviderRoleCounts`；
- 每个领域只暴露少量 facade manager；例如 Python 前端的 `analyze_project`、`collect_call_sites` 等阶段函数是 `PythonFrontend` 的内部 utility。
- 内部 utility 通过 `ownerProviderId` 归属到 facade manager，不生成独立卡片。
- 依赖方向为 `config ← model ← manager`，`utility ← manager`，`entry → manager`。

当前目录：

```text
archmap/
├── config/        project_config.py / contract_config.py / graph_config.py ...
├── model/         analysis_model.py / call_model.py / contract_model.py ...
├── utility/       graph_utility.py / validate_utility.py / render_utility.py ...
├── managers/      pipeline_manager.py / frontend_manager.py / graph_manager.py ...
├── entry/         cli_entry.py
├── frontends/     python/python_manager.py + internal utility stages
└── render/assets/
```

P2.3 迁移已最终完成：旧 import shim 文件已删除，测试、自举配置和 CLI 入口全部使用新目录；`python -m archmap` 与安装后的 `archmap` 命令均指向 `archmap.entry.cli_entry:main`。

详细规范见 [docs/archmap-architecture-spec.md](docs/archmap-architecture-spec.md)，迁移记录见 [docs/p2.3-migration-plan.md](docs/p2.3-migration-plan.md)。

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
- `role`：普通内部关系；不再生成模块输入输出边界边。
- 主流程边使用 `call` / `call_path` / `composition`，其中 composition 只能是低置信度虚线。
- 主流程只在主模块内部继续遍历；进入功能模块 canonical interface/provider 后停止，不穿透其内部 utility。
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

当前基线：`71 passed, 1 skipped`；显式开启浏览器测试后为 `1 passed`。

测试覆盖：

- 三层 bundle 契约和交叉引用。
- 唯一主模块、0..N 功能模块与无 I/O 端口不变量。
- 主流程 DAG、分支、dispatch 候选和 composition 虚线语义。
- 类节点、方法归属、抽象类边界。
- FunctionDetail、源码切片、sourceHash。
- CallSite 提取、callers/callees、模块级聚合边。
- API exposure、协议能力合成、Provider 分组和契约校验。
- Provider Role 判定、模块组合、config/model 类型卡片与 API 过滤。
- 宏布局几何、指纹稳定性和布局无关性。
- 自包含 HTML、方法详情页和 LLM 注解嵌入。
- CLI build/check/method 闭环。

浏览器交互已使用 Firefox Headless + geckodriver 验证：项目页、模块页、方法详情页、类方法详情、Hash 刷新恢复和无运行时错误。

## ArkTS 扩展

`archmap/frontends/` 提供语言适配层：

- `LanguageFrontend` 负责发现、解析、符号解析、CallSite 提取、FunctionDetail 和 API 契约能力构建。
- `graph_utility.py`、`validate_utility.py`、`render_utility.py` 及对应 Manager 与语言无关。
- 语言实例由 `FrontendManager` 显式注册，不是插件系统。
- ArkTS 阶段新增 `frontends/arkts`，可使用可选解析器依赖；当前 Python 后端仍保持标准库零依赖。

当前文档入口：

- [docs/README.md](docs/README.md)：文档索引与当前/历史文档边界。
- [docs/archmap-architecture-spec.md](docs/archmap-architecture-spec.md)：物理代码单元、八角色语义、依赖方向与迁移规范。
- [docs/archmap-v3-design.md](docs/archmap-v3-design.md)：v3.6 数据契约。
- [docs/archmap-api-contract-model.md](docs/archmap-api-contract-model.md)：Provider + Capability API 契约模型。
- [docs/function-detail-p1.5-plan.md](docs/function-detail-p1.5-plan.md)：P1.5 实现记录。
- [docs/p2.4-main-module-flow.md](docs/p2.4-main-module-flow.md)：主模块、功能模块、主流程 DAG 与 dispatch 契约。
- [docs/HANDOFF-P2.4-CLEANUP.md](docs/HANDOFF-P2.4-CLEANUP.md)：当前分支交接：P2.3 最终清理、主流程协议能力、布局/卡片修复、P3/P4 整合注意事项。
- [docs/HANDOFF-P2-P4.md](docs/HANDOFF-P2-P4.md)：已归档的 P2.2–P2.4 历史交接快照。

## 已知边界

- 仅实现 Python 前端。
- 静态调用解析无法覆盖动态 `getattr`、`**kwargs` 分发、运行时注册表等。
- 方法详情默认内嵌源码切片，单函数源码有长度上限；超大函数会标记为 truncated。
- 宏布局的局部重叠和边界启发式仍需要持续校验。
- P2.1 只合成 context manager、async context manager、callable、iterable；序列协议延期。
- 类焦点页和类内方法图不在当前产品计划中。
- 当前清理分支不包含 P3/P4 的继承、User Surface、Impact/Trace、DSM 能力；这些能力存在于独立 P3/P4 分支，尚未合入。
- 方法详情页是 P1.5 的主入口；旧语句级 FunctionFlow 已从默认 bundle、UI 和流水线中移除。主流程只表达函数级调用与模块组合，不表达 `if/while/try/with` 内部的逐语句执行顺序。
- `with` / `async with` 只识别 AST 中真实的 context expression；通过变量持有的上下文管理器不会追溯构造调用，动态 context manager 仍可能 unresolved。
- 同一类 Provider 当前只生成一个主流程边界节点；普通实例化与协议用法混合时不拆成多个节点。
- 本地保存的旧布局覆盖可能保留旧坐标；查看新默认主流程布局前可点击“重置布局”。
- 旧 Python import 兼容路径已删除，外部脚本需要改用 `archmap.managers.*`、`archmap.frontends.*`、`archmap.model.*`、`archmap.utility.*` 或 `archmap.entry.*`。
- 模块层次/子模块（`parentId`）尚未建模，当前模块配置是扁平的。
- 旧 `docs/archmap-2.0-design.md` 和旧 `docs/HANDOFF.md` 中的 FunctionFlow 内容是历史设计，不是当前契约。
