"""五子棋全局配置层。

职责：集中定义棋盘尺寸、胜负连子数、默认对局模式等静态参数，
作为这些事实的唯一来源，供领域层、应用层与入口层共同引用。
边界：不读写环境变量或文件以外的业务状态，也不依赖任何业务实现。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConfig:
    """一局五子棋的静态规则参数集合。

    职责：封装棋盘规格与默认对手模式，作为配置层值对象在各层间显式传递。
    角色：配置。
    生命周期：无状态、不可变，由入口层按需创建后只读传递，不持有资源。
    边界：不校验落子合法性，也不决定胜负，这些规则属于领域层。
    对外能力：字段 ``board_size``、``win_length``、``default_mode``。
    """

    board_size: int = 15
    win_length: int = 5
    default_mode: str = "human-vs-ai"

    def __post_init__(self) -> None:
        """校验配置不变量，防止非法棋盘规格流入领域层。

        输入：构造参数本身。
        输出：无返回值；校验通过后对象可用。
        副作用：无。
        约束：棋盘边长至少为 3、连子数介于 2 与棋盘边长之间，否则抛出 ValueError。
        """
        if not 3 <= self.board_size <= 25:
            raise ValueError(f"棋盘边长必须在 3 到 25 之间，收到 {self.board_size}")
        if not 2 <= self.win_length <= self.board_size:
            raise ValueError(
                f"连子数必须在 2 到 {self.board_size} 之间，收到 {self.win_length}"
            )
        if self.default_mode not in SUPPORTED_MODES:
            raise ValueError(f"不支持的默认对局模式：{self.default_mode}")


# 菜单可选的对手模式；UI 与用例层通过该常量保持一致，避免重复定义。
SUPPORTED_MODES: tuple[str, ...] = ("human-vs-ai", "human-vs-human")
