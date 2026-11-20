# 项目约定

本项目的架构、契约、编码和测试约束以 `约定编程` Skill v2.0 为基线，以下是项目自身的补充。

## 分层与依赖

```text
entry/interface   cli.py, renderer.py, input_parser.py, __main__.py, main.py
        ↓
application       game.py（GomokuGame、TurnOutcome、MoveSelector 协议）
        ↓
domain/model      board.py, models.py
        ↑
adapter           ai.py（SimpleAiPlayer 实现 MoveSelector）
config            config.py（GameConfig、SUPPORTED_MODES）
```

- 入口层只做输入解析、校验、渲染和退出码，不重新推导胜负或回合。
- 应用层负责回合推进、终局判定与电脑回合衔接；电脑落点必须来自注入的选择器。
- 领域层不访问终端、文件或随机数。
- 配置常量只在 `config.py` / `input_parser.py` 定义一次，其它模块引用而不复制。

## 关键契约

| 契约 | 位置 | 成功 | 失败 |
| --- | --- | --- | --- |
| 落子 | `Board.place_stone` | `MoveResult(is_accepted=True, ...)` | `is_accepted=False` + `reason`，不修改棋盘 |
| 人类回合 | `GomokuGame.play_human_move` | `TurnOutcome`（含电脑落点、终局状态） | 拒绝结果，不切换执子方 |
| 输入解析 | `parse_input` | `ParsedCommand(position/command)` | `ParsedCommand(error=ValidationError)` |
| 启动 | `cli.main` | 退出码 0 | 终端读写错误返回 1 |

- 回合归属的唯一事实来源是已落子数量：偶数步轮到黑棋，奇数步轮到白棋。
- 命令仅限单字母，坐标必须是「字母 + 数字」，两者形态不重叠。
- 所有外部输入（菜单、坐标、命令）都在入口层校验，非法输入只提示、不抛异常。

## 功能备注要求

- 每个模块、类、函数、方法、测试都必须有中文 docstring，包含目的、输入、输出、副作用与约束。
- 修改行为时同步修改 docstring、测试与 README。

## 验证方式

```bash
python3 -m pytest tests -q          # 单元 + 端到端测试
python3 -m compileall -q gomoku     # 语法检查
printf '2\nH8\nq\nn\n' | python3 main.py   # 手工冒烟
```

项目未引入 mypy/ruff，如需静态检查请先确认依赖必要性（Skill 第 10 节）。
