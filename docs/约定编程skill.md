# ArchMap 约定编程 Skill

> 版本：1.0<br>
> 适用版本：ArchMap 1.8.0 / bundle schema 3.8<br>
> 最后更新：2026-11-18<br>
> 适用对象：人类开发者、AI 编码助手、代码审查者和后续语言前端实现者。

## 1. Skill 目的

本 Skill 把 ArchMap 的架构边界、数据契约、编码流程和文档要求整理成可执行的编程约束。

使用本 Skill 时必须遵守以下优先级：

```text
bundle schema 与当前数据契约
  > 架构与编码规范
  > 根 README 的产品边界
  > 本 Skill 的流程与检查清单
  > 局部代码风格
```

如果本 Skill 与 `docs/archmap-v3-design.md`、`docs/p2.4-main-module-flow.md` 或 `docs/schema/archmap-v3-bundle.schema.json` 冲突，以后者为准，并同步修订本 Skill。

本 Skill 的核心目标：

1. 不破坏 ArchMap 的事实层、投影层、渲染层边界。
2. 不恢复已废弃的语句级 FunctionFlow。
3. 不让主流程穿透功能模块内部实现。
4. 不伪造没有源码证据的节点、边、候选或置信度。
5. 每个模块、类、函数、方法、测试和入口都有可读、可维护的功能备注。
6. 每次改动都能通过测试、构建、校验和文档检查。

---

## 2. 开始编码前必须完成的判断

在写代码之前，先回答下面五个问题：

1. **这段代码属于哪个物理代码单元？**
   - `config`
   - `model`
   - `manager`
   - `utility`
   - 例外：`entry` / `adapter` / `component` / `contract`

2. **这段代码的逻辑 Provider Role 是什么？**
   - `config`
   - `model`
   - `manager`
   - `entry`
   - `adapter`
   - `component`
   - `contract`
   - `utility`

3. **它是否改变 bundle 数据契约？**
   - 如果改变，先更新设计文档和 JSON Schema，再改实现。
   - 如果改变 schemaVersion，必须同步更新 validator、fixtures、测试和 README。

4. **它属于事实层、投影层还是展示层？**
   - 事实层：源码分析、CallSite、FunctionDetail、API Capability、类型/结构关系、User Surface。
   - 投影层：ProjectGraph、ModuleGraph、MainFlow、typeRelations 聚合、stats。
   - 展示层：HTML、CSS、JS、路由、布局、交互。
   - 禁止在展示层重新解析源码或推导新的事实。

5. **是否需要新增或更新功能备注？**
   - 只要新增/修改了模块、类、函数、方法、测试或入口，答案就是“是”。

---

## 3. 物理代码单元与 Provider Role

物理单元决定代码放在哪里，Provider Role 决定它在架构图中代表什么。两者不能混用。

### 3.1 物理文件规范

```text
<domain>/<domain>_config.py     静态定义、默认值、常量、枚举、配置 schema
<domain>/<domain>_model.py      数据结构、DTO、结果、契约接口
<domain>/<domain>_manager.py    状态、生命周期、行为编排、入口代理
<domain>/<domain>_utility.py    无状态内部辅助逻辑
```

允许的例外：

- `main.py` / `cli.py` / `__main__.py` 作为应用入口；
- 接口很多时可增加 `<domain>_contract.py`，物理归 model 层；
- 外部适配器很多时可增加 `<domain>_adapter.py`，物理归 manager 层；
- UI/协议组件很多时可增加 `<domain>_component.py`，物理归 manager 层。

### 3.2 八角色职责

| Role | 负责 | 不负责 |
|---|---|---|
| `config` | 常量、默认值、枚举、配置 schema、策略表 | 运行期数据、业务编排 |
| `model` | dataclass、DTO、分析结果、领域值对象 | 状态管理、外部资源、领域编排 |
| `contract` | ABC、Protocol、纯接口、抽象方法集合 | 具体实现、配置、运行期 DTO |
| `utility` | 无状态转换、算法、AST 遍历、格式化、校验辅助 | 生命周期、状态、领域编排、公开模块 API |
| `manager` | 状态、资源生命周期、多步业务编排、稳定开发者 API | 数据形状、外部系统适配 |
| `entry` | CLI、HTTP route、任务入口、外部输入边界 | 深层业务编排、长期状态 |
| `adapter` | DB、Redis、HTTP、socket、文件系统、第三方 SDK | 领域策略、UI 编排 |
| `component` | context manager、callable、iterable、UI widget | 通用 manager 职责 |

### 3.3 依赖方向

```text
config ← model ← manager
utility ← manager
contract ← manager
entry → manager
adapter → contract
```

强制规则：

- `utility` 不依赖 manager。
- `config` 不依赖 manager。
- `model` 不依赖 manager。
- `manager` 可以依赖 config/model/contract/utility/adapter。
- `entry` 只依赖 manager。
- 禁止新增循环依赖。
- 内部 utility 必须通过 `ownerProviderId` 归属到对应 facade manager。

### 3.4 可见性

```text
providerVisibility = public | internal
```

- `utility` 默认 `internal`。
- `utility` 不进入项目页/模块页默认视图。
- `utility` 仍是事实层数据，必须保留在 `functionDetails`、`callSites`、impact/trace 中。
- `config` / `model` 只展示类型卡片，`providedApis` 必须为空。
- 项目页角色计数只使用 `publicProviderRoleCounts`。

---

## 4. 模块与主流程约定

### 4.1 模块

- 每个项目恰好一个主模块，功能模块数量为 0..N。
- 不为了凑模块数量虚造功能模块。
- 模块不拥有输入/输出端口。
- 不存在 `module_input` / `module_output` / `project_input` / `project_output` 边。
- 模块间依赖只由调用/数据证据聚合，不硬编码。
- 项目页默认不绘制模块依赖线。

### 4.2 主流程

主流程是**主模块的函数级组合 DAG**，不是全量调用图，也不是语句级执行顺序图。

固定规则：

1. 从 entrypoint 开始。
2. 只在主模块内部继续遍历函数调用。
3. 经过隐藏 helper 时使用 `call_path` + `viaFunctionIds`。
4. 进入功能模块 canonical interface/provider 后立即停止。
5. 功能模块边界节点必须 `flowBoundary=true`、`expandable=false`，且没有出边。
6. 功能模块内部 utility/config/model/adapter 细节不得成为主流程 interface。
7. `composition` 只能用于动态分发/组合推断，必须低置信度虚线。
8. 普通条件分支共享 `branchGroup`；循环不展开；递归回边折叠。
9. dispatch 候选必须有明确来源；无候选时保留 unresolved，不猜测全图。

### 4.3 禁止事项

- 禁止恢复语句级 FunctionFlow。
- 禁止新增类焦点页或类内方法图。
- 禁止把 config/model/utility 物化成主流程 interface。
- 禁止把 composition 画成实线高置信度调用。
- 禁止为了“图完整”伪造节点、边或候选。

---

## 5. API Capability 约定

### 5.1 Provider + Capability

```text
Provider     类或自由函数
Capability   function / method / context_manager / async_context_manager / callable / iterable
Exposure     public / internal
```

规则：

- `__init__` 不作为 API 行，只作为类的 `usage.constructor`。
- `__enter__` / `__exit__` 合成 `context_manager`。
- `__aenter__` / `__aexit__` 合成 `async_context_manager`。
- `__call__` 合成 `callable`。
- `__iter__` 合成 `iterable`。
- 其他 dunder 默认不进入 API。
- `_name` 默认 internal。
- 非下划线、无标注默认 public，来源为 `naming`。
- 暴露来源必须是 `docstring` / `comment` / `decorator` / `config` / `entrypoint` / `protocol` / `naming` 之一。
- 每个 Capability 必须有稳定 ID、Provider 归属、证据函数 ID 和置信度。

### 5.2 继承 API

- 继承关系只解析项目内 canonical class。
- 继承 Capability 归属子类 Provider，但必须保留：
  - `inherited=true`
  - `declaredInProviderId`
  - `inheritedFromProviderId`
  - `overridesCapabilityId`
  - 真实 evidence function IDs
- 不伪造子类的继承方法函数 ID。
- 抽象/Protocol 调用使用多态 candidates，不指定唯一 `toFunctionId`。
- 多态候选集默认 `candidateSetComplete=false`。

### 5.3 序列协议

以下能力当前延期，不得偷偷实现为通用启发式：

```text
__len__ / __getitem__ / __setitem__ / __contains__
__reversed__ / 切片 / 索引签名
ArkTS length / index signature
```

如要支持，必须先更新数据契约、证据模型、配置入口和测试。

---

## 6. P3/P4 事实层约定

### 6.1 P3 类型关系

- `inherits`：具体类继承。
- `implements`：抽象类/Protocol/interface。
- 类节点必须有 `baseClassIds`、`subclassIds`、`mroClassIds`、`abstractMethodNames`。
- 子类必须正确继承有效抽象性。
- 多态 candidates 只沿后代方向收集，不允许兄弟污染。

### 6.2 P4 结构关系

- `instantiates`：构造调用。
- `uses`：参数、返回值和字段类型注解。
- `aggregates`：构造注入或字段持有。
- `composes`：构造函数内实例化并赋给实例字段。
- 每条关系必须有 `source`、Provider Role、可见性、confidence 和 evidence。
- 不允许仅凭命名或猜测生成结构边。

### 6.3 User Surface

- User Surface 是独立投影，不是 developer API 的别名。
- 识别来源包括 IO primitive、事件 primitive、entrypoint 可达性传播和显式配置覆盖。
- 每个 surface 必须有 evidence function IDs、entrypoint IDs 和 confidence。
- 配置覆盖优先于自动启发式。
- 不在渲染层重新识别 IO primitive。

### 6.4 Impact / Trace / DSM

- 三者都是只读查询，不写入默认 `architecture.json`。
- 必须支持 `maxDepth` / `maxNodes` / `truncated`。
- 禁止静默截断。
- 查询层不得重新解析源码。
- 多态候选在 trace 中必须保留为 candidate 边，不伪装成唯一调用。

---

## 7. 功能备注强制规范

> 本节是本 Skill 的硬性要求：**每个模块、类、函数、方法、测试、入口都必须写功能备注。**
> 不允许用括号、空字符串、重复签名或自动生成的无意义文本占位。

### 7.1 备注提取规则

ArchMap 按以下顺序提取人工备注：

1. docstring 第一段；
2. 函数体首部紧邻注释块；
3. 定义上方连续注释块（实现可 best-effort）。

推荐始终使用 docstring，因为：

- 可被 AST 稳定读取；
- 参与语义指纹和 `sourceHash`；
- 在 Method Detail 中直接展示；
- 不依赖注释排版。

### 7.2 模块级备注

每个 Python 文件必须有模块 docstring，说明：

- 该模块负责什么；
- 属于哪个物理单元；
- 不负责什么；
- 若为 facade 文件，说明内部 utility 的归属。

示例：

```python
"""ArchMap 应用流水线 facade。

负责 config → frontend → graph 的顶层编排。
不负责源码解析、图投影、校验或 HTML 渲染。
"""
```

### 7.3 类备注

每个类必须有类 docstring，至少说明：

1. **职责**：这个类解决什么问题。
2. **角色**：config / model / manager / entry / adapter / component / contract / utility。
3. **生命周期**：由谁构造、是否持有状态/资源、何时释放。
4. **边界**：不负责什么，避免职责膨胀。
5. **对外能力**：公开方法或协议能力；config/model 还要说明字段和默认值。

示例：

```python
class PipelineManager:
    """应用流水线 facade。

    职责：按 config → frontend → call sites → contracts → graph 的顺序编排。
    生命周期：调用方短暂构造，无长期外部资源。
    边界：不解析 Python AST，不执行图布局或 HTML 渲染。
    对外能力：build_architecture()。
    """
```

### 7.4 函数与方法备注

每个函数、方法（包括私有函数、工具函数、dunder 方法）必须有功能备注，至少包含：

1. **目的**：用一句话说明为什么存在。
2. **输入**：关键参数的业务含义；类型签名已表达的不要机械重复。
3. **输出**：返回值或产生的数据结构。
4. **副作用**：是否写文件、改状态、访问网络、修改全局事实层。
5. **约束**：重要不变量、边界、异常、置信度或 evidence 要求。

示例：

```python
def build_main_flows(...):
    """把 CallSite 和 Capability 投影成主模块流程 DAG。

    输入：分析结果、模块图、调用事实和显式 dispatch 配置。
    输出：只读的 MainFlow 列表，不修改 Provider Role、visibility 或 CallSite。
    约束：功能模块 interface/provider 必须为叶子边界；composition 只能低置信度。
    """
```

禁止示例：

```python
def build_main_flows(...):
    """构建主流程。"""  # 信息不足，未说明输入、输出和边界
```

### 7.5 测试函数备注

每个测试函数必须有备注，说明：

- 验证的场景；
- 预期不变量；
- 失败时代表什么契约被破坏。

示例：

```python
def test_main_flow_stops_at_functional_module_interfaces() -> None:
    """验证主流程进入功能模块 canonical interface 后不再穿透内部 utility。"""
```

### 7.6 构造、协议和特殊方法

- `__init__`：说明构造职责、必要参数、资源初始化和不变量。
- `__enter__` / `__exit__`：说明资源生命周期。
- `__aenter__` / `__aexit__`：说明异步资源生命周期。
- `__call__`：说明调用语义和副作用。
- `__iter__`：说明迭代顺序、终止条件和是否可重复迭代。
- CLI 命令函数：说明用户可见行为、退出码和错误输出。
- 渲染函数：说明输入 bundle、输出 HTML 和是否可安全重复调用。

### 7.7 备注与 LLM 注解的边界

- 人工功能备注写进源码 docstring/comment。
- LLM 语义写在独立 `llm-annotations.json` 侧车文件。
- LLM 文本不得写回源码，不得覆盖人工备注。
- `sourceHash` 不匹配时，LLM 注解必须标记为过期。
- 修改 docstring 或函数体后，必须考虑相关 `sourceHash` 是否需要重新生成。

### 7.8 备注质量检查

提交前逐项检查：

- [ ] 每个新增/修改的模块有模块 docstring。
- [ ] 每个新增/修改的类有职责、角色、生命周期、边界。
- [ ] 每个新增/修改的函数/方法有目的、输入、输出、副作用/约束。
- [ ] 每个新增/修改的测试有场景和预期不变量。
- [ ] 备注没有重复函数名或签名。
- [ ] 备注没有“实现逻辑”“处理数据”这类空泛表述。
- [ ] 修改后的备注不会让 LLM 注解静默过期。

---

## 8. 命名与代码风格

- Python 3.10+，使用 `from __future__ import annotations`。
- 公共 API 必须有类型注解。
- 数据结构优先使用 dataclass / TypedDict / Protocol，不用裸 dict 传递内部核心事实。
- 稳定 ID 使用 canonical 前缀：
  - 函数：`fn:...`
  - 类：`cls:...`
  - API：`api:...`
  - 类型关系：`type:...`
  - 主流程：`main-flow:...`
- 禁止在核心代码中硬编码具体项目类名或路径。
- 禁止新增 Python 前端运行时第三方依赖。
- 禁止在 HTML 中引入 CDN、外部字体、外部图片或网络请求。
- 禁止重新引入已删除的 import shim；统一使用 canonical 包路径。

---

## 9. 标准修改流程

### 9.1 修改前

1. 阅读根 README 和对应当前权威文档。
2. 确认修改属于事实层、投影层还是展示层。
3. 确认物理代码单元和 Provider Role。
4. 如果涉及数据契约，先更新设计和 schema。
5. 如果涉及 UI，确认不会破坏 Hash 路由、方法详情页和自包含 HTML。

### 9.2 实现顺序

推荐顺序：

```text
config / model
  → 前端事实提取
  → CallSite / FunctionDetail / Capability
  → 类型/结构/User Surface 事实
  → ProjectGraph / ModuleGraph / MainFlow 投影
  → validator
  → query / CLI
  → render / assets
  → tests / fixtures
  → README / current docs
```

不要先在 UI 层写死数据，再补投影层。

### 9.3 修改后

必须执行：

```bash
python3 -m pytest -q
python3 -m archmap build . --config examples/archmap_v3.archmap.json --out /tmp/archmap-self
python3 -m archmap check /tmp/archmap-self/architecture.json
python3 -m archmap build Projects/student_system --config examples/student_system.archmap.json --out /tmp/student
python3 -m archmap check /tmp/student/architecture.json
```

涉及 UI 时必须执行：

```bash
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q tests/test_browser_smoke.py
```

涉及打包或入口时必须执行：

```bash
python3 -m compileall -q archmap tests
python3 -m pip wheel . --no-deps -w /tmp/archmap-wheel
```

---

## 10. 数据契约变更协议

任何新增/删除/重命名字段都必须完成：

1. 更新 `docs/archmap-v3-design.md`。
2. 更新 `docs/schema/archmap-v3-bundle.schema.json`。
3. 更新对应的数据模型 dataclass / TypedDict。
4. 更新生成逻辑。
5. 更新 validator。
6. 更新至少一个 fixture 和测试。
7. 更新根 README 的使用说明或已知边界。
8. 如 schemaVersion 变化，同步更新版本号、README、schema 和相关文档。

禁止只改 Python dict 不改 schema、只改 schema 不写 validator、或只写 UI 不写事实层。

---

## 11. 测试与验收

### 11.1 测试分层

- 单元测试：纯 utility、解析、契约、validator。
- 集成测试：bundle 构建、fixture 全链路、CLI。
- 浏览器冒烟：项目页、模块页、方法详情、类详情、Hash 路由、主题。
- 架构不变量：主流程边界、composition low、utility internal、无假边。

### 11.2 最低验收门槛

- `pytest` 无失败。
- 至少一个新增/修改 fixture 通过 build + check。
- 自举和 student_system build/check 通过。
- diagnostics 为 0（或明确说明非零原因）。
- 旧 shim 和旧导入回归测试通过。
- UI 改动通过 browser smoke。
- 文档链接可解析。

---

## 12. 文档更新规则

- 当前产品状态只写入根 `README.md` 和 `docs/` 下的当前权威文档。
- 历史交接、旧设计、迁移计划和旧验收统一归档到 `docs/旧文档/`。
- 不在当前 docs 根目录新增阶段 handoff；完成一个阶段后再归档。
- 不新增独立 docs 索引文件；根 README 是唯一总入口。
- 数据契约以 `docs/archmap-v3-design.md` 为准。
- 主流程边界以 `docs/p2.4-main-module-flow.md` 为准。
- 架构与角色规范以 `docs/archmap-architecture-spec.md` 为准。
- API 契约以 `docs/archmap-api-contract-model.md` 为准。
- 每次合并到 master 后更新 README 的版本、状态和验收数据。

---

## 13. 绝对禁止事项

以下行为视为破坏项目契约：

1. 恢复语句级 FunctionFlow。
2. 新增类焦点页或类内方法图。
3. 让主流程穿透功能模块内部 utility。
4. 把 utility/config/model 物化成主流程 interface。
5. 伪造调用边、类型关系、User Surface 或 dispatch 候选。
6. 把 composition 变成高置信度实线调用。
7. 在 render/query 层重新解析源码。
8. 维护两套并行事实模型。
9. 只改 UI、不改事实层和 validator。
10. 保留或新增旧 import shim。
11. 给 Python 前端引入运行时第三方依赖。
12. 在 HTML 中加载 CDN 或发出外部网络请求。
13. 新增没有功能备注的类、函数、方法或测试。
14. 用 `"TODO"`、`"实现"`、`"处理逻辑"` 充当功能备注。
15. 把 LLM 注解直接写回源码替代人工备注。

---

## 14. 提交前检查清单

### 架构与契约

- [ ] 物理单元和 Provider Role 正确。
- [ ] 依赖方向没有倒置或循环。
- [ ] utility 默认 internal。
- [ ] config/model 没有公开模块 API。
- [ ] 主流程边界没有被穿透。
- [ ] composition 仍为 low/虚线。
- [ ] 没有伪造证据或候选。

### 数据与校验

- [ ] bundle 字段与 schema 一致。
- [ ] validator 覆盖新增不变量。
- [ ] fixture 和测试已更新。
- [ ] 跨引用 ID 可解析。
- [ ] diagnostics 为 0 或有明确说明。

### 功能备注

- [ ] 模块 docstring 已写。
- [ ] 类 docstring 已写。
- [ ] 函数/方法 docstring 已写。
- [ ] 测试函数 docstring 已写。
- [ ] 特殊方法已说明生命周期/副作用。
- [ ] 备注没有空泛表述。
- [ ] `sourceHash` 和 LLM 注解过期状态已考虑。

### 验证与文档

- [ ] pytest 通过。
- [ ] build/check 通过。
- [ ] browser smoke 通过（UI 改动）。
- [ ] wheel/compileall 通过（入口或打包改动）。
- [ ] 根 README 和当前文档链接有效。
- [ ] 历史材料只进入 `docs/旧文档/`。
- [ ] git status 干净。

---

## 15. Definition of Done

一个改动只有同时满足以下条件才算完成：

1. 代码符合物理单元、Provider Role 和依赖方向。
2. 没有破坏主流程、API Capability、类型/结构关系或 User Surface 边界。
3. 所有新增/修改的模块、类、函数和方法都有高质量功能备注。
4. 所有新增/修改的测试都有场景备注。
5. bundle schema、validator、fixture 和测试同步更新。
6. 完整测试、自举构建、样例构建和必要浏览器测试通过。
7. 文档入口、版本号、验收数据和已知边界已更新。
8. 没有新增无证据的架构关系，也没有恢复已废弃产品形态。

本 Skill 是提交前自检的最低标准，不是替代设计评审的充分条件。
