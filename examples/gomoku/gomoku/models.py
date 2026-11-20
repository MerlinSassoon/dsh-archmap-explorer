"""五子棋领域数据契约。

职责：定义棋盘坐标、棋子、落子结果和胜负结果等值对象，
所有跨层传递的对局事实都使用这里的数据结构，而不是裸字典。
边界：不包含任何 I/O、终端渲染或随机策略，只描述数据及轻量派生规则。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Stone(str, Enum):
    """棋子种类。

    职责：区分黑白双方，并提供显示与对手推导能力。
    角色：领域值对象。
    生命周期：无状态、全局共享的枚举成员。
    边界：不记录任何棋盘位置信息。
    对外能力：``opponent``、``display``。
    """

    BLACK = "black"
    WHITE = "white"

    @property
    def opponent(self) -> "Stone":
        """返回对手棋子。

        输入：无（使用当前枚举成员）。
        输出：另一方棋子，黑白互换；不会返回自身。
        副作用：无。
        约束：棋盘只有两种颜色，此推导是唯一事实来源。
        """
        return Stone.WHITE if self is Stone.BLACK else Stone.BLACK

    @property
    def display(self) -> str:
        """返回终端渲染用字符。

        输入：无。
        输出：黑棋为 ``X``，白棋为 ``O``，便于在纯文本棋盘上区分。
        副作用：无。
        约束：仅供展示层使用，不用于持久化标识。
        """
        return "X" if self is Stone.BLACK else "O"


@dataclass(frozen=True)
class Position:
    """棋盘坐标（行、列）。

    职责：表达一个落子位置，并承载边界校验所需的比较能力。
    角色：领域值对象。
    生命周期：不可变、可随意创建，不持有资源。
    边界：不知道棋盘尺寸，合法性由棋盘本次调用的规则判断。
    对外能力：字段 ``row``、``col``，以及可哈希语义（可作字典键）。
    """

    row: int
    col: int


@dataclass(frozen=True)
class MoveResult:
    """一次落子尝试的结果。

    职责：表达落子是否成功，以及在成功时是否结束对局。
    角色：领域结果对象，用于替代异常式控制流。
    生命周期：临时对象，落子后立即返回给调用方。
    边界：不负责提示文案渲染。
    对外能力：``is_accepted``、``winner``、``winning_line``。
    """

    is_accepted: bool
    reason: str = ""
    winner: Optional[Stone] = None
    winning_line: tuple[Position, ...] = ()

    @property
    def is_win(self) -> bool:
        """判断本次落子是否直接导致胜利。

        输入：无。
        输出：成功落子且存在胜者时为 True，否则 False。
        副作用：无。
        约束：只有 ``is_accepted`` 为 True 时 ``winner`` 才有意义。
        """
        return self.is_accepted and self.winner is not None


@dataclass(frozen=True)
class ValidationError:
    """输入校验失败的错误契约。

    职责：携带用户可读的错误信息，统一入口层的错误表达。
    角色：接口层错误结果。
    生命周期：一次性返回给输入解析方。
    边界：不包含异常堆栈或内部实现细节。
    对外能力：字段 ``message``。
    """

    message: str
