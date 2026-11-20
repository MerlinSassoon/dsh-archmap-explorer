"""终端输入解析模块（入口层辅助）。

职责：把用户输入的原始字符串解析为坐标、命令或校验错误，
所有用户在命令行键入的内容都在此边界完成格式化校验。
边界：不读写终端、不修改对局状态，只做纯字符串到契约对象的转换。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Union

from .models import Position, ValidationError

# 坐标格式：字母列 + 数字行，例如 "H8" / "h8"；字母从 A 开始（跳过 I 以贴近围棋习惯）。
_COORD_PATTERN = re.compile(r"^[A-HJ-Z][0-9]{1,2}$")

# 不需要坐标的命令集合，入口层据此执行菜单动作。
COMMAND_QUIT = "q"
COMMAND_RESTART = "r"
KNOWN_COMMANDS: tuple[str, ...] = (COMMAND_QUIT, COMMAND_RESTART)


@dataclass(frozen=True)
class ParsedCommand:
    """一次输入解析的结果。

    职责：区分"坐标落子"与"菜单命令"，并携带失败原因。
    角色：入口层契约对象。
    生命周期：一次性传递。
    边界：不解释命令的业务含义。
    对外能力：``position``、``command``、``error``。
    """

    position: Optional[Position] = None
    command: Optional[str] = None
    error: Optional[ValidationError] = None


# 列字母到列号的映射（跳过 I，保持与 coord 正则一致）。
_COLUMN_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def column_letters(size: int) -> str:
    """返回当前棋盘宽度对应的列字母表。

    输入：棋盘边长（3–25）。
    输出：从 A 起、跳过 I 的前 ``size`` 个字母，用于坐标提示。
    副作用：无。
    约束：``size`` 超出字母表长度时抛出 ValueError。
    """
    if not 1 <= size <= len(_COLUMN_LETTERS):
        raise ValueError(f"列字母表不支持棋盘边长 {size}")
    return _COLUMN_LETTERS[:size]


def format_position(position: Position) -> str:
    """把坐标格式化为用户可输入的文本。

    输入：合法坐标，调用方须保证列号在字母表范围内。
    输出：形如 ``H8`` 的字符串，行号按人类习惯从 1 起算。
    副作用：无。
    约束：格式化与 ``parse_position`` 互为逆操作。
    """
    return f"{_COLUMN_LETTERS[position.col]}{position.row + 1}"


def parse_position(text: str, size: int) -> Union[Position, ValidationError]:
    """解析用户坐标文本。

    输入：原始输入与棋盘边长；输入会去除首尾空白并转大写。
    输出：合法时返回 ``Position``（行列从 0 起算），否则返回 ``ValidationError``。
    副作用：无。
    约束：越界、格式错误、未支持的列字母都返回错误契约而不是抛异常。
    """
    normalized = text.strip().upper()
    if not _COORD_PATTERN.match(normalized):
        return ValidationError(
            f"无法识别的坐标“{text.strip()}”，请输入如 H8 的格式，"
            f"列范围 A-{_COLUMN_LETTERS[size - 1]}，行范围 1-{size}。"
        )

    col = _COLUMN_LETTERS.index(normalized[0])
    row = int(normalized[1:]) - 1
    # 行号从 1 起算，因此 "H0" 会得到 -1；必须显式拒绝，避免把负数坐标带进棋盘。
    if col >= size or not 0 <= row < size:
        return ValidationError(
            f"坐标 {normalized} 超出棋盘范围，列范围 A-{_COLUMN_LETTERS[size - 1]}，"
            f"行范围 1-{size}。"
        )
    return Position(row, col)


def parse_input(text: str, size: int) -> ParsedCommand:
    """解析一整条用户输入，区分命令与坐标。

    输入：原始输入与棋盘边长。
    输出：``ParsedCommand``；空输入、未知命令或非法坐标时 ``error`` 非空。
    副作用：无。
    约束：命令只接受单字母，坐标必须为"字母+数字"，两者形态不重叠，
          因此命令判定不会吞掉合法坐标（如 H8）。
    """
    normalized = text.strip().lower()
    if not normalized:
        return ParsedCommand(error=ValidationError("输入为空，请输入坐标或命令。"))
    if normalized in KNOWN_COMMANDS:
        return ParsedCommand(command=normalized)

    position = parse_position(text, size)
    if isinstance(position, ValidationError):
        return ParsedCommand(error=position)
    return ParsedCommand(position=position)
