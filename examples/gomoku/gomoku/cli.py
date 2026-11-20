"""五子棋命令行交互入口。

职责：负责菜单选择模式、读取用户输入、驱动对局用例、渲染棋盘与提示，
并统一处理退出码与异常边界。
边界：不实现棋盘规则、胜负判定或电脑策略；这些事实来自领域层与用例层。
入口方式：``python -m gomoku`` 或 ``python main.py``。
退出码：0 正常结束；1 启动参数或环境错误；2 用户输入流异常（如 EOF）。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional, TextIO

from .ai import SimpleAiPlayer
from .config import SUPPORTED_MODES, GameConfig
from .game import GomokuGame, TurnOutcome
from .input_parser import (
    COMMAND_QUIT,
    COMMAND_RESTART,
    ParsedCommand,
    parse_input,
)
from .models import Position, Stone
from .renderer import BoardRenderer, describe_stone, format_move_hint

# 菜单文案：模式与默认配置中的 default_mode 保持一致。
_MODE_LABELS: dict[str, str] = {
    "human-vs-ai": "人机对战（你执黑先行）",
    "human-vs-human": "双人对战（同屏轮流落子）",
}


class GameCli:
    """五子棋终端交互控制器。

    职责：把终端输入/输出流与对局用例串起来，处理菜单、落子、重开与退出命令。
    角色：入口/接口层。
    生命周期：每次进程启动创建一个，持有输入输出流但在本类中不关闭它们；
              流的所有权归调用方，便于测试注入。
    边界：不保存业务规则，电脑策略由内部按模式装配。
    对外能力：``run``。
    """

    def __init__(self, stdin: TextIO, stdout: TextIO, config: GameConfig) -> None:
        """构造交互控制器。

        输入：输入流、输出流与已校验的配置。
        输出：无。
        副作用：无（不启动对局，不写输出）。
        约束：输入输出流须支持 ``readline`` 与 ``write``；本类不负责关闭它们。
        """
        self._stdin = stdin
        self._stdout = stdout
        self._config = config

    def run(self) -> int:
        """启动主循环，直到用户退出或输入流结束。

        输入：无（从构造时注入的输入流读取）。
        输出：进程退出码，0 表示正常退出。
        副作用：持续读写终端，可能跨多局循环。
        约束：输入流 EOF 视为退出信号；单局内的非法输入只提示、不中断对局；
              单局内输入 q 只结束该局并回到"再来一局"询问。
        """
        self._write_intro()
        while True:
            mode = self._choose_mode()
            if mode is None:
                self._write("已退出游戏，感谢游玩！")
                return 0

            self._play_one_game(mode)
            if not self._ask_play_again():
                self._write("已退出游戏，感谢游玩！")
                return 0

    def _choose_mode(self) -> Optional[str]:
        """在交互菜单中选择对局模式。

        输入：从终端读取一行选择。
        输出：选中的模式标识；输入 ``q``/``0`` 或 EOF 时返回 None。
        副作用：写标准输出提示。
        约束：非法选择会循环重试，不会因误输入退出。
        """
        self._write("\n请选择对局模式：")
        for index, mode in enumerate(SUPPORTED_MODES, start=1):
            self._write(f"  {index}. {_MODE_LABELS[mode]}")
        self._write("  0. 退出")

        while True:
            line = self._read_line("> ")
            if line is None or line.strip().lower() in {"q", "0"}:
                return None
            if line.strip().isdigit() and 1 <= int(line.strip()) <= len(SUPPORTED_MODES):
                return SUPPORTED_MODES[int(line.strip()) - 1]
            self._write("无效选择，请输入 1、2 或 0。")

    def _ask_play_again(self) -> bool:
        """询问是否再开一局。

        输入：从终端读取一行。
        输出：回答为 y/是 时返回 True；EOF 或其它回答返回 False。
        副作用：写标准输出提示。
        约束：默认按"不再继续"处理，避免非交互流无限循环。
        """
        line = self._read_line("\n再来一局？[y/N] ")
        if line is None:
            return False
        return line.strip().lower() in {"y", "yes", "是"}

    def _play_one_game(self, mode: str) -> bool:
        """执行一整局对局直到结束或用户退出。

        输入：已选定的对局模式。
        输出：用户以 q/EOF 中途退出时返回 True，正常分出结果返回 False。
        副作用：持续读写终端并修改对局状态。
        约束：对局结果通过终端输出，退出状态通过返回值表达而非异常。
        """
        ai_player = SimpleAiPlayer() if mode == "human-vs-ai" else None
        game = GomokuGame(
            size=self._config.board_size,
            win_length=self._config.win_length,
            ai_player=ai_player,
        )
        last_move: Optional[Position] = None
        winning_line: tuple[Position, ...] = ()

        self._write(
            f"\n=== 五子棋 · {_MODE_LABELS[mode]} ==="
            f"（棋盘 {game.board.size}×{game.board.size}，先连成 {game.board.win_length} 子者胜）"
        )

        is_aborted = False
        while not game.is_game_over:
            self._draw(game, last_move, winning_line)
            if not game.is_human_turn:
                # 电脑回合由用例层负责落子；这里仅在无人值守模式下做兜底推进。
                played = game.play_ai_move()
                if played is None:
                    continue
                last_move = played
                continue

            prompt = f"轮到{describe_stone(game.current_stone)}，输入坐标（如 H8），r 重开，q 退出： "
            line = self._read_line(prompt)
            if line is None:
                self._write("输入已结束，退出游戏。")
                return True

            parsed = parse_input(line, game.board.size)
            handled = self._handle_human_input(game, parsed)
            if handled.is_aborted:
                is_aborted = True
                break
            # 重开或非法输入时用例没有产生新落点，保留上一帧的标记以免误导。
            if handled.last_move is not None:
                last_move = handled.last_move
                winning_line = handled.winning_line
            elif game.board.move_count == 0:
                last_move = None
                winning_line = ()

        self._draw(game, last_move, winning_line)
        if is_aborted:
            self._write("已退出本局，返回主菜单。")
        else:
            self._announce_result(game)
        return is_aborted

    def _handle_human_input(
        self, game: GomokuGame, parsed: ParsedCommand
    ) -> _InputHandled:
        """处理一次人类输入并汇总渲染所需的新状态。

        输入：当前对局与解析后的命令。
        输出：``_InputHandled``：包含是否退出、最新落点与获胜连线；提示类输入不更新落点。
        副作用：可能修改对局状态（落子、重开）并写终端提示。
        约束：``q`` 通过返回值表达退出而非抛异常；非法输入只提示不改变状态。
        """
        if parsed.error is not None:
            self._write(parsed.error.message)
            return _InputHandled()

        if parsed.command is not None:
            if parsed.command == COMMAND_QUIT:
                return _InputHandled(is_aborted=True)
            if parsed.command == COMMAND_RESTART:
                game.start_new_game()
                self._write("已重开本局，黑棋先行。")
                return _InputHandled()
            self._write("该命令暂不支持，请输入坐标。")
            return _InputHandled()

        assert parsed.position is not None  # parse_input 已保证命令与坐标互斥
        outcome = game.play_human_move(parsed.position)
        if not outcome.move_result.is_accepted:
            self._write(f"落子失败：{outcome.move_result.reason}")
            return _InputHandled()

        self._report_move(parsed, outcome)
        last_move = outcome.ai_position or parsed.position
        return _InputHandled(last_move=last_move, winning_line=outcome.move_result.winning_line)

    def _report_move(self, parsed: ParsedCommand, outcome: TurnOutcome) -> None:
        """输出本回合人类与本回合电脑落子的提示。

        输入：解析后的命令与用例返回结果。
        输出：无返回值。
        副作用：写终端。
        约束：只在人类落子成功后调用，电脑落点由用例结果提供，入口层不重新推导。
        """
        if parsed.position is None:
            return
        self._write(f"你落子：{format_move_hint(parsed.position)}")
        if outcome.ai_position is not None:
            self._write(f"电脑落子：{format_move_hint(outcome.ai_position)}")

    def _announce_result(self, game: GomokuGame) -> None:
        """输出对局结束文案。

        输入：已结束的对局。
        输出：无返回值。
        副作用：写终端。
        约束：平局与胜局必须可区分；胜负方只取自用例层的 ``winner``，
              人机模式才使用"你/电脑"措辞，双人模式一律报棋子颜色。
        """
        if game.winner is None:
            self._write("棋盘已满，本局平局。")
            return
        if not game.is_vs_ai:
            self._write(f"{describe_stone(game.winner)}获胜！")
        elif game.winner is game.human_stone:
            self._write("你赢了！恭喜。")
        else:
            self._write("电脑获胜，再接再厉！")

    def _draw(self, game: GomokuGame, last_move, winning_line) -> None:
        """渲染并输出当前棋盘。

        输入：对局、最近一步与获胜连线。
        输出：无返回值。
        副作用：写终端。
        约束：每次只输出一份棋盘，渲染器随棋盘实例创建以保持只读。
        """
        renderer = BoardRenderer(game.board)
        self._write("")
        self._write(renderer.render(last_move, tuple(winning_line)))
        self._write(renderer.render_legend())

    def _write_intro(self) -> None:
        """输出游戏开屏说明。

        输入：无。
        输出：无。
        副作用：写终端。
        约束：仅说明玩法与命令，不包含内部实现细节。
        """
        self._write("欢迎来到命令行五子棋！")
        self._write("规则：黑棋先行，横、竖、斜先连成五子者胜；输入“列字母+行号”落子。")

    def _read_line(self, prompt: str) -> Optional[str]:
        """读取一行用户输入。

        输入：提示文本。
        输出：去除换行的原始行；遇到 EOF 返回 None。
        副作用：写提示并阻塞等待输入。
        约束：EOF 由调用方决定如何退出，本方法不自行抛出异常。
        """
        self._stdout.write(prompt)
        self._stdout.flush()
        line = self._stdin.readline()
        if line == "":
            return None
        return line.rstrip("\n")

    def _write(self, text: str) -> None:
        """向输出流写一行文本。

        输入：任意文本。
        输出：无。
        副作用：写标准输出并立即刷新。
        约束：仅在入口层调用，业务层不得依赖此方法。
        """
        self._stdout.write(text + "\n")
        self._stdout.flush()


@dataclass(frozen=True)
class _InputHandled:
    """一次人类输入处理后的渲染状态。

    职责：把"是否退出、最新落点、获胜连线"打包返回给单局循环。
    角色：入口层内部结果对象。
    生命周期：单次输入内创建并立即消费。
    边界：不对外暴露，也不包含业务规则。
    对外能力：字段 ``is_aborted``、``last_move``、``winning_line``。
    """

    is_aborted: bool = False
    last_move: Optional[Position] = None
    winning_line: tuple = ()


def main(
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    config: Optional[GameConfig] = None,
) -> int:
    """命令行入口函数。

    输入：可注入的输入/输出流与配置；默认使用 ``sys.stdin/stdout`` 与默认配置。
    输出：进程退出码；``KeyboardInterrupt`` 返回 0，其它启动错误返回 1。
    副作用：读写终端，创建并驱动对局。
    约束：非幂等（每次调用是一个新的交互会话），不得在库代码中自动调用。
    """
    cli = GameCli(
        stdin=stdin if stdin is not None else sys.stdin,
        stdout=stdout if stdout is not None else sys.stdout,
        config=config if config is not None else GameConfig(),
    )
    try:
        return cli.run()
    except KeyboardInterrupt:
        cli._write("\n已中断，感谢游玩！")
        return 0
    except BrokenPipeError:
        # 输出被下游关闭（如管道接 head）时安静退出，避免在关闭的流上再次写入。
        return 1
    except OSError as error:
        cli._write(f"终端读写失败：{error}")
        return 1
