from abc import ABC, abstractmethod


class Worker(ABC):
    """Worker contract."""

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def run(self):
        """Run the worker."""

    def label(self):
        return self.name


class EchoWorker(Worker):
    """Concrete worker."""

    def run(self):
        self._helper()
        return self.label()

    def _helper(self):
        return 1


def make_worker():
    """Create a concrete worker."""
    return EchoWorker("demo")
