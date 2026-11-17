# ArchMap 分支交接与返回指引

> 用途：记录多阶段并行/串行开发时的基线分支、当前开发分支和安全返回路径。
> 最后更新：2026-11-18

## 当前分支关系

```text
p2.4-main-flow                 P2.4 完成基线，保持可随时返回
  └─ p3-inheritance-polymorphism  P3 开发分支（继承/实现/继承 API/多态 candidates）
```

| 分支 | 基线与用途 | 状态 |
|---|---|---|
| `p2.4-main-flow` | P2.4 完成基线；基线提交 `008d3c6` | 只读参考，不在其上继续 P3 |
| `p3-inheritance-polymorphism` | 从 `p2.4-main-flow` 新建；P3 开发与验收 | P3 已完成，待合入 |

## 返回与恢复命令

```bash
# 返回 P2.4 基线
git switch p2.4-main-flow

# 回到 P3 开发分支
git switch p3-inheritance-polymorphism
```

## 合入建议

P3 验收通过后，优先将 `p3-inheritance-polymorphism` 合入 `p2.4-main-flow`，确认自举与样例回归后，再进入 P4 分支。P3 与 P4 不在同一分支并行开发。

详细 P3 状态见 [`HANDOFF-P3.md`](HANDOFF-P3.md)。
