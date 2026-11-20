"""棋盘渲染测试。

职责：验证渲染输出包含正确的坐标表头、棋子符号、最近一步与获胜标记。
边界：只断言字符串内容，不依赖真实终端尺寸。
"""
from __future__ import annotations

from gomoku.board import Board
from gomoku.models import Position, Stone
from gomoku.renderer import BoardRenderer, describe_stone, format_move_hint


def _board_with_stone() -> Board:
    """构造一个含一颗黑棋的 9 路棋盘。

    输入：无。
    输出：黑棋位于 (0, 0) 的棋盘。
    副作用：无。
    约束：供渲染断言使用。
    """
    board = Board(size=9, win_length=5)
    board.place_stone(Position(0, 0), Stone.BLACK)
    return board


def test_render_contains_headers_and_stones() -> None:
    """验证渲染结果包含列字母、行号与棋子符号。"""
    text = BoardRenderer(_board_with_stone()).render()

    lines = text.splitlines()
    assert lines[0].split() == list("ABCDEFGHJ")
    assert lines[1].startswith(" 1")
    assert "X" in text
    assert text.count(lines[0]) == 2  # 顶部与底部表头一致


def test_render_marks_last_move_and_winning_line() -> None:
    """验证最近一步与获胜连线分别使用 + 与 # 标记。"""
    board = Board(size=9, win_length=3)
    for col in range(3):
        board.place_stone(Position(0, col), Stone.BLACK)
    renderer = BoardRenderer(board)
    winning = tuple(Position(0, col) for col in range(3))

    text = renderer.render(last_move=Position(0, 2), winning_line=winning)

    assert "#+" in text
    assert renderer.render_legend().count("#") == 1


def test_describe_stone_and_hint() -> None:
    """验证棋子中文名称与坐标提示格式符合界面契约。"""
    assert describe_stone(Stone.BLACK) == "黑棋"
    assert describe_stone(Stone.WHITE) == "白棋"
    assert format_move_hint(Position(7, 7)) == "H8"
