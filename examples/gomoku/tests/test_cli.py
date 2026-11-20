"""命令行入口端到端测试。

职责：以注入字符串流的方式验证菜单、落子、非法输入提示、重开、退出与胜负播报。
边界：不启动真实终端，不依赖随机性（双人模式优先；人机模式只验证流程推进）。
"""
from __future__ import annotations

import io

import pytest

from gomoku.cli import GameCli, main
from gomoku.config import GameConfig


def _run(input_text: str) -> tuple[int, str]:
    """用给定输入驱动一次 CLI 并返回退出码与输出。

    输入：模拟的标准输入全文。
    输出：``(exit_code, stdout)``。
    副作用：无（全部在内存流中进行）。
    约束：输入行须按交互顺序排列，否则会出现 EOF 提前退出。
    """
    stdin, stdout = io.StringIO(input_text), io.StringIO()
    code = main(stdin=stdin, stdout=stdout, config=GameConfig())
    return code, stdout.getvalue()


def test_cli_quit_from_menu_returns_zero() -> None:
    """验证菜单选择退出时返回 0 并输出告别语。"""
    code, output = _run("0\n")

    assert code == 0
    assert "已退出游戏" in output


def test_cli_rejects_invalid_menu_choice_then_continues() -> None:
    """验证非法菜单选择会提示并重试，而不是退出。"""
    code, output = _run("9\n2\nq\nn\n")

    assert code == 0
    assert "无效选择" in output
    assert "双人对战" in output


def test_cli_shows_board_and_accepts_move() -> None:
    """验证进入对局后渲染棋盘、回显落子，并在 q 后回到主菜单再退出。"""
    code, output = _run("2\nH8\nq\nn\n")

    assert code == 0
    assert "图例" in output
    assert "你落子：H8" in output
    assert "已退出本局，返回主菜单" in output
    assert "已退出游戏" in output


def test_cli_reports_invalid_and_occupied_moves() -> None:
    """验证格式错误与重复落子都得到提示且对局继续。"""
    code, output = _run("2\nZZ\nH8\nH8\nq\nn\n")

    assert code == 0
    assert "无法识别" in output
    assert "落子失败" in output


def test_cli_restart_clears_board() -> None:
    """验证 r 命令重开对局并提示黑棋先行。"""
    code, output = _run("2\nH8\nr\nq\nn\n")

    assert code == 0
    assert "已重开本局" in output


def test_cli_announces_human_win_in_human_vs_human() -> None:
    """验证双人模式五连后播报黑棋获胜并停止要求输入。"""
    code, output = _run("2\nA1\nA2\nB1\nB2\nC1\nC2\nD1\nD2\nE1\n")

    assert code == 0
    assert "黑棋获胜" in output
    assert "再来一局" in output


def test_cli_ai_mode_takes_turn_after_human() -> None:
    """验证人机模式下人类落子后电脑在提示中落子并交还回合。"""
    code, output = _run("1\nH8\nq\nn\n")

    assert code == 0
    assert "电脑落子" in output
    assert "轮到黑棋" in output


def test_cli_eof_exits_without_error() -> None:
    """验证输入流提前结束时安静退出并返回 0。"""
    code, output = _run("")

    assert code == 0
    assert "已退出游戏" in output


def test_cli_play_again_restarts_a_new_game() -> None:
    """验证回答 y 后重新进入模式菜单。"""
    code, output = _run("2\nq\ny\n2\nq\nn\n")

    assert code == 0
    assert output.count("请选择对局模式") == 2


def test_game_cli_does_not_close_injected_streams() -> None:
    """验证 CLI 不关闭调用方注入的流，流所有权归调用方。"""
    stdin, stdout = io.StringIO("0\n"), io.StringIO()
    cli = GameCli(stdin=stdin, stdout=stdout, config=GameConfig())
    cli.run()

    assert not stdin.closed
    assert not stdout.closed
