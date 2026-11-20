"""终端输入解析测试。

职责：验证坐标解析、命令识别、越界与格式错误的错误契约。
边界：纯字符串处理，不涉及终端或对局状态。
"""
from __future__ import annotations

import pytest

from gomoku.input_parser import (
    COMMAND_QUIT,
    COMMAND_RESTART,
    column_letters,
    format_position,
    parse_input,
    parse_position,
)
from gomoku.models import Position, ValidationError


def test_parse_position_accepts_letter_and_row() -> None:
    """验证标准坐标 H8 解析为 0 起算的行列。"""
    assert parse_position("H8", 15) == Position(row=7, col=7)


def test_parse_position_is_case_and_space_insensitive() -> None:
    """验证小写与首尾空格均可被规范化解析。"""
    assert parse_position("  a1 ", 15) == Position(row=0, col=0)


def test_parse_position_skips_letter_i() -> None:
    """验证列字母跳过 I，J 表示第 9 列，避免视觉误读。"""
    assert parse_position("J1", 15) == Position(row=0, col=8)


@pytest.mark.parametrize("text", ["", "8", "H", "H0", "H16", "Q1", "I1", "H-1", "1H", "H8x"])
def test_parse_position_rejects_invalid_text(text: str) -> None:
    """验证空串、缺字母、行号越界与格式错误都返回错误契约。"""
    result = parse_position(text, 15)
    assert isinstance(result, ValidationError)
    assert result.message


def test_parse_position_rejects_out_of_range_column() -> None:
    """验证超出棋盘宽度的列字母被拒绝并提示范围。"""
    result = parse_position("Q1", 15)  # 字母表跳过 I，Q 是第 16 列，超出 15 路棋盘的最大列 O

    assert isinstance(result, ValidationError)
    assert "超出" in result.message


def test_parse_input_recognizes_commands() -> None:
    """验证 q / r 被识别为命令而不是坐标。"""
    quit_result = parse_input(" q ", 15)
    restart_result = parse_input("R", 15)

    assert quit_result.command == COMMAND_QUIT
    assert restart_result.command == COMMAND_RESTART


def test_parse_input_distinguishes_command_from_coordinate() -> None:
    """验证 H8 不会被当命令，且返回坐标而非错误。"""
    result = parse_input("H8", 15)

    assert result.command is None
    assert result.error is None
    assert result.position == Position(7, 7)


def test_parse_input_reports_empty_input() -> None:
    """验证纯空白输入返回可读错误而不是抛异常。"""
    result = parse_input("   ", 15)

    assert result.error is not None
    assert "为空" in result.error.message


def test_format_and_parse_are_inverse() -> None:
    """验证格式化后再解析得到同一坐标。"""
    original = Position(row=14, col=13)

    assert parse_position(format_position(original), 15) == original


def test_column_letters_respects_board_size() -> None:
    """验证列字母表长度与棋盘宽度一致，且不包含 I。"""
    letters = column_letters(15)

    assert len(letters) == 15
    assert "I" not in letters
