"""棋盘领域规则测试。

职责：验证落子合法性、五连判定、平局与不可变契约。
边界：只覆盖领域层，不涉及输入解析或终端渲染。
"""
from __future__ import annotations

import pytest

from gomoku.board import Board
from gomoku.models import Position, Stone


def _place(board: Board, positions: list[Position], stone: Stone):
    """在棋盘上依次落一批同色棋子并返回最后一个结果。

    输入：棋盘、坐标列表、棋子颜色。
    输出：最后一次 ``MoveResult``。
    副作用：修改棋盘。
    约束：调用方须保证坐标均合法且未被占用。
    """
    result = None
    for position in positions:
        result = board.place_stone(position, stone)
    return result


def test_place_stone_updates_board_and_history() -> None:
    """验证空位落子成功、写入棋盘并记录最后一步。"""
    board = Board(size=15, win_length=5)
    result = board.place_stone(Position(7, 7), Stone.BLACK)

    assert result.is_accepted
    assert not result.is_win
    assert board.stone_at(Position(7, 7)) is Stone.BLACK
    assert board.move_count == 1
    assert board.last_move == (Stone.BLACK, Position(7, 7))


def test_place_stone_rejects_out_of_bounds_without_state_change() -> None:
    """验证越界落子被拒绝且棋盘保持为空。"""
    board = Board(size=15, win_length=5)
    result = board.place_stone(Position(15, 0), Stone.BLACK)

    assert not result.is_accepted
    assert "越界" in result.reason
    assert board.move_count == 0


def test_place_stone_rejects_occupied_cell() -> None:
    """验证同一格重复落子被拒绝，先落的棋子不被覆盖。"""
    board = Board(size=15, win_length=5)
    board.place_stone(Position(3, 3), Stone.BLACK)
    result = board.place_stone(Position(3, 3), Stone.WHITE)

    assert not result.is_accepted
    assert board.stone_at(Position(3, 3)) is Stone.BLACK
    assert board.move_count == 1


@pytest.mark.parametrize(
    ("start", "step"),
    [
        (Position(7, 3), Position(0, 1)),  # 横向
        (Position(3, 7), Position(1, 0)),  # 纵向
        (Position(3, 3), Position(1, 1)),  # 主对角
        (Position(3, 11), Position(1, -1)),  # 副对角
    ],
)
def test_place_stone_detects_five_in_a_row(start: Position, step: Position) -> None:
    """验证横、竖、两条斜线方向连成五子即判胜并给出获胜连线。"""
    board = Board(size=15, win_length=5)
    positions = [Position(start.row + step.row * i, start.col + step.col * i) for i in range(5)]
    result = _place(board, positions, Stone.BLACK)

    assert result.is_win
    assert result.winner is Stone.BLACK
    assert len(result.winning_line) >= 5


def test_gapped_line_is_not_a_win() -> None:
    """验证中间断开的同色棋子不构成五连。"""
    board = Board(size=15, win_length=5)
    positions = [Position(7, 3), Position(7, 4), Position(7, 6), Position(7, 7), Position(7, 8)]
    result = _place(board, positions, Stone.BLACK)

    assert result.is_accepted
    assert not result.is_win


def test_overlong_line_still_wins() -> None:
    """验证连成六子时同样判胜，且连线包含全部连续棋子。"""
    board = Board(size=15, win_length=5)
    positions = [Position(7, col) for col in range(2, 8)]
    result = _place(board, positions, Stone.BLACK)

    assert result.is_win
    assert len(result.winning_line) == 6


def test_board_reports_full_and_no_available_positions() -> None:
    """验证填满棋盘后 ``is_full`` 为真且无空位。"""
    board = Board(size=3, win_length=3)
    colors = [Stone.BLACK, Stone.WHITE]
    index = 0
    for row in range(3):
        for col in range(3):
            if (row, col) == (1, 1):
                continue  # 中心留空，避免提前出现三连
            board.place_stone(Position(row, col), colors[index % 2])
            index += 1
    before = board.is_full()
    board.place_stone(Position(1, 1), Stone.BLACK)

    assert not before
    assert board.is_full()
    assert board.available_positions() == []


def test_available_positions_returns_copy(small_board: Board) -> None:
    """验证 ``available_positions`` 返回新列表，外部修改不影响棋盘。"""
    positions = small_board.available_positions()
    positions.clear()

    assert len(small_board.available_positions()) == 25


def test_stone_opponent_and_display_are_consistent() -> None:
    """验证黑白互换与显示字符符合展示契约。"""
    assert Stone.BLACK.opponent is Stone.WHITE
    assert Stone.WHITE.opponent is Stone.BLACK
    assert Stone.BLACK.display == "X"
    assert Stone.WHITE.display == "O"
