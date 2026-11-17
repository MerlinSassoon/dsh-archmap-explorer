import sys
import time
import threading


class Spinner:
    def __init__(self, message="加载中"):
        """异步等待初始化"""
        self.message = message
        self.chars = ['.', '..', '...']
        self.running = False
        self.thread = None
        self.timeout_occurred = False

    def __enter__(self):
        """异步等待上下文管理器入口"""
        self.running = True
        self.timeout_occurred = False
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        """异步等待上下文管理器出口：捕获TimeoutError异常"""
        exc_type, exc_val, exc_tb = args
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 100) + "\r")
        sys.stdout.flush()

        self.timeout_occurred = False
        if exc_type is None:
            return False  # 无异常，不抑制

        # 只吞掉 TimeoutError，其它异常（包括 KeyboardInterrupt/SystemExit）照常抛出
        if issubclass(exc_type, TimeoutError):
            self.timeout_occurred = True
            return True  # 吞掉 TimeoutError
        return False  # 其余异常继续传播

    def _animate(self):
        """异步等待展示动画"""
        idx = 0
        while self.running:
            sys.stdout.write("\r" + " " * (len(self.message) + 100) + "\r")
            sys.stdout.write(f"\r{self.message} {self.chars[idx % 3]}")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.5)
