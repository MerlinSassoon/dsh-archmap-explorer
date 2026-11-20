"""对局用例编排测试。

职责：验证回合交替、终局拒绝落子、重开重置与人机模式衔接。
边界：不涉及终端输出，只断言用例层返回的结果契约。
"""
from __future__ import annotations

from gomoku.game import GomokuGame
from gomoku.models import Position, Stone


def test_human_vs_human_alternates_stones(human_vs_human_game: GomokuGame) -> None:
    """验证双人模式下黑先白后按回合交替。"""
    game = human_vs_human_game
    first = game.play_human_move(Position(7, 7))
    second = game.play_human_move(Position(8, 8))

    assert first.move_result.is_accepted
    assert second.move_result.is_accepted
    assert game.board.stone_at(Position(7, 7)) is Stone.BLACK
    assert game.board.stone_at(Position(8, 8)) is Stone.WHITE
    assert game.current_stone is Stone.BLACK
    assert game.is_human_turn


def test_rejected_move_does_not_advance_turn(human_vs_human_game: GomokuGame) -> None:
    """验证非法落子被拒绝且不切换执子方。"""
    game = human_vs_human_game
    game.play_human_move(Position(7, 7))
    rejected = game.play_human_move(Position(7, 7))

    assert not rejected.move_result.is_accepted
    assert game.current_stone is Stone.WHITE
    assert game.board.move_count == 1


def test_win_is_reported_and_further_moves_rejected(human_vs_human_game: GomokuGame) -> None:
    """验证五连后报告胜者，并对后续落子返回拒绝结果。"""
    game = human_vs_human_game
    black = [Position(7, c) for c in range(3, 8)]
    white = [Position(9, c) for c in range(3, 7)]
    last = None
    for index, position in enumerate(black):
        last = game.play_human_move(position)
        if index < len(white):
            game.play_human_move(white[index])

    assert last is not None
    assert last.is_game_over
    assert last.game_winner is Stone.BLACK
    after = game.play_human_move(Position(0, 0))

    assert not after.move_result.is_accepted
    assert after.is_game_over


def test_full_board_ends_game() -> None:
    """验证 3×3 棋盘被填满后对局结束，且不再接受落子。"""
    game = GomokuGame(size=3, win_length=4)
    moves = [(row, col) for row in range(3) for col in range(3)]
    outcome = None
    for row, col in moves:
        outcome = game.play_human_move(Position(row, col))
        if game.is_game_over:
            break

    assert outcome is not None
    assert game.is_game_over
    assert outcome.is_game_over
    after = game.play_human_move(Position(0, 0))
    assert not after.move_result.is_accepted


def test_start_new_game_resets_state(human_vs_human_game: GomokuGame) -> None:
    """验证重开后棋盘清空、执子方回到黑棋且胜者被清除。"""
    game = human_vs_human_game
    game.play_human_move(Position(7, 7))
    game.start_new_game()

    assert game.board.move_count == 0
    assert game.current_stone is Stone.BLACK
    assert game.winner is None
    assert not game.is_game_over


def test_ai_mode_plays_reply_after_human(human_vs_ai_game: GomokuGame) -> None:
    """验证人机模式下一手人类落子后电脑立即落一子并交还回合。"""
    game = human_vs_ai_game
    outcome = game.play_human_move(Position(7, 7))

    assert outcome.move_result.is_accepted
    assert outcome.ai_position is not None
    assert game.board.stone_at(outcome.ai_position) is Stone.WHITE
    assert game.board.move_count == 2
    assert game.current_stone is Stone.BLACK
    assert game.is_human_turn


def test_human_move_rejected_when_ai_turn(monkeypatch) -> None:
    """验证当前轮到电脑时，人类落子请求被拒绝且棋盘不变。"""
    class SkipAi:
        """不会自动回应的电脑桩，用于让对局停留在电脑回合。"""

        def choose_move(self, board, stone):
            """返回 None 表示本轮不落子，从而保持电脑回合。"""
            return None

    game = GomokuGame(size=15, win_length=5, ai_player=SkipAi())
    first = game.play_human_move(Position(7, 7))
    assert first.move_result.is_accepted
    assert not game.is_human_turn

    rejected = game.play_human_move(Position(8, 8))

    assert not rejected.move_result.is_accepted
    assert game.board.stone_at(Position(8, 8)) is None


def test_human_vs_human_has_no_ai() -> None:
    """验证双人模式不会触发电脑落子，且对外暴露正确的模式标志。"""
    game = GomokuGame(size=15, win_length=5)

    assert not game.is_vs_ai
    assert game.play_ai_move() is None
    assert game.human_stone is Stone.BLACK
