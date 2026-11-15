# ArchMap v1 验收记录

日期：2026-11-15  
样例：`student_system`  
产物：`.archmap/student_system/architecture.json`、`architecture.html`

## 样例构建结果

```text
project:   student_system
modules:   5
functions: 45
nodes:     468
edges:     612
macroEdges:95
maxRank:   22
diagnostics: error=0 warning=0 info=5
```

- 项目页：5 个逻辑模块、项目输入/输出、8 条宏观关系。
- 模块页：模块输入/输出、函数节点、真实函数调用边界。
- 函数页：真实 AST 生成的 ENTRY/EXIT、步骤、分支、循环、数据流和布局。
- 入口：`main.server`、`main.client`、`main.__main__`。
- 源码备注提取、LLM 注解占位与侧车读取路径已接通。
- 布局覆盖保存、重置、导出和导入已实现。

## 自动化验证

```bash
python3 -m archmap check .archmap/student_system/architecture.json
ARCHMAP_RUN_BROWSER=1 python3 -m pytest -q
```

结果：

- bundle 结构、交叉引用、函数不变量和布局校验通过。
- `12 passed`（含 Firefox Headless WebDriver 冒烟测试）。
- 浏览器测试覆盖：项目页、模块页、函数页、模块展开、Hash 刷新恢复。

## 性能

- `student_system` 完整 build：约 0.29s。
- 1000 节点函数 layout：约 17ms。
- 单文件 HTML：约 785KB，无 CDN、外部字体、外部图片或网络请求。

## 未实现 / 后续

- 未实现 ArkTS 前端，但已提供 `LanguageFrontend` 协议、显式语言注册表和 canonical IR 扩展边界。
- `try/except/finally` 与 `match` 按 v1 策略简化，并输出诊断。
- 未实现 LLM 自动生成，仅读取并展示侧车注解。
- 函数内 call step 保留目标函数 ID 和跳转能力，但三层页面导航仍是主要路径。
