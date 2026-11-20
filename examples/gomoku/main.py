"""脚本启动入口。

职责：提供 ``python main.py`` 的便捷启动方式，转发到 ``gomoku.cli.main``。
边界：不实现游戏规则；异常边界与退出码统一由 ``gomoku.cli.main`` 负责。
"""
from __future__ import annotations

import sys

from gomoku.cli import main

if __name__ == "__main__":
    sys.exit(main())
