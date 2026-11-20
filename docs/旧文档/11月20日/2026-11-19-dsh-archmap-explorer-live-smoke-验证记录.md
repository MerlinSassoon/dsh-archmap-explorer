# DSH ArchMap Explorer 0.2.0 真实宿主模型 Live Smoke 验证记录

> 状态：宿主模型主链路通过；发现行为验收、dispatchHint 契约和注解可信度等后续项<br>
> 记录日期：2026-11-19<br>
> 插件：`dsh-archmap-explorer` 0.2.0 / 标签 `dsh-plugin-v0.2.0`<br>
> Python 核心：ArchMap 2.6.0 / bundle schema 6.4<br>
> 目标 DSH：0.2.2-rc.1<br>
> 验证样本：`学生管理系统_v2`<br>
> 过程会话：`session-9dbba26f-32c0-49c0-a661-215c9fe486cb`<br>
> 评价会话：`session-43d4ad0c-6318-4145-ba1e-4b3d64cabf82`

## 1. 验证目的

补完 0.2.0 发布后唯一未完成的“真实 DSH Web 宿主模型 live smoke”，确认以下链路不是仅由 Node mock 覆盖：

```text
真实 DSH 会话
→ archmap_guide
→ archmap_build
→ archmap_query
→ archmap_annotate
→ llm-annotations.json
→ architecture.html 重新渲染
```

本记录只记录验证事实和后续问题，不代表这些后续问题已经修复。

## 2. 运行环境与规模

```text
DSH：0.2.2-rc.1
Agent preset：minimal
模型：deepseek-official / deepseek-flash
工作目录：/home/sasson/桌面/Project/dsh_project/学生管理系统_v2
```

过程会话包含 2 个 turn、52 个 step、58 次工具调用，记录时长约 755 秒。工具分布：

```text
bash             39
archmap_build     5
archmap_query     9
archmap_annotate  2
archmap_guide     3
```

评价会话为只读审阅，共 1 个 turn、16 个 step、32 次工具调用；没有修改项目文件，也没有运行 pytest/build。

## 3. 通过项

### 3.1 Guide / Skill fallback

在 minimal preset 下，`archmap_guide` 成功返回三份权威内容：

```text
code-conventions
config-generation
usage
```

这验证了原生 `skill` 工具不可用时的 fallback 送达路径。

### 3.2 Build 与 Query

最终构建结果：

```text
modules: 5
functions: 94
execution flows: 3
call sites: 382
diagnostics: 0 error, 0 warning, 1 info
```

实际调用并通过的查询：

```text
archmap_query check
archmap_query surfaces
archmap_query dsm
archmap_query trace
```

`trace` 最终成功返回：

```text
run_server: nodes=6 paths=5 unresolved=2 truncated=false
run_client: nodes=19 paths=35 unresolved=0 truncated=false
```

### 3.3 真实宿主模型注解

两次 `archmap_annotate` 均真实走通宿主模型：

```text
第一轮：
scope=all, refreshMode=missing
targets: total=100 selected=50 remaining=50
applied: 50, skipped: 0, rejected: 0
batches: 9
duration: 59.726s

第二轮：
scope=all, refreshMode=missing
targets: total=100 selected=50 remaining=0
applied: 50, skipped: 0, rejected: 0
batches: 9
duration: 50.073s
```

`100` 个节点为：

```text
项目节点 1 + 模块节点 5 + 函数节点 94
```

验证结果：

- `llm-annotations.json` 共有 100 条 `host-llm` 注解。
- 注解节点包含权威 `sourceHash`。
- `architecture.html` 中能找到 `llm-annotations.json` 里的注解文本。
- HTML 重新渲染成功。
- `maxNodes` 分页和 `refreshMode=missing` 的实际行为可用。

### 3.4 示例项目结构与测试基线

- 5 个模块：`student-records`、`student-api`、`student-client`、`app`、`tests`。
- 11 个 pytest 用例通过。
- 最终 `archmap check`：0 error / 0 warning。

## 4. 发现项

### 4.1 CLI 运行期回归未被 build/check 与 pytest 捕获

构建和 11 个测试通过后，用户手动执行：

```bash
python3 -m app.main client list
python3 -m app.main client get --student-id S001
python3 -m app.main client delete --student-id S001
```

分别出现：

```text
AttributeError: 'Namespace' object has no attribute 'student_id'
AttributeError: 'Namespace' object has no attribute 'name'
```

根因是不同 `argparse` 子命令生成的 Namespace 字段形状不一致，而 `main()` 无条件读取所有客户端字段。

该问题说明：

- 静态结构分析无法发现运行时 Namespace 形状错误；
- 现有测试没有覆盖 `main([...])` 到 `run_client()` 的 CLI 参数转发链路；
- `0 diagnostics` 只能说明结构和交叉引用通过，不能说明行为正确。

### 4.2 `dispatchHints` 的 warning 修复建议与实际效果不一致

首次构建出现 6 条 `POLYMORPHIC_CALL_CANDIDATES` warning，提示：

```text
keep the abstraction and add dispatchHints or explicit incomplete evidence
```

过程会话加入并修正 `dispatchHints` 后，build fingerprint 未变化，6 条 warning 仍存在。最终消除 warning 的方式是让 `JsonStudentRepository` 显式继承 `StudentRepository`，而不是 `dispatchHints`。

当前需要进一步确认：

- `dispatchHints` 是否只服务 execution flow 的 dispatch 投影；
- 它为什么没有影响 callSite 级 polymorphic warning；
- warning 文案是否应改成指向 callSite 解析或显式 incomplete 声明。

在该契约澄清前，不应宣称 `dispatchHints` 可以消除所有 polymorphic warning。

### 4.3 `trace` 起点 ID 需要 canonical 形式

以下起点无法查询：

```text
app.main:run_server
```

返回：

```text
error: trace start not found
```

改用 canonical function id 后成功：

```text
fn:app.main.run_server
```

查询能力本身可用，但起点归一化或错误提示仍有改进空间。

### 4.4 execution entrypoint 与 flow 叙事

过程中通过把 `main` 加入 `executionEntrypoints`，才消除：

```text
EXECUTION_ONLY_NOT_IN_FLOW
```

最终生成 3 条 flow：

```text
main()
run_server()
run_client()
```

这会带来一定的叙事重复：`main()` 已包含 server/client 分支，另外两条 flow 又以同层卡片重复表达。

### 4.5 注解成本与语义可信度

- 100 个节点分两轮完成，共约 110 秒、18 个 batch。
- 评价会话统计：注解约 75KB，docstring 约 11.9KB，注解约为 docstring 的 6.3 倍。
- 注解内容大量复述 docstring；同模型生成代码和注解容易形成自我复述。
- 已观察到个别注解语义偏差。

因此注解技术链路通过，但不能直接视为独立、可验证的架构文档。

### 4.6 能力面、角色与 scope 预算的产品问题

评价会话补充发现：

- 34 个 capability API 全部来自 `naming` 推断，confidence 为 medium。
- 测试替身进入能力面；契约与实现存在 API 重复。
- `StudentClientManager` 被推断为低置信度 `adapter`，与门面职责不符。
- `run_client` scope 只有 24 个节点，被预算截断，omitted 3。
- 约 1,926 行源码对应约 1.6MB JSON 和 1.4MB HTML。
- 项目没有 CI/pre-commit，build/check 仍是手动动作。

这些是后续产品化问题，不影响本次 live smoke 的主链路结论。

## 5. 本次未覆盖

以下能力仍由自动化测试覆盖，但没有在本次真实会话中触发：

- 模型非法 JSON 后仅修复一次；
- 取消信号是否同时终止模型流与 Python 子进程；
- 超时后的 `ARCHMAP_TIMEOUT`；
- workspace 路径越界；
- `refreshMode=stale`；
- `archmap_query impact`；
- `archmap_query method`；
- 大型项目性能、bundle 体积和查询延迟。

## 6. 结论

本次 live smoke 可以确认：

1. 真实 DSH 宿主模型路由、`archmap_guide`、`archmap_build`、`archmap_query`、`archmap_annotate` 和 HTML 重渲染主链路已经走通。
2. 0.2.0 发布交接中“真实宿主模型 live smoke 未完成”的阻塞项可以关闭。
3. live smoke 同时暴露了 CLI 行为验收、`dispatchHints` 契约、trace ID 归一化、flow 叙事、能力面策展和注解可信度等后续问题。
4. 不移动 `dsh-plugin-v0.2.0` 标签；后续修复应新增版本和标签。

## 7. 后续验收建议

- 增加一键 `verify`：pytest + build + check + CLI 入口级 E2E。
- 为 `main([...])` 的各客户端子命令增加参数转发测试。
- 澄清 `dispatchHints` 与 callSite polymorphic warning 的契约关系。
- 为 `trace` 起点增加唯一简写归一化和候选提示。
- 评估能力面显式策展、测试模块排除和 Provider Role low-confidence 提示。
- 将注解结构化到可验证字段，并保留源码行证据。
