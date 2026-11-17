from .base import Notifier, Worker


class EchoWorker(Worker):
    """Concrete worker that echoes its label."""

    def run(self) -> str:
        self._mark()
        return self.label()

    def _mark(self) -> int:
        return 1


class LoudWorker(Worker):
    """Concrete worker that uppercases its label."""

    def run(self) -> str:
        return self.label().upper()


class SilentWorker(Worker):
    """Abstract worker with no implementation."""


class EmailNotifier(Notifier):
    """Concrete notifier."""

    def notify(self, message: str) -> None:
        self.last_message = message
