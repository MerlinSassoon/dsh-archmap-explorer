"""本地人机对弈适配器。

职责：为棋盘提供"简单但不会明显送分"的电脑落点选择，
优先取胜、其次封堵对手成五，再按邻近度启发式评分。
边界：只读取棋盘，不修改棋盘；不负责提示文案和输入输出。
"""
from __future__ import annotations

import random
from typing import Optional

from .board import WIN_DIRECTIONS, Board
from .models import Position, Stone


class SimpleAiPlayer:
    """基于局部评分的五子棋电脑对手。

    职责：在给定棋盘与己方颜色下选择一个合理落点。
    角色：适配器（决策策略），由对局用例按模式装配。
    生命周期：随对局创建，只持有可注入的随机数发生器，不持有棋盘。
    边界：不做深度搜索或多层博弈；不判断轮流合法性。
    对外能力：``choose_move``。
    """

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        """构造电脑对手。

        输入：可选 ``random.Random`` 实例；不传则新建一个，便于测试固定种子。
        输出：无。
        副作用：仅创建随机数发生器，不触碰外部资源。
        约束：随机源可在测试中注入以保证可重复性。
        """
        self._rng = rng or random.Random()

    def choose_move(self, board: Board, stone: Stone) -> Optional[Position]:
        """为指定棋子选择落点。

        输入：当前棋盘与电脑棋子颜色；棋盘须至少有一个空位。
        输出：选中的空位坐标；棋盘已满时返回 None。
        副作用：无（不修改棋盘）。
        约束：评分相同的位置中随机选择，避免对局千篇一律；仅考虑已有棋子邻域，
              空棋盘时直接选择中心点。
        """
        candidates = self._candidate_positions(board)
        if not candidates:
            return None

        best_score = -1
        best_moves: list[Position] = []
        for position in candidates:
            score = self._score_position(board, position, stone)
            if score > best_score:
                best_score = score
                best_moves = [position]
            elif score == best_score:
                best_moves.append(position)
        return self._rng.choice(best_moves)

    def _candidate_positions(self, board: Board) -> list[Position]:
        """筛选值得评估的空位候选。

        输入：当前棋盘。
        输出：已有棋子周围两格内的空位；棋盘为空时返回中心点列表。
        副作用：无。
        约束：限制搜索范围以保持 O(空位×邻域) 的简单计算量。
        """
        if board.move_count == 0:
            center = board.size // 2
            return [Position(center, center)]

        seen: set[Position] = set()
        for row in range(board.size):
            for col in range(board.size):
                if board.stone_at(Position(row, col)) is None:
                    continue
                for d_row in range(-2, 3):
                    for d_col in range(-2, 3):
                        candidate = Position(row + d_row, col + d_col)
                        if board.in_bounds(candidate) and not board.is_occupied(candidate):
                            seen.add(candidate)
        return sorted(seen, key=lambda p: (p.row, p.col))

    def _score_position(self, board: Board, position: Position, stone: Stone) -> int:
        """评估在空位落子后的局部价值。

        输入：棋盘、候选空位、电脑棋子颜色。
        输出：整数分值；成五最高，其次为封堵对手成五，随后是双方连子潜力与邻近度。
        副作用：无（通过纯函数统计模拟，不写棋盘）。
        约束：分值比较是启发式而非严格博弈最优。
        """
        own = self._line_quality(board, position, stone)
        opponent = self._line_quality(board, position, stone.opponent)
        return max(own, opponent) * 10 + min(own, opponent) + 1

    def _line_quality(self, board: Board, position: Position, stone: Stone) -> int:
        """计算某方在该点四个方向上的最大连续长度。

        输入：棋盘、假设落子点、被评估棋子。
        输出：四个方向中最长的同色连续段长度（不包含假设点本身之外的修正）。
        副作用：无。
        约束：该点必须为空位，否则统计结果无业务意义。
        """
        best = 0
        for d_row, d_col in WIN_DIRECTIONS:
            length = 1
            for sign in (1, -1):
                row, col = position.row + d_row * sign, position.col + d_col * sign
                while (
                    0 <= row < board.size
                    and 0 <= col < board.size
                    and board.stone_at(Position(row, col)) is stone
                ):
                    length += 1
                    row, col = row + d_row * sign, col + d_col * sign
            best = max(best, length)
        return best
