"""电脑对手策略测试。

职责：验证电脑优先取胜、优先封堵、无空位时返回 None 的契约。
边界：只测试落点选择，不测试终端交互。
"""
from __future__ import annotations

import random

from gomoku.ai import SimpleAiPlayer
from gomoku.board import Board
from gomoku.models import Position, Stone


def _fill(board: Board, positions: list[Position], stone: Stone) -> None:
    """批量落子以构造测试局面。

    输入：棋盘、坐标列表、棋子颜色。
    输出：无。
    副作用：修改棋盘。
    约束：坐标须合法且为空位。
    """
    for position in positions:
        board.place_stone(position, stone)


def test_ai_takes_immediate_win(seeded_ai: SimpleAiPlayer) -> None:
    """验证电脑有四连时选择直接连成五子的位置而不是其它位置。"""
    board = Board(size=15, win_length=5)
    _fill(board, [Position(7, 3), Position(7, 4), Position(7, 5), Position(7, 6)], Stone.WHITE)
    _fill(board, [Position(9, 9), Position(9, 10)], Stone.BLACK)

    chosen = seeded_ai.choose_move(board, Stone.WHITE)

    assert chosen in (Position(7, 2), Position(7, 7))


def test_ai_blocks_opponent_four(seeded_ai: SimpleAiPlayer) -> None:
    """验证电脑在己方无胜势时会封堵对手的四连。"""
    board = Board(size=15, win_length=5)
    _fill(board, [Position(5, 5), Position(5, 6), Position(5, 7), Position(5, 8)], Stone.BLACK)

    chosen = seeded_ai.choose_move(board, Stone.WHITE)

    assert chosen in (Position(5, 4), Position(5, 9))


def test_ai_opens_at_center_on_empty_board(seeded_ai: SimpleAiPlayer) -> None:
    """验证空棋盘时电脑选择天元中心点。"""
    board = Board(size=15, win_length=5)

    assert seeded_ai.choose_move(board, Stone.WHITE) == Position(7, 7)


def test_ai_returns_none_when_board_full() -> None:
    """验证棋盘已满时电脑返回 None 表达无可用落点。"""
    board = Board(size=3, win_length=4)
    # 轮流填满 3×3 棋盘；win_length=4 保证不会中途判胜，从而走完整盘。
    colors = [Stone.BLACK, Stone.WHITE]
    for index, (row, col) in enumerate((r, c) for r in range(3) for c in range(3)):
        board.place_stone(Position(row, col), colors[index % 2])
    ai = SimpleAiPlayer(rng=random.Random(0))

    assert ai.choose_move(board, Stone.WHITE) is None


def test_ai_move_is_always_legal(seeded_ai: SimpleAiPlayer) -> None:
    """验证候选点中选出的落点必定在棋盘内且为空位。"""
    board = Board(size=9, win_length=5)
    _fill(board, [Position(4, 4), Position(3, 3)], Stone.BLACK)
    _fill(board, [Position(4, 5)], Stone.WHITE)

    for _ in range(10):
        chosen = seeded_ai.choose_move(board, Stone.WHITE)
        assert chosen is not None
        assert board.in_bounds(chosen)
        assert not board.is_occupied(chosen)
