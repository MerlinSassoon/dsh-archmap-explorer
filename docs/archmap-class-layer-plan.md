# ArchMap 类语义层设计与实施计划

> 状态：设计讨论稿  
> 日期：2026-11-16  
> 目标：解决“类被当作流程节点、类方法在模块页平铺、模块边界被方法污染”的问题。  
> 结论：类应成为模块内的一等语义容器；类本身不是执行流节点，方法才是。

## 1. 设计结论

### 1.1 类在四类图中的位置

| 图/视图 | 类是否出现 | 节点语义 |
|---|---|---|
| ProjectGraph | 否 | 项目页只展示逻辑模块与项目边界 |
| ModuleGraph | 是 | 类节点、模块级自由函数、模块边界 |
| ClassFocusView / ClassGraph | 是，作为容器 | 方法节点、方法间关系、契约/继承信息 |
| FunctionFlow | 否 | 方法内部的 ENTRY / 步骤 / 分支 / 循环 / EXIT |

类可以被视为“模块内的一等组件节点”，但**不能被视为一个具备单一控制流的函数节点**。  
因此：

- 类可以有 `ENTRY` / `EXIT` 吗？不能。类没有单一执行流。
- 类可以出现在模块页吗？可以，作为组件/容器节点。
- 方法可以有执行流吗？可以，`FunctionFlow` 属于方法。
- 抽象类可以接入模块输入输出吗？默认不能。抽象类不是可实例化的运行时入口。

### 1.2 导航上的落点

不建议直接把现有三层页面无条件扩成四层。推荐：

```text
项目页
  └─ 模块页（类节点 + 自由函数节点）
       └─ 类焦点页（方法节点 + 方法关系）
            └─ 函数执行流页（方法内部）
```

类焦点页是 ModuleGraph 的一个聚焦投影，不是重新定义一套语义。  
模块页默认显示“折叠的类节点”；类焦点页负责展开方法。这样既保留类作为语义容器的地位，也避免 18 个方法直接铺在模块页。

后续可以在模块页增加“内联展开类”能力，但第一版优先使用类焦点页，因为当前布局是 Python 预计算 + 确定性正交路由，类焦点页更容易复用现有宏布局。

## 2. 调研结论

### 2.1 Sourcetrail（已归档）

来源：https://github.com/CoatiSoftware/Sourcetrail

其文档明确把类作为可展开节点：

- 类节点默认显示成员；
- 成员可以展开/收起；
- “默认只显示有关系的成员”；
- 边可以按关系类型批量折叠成 bundle；
- 图聚焦当前选中符号，展示其入边和出边邻域。

对我们的启示：

- 类节点必须具有“容器 + 可展开成员”的语义；
- 模块页不应无条件展示所有方法；
- 类焦点视图本质上是一个聚焦邻域，而不是另一套数据模型。

### 2.2 CodeViz AI（Ansh-san/codeviz-ai）

来源：https://github.com/Ansh-san/codeviz-ai

其 Python/Java/TS 解析器输出：

- `classNode` 与 `functionNode` 并列；
- 方法节点通过 `membership` 边连接到类节点；
- 方法带有 `containingClass`；
- 前端使用 ELK 的 `INCLUDE_CHILDREN`，把方法作为类的子节点参与层级布局；
- 类节点支持 collapse/expand。

对我们的启示：

- 数据模型可以是**统一符号图**：类、方法、自由函数、导入都是节点，只是 `kind` 不同；
- `contains` / `membership` 是结构关系，不应和 `calls` 混为一类；
- 如果以后做内联展开，ELK/层级布局是成熟参考。

### 2.3 cgviz

来源：https://github.com/qlinhta/cgviz

其架构特点：

- 读取只读的 CodeGraph SQLite 数据库；
- 节点有 `kind`、`qualified_name`、`visibility`、`is_abstract`、`is_static` 等元数据；
- 边有 `kind`（如 `calls`、`imports`、`instantiates`、`extends`、`contains`）；
- 支持 focus mode、调用图/继承图/结构图等视图切换；
- 提供 impact analysis、trace path 查询。

对我们的启示：

- 不要为“类页”再造一套孤立模型，应该使用统一的符号节点/边，再按视图过滤；
- `kind` 和 `edge kind` 应该显式化，而不是塞进一个模糊的 `primaryType`；
- 类焦点页可以理解为 ModuleGraph 上的 focus 子图。

### 2.4 codeglass（PyPI `codeglass` / pylens）

来源：https://pypi.org/project/codeglass/0.1.2/

公开包中确认：

- `Symbol.kind` 包含 `function`、`class`、`method`、`interface`、`module` 等；
- `Symbol.parent` 表示所属类；
- `TypeHierarchyResult` 包含 `bases`、`subclasses`、`is_abstract`；
- 提供 `get_symbols`、`get_import_graph`、`get_call_graph`、`get_type_hierarchy` 等操作。

对我们的启示：

- 类/方法/接口应有统一 `kind`；
- `parent` 或 `ownerClassId` 是必须字段；
- 抽象类信息至少包括 `is_abstract`、`bases`、`subclasses`；
- 不必把所有信息都塞进一张图，可以提供按需查询视图。

### 2.5 codescope / Scope

来源：https://pypi.org/project/codescope/1.0.1/

公开的 `codescope` 包实际是 Adrenaline Scope，主要能力是：

- LSP + AST 调用图；
- definitions / references / calltree；
- 支持多语言；
- 后续计划包括子图提取、增量图更新等。

本次公开资料中未确认其存在 “`COMPOSES` / `AGGREGATES` / `INHERITS`” 三分类 API。  
因此组合/聚合关系可以借鉴 UML 思想，但不应把该说法当作已验证的实现依据。

### 2.6 CortexPlexus

来源：https://github.com/DT-Tuan/cortexplexus

其公开说明包含：

- 统一知识图谱：类、方法、调用图、DI、API 路由等；
- `get_class_hierarchy`：方向性继承/实现遍历，强调“no sibling bleeding”；
- `get_implementations`：查找接口实现；
- `get_callers` / `get_callees`；
- `get_dependencies` / `get_impact_analysis`。

对我们的启示：

- 抽象类/接口的查询应该是有方向的，不应把兄弟类混入结果；
- 调用抽象方法时，应返回实现候选，而不是伪造唯一直接目标；
- 类层次、调用关系、依赖关系应该是可区分的查询语义。

### 2.7 Emerge

来源：https://github.com/glato/emerge

Emerge 把图明确拆成不同分析视图：

- file dependency graph；
- entity dependency graph；
- inheritance graph；
- complete graph（dependency + inheritance 的并集）。

对我们的启示：

- 类依赖图和类继承图应当可以分别查看；
- 后续可以采用“视图切换”而不是把结构关系混进调用图；
- 当前 ArchMap 已经有 `ProjectGraph` / `ModuleGraph` / `FunctionFlow` 的多投影传统，适合继续扩展。

### 2.8 Understand / Structure101 / Lattix / Stan4j

这些商业工具的开源实现不可直接复用，但其设计方向可以采纳：

- Understand：不同粒度拆成不同图；类通常放在 UML/类型层级，函数放在控制流图；
- Structure101 / Lattix：用 DSM 或依赖矩阵避免“边界到所有节点”的启发式污染；
- Stan4j：类级依赖需要独立视图。

ArchMap 不应照搬其 UI，但应采纳其核心原则：

1. 类、方法、执行流是不同语义；
2. 继承、组合、调用、数据依赖不应混在一种边里；
3. 入口应显式声明，而不是从“没有入边”反推。

## 3. 推荐的数据模型

### 3.1 统一符号节点

建议把类、方法、自由函数统一为符号节点，并增加语义字段：

```json
{
  "id": "cls:menu_system.MenuSystem",
  "kind": "class",
  "name": "MenuSystem",
  "qualifiedName": "menu_system.MenuSystem",
  "moduleId": "menu",
  "classKind": "service",
  "isAbstract": false,
  "parentId": null,
  "methodCount": 18,
  "publicMethodIds": [],
  "entryMethodIds": [],
  "bases": [],
  "decorators": [],
  "file": "menu_system.py",
  "line": 1,
  "note": ""
}
```

方法节点：

```json
{
  "id": "fn:menu_system.MenuSystem.run",
  "kind": "method",
  "name": "run",
  "qualifiedName": "menu_system.MenuSystem.run",
  "moduleId": "menu",
  "ownerClassId": "cls:menu_system.MenuSystem",
  "methodKind": "public_api",
  "visibility": "public",
  "isAbstract": false,
  "isStatic": false,
  "isClassMethod": false,
  "functionFlowId": "fn:menu_system.MenuSystem.run"
}
```

自由函数保持 `kind: "function"`，没有 `ownerClassId`。

### 3.2 结构关系与行为关系分开

建议至少区分以下边类型：

**结构关系：**

- `contains`：模块 → 类、类 → 方法、函数 → 嵌套函数；
- `inherits`：类 → 基类；
- `implements`：类 → 接口/Protocol；
- `composes` / `aggregates`：后续从字段类型和构造赋值中提取。

**行为/依赖关系：**

- `calls`：方法/函数之间；
- `uses`：类型引用、字段访问等；
- `instantiates`：构造调用；
- `data`：数据依赖；
- `control`：边界控制关系，仅用于真正的入口/出口。

`primaryType` 目前只有 `call/data/control`，不足以表达类层次。建议新增 `kind` 和 `category` 字段，或者把结构关系放到单独的 `structuralEdges` 中。

### 3.3 ModuleGraph 与类焦点视图

第一版不必新增一份完全独立的 ClassGraph 数据源。推荐：

- `ModuleGraph.nodes` 包含类节点、自由函数节点、边界节点；
- 方法节点可以存在，但默认隐藏，带 `ownerClassId`；
- `ModuleGraph.edges` 保留 `contains`、`calls` 等真实关系；
- 类焦点视图从 ModuleGraph 中过滤出 `classId + methods + 相关边`，再由后端生成该视图的布局。

这样：

- 类页不是另一套事实来源；
- 后续做内联展开时，前后端数据结构不需要推翻；
- 模块页可以折叠类，类页展开方法。

## 4. 模块边界规则

### 4.1 停止根据入边/出边猜测入口

当前逻辑：

```text
没有内部入边的方法 -> module_input
没有内部出边的方法 -> module_output
```

必须替换为：

- 显式配置入口；
- 类的 `entryMethodIds`；
- 模块级公开函数的入口元数据；
- 无法确定时输出诊断，不要伪造边界。

### 4.2 边界边指向组件，而不是每个方法

推荐：

```json
{
  "from": "module:menu:input:0",
  "to": "cls:menu_system.MenuSystem",
  "role": "module_input",
  "viaMethodIds": ["fn:menu_system.MenuSystem.run"],
  "confidence": "medium"
}
```

这样：

- 菜单模块不再出现 17 条“模块输入 → 每个方法”；
- `MenuSystem` 是一个真实组件入口；
- 具体由哪个公开方法承接，仍然有证据可查；
- 类折叠/展开时视觉稳定。

### 4.3 抽象类不接边界

抽象类/接口：

- 不生成模块输入/输出边；
- 不生成类级 FunctionFlow；
- 可以生成 `inherits` / `implements` 结构边；
- 抽象方法只作为契约节点，不生成执行流；
- 抽象类中的具体模板方法仍可生成 FunctionFlow。

## 5. 抽象类与多态

### 5.1 类分类

建议增加：

```text
classKind: service | component | abstract | interface | dataclass | enum | exception | utility | model
```

检测依据：

- `abc.ABC` / `ABCMeta`；
- `typing.Protocol`；
- `@abstractmethod`；
- decorators（`dataclass`、`enum.Enum` 等）；
- 字段/方法结构。

### 5.2 多态调用

调用抽象方法时：

```json
{
  "resolved": false,
  "polymorphic": true,
  "candidates": [
    "fn:repo.StudentRepository.load",
    "fn:repo.TeacherRepository.load"
  ],
  "confidence": "medium"
}
```

不要生成一条“确定调用抽象方法”的边。  
类层次查询必须有方向，避免兄弟类污染。

## 6. UI 与路由

模块页：

- 类节点显示 `class` 标识、类类型、方法数、公开方法摘要；
- 类节点默认折叠；
- 自由函数节点保持原样；
- 双击/按钮进入类焦点页。

类焦点页：

- 展示该类的方法节点；
- 分组：公开 API、生命周期、内部方法；
- 方法间 `calls` / `data` 边；
- 继承/实现关系以结构边或详情区展示；
- 双击方法进入 FunctionFlow。

建议路由：

```text
#/project
#/module/:moduleId
#/module/:moduleId/class/:classId
#/module/:moduleId/class/:classId/function/:methodId
#/module/:moduleId/function/:functionId
```

## 7. 实施顺序

### Phase 0：数据契约

- `analysis.py` 的 `ClassInfo` 投影到 bundle；
- 增加 `class` 节点、`method` 节点、`ownerClassId`、`classKind`；
- 增加 `contains` 边；
- FunctionFlow 增加 `ownerClassId` 和 `methodKind`。

### Phase 1：模块页重构

- 类节点替代方法平铺；
- 自由函数与类节点并列；
- 模块边界改为 `entryMethodIds` 显式驱动；
- 无入口时输出 `ENTRY_AMBIGUOUS` 诊断，不生成假边。

### Phase 2：类焦点视图

- 从 ModuleGraph 过滤出类 + 方法 + 相关边；
- 复用现有宏布局算法生成类内方法布局；
- 增加类焦点路由与右侧详情；
- 方法节点双击进入 FunctionFlow。

### Phase 3：抽象类与继承

- 检测 abstract/interface/protocol；
- 增加 `inherits` / `implements`；
- 抽象方法契约视图；
- 多态调用 candidates；
- 类层次视图/筛选。

### Phase 4：类关系增强

- 从类型注解/构造赋值提取 `composes` / `aggregates`；
- 区分 `uses` / `instantiates`；
- 类级 impact / trace 查询；
- 可选内联展开类节点。

## 8. 验收标准

以 `student_system` 为例：

1. “菜单与交互”模块页只出现：
   - 模块输入/输出；
   - `MenuSystem` 类节点；
   - `get_display_width` 自由函数节点；
   - 不再出现 18 个方法平铺。
2. `MenuSystem` 类焦点页出现 18 个方法节点；
3. 模块输入/输出只连接到 `MenuSystem` 类节点，不连接到每个方法；
4. `Spinner` 模块页只出现 `Spinner` 类节点，`_animate` 不再直接接模块输入/输出；
5. 抽象类不生成模块边界，不生成类级执行流；
6. 同一份数据可生成模块页、类焦点页和 FunctionFlow；
7. `archmap check` 不产生新增 error；
8. 浏览器路由、类页拖拽、布局覆盖和重置可用。

## 9. 需要保持的兼容性

- 旧 `#/module/:id/function/:functionId` 路由保留；
- 旧 bundle 的读取尽可能兼容；
- 布局覆盖增加 `classes` 命名空间，不复用模块页坐标；
- 语义指纹加入类归属、类类型、继承/实现和显式入口；
- 旧布局覆盖若不匹配新几何，忽略或提示重置。

## 10. 下一步

先实现 Phase 0 + Phase 1，不先改类页 UI。  
先用 `student_system` 重建，确认：

- 类节点数量正确；
- 模块边界边数量显著下降；
- 方法归属正确；
- 抽象类/继承信息可输出；
- 现有函数执行流和布局校验仍然通过。

数据模型验证通过后，再做类焦点页。
