# ArchMap 分支交接与返回指引

> 用途：记录阶段开发分支、基线和安全返回路径。
> 最后更新：2026-11-18

## 当前分支关系

```text
p2.4-main-flow
  └─ p3-inheritance-polymorphism（40ab924）
       └─ p4-impact-trace-surfaces（P4 开发分支，当前）
```

| 分支 | 基线与用途 | 状态 |
|---|---|---|
| `p2.4-main-flow` | P2.4 完成基线，提交 `008d3c6` | 只读参考 |
| `p3-inheritance-polymorphism` | P3 继承、实现、继承 API、多态 | P3 已完成，保留 |
| `p4-impact-trace-surfaces` | 从 P3 直接切出；P4 结构关系、user surface、impact/trace、DSM | P4 开发中/待验收 |

按要求，P4 未等待 P3 合入基线，直接在 P3 分支上继续。

## 返回与恢复命令

```bash
# 回到 P2.4 基线
git switch p2.4-main-flow

# 回到 P3
git switch p3-inheritance-polymorphism

# 回到 P4
git switch p4-impact-trace-surfaces
```

## 合入建议

P4 验收通过后，可先将 `p4-impact-trace-surfaces` 合入 `p3-inheritance-polymorphism`，再整体合入 `p2.4-main-flow`。在合入前不要删除中间分支，便于回滚和对比。

详细状态见 [`HANDOFF-P3.md`](HANDOFF-P3.md) 与 [`HANDOFF-P4.md`](HANDOFF-P4.md)。
