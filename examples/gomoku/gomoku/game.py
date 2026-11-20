"""五子棋对局用例模块（应用/编排层）。

职责：组织一局完整对局的状态流转：当前执子方、合法落子、终局判定与重置，
并协调领域棋盘与可选的电脑对手。
边界：不包含终端渲染和文本解析；通过返回结果对象向入口层报告事实。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from .board import Board
from .models import MoveResult, Position, Stone


class MoveSelector(Protocol):
    """电脑落点选择器的显式契约。

    职责：声明应用层对自动落子策略所需的最小能力。
    角色：接口协议，由 ``SimpleAiPlayer`` 等适配器实现。
    生命周期：由调用方创建并注入对局，对局不负责关闭它。
    边界：只允许读取棋盘，不得修改对局状态。
    对外能力：``choose_move``。
    """

    def choose_move(self, board: Board, stone: Stone) -> Optional[Position]:
        """返回该棋子颜色的建议落点，无可用落点时应返回 None。"""
        ...


@dataclass(frozen=True)
class TurnOutcome:
    """一次回合操作的结果契约。

    职责：向入口层描述本回合发生了什么，避免入口层重新推导业务事实。
    角色：应用层结果对象。
    生命周期：一次性返回给终端入口。
    边界：不包含格式化文本。
    对外能力：``move_result``、``ai_position``、``is_game_over``。
    """

    move_result: MoveResult
    ai_position: Optional[Position] = None
    is_game_over: bool = False
    game_winner: Optional[Stone] = None

    @property
    def is_draw(self) -> bool:
        """判断本回合结束后是否平局。

        输入：无。
        输出：对局结束且无胜者时为 True。
        副作用：无。
        约束：仅在 ``is_game_over`` 为 True 时才有业务意义。
        """
        return self.is_game_over and self.game_winner is None


class GomokuGame:
    """一局五子棋的对局用例编排对象。

    职责：维护棋盘、执子方顺序、终局状态，并执行人类与电脑落子用例。
    角色：应用/编排层服务。
    生命周期：每局创建一次，一局结束后由入口层调用 ``reset`` 或重新创建；不持有外部资源。
    边界：不做输入解析、画面渲染；不直接决定电脑落点，而是委托注入的选择器。
    对外能力：``start_new_game``、``play_human_move``、``play_ai_move``、``reset``。
    """

    def __init__(
        self,
        size: int,
        win_length: int,
        ai_player: Optional[MoveSelector] = None,
        human_stone: Stone = Stone.BLACK,
    ) -> None:
        """创建对局并初始化首回合状态。

        输入：棋盘边长、连子数、可选的电脑选择器；提供选择器时电脑执对方颜色。
        输出：无。
        副作用：无外部副作用，仅创建内部棋盘。
        约束：黑棋先行；调用方须保证 ``size`` 与 ``win_length`` 已通过配置校验。
        """
        self._size = size
        self._win_length = win_length
        self._ai_player = ai_player
        self._human_stone = human_stone
        self._current = Stone.BLACK
        self._winner: Optional[Stone] = None
        self._board = Board(size, win_length)

    @property
    def board(self) -> Board:
        """返回当前棋盘（只读约定）。

        输入：无。
        输出：棋盘实例，供渲染层与 AI 读取。
        副作用：无。
        约束：调用方不得直接落子，落子必须通过本类的用例方法。
        """
        return self._board

    @property
    def current_stone(self) -> Stone:
        """返回当前该落子的棋子颜色。

        输入：无。
        输出：黑或白。
        副作用：无。
        约束：对局已结束时该值不再具有推进意义，入口层应先检查 ``is_game_over``。
        """
        return self._current

    @property
    def is_vs_ai(self) -> bool:
        """判断本局是否由电脑对手参与。

        输入：无。
        输出：构造时注入了 ``ai_player`` 时为 True。
        副作用：无。
        约束：用于入口层选择文案，不参与规则判定。
        """
        return self._ai_player is not None

    @property
    def human_stone(self) -> Stone:
        """返回人类一方的棋子颜色。

        输入：无。
        输出：黑棋或白棋；双人模式默认黑棋。
        副作用：无。
        约束：人机模式下电脑执其对方颜色。
        """
        return self._human_stone

    @property
    def is_human_turn(self) -> bool:
        """判断当前是否由人类落子。

        输入：无。
        输出：无人机对局或轮到人类时为 True；轮到电脑时为 False。
        副作用：无。
        约束：不改变任何状态，可安全用于渲染提示。
        """
        return self._ai_player is None or self._current is self._human_stone

    @property
    def winner(self) -> Optional[Stone]:
        """返回对局胜者。

        输入：无。
        输出：胜者棋子；对局未结束或平局时为 None。
        副作用：无。
        约束：由最近一次成功的落子结果更新。
        """
        return self._winner

    @property
    def is_game_over(self) -> bool:
        """判断对局是否结束。

        输入：无。
        输出：已有胜者或棋盘已满时为 True。
        副作用：无。
        约束：结束后所有落子用例都必须拒绝继续落子。
        """
        return self._winner is not None or self._board.is_full()

    def start_new_game(self) -> None:
        """清空棋盘并恢复黑棋先行的初始状态。

        输入：无。
        输出：无返回值；棋盘、胜者与执子方均被重置。
        副作用：覆盖当前对局状态（不可撤销）。
        约束：应在入口层保存对局配置后调用，以支持"再来一局"。
        """
        self._board = Board(self._size, self._win_length)
        self._current = Stone.BLACK
        self._winner = None

    def play_human_move(self, position: Position) -> TurnOutcome:
        """执行人类落子，并在人机模式下立即衔接电脑回合。

        输入：人类给出的坐标，可越界或占用，非法输入会被拒绝。
        输出：``TurnOutcome``，含人类落子结果、电脑落点与终局状态。
        副作用：修改棋盘与执子方；人机模式下会追加电脑落子。
        约束：对局已结束或当前不该人类落子时返回拒绝结果，不修改棋盘。
        """
        if self.is_game_over:
            return TurnOutcome(MoveResult(False, "对局已结束"), is_game_over=True, game_winner=self._winner)
        if not self.is_human_turn:
            return TurnOutcome(MoveResult(False, "现在轮到电脑落子"))

        # 双人模式下人类轮流执黑白，因此以当前执子方为准，而不是固定的"人类颜色"。
        human_result = self._apply_move(position, self._current)
        if not human_result.is_accepted:
            return TurnOutcome(human_result)

        if self.is_game_over:
            return TurnOutcome(human_result, is_game_over=True, game_winner=self._winner)

        ai_position = self.play_ai_move()
        return TurnOutcome(
            human_result,
            ai_position=ai_position,
            is_game_over=self.is_game_over,
            game_winner=self._winner,
        )

    def play_ai_move(self) -> Optional[Position]:
        """执行一次电脑落子。

        输入：无；需要在人机模式下且轮到电脑。
        输出：电脑实际落下的坐标；无电脑、不该电脑走或对局结束时返回 None。
        副作用：修改棋盘与执子方。
        约束：电脑返回非法坐标时视为适配器违约，直接抛出 RuntimeError，
              避免以静默失败掩盖错误契约。
        """
        if self._ai_player is None or self.is_human_turn or self.is_game_over:
            return None

        position = self._ai_player.choose_move(self._board, self._current)
        if position is None:
            return None
        result = self._apply_move(position, self._current)
        if not result.is_accepted:
            raise RuntimeError(f"电脑选择了非法落点：{result.reason}")
        return position

    def _apply_move(self, position: Position, stone: Stone) -> MoveResult:
        """在内部统一完成合法落子、胜者更新与回合移交。

        输入：坐标与执子颜色，调用方须保证当前确实轮到该颜色。
        输出：领域落子结果。
        副作用：成功时修改棋盘、更新胜者并推进执子方。
        约束：失败时不修改任何对局状态；回合顺序的唯一事实来源是落子数，
              因此重开或批量落子后执子方仍然自洽。
        """
        result = self._board.place_stone(position, stone)
        if not result.is_accepted:
            return result
        if result.winner is not None:
            self._winner = result.winner
        else:
            self._current = self._stone_for_move_count(self._board.move_count)
        return result

    @staticmethod
    def _stone_for_move_count(move_count: int) -> Stone:
        """根据已落子总数推导下一步执子方。

        输入：棋盘上已成功落下的棋子数量。
        输出：偶数步后轮到黑棋，奇数步后轮到白棋。
        副作用：无。
        约束：黑棋先行是唯一规则来源，禁止在其它位置重复实现。
        """
        return Stone.BLACK if move_count % 2 == 0 else Stone.WHITE
