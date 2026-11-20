"""``python -m gomoku`` 启动入口。

职责：把模块执行转换为 ``gomoku.cli.main`` 调用，并以其返回值作为进程退出码。
边界：不包含任何对局逻辑或输入解析。
"""
from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
