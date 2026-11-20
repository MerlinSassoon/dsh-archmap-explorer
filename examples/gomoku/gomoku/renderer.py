"""终端棋盘渲染模块（入口/展示层）。

职责：把棋盘、状态与结果翻译为纯文本，负责获取终端尺寸并适配列宽。
边界：只读取棋盘，不修改对局；不解析用户输入。
"""
from __future__ import annotations

import shutil
from typing import Optional

from .board import Board
from .input_parser import column_letters, format_position
from .models import Position, Stone

# 每格宽度（含分隔线），保证 15 路棋盘在 80 列终端内完整显示。
_CELL_WIDTH = 3


def terminal_width(default: int = 80) -> int:
    """获取当前终端列数。

    输入：可选默认值，在非交互环境读取失败时使用。
    输出：终端可用列数。
    副作用：查询终端尺寸，不写标准输出。
    约束：输出被重定向时 ``shutil`` 可能返回 0 或抛错，此时回退为默认值。
    """
    try:
        width = shutil.get_terminal_size().columns
    except OSError:
        return default
    return width if width > 0 else default


class BoardRenderer:
    """纯文本棋盘渲染器。

    职责：输出带列号、行号的棋盘，并高亮最近一步与获胜连线。
    角色：入口层展示适配器。
    生命周期：无状态，可复用于多局对局。
    边界：不决定对局规则，也不保存任何棋盘数据。
    对外能力：``render``、``render_legend``。
    """

    def __init__(self, board: Board) -> None:
        """绑定待渲染棋盘。

        输入：要展示的棋盘；渲染器只做只读访问。
        输出：无。
        副作用：无。
        约束：棋盘在渲染过程中变化会导致输出不一致，调用方应串行使用。
        """
        self._board = board

    def render(
        self,
        last_move: Optional[Position] = None,
        winning_line: tuple[Position, ...] = (),
    ) -> str:
        """生成棋盘文本。

        输入：最近一步坐标与获胜连线（均可为空）。
        输出：多行字符串；每行以行号开头，列号在顶部与底部各出现一次。
        副作用：无（仅返回字符串，打印由调用方负责）。
        约束：获胜连线的棋子用 ``#`` 表示，最近一步用 ``+`` 标记。
        """
        size = self._board.size
        header = self._column_header(size)
        rows = [header]
        for row in range(size):
            cells = [f"{row + 1:>2}"]
            for col in range(size):
                position = Position(row, col)
                cells.append(self._cell(position, last_move, winning_line))
            rows.append("".join(cells))
        rows.append(header)
        return "\n".join(rows)

    def render_legend(self) -> str:
        """生成棋子图例说明。

        输入：无。
        输出：一行说明 X/O/#/+ 含义的文本。
        副作用：无。
        约束：图例需与 ``render`` 的标记保持一致。
        """
        return "图例：X=黑棋  O=白棋  #=获胜连线  +=最近一步"

    def _column_header(self, size: int) -> str:
        """生成列号表头。

        输入：棋盘边长。
        输出：与棋盘等宽、每格居中的列字母行。
        副作用：无。
        约束：必须使用与坐标解析相同的字母表（跳过 I）。
        """
        letters = column_letters(size)
        return "  " + "".join(f"{letter:^{_CELL_WIDTH}}" for letter in letters)

    def _cell(
        self,
        position: Position,
        last_move: Optional[Position],
        winning_line: tuple[Position, ...],
    ) -> str:
        """渲染单个格子。

        输入：格子坐标、最近一步、获胜连线。
        输出：定宽字符串，空位显示 ``.``，获胜连线上的棋子显示 ``#``，
              普通棋子显示 ``X``/``O``，最近一步追加 ``+`` 标记。
        副作用：无。
        约束：空位但属于最近一步的情况不会出现，因为最近一步必有棋子。
        """
        stone = self._board.stone_at(position)
        if stone is None:
            return f"{'.':^{_CELL_WIDTH}}"
        if position in winning_line:
            symbol = "#"
        else:
            symbol = stone.display
        suffix = "+" if last_move == position else " "
        return f"{symbol + suffix:^{_CELL_WIDTH}}"


def describe_stone(stone: Stone) -> str:
    """返回棋子颜色的中文名称。

    输入：棋子枚举。
    输出：``黑棋`` 或 ``白棋``。
    副作用：无。
    约束：仅用于界面文案。
    """
    return "黑棋" if stone is Stone.BLACK else "白棋"


def format_move_hint(position: Position) -> str:
    """把坐标格式化为用户上下文中的可读文本。

    输入：棋盘坐标。
    输出：形如 ``H8`` 的输入格式，便于用户复用。
    副作用：无。
    约束：依赖坐标格式与输入解析保持一致。
    """
    return format_position(position)
