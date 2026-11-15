import sys
import time
import threading


class Spinner:
    def __init__(self, message="加载中"):
        self.message = message
        self.chars = ['.', '..', '...']
        self.running = False
        self.thread = None
        self.exception_occurred = False

    def __enter__(self):
        self.running = True
        self.exception_occurred = False
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        exc_type, exc_val, exc_tb = args
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 100) + "\r")
        sys.stdout.flush()

        if exc_type:
            self.exception_occurred = True
            return False
        return True

    def _animate(self):
        idx = 0
        while self.running:
            sys.stdout.write("\r" + " " * (len(self.message) + 100) + "\r")
            sys.stdout.write(f"\r{self.message} {self.chars[idx % 3]}")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.5)
