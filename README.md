# ArchMap v3

把 Python 项目转换为**模块优先、三层下钻、可交互**的架构图：

```text
项目页（模块 + 用户输入/输出）
  └─ 模块页（模块输入/输出 + 函数节点）
       └─ 函数执行流页（ENTRY → 步骤/分支/循环 → EXIT）
```

v1 交付为独立 CLI + 自包含单文件 HTML，不注册插件、不依赖 CDN、不需要第三方运行时依赖。

## 快速开始

```bash
# 在当前环境中直接运行
python -m archmap build .

# 分析 student_system 样例
python -m archmap build /path/to/student_system \
  --config examples/student_system.archmap.json \
  --out .archmap/student_system

# 校验产物
python -m archmap check .archmap/student_system/architecture.json

# 本地预览
python -m archmap serve .archmap/student_system
```

产物：

```text
.archmap/student_system/
├── architecture.json
├── architecture.html
├── llm-annotations.json     # 可选输入
└── layout-overrides.json    # 前端可导出
```

## 三层视图

- **项目页**：模块节点、项目输入/输出边界、模块间真实调用/数据关系。
- **模块页**：模块输入/输出、函数节点、函数间真实调用/数据关系。
- **函数执行流页**：每个函数恰好一个 ENTRY/EXIT；仅使用 `next_step` 和 `data_dep`；采用 Python 预计算的正交布局、Merge 对齐和 Lane。
- 所有页面使用 Hash 路由和平级切换，不使用弹窗。
- 模块节点、项目边界、模块页函数节点、展开卡片内函数节点支持拖拽。
- 布局默认坐标由 Python 生成，浏览器只保存用户覆盖。

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
- 备注属于源码语义，参与指纹。
- LLM 文本不写回源码，放在独立侧车文件：

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

## 宏观边语义

每条宏观边包含：

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
python -m archmap flow <project> [--file FILE] [--function NAME] [--json]
python -m archmap serve <directory> [--port 8765]
python -m archmap diff <before.json> <after.json>
```

## 测试

```bash
python -m pytest -q
```

测试覆盖：

- 三层 bundle 契约和交叉引用。
- 函数内部 ENTRY/EXIT、边类型和结构不变量。
- 备注提取。
- 布局无重叠、Merge 对齐、正交路径。
- 指纹稳定性和布局无关性。
- 自包含 HTML 和 LLM 注解嵌入。
- CLI build/check 闭环。

浏览器交互已使用 Firefox Headless + geckodriver 验证：项目页、模块页、函数页、模块展开、Hash 刷新恢复、节点详情和无运行时错误。

## ArkTS 扩展

`archmap/frontends/` 提供语言适配层：

- `LanguageFrontend` 负责发现、解析、符号解析、模块投影和 canonical `FunctionFlow` 构建。
- `graph.py`、`layout.py`、`validate.py`、`render.py` 与语言无关。
- 语言注册使用显式 `FRONTENDS` 字典，不是插件系统。
- ArkTS 阶段新增 `frontends/arkts`，可使用可选解析器依赖；Python v1 仍保持标准库零依赖。

详见 [docs/archmap-v3-design.md](docs/archmap-v3-design.md)。

## v1 已知边界

- 仅实现 Python 前端。
- `try/except/finally` 只顺序展开主 body，并输出 `TRY_SIMPLIFIED`。
- `match` 不展开 case，并输出 `MATCH_UNSUPPORTED`。
- 动态 `getattr`、`**kwargs` 分发、运行时注册表无法静态解析。
- 函数内 call step 已保留目标函数 ID，但三层页面导航仍是主要路径。
- 不实现插件、远程 LLM 调用、外部网络请求或前端自动布局。
