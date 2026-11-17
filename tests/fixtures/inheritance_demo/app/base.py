from abc import ABC, abstractmethod
from typing import Protocol


class Worker(ABC):
    """Worker contract."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self) -> str:
        """Execute the worker contract."""

    def label(self) -> str:
        """Return a human-readable worker label."""
        return self.name

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class Notifier(Protocol):
    """Notification contract."""

    def notify(self, message: str) -> None:
        """Deliver one notification."""
        ...
