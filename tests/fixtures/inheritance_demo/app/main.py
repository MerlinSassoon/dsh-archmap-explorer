from .base import Notifier, Worker
from .impl import EchoWorker, EmailNotifier


def execute(worker: Worker) -> str:
    """Execute through the abstract worker contract."""
    return worker.run()


def notify_user(notifier: Notifier, message: str) -> None:
    """Notify through the protocol contract."""
    notifier.notify(message)


def main() -> str:
    """Program entry."""
    worker = EchoWorker("demo")
    result = execute(worker)
    notify_user(EmailNotifier(), result)
    return result
