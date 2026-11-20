"""测试公共 fixture。

职责：提供确定性棋盘、固定种子的电脑对手和字符串流，避免测试依赖随机数或终端。
边界：不包含被测业务逻辑，也不启动真实终端。
"""
from __future__ import annotations

import io
import random

import pytest

from gomoku.ai import SimpleAiPlayer
from gomoku.board import Board
from gomoku.config import GameConfig
from gomoku.game import GomokuGame


@pytest.fixture
def small_board() -> Board:
    """构造 5×5 棋盘。

    输入：无。
    输出：空棋盘实例，边长为 5。
    副作用：无。
    约束：每个测试得到独立实例，避免状态串扰。
    """
    return Board(size=5, win_length=5)


@pytest.fixture
def seeded_ai() -> SimpleAiPlayer:
    """构造使用固定随机种子的电脑对手。

    输入：无。
    输出：``SimpleAiPlayer``，随机选择可重复。
    副作用：无。
    约束：种子固定为 1234，仅用于测试稳定性。
    """
    return SimpleAiPlayer(rng=random.Random(1234))


@pytest.fixture
def human_vs_human_game() -> GomokuGame:
    """构造双人模式对局。

    输入：无。
    输出：15 路、无电脑对手的 ``GomokuGame``。
    副作用：无。
    约束：黑棋先行。
    """
    return GomokuGame(size=15, win_length=5)


@pytest.fixture
def human_vs_ai_game(seeded_ai: SimpleAiPlayer) -> GomokuGame:
    """构造人机模式对局。

    输入：由 ``seeded_ai`` 提供的确定性电脑对手。
    输出：电脑执白、人类执黑的 ``GomokuGame``。
    副作用：无。
    约束：依赖 fixture 顺序，pytest 保证依赖先构建。
    """
    return GomokuGame(size=15, win_length=5, ai_player=seeded_ai)


@pytest.fixture
def config() -> GameConfig:
    """构造默认游戏配置。

    输入：无。
    输出：``GameConfig()`` 默认值。
    副作用：无。
    约束：若默认值变化，评估各端到端测试是否仍适用。
    """
    return GameConfig()


@pytest.fixture
def streams():
    """构造可注入的输入输出流。

    输入：无。
    输出：``(stdin, stdout)``，均为内存字符串流。
    副作用：无。
    约束：调用方可通过 ``stdout.getvalue()`` 断言输出。
    """
    return io.StringIO(), io.StringIO()
