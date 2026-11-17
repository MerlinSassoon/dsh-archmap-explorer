# ArchMap P3 交接文档：继承、实现、继承 API 与多态

> 日期：2026-11-18<br>
> 版本：ArchMap 1.7.0 / bundle schema 3.7<br>
> 开发分支：`p3-inheritance-polymorphism`<br>
> 基线分支：`p2.4-main-flow`（提交 `008d3c6`）<br>
> 状态：P3 核心能力已完成；P4 未开始。

---

## 0. 分支信息与返回方式

P3 开发从 P2.4 完成基线切出：

```text
p2.4-main-flow                 基线，可随时返回
  └─ p3-inheritance-polymorphism  P3 开发与验收
```

```bash
# 返回 P2.4 基线
git switch p2.4-main-flow

# 切回 P3 分支
git switch p3-inheritance-polymorphism
```

分支交接总表见 [`BRANCHES.md`](BRANCHES.md)。

---

## 1. P3 目标与完成范围

P3 的目标是把“类名列表”升级为可验证的类型契约层，并让抽象/协议方法的调用表达为多态候选，而不是伪造唯一调用边。

已完成：

- 基类表达式解析：同模块、跨模块、相对导入、导入别名、包 re-export；
- `inherits` / `implements` canonical 结构关系；
- `baseClassIds` / `subclassIds` / `mroClassIds` / `abstractMethodNames`；
- 有效抽象性：子类未实现抽象方法时保持 abstract，不能用“没有 own abstract method”误判为具体类；
- 继承 API：子类 `providedApis` 包含继承能力，并保留声明来源与 override 来源；
- 抽象/Protocol 调用生成多态 candidates：`resolved=false`、`toFunctionId=null`、候选函数 ID 集合、`dispatchKind=polymorphic`；
- 主流程把多态候选投影为 `candidateSource=polymorphic` 的 dispatch 节点与低置信度虚线 composition；
- FunctionDetail 增加 override / overridden-by / polymorphic callers / polymorphic callees；
- Module/Project 数据增加 `typeRelations`，模块契约条展示类型关系，类详情展示 hierarchy；
- validator 增加类型关系端点、重复、自环、环、模块投影一致性和多态调用不变量；
- bundle schema 从 3.6 升级到 3.7。

P3 不做：

- 不新增类焦点页或类内方法图；
- 不把类放进主流程执行节点；
- 不改变功能模块边界规则；
- 不把多态候选伪装成 high-confidence call；
- 不引入序列协议、组合/聚合关系或 impact/trace；这些留给 P4 或后续阶段。

---

## 2. 数据契约增量

### 2.1 类型关系

`projectGraph.typeRelations` 与 `moduleGraphs[].typeRelations`：

```json
{
  "id": "type:cls:app.impl.EchoWorker:implements:cls:app.base.Worker",
  "kind": "implements",
  "fromClassId": "cls:app.impl.EchoWorker",
  "toClassId": "cls:app.base.Worker",
  "toClassName": "Worker",
  "moduleId": "impl",
  "targetModuleId": "base",
  "confidence": "high",
  "evidence": {"file": "app/impl.py", "line": 5}
}
```

- `kind` 只能是 `inherits` / `implements`。
- 只有当基类表达式解析到项目内 canonical class ID 时才生成关系。
- `implements` 用于抽象类或 Protocol/interface 目标；具体类目标使用 `inherits`。
- 外部/第三方基类不生成结构边，保留在类节点的 `unresolvedBases`。

### 2.2 类层次字段

类节点与 `usage` 增加：

```json
{
  "baseClassIds": ["cls:app.base.Worker"],
  "subclassIds": [],
  "mroClassIds": ["cls:app.impl.EchoWorker", "cls:app.base.Worker"],
  "unresolvedBases": [],
  "abstractMethodNames": [],
  "declaredApiCount": 1,
  "inheritedApiCount": 2
}
```

规则：

- `mroClassIds` 为 best-effort C3；解析冲突时确定性 fallback，并由 validator 报环/异常。
- `subclassIds` 是直接子类，不做兄弟扩散。
- 类节点 `isAbstract` 是有效抽象性，不再只是“自身是否直接继承 ABC”。

### 2.3 继承 Capability

继承 API 仍归属子类 Provider，但保留来源：

```json
{
  "id": "api:cls:app.impl.EchoWorker:inherited:api:fn:app.base.Worker.label",
  "display": "EchoWorker.label()",
  "providerId": "cls:app.impl.EchoWorker",
  "providerName": "EchoWorker",
  "inherited": true,
  "declaredInProviderId": "cls:app.base.Worker",
  "inheritedFromProviderId": "cls:app.base.Worker",
  "overridesCapabilityId": null,
  "evidenceFunctionIds": ["fn:app.base.Worker.label"],
  "functionId": "fn:app.base.Worker.label"
}
```

子类声明覆盖方法时：

```json
{
  "inherited": false,
  "declaredInProviderId": "cls:app.impl.EchoWorker",
  "overridesCapabilityId": "api:fn:app.base.Worker.run"
}
```

- 继承能力不重复计为子类 declared API。
- config/model/utility 仍不暴露模块 API。
- 代码证据始终指向真实声明函数，不伪造子类函数 ID。

### 2.4 多态 CallSite

```json
{
  "calleeText": "worker.run",
  "resolved": false,
  "toFunctionId": null,
  "polymorphic": true,
  "dispatchKind": "polymorphic",
  "candidates": [
    "fn:app.impl.EchoWorker.run",
    "fn:app.impl.LoudWorker.run"
  ],
  "confidence": "medium"
}
```

规则：

- 抽象/Protocol 方法调用不选一个目标冒充唯一调用。
- candidates 只沿目标类后代方向收集，不出现兄弟污染。
- 具体方法或 `super()` 直接调用仍是 static resolved。
- 多态候选进入主流程后使用低置信度 dashed composition。
- 本地候选集仍标记 `candidateSetComplete=false`，因为项目外实现不可知。

### 2.5 FunctionDetail 增量

```json
{
  "overrideOfFunctionId": "fn:app.base.Worker.run",
  "overriddenByFunctionIds": ["fn:app.impl.EchoWorker.run"],
  "polymorphicCallers": [],
  "polymorphicCallees": [],
  "polymorphicCallerCount": 0,
  "polymorphicCalleeCount": 0
}
```

---

## 3. 代码地图增量

| 文件 | P3 职责 |
|---|---|
| `archmap/frontends/python/type_utility.py` | Python 基类表达式解析、C3 MRO、有效抽象性、结构关系数据 |
| `archmap/model/analysis_model.py` | `ClassInfo` 类型层次字段 |
| `archmap/model/contract_model.py` | `ClassRelation`、继承 Capability 字段 |
| `archmap/model/call_model.py` | 多态 candidate / dispatchKind 字段 |
| `archmap/frontends/python/contract_utility.py` | 继承 Capability、override 关系、classUsage hierarchy |
| `archmap/frontends/python/call_utility.py` | MRO 方法解析、abstract/Protocol 多态 candidate、继承构造解析 |
| `archmap/frontends/python/detail_utility.py` | override / polymorphic callers/callees |
| `archmap/utility/main_flow_utility.py` | 多态 dispatch 投影 |
| `archmap/utility/graph_utility.py` | typeRelations、hierarchy 节点字段、统计 |
| `archmap/utility/validate_utility.py` | P3 结构关系与多态不变量 |
| `archmap/render/assets/app.js` / `app.css` | hierarchy 摘要、继承 API badge、多态调用与 composition 展示 |
| `tests/test_inheritance.py` | P3 专用回归 |
| `tests/fixtures/inheritance_demo/` | 跨模块 ABC/Protocol、继承 API、override、多态和主流程 fixture |

---

## 4. 验证与验收

```text
pytest:                 70 passed, 1 skipped
browser smoke:          1 passed（ARCHMAP_RUN_BROWSER=1）
schemaVersion:          3.7
self build/check:       OK
student build/check:    OK
inheritance build/check: OK
self stats:             6 modules / 26 classes / 199 functions / 2502 call sites
student stats:          7 modules / 52 functions / 265 call sites
inheritance stats:      3 modules / 6 classes / 13 functions / 10 call sites / 4 typeRelations / 2 polymorphicCalls
self diagnostics:       0
student diagnostics:    0
inheritance diagnostics: 0
```

P3 fixture 验收点：

- `EchoWorker implements Worker`、`EmailNotifier implements Notifier`；
- `SilentWorker` 未实现 `run`，保持 `isAbstract=true` 且 `classKind=abstract`；
- `EchoWorker.label()` 为 inherited capability，来源 `Worker.label`；
- `EchoWorker.run()` 标记 override `Worker.run`；
- `worker.run` 多态候选为 `EchoWorker.run` + `LoudWorker.run`，不包含 `SilentWorker.run`；
- `notifier.notify` 候选为 `EmailNotifier.notify`；
- 主流程有 2 个 polymorphic dispatch、3 条 low/dashed composition，功能模块边界无出边。

---

## 5. 已知边界与风险

- 仅解析项目内 canonical class；第三方/条件导入基类保留 unresolved，不生成结构边。
- 多态候选只覆盖项目内已解析后代；`candidateSetComplete=false`。
- 动态注入、运行时注册表、`getattr` 分发仍需显式 dispatch 配置。
- `super()` 的复杂多继承跳跃、元类和 `__getattr__` 代理不建模。
- 继承 Protocol 的结构化实现（结构性 subtyping）目前不做；仅解析显式基类。
- 继续遵守：不新增类焦点页；不把类塞进主流程；不让主流程穿透功能模块内部 utility。

---

## 6. P4 建议起点

P4 建议按以下顺序：

1. 角色感知的关系增强：`uses` / `instantiates` / `composes` / `aggregates`；
2. API/type/provider impact 与 trace 查询层；
3. user surface 识别与传播；
4. 可选 DSM；
5. 最后再考虑深层类关系可视化，仍不新增类焦点页。

P3 的 `typeRelations`、inherited capability 来源和 polymorphic candidates 是 P4 impact/trace 的前置事实，不应在 P4 中重新推导一套平行模型。
