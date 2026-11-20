# 命令行五子棋

一个零第三方依赖的 Python 命令行五子棋小游戏，支持**人机对战**与**双人同屏对战**。

## 运行

```bash
python3 main.py
# 或
python3 -m gomoku
```

需要 Python 3.9+（开发环境为 3.10）。

## 玩法

- 黑棋先行，横、竖、斜任意方向先连成 5 子者胜；棋盘填满则平局。
- 落子输入格式为「列字母 + 行号」，例如 `H8`。列字母跳过 `I`，避免与数字 1 混淆。
- 对局中命令：

| 输入 | 作用 |
| --- | --- |
| `H8` | 在 H 列第 8 行落子 |
| `r` | 重开当前对局（黑棋先行） |
| `q` | 退出当前对局，回到主菜单 |

菜单中用 `1` 选择人机对战、`2` 选择双人对战、`0` 退出。

## 测试

```bash
python3 -m pytest tests -q
```

## 目录结构

```text
main.py                 脚本启动入口
gomoku/__main__.py      python -m gomoku 入口
gomoku/config.py        配置层：棋盘尺寸、连子数、模式常量
gomoku/models.py        领域数据契约：坐标、棋子、落子结果、错误对象
gomoku/board.py         领域层：棋盘状态与胜负判定
gomoku/ai.py            适配器：本地电脑对手策略
gomoku/game.py          应用层：对局用例编排
gomoku/input_parser.py  入口辅助：输入解析与边界校验
gomoku/renderer.py      入口展示：纯文本棋盘渲染
gomoku/cli.py           入口层：菜单、交互循环、退出码
tests/                  单元与端到端测试
docs/CONVENTIONS.md     项目约定（架构、契约、验证方式）
```

依赖方向：`cli → game → board/models`，`cli → renderer/input_parser`，`game → ai`（通过协议），
`config` 与 `models` 不被任何下层反向依赖。
