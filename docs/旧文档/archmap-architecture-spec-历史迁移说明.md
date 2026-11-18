# ArchMap 架构规范历史迁移说明归档

> 归档日期：2026-11-19<br>
> 本文承接原 `docs/archmap-architecture-spec.md` 的 P2.3 识别策略与迁移原则，仅用于追溯。

## 6. 识别与发现策略

解析器采用双模式：

1. **规范模式**：文件名后缀和目录结构提供确定性的代码单元类型；
2. **兼容模式**：不符合规范时回退到通用 AST 启发式，并输出 diagnostics。

P2.3 先完成代码迁移，不在迁移过程中反复重写识别器。迁移完成后，再根据本规范实现规范模式识别：

```text
path + file suffix → code unit type
class/function shape → provider role refinement
entrypoint/config/contract/protocol evidence → derived role
visibility → default presentation
```

禁止继续使用“有循环 + 调用一个项目类 = manager”这类宽松规则作为主要判定依据。

## 7. P2.3 迁移原则

- 先冻结契约，再迁移代码；
- 先 config/model，再 utility，再 manager；
- 旧 import shim 最终已删除，所有内部引用使用新目录；
- CLI、bundle schema、HTML 行为保持稳定；
- utility 默认不进入主视图；
- 迁移完成后更新自举配置和文档；
- P3/P4 已在 P2.3 验收后完成，并继续遵守本规范。
