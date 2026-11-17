"""Reusable terminal spinner component."""

from __future__ import annotations

import sys
import threading
import time


class Spinner:
    """Context-managed background terminal spinner."""

    def __init__(self, message: str = "加载中"):
        """异步等待初始化"""
        self.message = message
        self.chars = [".", "..", "..."]
        self.running = False
        self.thread: threading.Thread | None = None
        self.timeout_occurred = False

    def __enter__(self):
        """异步等待上下文管理器入口"""
        self.running = True
        self.timeout_occurred = False
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        """异步等待上下文管理器出口：捕获 TimeoutError 异常"""
        exc_type, _, _ = args
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 100) + "\r")
        sys.stdout.flush()

        self.timeout_occurred = False
        if exc_type is None:
            return False
        if issubclass(exc_type, TimeoutError):
            self.timeout_occurred = True
            return True
        return False

    def _animate(self):
        """异步等待展示动画"""
        index = 0
        while self.running:
            sys.stdout.write("\r" + " " * (len(self.message) + 100) + "\r")
            sys.stdout.write(f"\r{self.message} {self.chars[index % 3]}")
            sys.stdout.flush()
            index += 1
            time.sleep(0.5)
