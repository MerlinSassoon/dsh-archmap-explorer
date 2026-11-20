"""五子棋棋盘与胜负判定领域模块。

职责：维护棋盘格子的唯一事实来源，校验落子、执行落子、判定五连与平局。
边界：不做终端渲染、不读取用户输入、不选择 AI 落点；本模块无 I/O 副作用。
公共接口：``Board``。
"""
from __future__ import annotations

from typing import Optional

from .models import MoveResult, Position, Stone

# 胜负判定只需检查四个方向：横、竖、主对角、副对角；反向由正反两个方向累加覆盖。
WIN_DIRECTIONS: tuple[tuple[int, int], ...] = ((0, 1), (1, 0), (1, 1), (1, -1))


class Board:
    """五子棋棋盘。

    职责：保存棋子布局，校验并执行落子，判定胜负与平局。
    角色：领域模型，是棋盘状态的唯一权威来源。
    生命周期：由对局用例创建并被其持有至一局结束；不持有外部资源。
    边界：不负责界面展示、输入解析和 AI 决策。
    对外能力：``place_stone``、``stone_at``、``is_full``、``available_positions``。
    """

    def __init__(self, size: int, win_length: int) -> None:
        """初始化一个空棋盘。

        输入：棋盘边长 ``size`` 与连子数 ``win_length``，须已通过配置层校验。
        输出：无；构造后棋盘为空且无胜者。
        副作用：无。
        约束：内部使用二维列表，行列均按 0 起算；坐标唯一事实来源在本类。
        """
        self._size = size
        self._win_length = win_length
        self._grid: list[list[Optional[Stone]]] = [
            [None for _ in range(size)] for _ in range(size)
        ]
        self._moves: list[tuple[Stone, Position]] = []

    @property
    def size(self) -> int:
        """返回棋盘边长。

        输入：无。
        输出：行数与列数相同的整数边长。
        副作用：无。
        约束：由构造函数确定，运行期不可变。
        """
        return self._size

    @property
    def win_length(self) -> int:
        """返回获胜所需连子数。

        输入：无。
        输出：正整数连子数。
        副作用：无。
        约束：由构造函数确定，运行期不可变。
        """
        return self._win_length

    @property
    def move_count(self) -> int:
        """返回已落子总数。

        输入：无。
        输出：棋盘上棋子数量，等于落子历史长度。
        副作用：无。
        约束：用于平局判断与展示回合数。
        """
        return len(self._moves)

    @property
    def last_move(self) -> Optional[tuple[Stone, Position]]:
        """返回最近一次成功落子。

        输入：无。
        输出：（棋子, 坐标）元组；棋盘为空时返回 None。
        副作用：无。
        约束：只读，不修改落子历史。
        """
        return self._moves[-1] if self._moves else None

    def in_bounds(self, position: Position) -> bool:
        """判断坐标是否落在棋盘内。

        输入：任意整数坐标，可以越界。
        输出：在 [0, size) 范围内返回 True。
        副作用：无。
        约束：只做边界判断，不检查该格是否已有棋子。
        """
        return 0 <= position.row < self._size and 0 <= position.col < self._size

    def stone_at(self, position: Position) -> Optional[Stone]:
        """读取指定坐标的棋子。

        输入：坐标；调用方应保证其已通过 ``in_bounds`` 校验。
        输出：该格的棋子；空位返回 None。
        副作用：无。
        约束：越界坐标会抛出 IndexError，视为调用方违约。
        """
        return self._grid[position.row][position.col]

    def is_occupied(self, position: Position) -> bool:
        """判断坐标是否已有棋子。

        输入：坐标；越界坐标在本方法内被视为不可落子并返回 True。
        输出：已有棋子或越界时 True，空位为 False。
        副作用：无。
        约束：供落子校验与 UI 提示共用。
        """
        if not self.in_bounds(position):
            return True
        return self.stone_at(position) is not None

    def is_full(self) -> bool:
        """判断棋盘是否已无空位。

        输入：无。
        输出：落子数等于格子总数时 True。
        副作用：无。
        约束：棋盘满且无胜者时，对局结果应为平局。
        """
        return self.move_count == self._size * self._size

    def place_stone(self, position: Position, stone: Stone) -> MoveResult:
        """在指定坐标落子并返回结果。

        输入：坐标与棋子颜色；坐标须在棋盘内且为空位。
        输出：``MoveResult``；成功时包含胜者与获胜连线（若获胜）。
        副作用：成功时修改棋盘格与落子历史；失败时不产生任何修改。
        约束：越界或占用返回 ``is_accepted=False`` 且不抛异常；本方法不做轮流校验。
        """
        if not self.in_bounds(position):
            return MoveResult(False, f"坐标越界：{position.row},{position.col}")
        if self.stone_at(position) is not None:
            return MoveResult(False, f"该位置已有棋子：{position.row},{position.col}")

        self._grid[position.row][position.col] = stone
        self._moves.append((stone, position))

        line = self._find_winning_line(position, stone)
        if line:
            return MoveResult(True, winner=stone, winning_line=tuple(line))
        return MoveResult(True)

    def available_positions(self) -> list[Position]:
        """列出所有空位坐标。

        输入：无。
        输出：按行优先顺序排列的空位列表。
        副作用：无。
        约束：返回新列表，调用方修改它不会影响棋盘。
        """
        return [
            Position(row, col)
            for row in range(self._size)
            for col in range(self._size)
            if self._grid[row][col] is None
        ]

    def _find_winning_line(
        self, position: Position, stone: Stone
    ) -> list[Position]:
        """检查落子后是否形成连子并返回获胜连线。

        输入：刚落下的坐标及棋子颜色，须已写入棋盘。
        输出：长度不小于连子数的连续坐标列表；未获胜时为空列表。
        副作用：无。
        约束：只沿四个轴向扫描，时间复杂度 O(方向数 × 连子数)。
        """
        for d_row, d_col in WIN_DIRECTIONS:
            line = [position]
            for sign in (1, -1):
                line = line + self._scan_direction(
                    position, stone, d_row * sign, d_col * sign
                )
            if len(line) >= self._win_length:
                return sorted(line, key=lambda p: (p.row, p.col))
        return []

    def _scan_direction(
        self, origin: Position, stone: Stone, d_row: int, d_col: int
    ) -> list[Position]:
        """沿单一方向连续扫描同色棋子。

        输入：起点、目标棋子、行/列增量（增量为单位向量或零）。
        输出：从起点邻近一格开始、连续同色的坐标列表。
        副作用：无。
        约束：遇到棋盘边界、空位或异色棋子即停止。
        """
        found: list[Position] = []
        row, col = origin.row + d_row, origin.col + d_col
        while (
            0 <= row < self._size
            and 0 <= col < self._size
            and self._grid[row][col] is stone
        ):
            found.append(Position(row, col))
            row, col = row + d_row, col + d_col
        return found
